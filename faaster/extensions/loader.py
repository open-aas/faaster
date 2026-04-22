from pathlib import Path
from typing import Dict, Optional, Type
from faaster.interfaces import IOPCUAServer
from faaster.parser.node_registry import NodeRegistry
from faaster.interfaces import IAddressSpace
from faaster.log import get_logger
from .context import SubmodelContext
from .interfaces import ISubmodelExtension

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
    Carrega os scripts customizados da pasta extensions/,
    instancia as classes e chama init() em cada uma.

    Convenção:
        extensions/{id_short_snake_case}.py
        class {IdShortPascalCase}(ISubmodelExtension)

    Exemplo:
        extensions/condition_monitoring.py
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
        script_path = self._extensions_dir / f"{snake_name}.py"

        if not script_path.exists():
            logger.info(
                "extension_loader.script_not_found",
                id_short=submodel_id_short,
                path=str(script_path),
            )
            return

        module = self._import_module(snake_name, script_path)
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
            self._instances[submodel_id_short] = instance(context)
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

    @staticmethod
    def _import_module(name: str, path: Path):
        """Importa um módulo Python a partir do path."""
        try:
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
