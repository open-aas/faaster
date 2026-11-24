# Submodel extensions

An extension is the user code that connects one submodel to the real device (MQTT, Modbus, PLC,
HTTP…). Faaster loads it from `sources/` and gives it access to the address space.

## Naming convention

For a submodel with `idShort` `ConditionMonitoring`:

| Item | Value |
|---|---|
| Package (tried first) | `sources/condition_monitoring/__init__.py` |
| Script (fallback) | `sources/condition_monitoring.py` |
| Class | `ConditionMonitoring(ISubmodelExtension)` |

The loader (`faaster/extensions/loader.py`) converts the `idShort` to snake_case for the file and
back to PascalCase for the class. A submodel without a matching file has no extension; that is not
an error. For a package, `sources/` is added to `sys.path` so the package can import its own
modules (see `sources/i_o_interface/` in the CP-Lab 406 example).

`sources/` and `models/` are gitignored: they hold deployment-specific code and models.

## Interface

`faaster/extensions/interfaces.py`:

```python
class ISubmodelExtension(ABC):
    def __init__(self, context: SubmodelContext) -> None: ...
    async def init(self) -> None: ...   # resolve nodes, start background tasks
    async def stop(self) -> None: ...   # cancel tasks, close connections
```

Lifecycle: the class is instantiated during `server.load_extension()`; `init()` runs as an asyncio
task once the OPC UA server is listening (`server.run()`); `stop()` runs on SIGINT/SIGTERM, before
the HDA flushes.

## SubmodelContext

`faaster/extensions/context.py` — what the extension receives:

| Member | Use |
|---|---|
| `server` | `IOPCUAServer` |
| `address_space` | `IAddressSpace`: `set_value(node=…, value=…)`, read values, add nodes |
| `registry` | the whole `NodeRegistry` |
| `submodel_id_short` | this submodel's idShort |
| `get_node("Coll/Prop/Value")` | `NodeMetadata` by path relative to the submodel (dynamic variables only; list items are `List/[i]/Value`) |
| `get_nodes_by_semantic_id(id)` | lookup by semantic ID |
| `all_nodes` | every registered node of this submodel |

Every write through the address space is historized when the node has HDA (see [HDA](hda.md)).

## Failures

A failing extension does not stop the server. `ExtensionLoader.failures` maps the idShort to a
reason category with the exception type only — never the message, which may carry credentials and
is readable by OPC UA clients:

| Reason | When |
|---|---|
| `import_error: <Type>` | the file or package cannot be imported |
| `class_not_found` | the module has no class with the expected name |
| `init_error: <Type>` | the constructor raised, or `init()` raised in its task |

The full message goes only to the log. The failures are published in `Objects/FaasterRuntime`
(see [architecture](architecture.md#runtime-diagnostics)). `--validate-only` checks extensions
before deployment without importing them (see [validation](validation.md)).

## Operations

An AAS `Operation` becomes an OPC UA Method whose callback is a `MethodBinder` proxy
(`faaster/extensions/method_binder.py`), created by the parser. After instantiating an extension the
loader looks for a method named after the Operation's idShort in snake_case
(`StartDrilling` → `start_drilling`), wraps it with asyncua's `uamethod` and binds it.

- Bound: OPC UA `Call` runs the extension method; its arguments are the Operation input variables.
- Not bound: the Method exists and returns `[]` — no error, logged as `operations_unbound`.

## Example

```python
# sources/condition_monitoring.py
import asyncio
from faaster.extensions.interfaces import ISubmodelExtension
from faaster.extensions.context import SubmodelContext


class ConditionMonitoring(ISubmodelExtension):
    def __init__(self, context: SubmodelContext) -> None:
        self._context = context
        self._task = None

    async def init(self) -> None:
        self._voltage = self._context.get_node("Electrical/PhaseA/Voltage/Value")
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def reset_counters(self, parent):   # bound to Operation "ResetCounters"
        return []

    async def _run(self) -> None:
        while True:
            value = await read_from_device()
            await self._context.address_space.set_value(node=self._voltage.node, value=value)
            await asyncio.sleep(1)
```

The project skill `.claude/skills/faaster-extension/` covers the same convention for agents.
