from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict
from datetime import datetime
from faaster.hda.buffer import WindowResult
from faaster.hda.policies import AggregationPolicy, HDAFunction

from .inode import INode


class IDatabase(ABC):

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def bootstrap(self) -> None:
        """Cria estruturas base do banco se não existirem."""
        ...

    @abstractmethod
    async def create_node_table(
        self,
        table_name: str,
        index: str,
        id_short: str,
        submodel: str,
        submodel_id: str,
        path: str,
        semantic_id: Optional[str],
        policy: Optional[AggregationPolicy],
    ) -> None:
        """
        Cria a hypertable do nó ou a reconcilia com a policy atual do modelo
        (chamado a cada partida).

        policy=None  → hypertable raw simples, sem continuous aggregates
        policy.is_sample → hypertable raw + continuous aggregates por level
        policy.is_aggregate → hypertable de janela agregada
        """
        ...

    @abstractmethod
    async def insert(
        self,
        table_name: str,
        value: Any,
        source_timestamp: datetime,
        variant_type: int,
    ) -> None: ...

    @abstractmethod
    async def insert_aggregate(
        self,
        table_name: str,
        result: WindowResult,
        window: str,
        function: HDAFunction,
    ) -> None:
        """Grava o agregado de uma janela, combinando com um já gravado na mesma janela."""
        ...

    @abstractmethod
    async def query(
        self,
        table_name: str,
        start: Optional[datetime],
        end: Optional[datetime],
        limit: int,
        level: str = "raw",
        reverse: bool = False,
    ) -> List[Dict]:
        """
        Linhas com start <= tempo <= end (None = sem limite), em ordem
        crescente (ou decrescente com reverse), no máximo limit.
        """
        ...

    @abstractmethod
    async def query_aggregate(
        self,
        table_name: str,
        start: Optional[datetime],
        end: Optional[datetime],
        limit: int,
        window: str,
        function: HDAFunction,
        reverse: bool = False,
    ) -> List[Dict]:
        """Como query(), sobre as janelas gravadas no modo aggregate."""
        ...

class IHDAManager(ABC):
    """
    Interface para o gerenciador de Historical Data Access.

    Orquestra a injeção do storage no servidor OPC UA e
    o registro dos nós para historização.
    """

    @abstractmethod
    async def init(self, nodes: List[INode]) -> None:
        """
        Inicializa o HDA:
            1. Injeta o IHDAStorage no servidor OPC UA via
               IOPCUAServer.set_history_storage()
            2. Registra cada nó para historização via
               IOPCUAServer.historize_node()
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Encerra a conexão com o backend de séries temporais."""
        ...
