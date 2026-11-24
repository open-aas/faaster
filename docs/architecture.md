# Architecture

## Startup lifecycle

`server.py` parses the CLI, configures logging and runs `main()` under `uvloop`:

```
--validate-only? → validate_only(args)    model + extensions report, exit 0/1 (no server)
AssetAdministrationShell(args)            build every component (dependency container)
server.setup(args)                        endpoint, namespace, BuildInfo, PKI + security policies
server.build_address_space(model)         loader → parser → OPC UA nodes; returns dynamic nodes
server.init_hda()                         storage init, historize dynamic nodes, Value@level reads
server.load_extension()                   import sources/, instantiate classes, bind Operations,
                                          publish Objects/FaasterRuntime
SIGINT/SIGTERM → server.stop()            handlers installed
server.run()                              start OPC UA, LDS/GDS/certificate tasks, extension.init()
```

`run()` blocks on a stop event. `stop()` is idempotent (a second Ctrl+C does nothing) and runs in
this order: `extension.stop()` for each extension, cancel the extension tasks, `hda_manager.stop()`
(persists pending samples and open aggregate windows, closes the pool), then release `run()`.

Note that `extension.init()` is started as a task inside `run()`, after the OPC UA server is
listening — not in `load_extension()`. A failed `init()` is logged as
`opcua_server.extension_init_failed` and reflected in `FaasterRuntime`.

`--validate-only` never builds the container nor starts a server: see [validation](validation.md).

## Runtime diagnostics

`faaster/infra/runtime_info.py` publishes `Objects/FaasterRuntime` after the extensions load, so a
client (e.g. a twin manager) reads the health of the runtime in the same OPC UA session:

| Node | Type | Content |
|---|---|---|
| `Version` | String | Faaster package version |
| `StartedAt` | DateTime | start time |
| `ExtensionsLoaded` | String[] | idShorts of the loaded extensions |
| `ExtensionsFailed` | String[] | `"<idShort>: <reason>"`, see [extensions](extensions.md#failures) |
| `ExtensionErrors` | Int32 | number of failed extensions |

## Dependency container

`faaster/asset_administration_shell.py` — `AssetAdministrationShell` is the only place that names
concrete classes. It creates:

| Component | Class | Depends on |
|---|---|---|
| OPC UA server | `asyncua.Server` | — |
| Address space | `AddressSpaceAdapter` (`faaster/infra/address_space.py`) | asyncua server |
| Node registry | `NodeRegistry` (`faaster/parser/node_registry.py`) | — |
| Element creator | `AASElementCreator` with one `BaseCreator` per element type | — |
| Parser | `AASParser` | address space, element creator, registry |
| Extension loader | `ExtensionLoader` | address space, registry |
| Lifecycle | `OPCUAServer` (`faaster/infra/aas_server.py`) | all of the above |
| HDA (only with `--url-database`) | `HDAManagerFactory.create(...)` → `HDAManager` | server, registry |

The HDA manager is created after `OPCUAServer` and injected through the `hda_manager` setter,
because the manager needs the server to historize nodes.

## Layers

```
server.py, faaster/cli/              entry point and arguments
faaster/asset_administration_shell   wiring
faaster/infra/                       asyncua + TimescaleDB implementations
faaster/parser/  faaster/loader/     model → address space
faaster/aas_metamodel/               Pydantic AAS V3 models + AASd constraint validators
faaster/hda/                         policies, buffers, storage, manager
faaster/extensions/                  user code integration
faaster/validation/                  --validate-only pipeline and report
faaster/security/  faaster/gds/      PKI, policies, GDS client
faaster/interfaces/                  contracts shared by all of the above
faaster/log/                         structlog configuration
```

## Interfaces

All infrastructure sits behind the abstractions in `faaster/interfaces/`. The parser, HDA and
extensions use them and never import asyncua directly.

| Interface | File | Implemented by |
|---|---|---|
| `IOPCUAServer` | `iserver.py` | `OPCUAServer` |
| `IAddressSpace` | `iaddress_space.py` | `AddressSpaceAdapter` |
| `INode` | `inode.py` | node wrapper in `infra/address_space.py` (`.raw` is the asyncua node) |
| `IElementCreator` | `ielement_creator.py` | `AASElementCreator` |
| `IDatabase`, `IHDAManager` | `idatabase.py` | `TimescaleDatabase`, `HDAManager` |
| `IHDAStorage` | `ihda.py` | `TimescaleHDAStorage` (an asyncua history storage) |
| `FaasterVariantType` | `types.py` | value types used by the creators |

A new HDA backend implements `IDatabase` (and, if needed, `IHDAStorage`) and is added to
`HDAManagerFactory` (`faaster/hda/factory.py`). `mongodb` is reserved there and currently raises
`NotImplementedError`.

## Logging

`faaster/log/log.py` configures structlog. Events are dotted names (`opcua_server.setup.done`,
`aas_parser.element.unknown_type`) with keyword fields. `--debug` raises the level and
`--log-file` also writes to a file.
