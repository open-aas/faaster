"""
MethodBinder — proxy callable para callbacks de métodos OPC UA.

Criado pelo OperationCreator durante o parser e registrado como
callback do nó Method. Quando a extensão do submodelo é instanciada,
bind() conecta o handler real.

Isso permite que o método OPC UA exista no address space desde o
início, sem depender da ordem de carregamento das extensões.
"""
from __future__ import annotations

import inspect


class MethodBinder:
    """
    Proxy assíncrono que delega a chamada OPC UA para o handler
    real após bind() ser chamado.

    Enquanto não houver handler vinculado, retorna lista vazia
    (comportamento equivalente ao BadNotImplemented do asyncua).
    """

    __slots__ = ("_handler", "_is_coroutine_marker")

    def __init__(self) -> None:
        self._handler = None
        # o asyncua decide se aguarda o callback com asyncio.iscoroutinefunction,
        # que é False para instâncias com __call__ assíncrono: sem a marca, o
        # binder rodaria numa thread e a coroutine nunca seria aguardada
        inspect.markcoroutinefunction(self)

    def bind(self, handler) -> None:
        """Conecta o handler real (já decorado com uamethod)."""
        self._handler = handler

    @property
    def is_bound(self) -> bool:
        return self._handler is not None

    async def __call__(self, parent, *args):
        if self._handler is None:
            return []
        return await self._handler(parent, *args)
