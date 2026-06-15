# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Faaster** (**Fa**ster **A**sset **A**dministration **S**hell **T**ype 2 ov**er** OPC UA) is a Python framework that automatically deploys a Reactive AAS (Type 2) over OPC UA from a JSON-serialized AAS V3 metamodel. It parses the model, constructs the OPC UA address space, enables Historical Data Access (HDA), and loads user-defined submodel extensions.

## Commands

### Installation
```bash
poetry install -G system
```

### Run the server
```bash
python server.py -m models/my_asset.json --host 0.0.0.0 --port 4840
```

### With HDA (TimescaleDB)
```bash
docker-compose -f docker-compose-dev.yaml up   # start DB
python server.py -m models/my_asset.json \
  --url-database postgresql://user:pass@localhost:5432 \
  --db-backend timescaledb --db-name my_asset_001
```

### Validate AAS model only (no server)
```bash
python server.py -m models/my_asset.json --validate-only
```

### Run tests
```bash
pytest tests/
pytest tests/interfaces/test_base_client.py   # single file
```

### Versioning / changelog
Uses [commitizen](https://commitizen-tools.github.io/commitizen/) with `cz_conventional_commits` and PEP 440. Bump with `cz bump`.

## Architecture

### Startup lifecycle (`server.py` → `OPCUAServer`)
```
1. AssetAdministrationShell(args)  — dependency container wires all implementations
2. aas.server.setup(args)          — configure OPC UA endpoint, BuildInfo, security
3. aas.server.build_address_space  — parse AAS model → OPC UA nodes
4. aas.server.init_hda()           — connect TimescaleDB, create hypertables
5. aas.server.load_extension()     — load sources/ scripts, call init() on each
6. aas.server.run()                — start event loop + LDS re-registration
```

### Key modules

| Path | Role |
|---|---|
| `faaster/asset_administration_shell.py` | Dependency container — wires all concrete implementations |
| `faaster/parser/aas_parser.py` | Walks AAS V3 metamodel tree, calls element creators, builds node registry |
| `faaster/parser/node_registry.py` | `NodeRegistry` indexes `NodeMetadata` by path, semantic ID, and submodel |
| `faaster/parser/element_creator.py` | Dispatcher that routes each AAS element type to its `IElementCreator` |
| `faaster/parser/creators/` | One creator per element type (Property, Operation, Collection, Range, etc.) |
| `faaster/extensions/loader.py` | Discovers and loads `sources/` scripts; maps submodel `idShort` → class |
| `faaster/extensions/context.py` | `SubmodelContext` — what extensions receive; wraps address space + registry |
| `faaster/hda/policies.py` | Parses `faaster:hda:*` extensions into `AggregationPolicy` |
| `faaster/hda/manager.py` | Orchestrates historization: subscribes to node changes, writes to storage |
| `faaster/infra/aas_server.py` | `OPCUAServer` — asyncua-backed `IOPCUAServer` implementation |
| `faaster/infra/address_space.py` | `AddressSpaceAdapter` — `IAddressSpace` over asyncua |
| `faaster/infra/database_timescale.py` | TimescaleDB `IHDAStorage` implementation |
| `faaster/loader/` | `LoaderFactory` dispatches `.json` / `.xml` / `.aasx` to the right `ILoader` |
| `faaster/aas_metamodel/models/` | Pydantic models for every AAS V3 metamodel element |
| `faaster/interfaces/` | `IOPCUAServer`, `IAddressSpace`, `INode`, `IDatabase`, `IElementCreator`, `types` |

### AAS V3 → OPC UA mapping
- `AAS`, `Submodel`, `SubmodelElementCollection` → OPC UA Object/FolderType
- `Property` → OPC UA DataVariable; if `category = VARIABLE`, also registered in `NodeRegistry` and historized
- `Operation` → OPC UA Method
- Virtual nodes (`Value@1min`, `Value@1hour`, `Value@1day`) are created automatically for VARIABLE properties that carry `faaster:hda:*` extensions

### Extension convention (`sources/`)
- File: `sources/{submodel_id_short_snake_case}.py` **or** `sources/{submodel_id_short_snake_case}/__init__.py`
- Class: `{SubmodelIdShortPascalCase}(ISubmodelExtension)` — must implement `__init__(context)`, `async init()`, `async stop()`
- `SubmodelContext.get_node("Collection/Property/Value")` resolves a node by path relative to the submodel

### HDA policy (declared in the AAS model)
Policies are `Extension` elements prefixed `faaster:hda:` on any `VARIABLE` property:
- `mode: sample` — raw hypertable + continuous aggregates per level (default)
- `mode: aggregate` — in-memory buffer flushed at window boundary (e.g. ANEEL 15-min intervals)
- Supported windows: `1min`, `5min`, `10min`, `15min`, `1hour`, `1day`

### Interfaces and decoupling
All infrastructure is hidden behind interfaces in `faaster/interfaces/`. Parser and HDA components depend only on `IAddressSpace`, `INode`, etc. — never on asyncua directly. New backends (e.g. MongoDB) implement `IHDAStorage` and register via `HDAManagerFactory`.
