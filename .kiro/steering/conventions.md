---
inclusion: always
---
# Convenções de código

- Docstrings e comentários em **pt-BR**; identificadores em inglês; README em inglês.
- Interfaces com prefixo `I` (`IAddressSpace`, `IElementCreator`) em `faaster/interfaces/` ou `*/interfaces.py`.
- Tudo de I/O é `async def`; não bloquear o loop (sem `time.sleep`, sem drivers síncronos sem `asyncio.to_thread`).
- Logs: `logger = get_logger(__name__)`; `logger.info("componente.evento", chave=valor)` — nunca f-strings em mensagens de log.
- Tipagem explícita (`Optional`, `Dict`, `List`), `@dataclass` para estruturas de dados simples, Pydantic para metamodelo.
- Referências a especificações nos docstrings (ex.: `OPC 10000-12 §7.9`, `AASd-122`).
- Testes: pytest + pytest-asyncio (`asyncio_mode=auto`), mocks com `unittest.mock` (`AsyncMock`); testes unitários não sobem servidor real; modelos JSON de teste em `tests/json-models/`.
- Toda feature nova deve vir com teste em `tests/unit/` e, se tocar o address space, em `tests/integration/`.
