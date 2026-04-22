# Faaster

**Fa**ster **A**sset **A**dministration **S**hell **T**ype 2 ov**er** OPC UA

> An open-source Python framework for automated deployment of Reactive Asset Administration Shell (Type 2) over OPC UA.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![OPC UA](https://img.shields.io/badge/OPC%20UA-Type%202-green)](https://opcfoundation.org)
[![AAS](https://img.shields.io/badge/AAS-V3%20IDTA--01001--3--0-orange)](https://industrialdigitaltwin.org)

---

## Overview

The **Asset Administration Shell (AAS)** is the cornerstone of digital representation and interoperability in Industry 4.0, acting as the central element of the RAMI 4.0 reference model. A Reactive AAS (Type 2) exposes a standardized programming interface (API) that allows external systems to read and write asset data in real time — with OPC UA as the recommended protocol for its implementation.

However, implementing a Reactive AAS (Type 2) over OPC UA still requires significant manual effort, particularly in:

- Building the OPC UA address space from scratch
- Enabling Historical Data Access (HDA) for selected variables
- Configuring event-based monitoring and threshold alerts
- Integrating proprietary device protocols (MQTT, Modbus, BLE, etc.)

**Faaster** automates all of these tasks from a JSON-serialized AAS V3 metamodel, enabling the deployment of a fully functional OPC UA server in under one minute — with zero additional programming beyond the device integration layer.

---

## Key Features

- **Automatic AAS V3 Parser** — Parses the AAS V3 metamodel (JSON) and maps it to an OPC UA address space, including full validation of AASd constraints defined in IDTA-01001-3-0
- **Selective HDA** — Enables Historical Data Access for variables marked as `VARIABLE` in the metamodel, with configurable time-series backends (TimescaleDB)
- **Policy-driven storage** — HDA aggregation and retention policies defined directly in the AAS model via `Extension` elements (`faaster:hda:*`), aligned with industrial standards such as IEC 61000-4-30 and ANEEL Module 8
- **Threshold-based OPC UA events** — Configurable event generation via JSON configuration file, with custom `EventType` derived from `BaseEventType`
- **Extension mechanism** — User-defined runtime extensions via Python scripts loaded from the `sources/` directory, receiving a `SubmodelContext` with full access to the OPC UA address space and node registry
- **Automatic LDS registration** — Registers the server in the OPC UA Local Discovery Service (LDS) with periodic re-registration
- **Edge-ready** — Runs on any Linux device with a Python interpreter, from conventional servers to embedded edge devices

---

## Architecture

Faaster initializes in the following sequential steps:

```
1. OPC UA server configuration  →  endpoint, build_info, security
2. AAS metamodel loading        →  JSON parsing + AASd constraint validation
3. Address space construction   →  automatic OPC UA node generation
4. Extension loading            →  user scripts loaded from sources/
5. HDA initialization           →  time-series backend + node historization
6. Main server loop             →  OPC UA server running + LDS registration
```

### AAS V3 → OPC UA Mapping

| AAS V3 Element              | OPC UA Type               |
|-----------------------------|---------------------------|
| AAS, Submodel, SubmodelElement | ObjectType             |
| SubmodelElementList         | ObjectType + FolderType   |
| Property                    | VariableType (DataVariable) |
| Operation                   | MethodType                |

Variables marked with `category = VARIABLE` in the metamodel have HDA enabled automatically and are included in the historized node list, avoiding the overhead of historizing all nodes.

---

## HDA Policy via AAS Extensions (*Development)

Faaster introduces a novel approach to HDA configuration: **storage policies are defined in the AAS model itself**, not in the monitoring system. This means the policy travels with the asset throughout its lifecycle, independent of which monitoring platform is in use.

Policies are declared as `Extension` elements with the `faaster:hda:` prefix — a legitimate use of the AAS V3 Extension mechanism, designed precisely for proprietary and temporary information that does not require global interoperability.

### Sample mode (raw data + continuous aggregates)

```json
{
  "idShort": "Voltage",
  "category": "VARIABLE",
  "extensions": [
    { "name": "faaster:hda:mode",          "value": "sample"       },
    { "name": "faaster:hda:levels",        "value": "1min,1hour,1day" },
    { "name": "faaster:hda:retention:raw", "value": "30 days"      },
    { "name": "faaster:hda:retention:1min","value": "1 year"       }
  ]
}
```

### Aggregate mode (window-based, e.g. ANEEL 15-minute intervals)

```json
{
  "idShort": "ActiveEnergy",
  "category": "VARIABLE",
  "extensions": [
    { "name": "faaster:hda:mode",      "value": "aggregate" },
    { "name": "faaster:hda:window",    "value": "15min"     },
    { "name": "faaster:hda:function",  "value": "mean"      },
    { "name": "faaster:hda:retention", "value": "5 years"   }
  ]
}
```

Variables with HDA policies automatically get virtual OPC UA nodes (`Value@1min`, `Value@1hour`, `Value@1day`) that expose the pre-aggregated data directly via standard OPC UA HDA — without requiring clients to know the underlying storage strategy.

---

## Getting Started

### Requirements

- Python 3.11+
- Docker (recommended for TimescaleDB)

### Installation

```bash
git clone https://github.com/open-aas/faaster.git
cd faaster
poetry install -G system
```

### Running the database

```bash
docker-compose -f docker-compose-dev.yaml up
```

### Basic usage

```bash
python server.py \
  -m models/my_asset.json \
  --host 0.0.0.0 \
  --port 4840
```

### With HDA (TimescaleDB)

```bash
python server.py \
  -m models/my_asset.json \
  --url-database postgresql://user:pass@localhost:5432 \
  --db-backend timescaledb \
  --db-name my_asset_001 \
  --port 4840
```

### Validate AAS model only (no server) (development)

```bash
python server.py -m models/my_asset.json --validate-only
```

---

## Writing a Submodel Extension

Extensions are Python scripts placed in the `sources/` directory. Each script corresponds to a submodel, following the naming convention `{submodel_id_short_snake_case}.py`.

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
        # resolve nodes from the AAS address space
        self._voltage = self._context.get_node(
            "Electrical/PhaseA/Voltage/Value"
        )
        # start background communication task
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _run(self) -> None:
        # your device protocol here (MQTT, Modbus, BLE, HTTP...)
        while True:
            value = await self._read_from_device()
            await self._context.address_space.set_value(
                node=self._voltage.node,
                value=value,
            )
            await asyncio.sleep(1)
```

---

## CLI Reference

```
usage: server.py [-m MODELING_FILE] [options]

Modeling:
  -m, --modeling-file PATH      Path to the AAS V3 JSON modeling file (required)
  --aas_id_short                The IdShort of the AAS model
  --aas_id                      The Id of the AAS model, must be unique for each AAS

OPC UA Server:
  --host HOST                   Host address to bind (default: 0.0.0.0)
  --port PORT                   OPC UA server port (default: 4840)
  --url-discovery URL           OPC UA LDS URL for automatic registration

Historical Data Access (HDA):
  --url-database URL            Time-series database connection URL
  --db-backend BACKEND          Database backend: timescaledb (default: inferred)
  --db-name NAME                Database name (default: AAS idShort)

OPC UA Server Identity:
  --product-uri URI             Product URI exposed in BuildInfo
  --manufacturer-name NAME      Manufacturer name exposed in BuildInfo
  --product-name NAME           Product name exposed in BuildInfo
  --software-version VERSION    Software version (default: package version)
  --build-number NUMBER         Build number (default: 1)
  --build-date DATETIME         Build date in ISO 8601 (default: startup time)

Diagnostics:
  --debug                       Enable debug logging
  --log-file PATH               Write logs to file
  --validate-only               Validate AAS model and exit
```

---

## Comparison with Existing Implementations

| Feature                    | AASX Server | Eclipse BaSyx | FA³ST | NOVAAS | **Faaster** |
|----------------------------|:-----------:|:-------------:|:-----:|:------:|:-----------:|
| OPC UA as API              | ✅          | ❌            | ✅    | ❌     | ✅          |
| Integrated HDA             | ❌          | ❌            | ❌    | ❌     | ✅          |
| Automatic JSON parser      | ❌          | ❌            | ✅    | ❌     | ✅          |
| Policy-driven HDA          | ❌          | ❌            | ❌    | ❌     | ✅          |
| Extension via script       | ❌          | Partial       | Partial | ❌   | ✅          |
| Edge execution             | ✅          | Partial       | ✅    | ✅     | ✅          |

---

## Validated Use Cases

### Energy Monitoring of a Three-Phase Motor

The framework was validated in an industrial scenario involving energy monitoring of a fan-coil unit using a custom acquisition board based on ESP32 + ADE9000, capable of measuring three-phase electrical quantities. The board operates as an MQTT beacon, publishing measurements periodically. Through the extension layer, each MQTT message is mapped to the corresponding OPC UA node in the `ConditionMonitoring` submodel.

The validation confirmed:
- Correct OPC UA address space generation from the AASX model
- Continuous historical data storage and real-time retrieval via HDA
- Automatic detection of AASd-122 constraint violations in the official IDTA dataset

### Automatic Detection of AAS Non-Conformities

During validation with AAS models from the official IDTA dataset, Faaster automatically identified non-conformities related to constraints defined in the AAS V3 metamodel specification. The most recurrent was a violation of **Constraint AASd-122**, which determines that for `ExternalReference` types, the first key must belong to `GenericGloballyIdentifiables`. This inconsistency indicates that part of the official dataset was elaborated based on earlier versions of the metamodel (V2.0).

---

## Project Structure

```
faaster/
├── aas_metamodel/       — AAS V3 metamodel Pydantic models + validators
├── cli/                 — CLI argument parsing
├── extensions/          — Extension loader, context and interfaces
├── hda/                 — HDA manager, storage, policies and factory
├── infra/               — asyncua server and address space implementations
├── interfaces/          — IOPCUAServer, IAddressSpace, INode, IDatabase, types
├── loader/              — AAS file loaders (JSON, XML, AASX)
├── log/                 — structlog configuration
├── parser/              — AAS parser, element creators, node registry
├── asset_administration_shell.py  — dependency container
models/                  — place your AAS JSON models here
sources/                 — place your submodel extension scripts here
server.py                — entry point
```

---

## Roadmap

- [ ] Semantic mapping based on OPC UA ObjectTypes and Interfaces (Braunisch et al., 2025)
- [ ] Sensor driver SDK for direct mapping between AAS variables and physical devices
- [ ] OPC UA events based on `Range` and `BasicEventElement` metamodel elements
- [ ] Machine Learning integration at the edge for anomaly detection in historized variables
- [ ] Global Discovery Server (OPC UA Part 12) with automatic X.509 certificate management
- [ ] Horizontal scaling of Faaster instances in distributed industrial environments
- [ ] MongoDB HDA backend

---

## Contributing

Contributions are welcome. Please open an issue or submit a pull request on [GitHub](https://github.com/open-aas/faaster).

---

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.

Copyright 2026 Open AAS Contributors