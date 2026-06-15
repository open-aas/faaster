from pathlib import Path
from typing import Dict, Optional, Type
from faaster.interfaces import IOPCUAServer
from faaster.parser.node_registry import NodeRegistry
from faaster.interfaces import IAddressSpace
from faaster.log import get_logger
from .context import SubmodelContext
from .interfaces import ISubmodelExtension

from asyncua.common.methods import uamethod

import importlib.util
import inspect
import re
import sys


logger = get_logger(__name__)


_EXTENSIONS_DIR = "sources"


def _to_snake_case(name: str) -> str:
    """IdShort PascalCase → snake_case."""
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


def _to_pascal_case(name: str) -> str:
    """snake_case → PascalCase."""
    return ''.join(word.capitalize() for word in name.split('_'))


class ExtensionLoader:
    """
    Carrega extensões customizadas da pasta sources/, instancia as classes
    e chama init() em cada uma.

    Convenção (módulo tem prioridade sobre script plano):
        sources/{id_short_snake_case}/__init__.py   ← módulo Python
        sources/{id_short_snake_case}.py            ← script plano (fallback)
        class {IdShortPascalCase}(ISubmodelExtension)

    Exemplo:
        sources/condition_monitoring/__init__.py
        class ConditionMonitoring(ISubmodelExtension)
    """

    def __init__(
        self,
        address_space: IAddressSpace,
        registry: NodeRegistry,
    ) -> None:
        self._address_space = address_space
        self._registry = registry
        self._extensions_dir = Path(_EXTENSIONS_DIR)
        self._instances: Dict[str, ISubmodelExtension] = {}

    async def load(self, server: IOPCUAServer) -> Dict[str, ISubmodelExtension]:
        """
        Para cada submódulo do environment:
            1. Verifica se existe extensions/{id_short_snake}.py
            2. Importa o módulo
            3. Instancia a classe
            4. Chama init(context)
            5. Armazena em _instances

        Retorna o dict de instâncias para a AssetAdministrationShell.
        """
        if not self._extensions_dir.exists():
            logger.info(
                "extension_loader.dir_not_found",
                path=str(self._extensions_dir),
            )
            return {}

        for submodel in self._registry.node_submodels.keys():
            await self._load_submodel_extension(
                server=server,
                submodel_id_short=submodel
            )

        logger.info(
            "extension_loader.done",
            loaded=list(self._instances.keys()),
        )

        return self._instances

    async def stop(self) -> None:
        """Encerra todas as extensões carregadas."""
        for id_short, instance in self._instances.items():
            try:
                await instance.stop()
                logger.info(
                    "extension_loader.stopped",
                    id_short=id_short,
                )
            except Exception as e:
                logger.error(
                    "extension_loader.stop.error",
                    id_short=id_short,
                    error=str(e),
                )

    async def _load_submodel_extension(
        self,
        server,
        submodel_id_short: str,
    ) -> None:
        snake_name = _to_snake_case(submodel_id_short)
        module_path = self._extensions_dir / snake_name
        script_path = self._extensions_dir / f"{snake_name}.py"

        if (module_path / "__init__.py").exists():
            load_path = module_path
        elif script_path.exists():
            load_path = script_path
        else:
            logger.info(
                "extension_loader.extension_not_found",
                id_short=submodel_id_short,
                module_path=str(module_path),
                script_path=str(script_path),
            )
            return

        module = self._import_module(snake_name, load_path)
        if module is None:
            return

        class_name = _to_pascal_case(snake_name)
        instance = self._instantiate(module, class_name, submodel_id_short)

        if instance is None:
            return

        context = SubmodelContext(
            server=server,
            address_space=self._address_space,
            registry=self._registry,
            submodel_id_short=submodel_id_short
        )

        try:
            loaded_instance = instance(context)
            self._instances[submodel_id_short] = loaded_instance
            self._bind_operations(submodel_id_short, loaded_instance)
            logger.info(
                "extension_loader.loaded",
                id_short=submodel_id_short,
                class_name=class_name,
            )

        except Exception as e:
            logger.error(
                "extension_loader.init.error",
                id_short=submodel_id_short,
                class_name=class_name,
                error=str(e),
            )

    def _bind_operations(self, submodel_id_short: str, instance) -> None:
        """
        Associa métodos da instância às operações OPC UA do submodelo.

        Para cada operação registrada no NodeRegistry, deriva o nome do
        método Python via pascal_to_snake e, se existir na instância,
        envolve com uamethod (conversão automática de tipos) e conecta
        ao MethodBinder.

        Operações sem método correspondente ficam registradas no address
        space mas retornam lista vazia ao cliente (não geram erro).
        """
        operations = self._registry.get_operations(submodel_id_short)
        if not operations:
            return

        bound, unbound = [], []

        for op in operations:
            method_name = _to_snake_case(op.id_short)
            handler = getattr(instance, method_name, None)

            if handler is not None and callable(handler):
                op.binder.bind(uamethod(handler))
                bound.append(method_name)
            else:
                unbound.append(method_name)

        if bound:
            logger.info(
                "extension_loader.operations_bound",
                id_short=submodel_id_short,
                bound=bound,
            )
        if unbound:
            logger.info(
                "extension_loader.operations_unbound",
                id_short=submodel_id_short,
                unbound=unbound,
                hint="Implemente o método ou ignore — sem impacto no servidor",
            )

    @staticmethod
    def _import_module(name: str, path: Path):
        """Importa um módulo ou pacote Python a partir do path."""
        try:
            if path.is_dir():
                # Pacote: adiciona sources/ ao sys.path para que imports
                # relativos internos ao módulo funcionem corretamente.
                sources_dir = str(path.parent.resolve())
                if sources_dir not in sys.path:
                    sys.path.insert(0, sources_dir)
                import importlib as _il
                module = _il.import_module(name)
            else:
                spec = importlib.util.spec_from_file_location(name, path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
            return module

        except Exception as e:
            logger.error(
                "extension_loader.import.error",
                module=name,
                path=str(path),
                error=str(e),
            )
            return None

    @staticmethod
    def _instantiate(
        module,
        class_name: str,
        submodel_id_short: str,
    ) -> Optional[Type[ISubmodelExtension]]:
        """Localiza e instancia a classe ISubmodelExtension no módulo."""
        cls = getattr(module, class_name, None)

        if cls is None:
            logger.warning(
                "extension_loader.class_not_found",
                class_name=class_name,
                id_short=submodel_id_short,
                hint=f"Expected class '{class_name}' in module",
            )
            return None

        if not inspect.isclass(cls):
            logger.warning(
                "extension_loader.not_a_class",
                class_name=class_name,
            )
            return None

        if not issubclass(cls, ISubmodelExtension):
            logger.warning(
                "extension_loader.invalid_base_class",
                class_name=class_name,
                hint=f"Class must inherit from ISubmodelExtension",
            )
            return None

        try:
            return cls

        except Exception as e:
            logger.error(
                "extension_loader.instantiate.error",
                class_name=class_name,
                error=str(e),
            )

            return None

    @property
    def instances(self) -> Dict[str, ISubmodelExtension]:
        return self._instances
