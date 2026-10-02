---
name: faaster-extension
description: Use ao criar ou alterar uma extensão de submodelo do Faaster em sources/ — conectar dispositivo (MQTT, Modbus, HTTP, cobot) a variáveis OPC UA ou implementar Operations do AAS.
---
# Criando uma extensão de submodelo

## Convenção (obrigatória — o ExtensionLoader descobre por nome)
- Submodelo `idShort = ConditionMonitoring` →
  - arquivo `sources/condition_monitoring.py` **ou** pacote `sources/condition_monitoring/__init__.py`
  - classe `ConditionMonitoring(ISubmodelExtension)`
- Implementar `__init__(self, context)`, `async init()`, `async stop()`.

## Operations
Cada `Operation` do submodelo vira um Method OPC UA com `MethodBinder`. O loader vincula o método da classe cujo nome é o **idShort em snake_case** (`StartMotor` → `start_motor`), envolvido com `uamethod` (args já convertidos para tipos Python). Recebe `(parent, *input_args)` e retorna os output args. Método ausente = operação responde `[]` (só log `operations_unbound`).

## Template
```python
import asyncio
from faaster.extensions.interfaces import ISubmodelExtension
from faaster.extensions.context import SubmodelContext
from faaster.log import get_logger

logger = get_logger(__name__)


class ConditionMonitoring(ISubmodelExtension):

    def __init__(self, context: SubmodelContext) -> None:
        self._context = context
        self._task: asyncio.Task | None = None

    async def init(self) -> None:
        # path relativo ao submodelo; retorna NodeMetadata (ou None)
        self._voltage = self._context.get_node("Electrical/PhaseA/Voltage/Value")
        if self._voltage is None:
            logger.warning("condition_monitoring.node_not_found", path="Electrical/PhaseA/Voltage/Value")
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _run(self) -> None:
        while True:
            value = await self._read_from_device()
            await self._context.address_space.set_value(node=self._voltage.node, value=value)
            await asyncio.sleep(1)

    async def start_motor(self, parent, speed: float) -> bool:   # Operation "StartMotor"
        ...
        return True
```

## Checklist
- [ ] Nome do arquivo/classe confere com o idShort (confirme no modelo em `models/`).
- [ ] Paths usados em `get_node` existem (use `context.all_nodes` para listar) e a Property tem `category: VARIABLE` (só essas entram no registry/HDA).
- [ ] Nenhuma chamada bloqueante; tasks canceladas em `stop()`; conexões fechadas.
- [ ] Dependências de dispositivo no grupo Poetry adequado (`cobot` para ur-rtde/pymodbus).
- [ ] Lembre: `sources/` é gitignored — a extensão é artefato do usuário, não do framework.
- [ ] Teste: `python server.py -m models/<modelo>.json --debug` e procure `extension_loader.operations_bound` no log.
