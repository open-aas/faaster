from typing import List
from abc import ABC, abstractmethod
from asyncua.server.history import HistoryStorageInterface

from .inode import INode


class IHDAManager(ABC):
    """
    Interface para o gerenciador de Historical Data Access.

    Desacoplada do servidor — recebe os nós a historizar
    e gerencia o backend de séries temporais.
    """

    @abstractmethod
    async def init(self, nodes: List[INode]) -> None:
        """
        Inicializa o HDA para os nós fornecidos.

        Cada nó recebido teve category=VARIABLE no metamodelo AAS V3
        e deve ter seu histórico persistido no backend configurado.
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Encerra a conexão com o backend de séries temporais."""
        ...


class IHDAStorage(HistoryStorageInterface, ABC):
    """
    Interface base para implementações de armazenamento histórico
    compatíveis com o asyncua.

    Herda de HistoryStorageInterface para garantir compatibilidade
    com o mecanismo interno do asyncua, e de ABC para permitir
    métodos abstratos adicionais do Faaster.

    Implementações concretas:
        - MongoDBHDAStorage
        - TimescaleDBHDAStorage
    """
    ...
