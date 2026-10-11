from abc import ABC, abstractmethod
from argparse import Namespace
from typing import Optional, Any

from .inode import INode
from .ihda import IHDAStorage
from .types import FaasterLocalizedText, FaasterVariantType


class IOPCUAServer(ABC):
    """
    Interface que define o ciclo de vida do servidor OPC UA no Faaster.

    Ordem obrigatória de execução:
        1. setup()
        2. build_address_space()
        3. bind_assets()
        4. init_hda()
        5. load_extension()
        6. run()
    """

    @abstractmethod
    async def setup(self, args: Namespace) -> None:
        ...

    @abstractmethod
    async def build_address_space(self, modeling_file: str) -> None:
        ...

    async def bind_assets(self) -> None:
        """
        Prepara o vínculo AAS ↔ ativo a partir do AID/AIMC do modelo.
        As conexões com o ativo abrem em run().
        """
        return None

    @abstractmethod
    async def load_extension(self) -> None:
        ...

    @abstractmethod
    async def init_hda(self) -> None:
        ...

    @abstractmethod
    async def run(self) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

    @abstractmethod
    async def set_history_storage(self, storage: IHDAStorage) -> None:
        """
        Injeta a implementação de armazenamento histórico
        no servidor OPC UA interno do asyncua.

        Deve ser chamado pelo IHDAManager.init() antes de
        historize_node().
        """
        ...

    @abstractmethod
    async def historize_node(self, node: INode) -> None:
        """
        Registra um nó para historização no servidor OPC UA.

        Deve ser chamado após set_history_storage().
        """
        ...
