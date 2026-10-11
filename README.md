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
- **Declarative asset binding** — Connects the AAS to the physical asset from the *Asset Interfaces Description* (IDTA 02017) and *Asset Interfaces Mapping Configuration* (IDTA 02027) submodels, with no asset-specific code; built-in OPC UA client driver, other protocols as plugins
- **Extension mechanism** — User-defined runtime extensions via Python scripts or packages loaded from the `sources/` directory, receiving a `SubmodelContext` with full access to the OPC UA address space and node registry
- **OPC UA Security** — Standalone X.509 certificate management (self-signed bootstrap + PKI store per OPC 10000-12 Annex F) with configurable security policies (`basic256`, `aes128`, `aes256`) and modes (`sign`, `sign-and-encrypt`)
- **GDS Integration** — Application registration and Pull Certificate Management against an OPC UA Global Discovery Server (OPC 10000-12 §6–7), including automatic TrustList updates
- **Automatic LDS registration** — Registers the server in the OPC UA Local Discovery Service (LDS) with periodic re-registration
- **Edge-ready** — Runs on any Linux device with a Python interpreter, from conventional servers to embedded edge devices

---

## Architecture

Faaster initializes in the following sequential steps:

```
1. OPC UA server configuration  →  endpoint, build_info
2. PKI bootstrap                →  certificate generation/loading (if --pki-dir)
3. Security policies            →  security mode + trust store configuration
4. AAS metamodel loading        →  JSON parsing + AASd constraint validation
5. Address space construction   →  automatic OPC UA node generation
6. Extension loading            →  user scripts/packages loaded from sources/
7. HDA initialization           →  time-series backend + node historization
8. Main server loop             →  OPC UA server running + LDS/GDS registration
```

### AAS V3 → OPC UA Mapping

Every element becomes an Object named after its `idShort`, with its metadata as properties (`IdShort`,
`ModelType`, `Category`, `SemanticId`, `Description`...) and its children below it:

| AAS V3 Element | OPC UA nodes |
|---|---|
| AAS, Submodel, SubmodelElementCollection | Object with its elements as children |
| SubmodelElementList | Object with `OrderRelevant`, `TypeValueListElement`, `ValueTypeListElement`, `SemanticIdListElement`; items as children named by index (`[0]`, `[1]`...), as in the API `idShortPath` |
| Entity | Object with `EntityType`, `GlobalAssetId`, `SpecificAssetIds`; statements as children |
| RelationshipElement | Object with `First` and `Second` reference folders (`Type`, `Key[i]@<type>`) |
| AnnotatedRelationshipElement | As RelationshipElement, with the annotations as children |
| Property | Object with a `Value` DataVariable of the `valueType` |
| MultiLanguageProperty | Object with one property per language |
| Range | Object with `Min` and `Max` DataVariables |
| File | Object with `ContentType` and `Value` (path or URL) |
| Blob | Object with `ContentType` and `Value` (ByteString) |
| ReferenceElement | Object with its keys |
| BasicEventElement | Object with its attributes |
| Capability | Object (metadata only) |
| Operation | Object with a Method |

Variables marked with `category = VARIABLE` in the metamodel have HDA enabled automatically and are included in the historized node list, avoiding the overhead of historizing all nodes — including properties inside lists, entities and annotations.

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

### How it is stored

- **Every write is historized**: OPC UA client writes, `PATCH …/$value`, extensions and asset bindings
  alike, including repeated values and bursts. The value's `SourceTimestamp` (when it was measured)
  is stored; without one, the server time is used.
- **Sample mode**: each level (`1min`, `5min`, `10min`, `15min`, `1hour`, `1day`, in any combination
  and order) is a TimescaleDB continuous aggregate computed **directly from the raw data**: `avg`,
  `max`, `min`, `stddev` and `count` are exact. The last, not yet materialized buckets are completed at
  query time (real-time aggregation). `Value@<level>` returns the bucket average as `Double`. The raw
  hypertable is compressed after 7 days.
- **Aggregate mode**: windows are aligned to the clock in UTC (a `15min` window closes at :00, :15,
  :30, :45). Each window is persisted right after it closes, as one row per window. A late sample of
  an already persisted window is merged into it (weighted mean, sum, max, min, or the latest sample
  for `last`). When the database is down, results are kept and retried on the next window. On
  shutdown the open window is persisted too, and merged with the rest of it after restart. The
  `Value` node returns the window values as `Double`, timestamped with the window start.
- **Retention**: `<n> <minute|hour|day|week|month|year>[s]` or `none` (no expiry). Defaults: raw
  30 days, `1min` 1 year, `1hour` 5 years, `1day` none; aggregate mode 5 years. Each level is
  refreshed from the last minutes/hours/days of raw data (`1day`: 4 days), so the raw retention
  (and the level's own retention) must be longer than that — the model is rejected otherwise.
  `faaster:hda:window` is required in aggregate mode.

### Changing a policy

The policy in the model is applied on every startup. Policies (refresh jobs and retention) are
recreated each time, which only touches TimescaleDB's job catalog. A level's view is only rebuilt
when it changes:

| Change in the model | What happens |
|---|---|
| Level unchanged | View and its data are kept (no cost) |
| Level added | View created, then the retained raw history is materialized in the background |
| Level removed | View and its aggregated history are dropped |
| Retention changed | Retention policy recreated; data already dropped is not recovered |
| `sample` ↔ `aggregate` | Each mode has its own table; the other mode's data is kept |
| Policy removed | Raw table kept, without retention (no expiry) |

Rebuilding a view costs one pass over the raw data still retained (e.g. 30 days at 1 Hz ≈ 2.6 M
rows per variable, typically seconds) and does not block startup: queries are correct meanwhile.
Aggregated history older than the raw retention cannot be rebuilt — that is why unchanged views are
never recreated.

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

Stop the server with Ctrl+C (SIGINT) or SIGTERM (`docker stop`): extensions are stopped and the HDA
writes pending samples and the open aggregate windows before exiting.

### Validate AAS model only (no server) (development)

```bash
python server.py -m models/my_asset.json --validate-only
```

### Running the tests

```bash
pytest tests/ --ignore=tests/interfaces   # tests/interfaces still imports the former core package
```

The HDA integration tests (`tests/integration/test_hda_*.py`) run against a real TimescaleDB: a
throwaway container (`timescale/timescaledb:latest-pg17`, or `FAASTER_TEST_TIMESCALE_IMAGE`) is
started with Docker, or an existing server is used with
`FAASTER_TEST_TIMESCALE_URL=postgresql://user:pass@host:5432`. Without either, they are skipped.

---

## OPC UA Security

Faaster supports two security modes: **standalone** (self-signed certificate, no external dependencies) and **GDS-managed** (certificates issued and renewed by a Global Discovery Server). Both modes use the same PKI directory layout (OPC 10000-12 Annex F).

### PKI directory layout

```
pki/
├── own/
│   ├── certs/          ← server certificate (DER)
│   └── private/        ← private key (PEM, chmod 600)
├── trusted/
│   ├── certs/          ← trusted client/server certificates
│   └── crl/            ← CRLs from trusted issuers
├── issuers/
│   ├── certs/          ← CA chain certificates
│   └── crl/            ← CA CRLs
└── rejected/           ← untrusted client certificates (pending approval)
```

### Standalone mode

On first startup, Faaster generates a self-signed RSA-2048 certificate compatible with Basic256Sha256 (OPC 10000-7). On subsequent startups, the existing certificate is loaded from the PKI store.

```bash
python server.py \
  -m models/my_asset.json \
  --pki-dir ./pki \
  --security-policy basic256 \
  --security-mode sign-and-encrypt
```

To allow both secure and unauthenticated connections (useful for gradual migration):

```bash
python server.py -m models/my_asset.json \
  --pki-dir ./pki \
  --security-policy basic256 \
  --allow-anonymous
```

### Security policies

| CLI value   | OPC UA policy             | Notes                        |
|-------------|---------------------------|------------------------------|
| `basic256`  | Basic256Sha256            | Widely supported, recommended |
| `aes128`    | Aes128_Sha256_RsaOaep     | More efficient, newer clients |
| `aes256`    | Aes256_Sha256_RsaPss      | Strongest available           |

Multiple policies can be specified by repeating `--security-policy`. The `--security-mode` flag (`sign` or `sign-and-encrypt`, default) applies to all configured policies.

### Client certificate approval

When a client presents an untrusted certificate, the connection is rejected and the certificate is saved to `pki/rejected/` for review. To approve a client manually, move its certificate to `pki/trusted/certs/` and restart the server (or wait for the next trust store reload).

For development environments, use `--auto-accept-clients` to automatically approve any connecting client:

```bash
python server.py -m models/my_asset.json \
  --pki-dir ./pki \
  --security-policy basic256 \
  --auto-accept-clients
```

> **Warning:** `--auto-accept-clients` accepts any certificate without validation. Never use in production.

### Client connection workflow (UaExpert example)

1. Connect to the server without security to retrieve its certificate
2. Add the server certificate to your client's trusted store
3. Set the security policy to match (e.g. `Basic256Sha256 - Sign & Encrypt`)
4. Reconnect — the server will place your client certificate in `pki/rejected/`
5. Approve the client certificate (move to `pki/trusted/certs/` or use `--auto-accept-clients`)
6. Reconnect again — secure session established

---

## GDS Integration

Faaster can register itself with an OPC UA Global Discovery Server and delegate full certificate lifecycle management to it (OPC 10000-12 §6–7).

### Application registration (§6.4)

When `--gds-url` is provided, Faaster registers the server with the GDS on startup and keeps the registration alive with periodic `UpdateApplication` calls. On shutdown, `UnregisterApplication` is called automatically.

```bash
python server.py \
  -m models/my_asset.json \
  --pki-dir ./pki \
  --gds-url opc.tcp://gds-server:58810 \
  --gds-username admin \
  --gds-password secret \
  --renew-interval 3600
```

### Pull Certificate Management (§7.9)

When both `--pki-dir` and `--gds-url` are provided, Faaster performs the full Pull Management workflow automatically:

```
GetCertificateGroups     → lists available certificate groups
GetCertificateStatus     → checks if certificate renewal is needed
StartSigningRequest      → submits a CSR (key stays local, GDS signs it)
FinishRequest            → polls until the CA issues the signed certificate
GetTrustList             → retrieves the TrustList node from the GDS
read_trust_list          → reads TrustListDataType via FileType (OpenWithMasks)
CertificateStore.apply   → applies the trust list to the local PKI store
```

The private key is always generated locally and never sent to the GDS. Only the Certificate Signing Request (CSR) is transmitted.

Certificate renewal runs automatically every `--renew-interval` seconds. If the GDS reports that a certificate update is required (`GetCertificateStatus → true`), the renewal cycle starts immediately.

### GDS CLI reference

```
--gds-url URL           GDS endpoint (e.g. opc.tcp://gds:58810)
--gds-username NAME     GDS user with ApplicationSelfAdmin or DiscoveryAdmin role
--gds-password PASS     GDS password
--renew-interval SEC    Registration and certificate renewal interval (default: 60s)
```

---

## AAS HTTP/REST API (IDTA-01002-3-2)

Faaster can serve the AAS Part 2 HTTP/REST API ([IDTA-01002-3-2](docs/specs/IDTA-01002-3-2/)) alongside
the OPC UA server, in the same process and event loop. The API is optional and is enabled with `--http-port`. The model structure is served exactly as
authored in the AAS JSON file, while `Property` values are read live from the OPC UA address space,
so a REST client always sees the same value as an OPC UA client.

```bash
python server.py -m models/my_asset.json --port 4840 --http-port 8080
curl http://localhost:8080/api/v3/description
curl http://localhost:8080/api/v3/submodels
```

Interactive documentation (Swagger UI): `http://localhost:8080/api/v3/docs`.

Identifiers in the URL are base64url-encoded without padding, and `idShortPath` uses dots and
URL-encoded brackets (e.g. `Motor.Status.Running`, `Setpoints%5B1%5D`):

```bash
SM=$(printf 'urn:example:sm:operational' | base64 -w0 | tr '+/' '-_' | tr -d '=')
curl "http://localhost:8080/api/v3/submodels/$SM/submodel-elements/Motor.Speed"
curl "http://localhost:8080/api/v3/submodels/$SM/\$value"            # {"Motor": {"Speed": 1450, ...}}
curl "http://localhost:8080/api/v3/submodels/$SM/\$path?level=core"  # ["Temperature", "Motor", ...]
```

Values of `Property` elements can be written with `PATCH …/$value` (ValueOnly body). The write goes
straight to the OPC UA node — like an OPC UA client write, so OPC UA subscribers see it and HDA
historizes it for `VARIABLE` properties — and is **not** persisted to the model file:

```bash
curl -X PATCH -H 'Content-Type: application/json' -d '1450' \
  "http://localhost:8080/api/v3/submodels/$SM/submodel-elements/Motor.Speed/\$value"   # 204
curl -X PATCH -H 'Content-Type: application/json' -d '{"Temperature": 21.5, "Motor": {"Speed": 900}}' \
  "http://localhost:8080/api/v3/submodels/$SM/\$value"                                 # 204
```

The whole body is validated against each `valueType` (and the OPC UA node type) before anything is
written: an invalid value returns `400` and leaves every node untouched. Properties are writable
wherever they are — in collections, lists (`Setpoints[1]`, or the whole list as an array), entity
statements and relationship annotations. Elements whose value is not backed by an OPC UA node yet
(MultiLanguageProperty, Range, File, Blob, and Entity/AnnotatedRelationshipElement as a whole) return
`501`.

Operations are invoked through the same OPC UA Call service used by OPC UA clients, so the handler is
the method of the submodel extension bound to the Operation (method name = `idShort` in snake_case):

```python
# sources/showcase.py — submodel "Showcase" with an Operation "Add" (inputs a, b; output sum)
class Showcase(ISubmodelExtension):
    async def add(self, parent, a, b):
        return float(a + b)
```

```bash
OP="http://localhost:8080/api/v3/submodels/$SM/submodel-elements/Add"
curl -X POST -H 'Content-Type: application/json' -d '{"inputArguments": {"a": 2, "b": 1.5}}' "$OP/invoke/\$value"
# {"executionState": "Completed", "success": true, "outputArguments": {"sum": 3.5}}

curl -i -X POST -H 'Content-Type: application/json' \
  -d '{"inputArguments": {"a": 2}, "clientTimeoutDuration": "PT30S"}' "$OP/invoke-async/\$value"
# 202 + Location: …/Add/operation-status/{handleId}  →  200 Running … then 302 to …/operation-results/{handleId}
```

Inputs are validated against each `valueType` before the call (`400`); a missing input falls back to
the value declared in the model. An Operation with no bound extension method returns `501`. Errors
raised by the handler, or an expired `clientTimeoutDuration`, return `200` with `executionState`
`Failed`/`Timeout`, as required by the spec.

Submodels and submodel elements can also be created, replaced, patched and deleted
(`POST`/`PUT`/`PATCH`/`PATCH …/$metadata`/`DELETE`). Each change is applied to the model served by the
API **and** to the OPC UA address space, and — like value writes — is not persisted to the model file.
The old and new models are reconciled element by element, touching only what changed:

- new / removed elements get their OPC UA subtree created / removed (new elements are live but not
  historized: HDA tables are built at startup);
- a Submodel, an element with children (SubmodelElementCollection, SubmodelElementList, Entity,
  AnnotatedRelationshipElement) or a Property whose runtime attributes (`valueType`, `category`,
  `extensions`, `semanticId`) are unchanged is **updated in place** — only its metadata nodes are recreated
  and new values written, so NodeIds, OPC UA subscriptions, HDA and extensions keep working. A
  `GET` → edit → `PUT` round trip therefore never disturbs the address space beyond the edit;
- list items are matched by position; removing an item from the middle of a list recreates the
  following items with their new index (`[2]` becomes `[1]`), carrying their live values;
- any other change rebuilds the element's subtree;
- removing or rebuilding a subtree in use by the runtime (a historized property or an Operation bound to
  an extension) returns `409`; values remain writable with `PATCH …/$value`.

```bash
curl -X POST -H 'Content-Type: application/json' \
  -d '{"modelType": "Property", "idShort": "Torque", "valueType": "xs:double", "value": "1.5"}' \
  "http://localhost:8080/api/v3/submodels/$SM/submodel-elements/Motor"      # 201 + Location
curl -X DELETE "http://localhost:8080/api/v3/submodels/$SM/submodel-elements/Motor.Torque"   # 204
```

| Service / profile | Status |
|---|---|
| Submodel Repository — read (`SSP-002`): `GetAllSubmodels`, `GetSubmodelById`, `GetAllSubmodelElements`, `GetSubmodelElementByPath`, with `level`, `extent`, `limit`/`cursor`, `idShort` and `semanticId` | ✅ |
| Content modifiers `$value` (ValueOnly), `$metadata`, `$reference`, `$path` on all of the above | ✅ |
| AAS Repository — read (`SSP-002`): `/shells` (filters `assetIds`, `idShort`), `$reference`, `asset-information`, `submodel-refs` and the superpath `/shells/{aas}/submodels/{sm}/…` | ✅ |
| Concept Description Repository — read: `/concept-descriptions` (filters `idShort`, `isCaseOf`, `dataSpecificationRef`) | ✅ |
| `/serialization` (JSON, with live values and referenced Concept Descriptions) | ✅ |
| `/attachment`, `asset-information/thumbnail`, `$recent-changes`, XML/AASX serialization | 🚧 |
| Value writes — `PatchSubmodelById-ValueOnly`, `PatchSubmodelElementByPath-ValueOnly` (Property → OPC UA node, also via the superpath) | ✅ |
| Value writes for MultiLanguageProperty, Range, File, Blob, Entity, AnnotatedRelationshipElement | 🚧 |
| Operation invocation — `/invoke`, `/invoke-async`, `operation-status`, `operation-results` (normal and `$value`, also via the superpath) | ✅ |
| Operations with `inoutputVariables` or non-Property arguments | 🚧 |
| Structural writes — `PostSubmodel`, `Put`/`Patch`(+`$metadata`)/`DeleteSubmodelById`, `PostSubmodelElement(ByPath)`, `Put`/`Patch`(+`$metadata`)/`DeleteSubmodelElementByPath`, synchronized with the OPC UA address space | ✅ |
| Structural writes for AAS and Concept Descriptions (`/shells`, `/concept-descriptions`, `submodel-refs`) | 🚧 |

---

## Asset Binding (AID + AIMC)

When the model contains an *Asset Interfaces Description* (AID, IDTA 02017) and an
*Asset Interfaces Mapping Configuration* (AIMC 2.x, IDTA 02027), Faaster binds the AAS
to the asset by itself — no extension script is needed for the I/O. Both submodels are
found by their `semanticId`, never by `idShort`.

| AIMC mapping | Direction | Behaviour |
|---|---|---|
| Source = AID property, Sink = Property | asset → AAS | Observable points become OPC UA monitored items (initial value included); others are polled at `PollingInterval` / `DefaultPollingInterval` |
| Source = Property, Sink = AID property | AAS → asset | Any write to the Property node — OPC UA client, REST `PATCH …/$value` or an extension — is forwarded to the asset. **Faaster extension:** AIMC 2 lists writing to assets as an upcoming use case |

Rules:

- **AID without AIMC binds nothing** (warning). Bindings are never inferred from names.
- **The binding owns the nodes it feeds.** Extensions write to the AAS node; with an
  AAS → asset mapping the value reaches the asset. A write to a node fed only by the asset
  is overwritten by the next reading (warning).
- **No echo loop:** each node keeps the expected asset state (last reading or last command),
  and a write equal to it is not sent back. Fast pulses (`True` then `False`) are preserved.
- A failed write to the asset restores the node to the last value read from the asset.
- Mappings with a Lua `Transformation`, AAS → AAS mappings and AIMC 1.x are not supported yet
  (skipped with a warning).

OPC UA points are resolved by the NodeId in `href` (`?id=ns=3;s=…`) or, when it is absent,
by `uav_browsePath` (relative to `Objects`). The driver reconnects on its own and re-subscribes
after an outage. Only the `nosec` security scheme is supported for now.

Other protocols are plugins, selected by the URI scheme of `EndpointMetadata/base`:

```toml
# pyproject.toml of the plugin package
[project.entry-points."faaster.bindings"]
"modbus+tcp" = "my_package.modbus:ModbusDriver"   # implements faaster.binding.IAssetDriver
```

Binding is on by default; `--no-asset-binding` disables it.

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
  --no-asset-binding            Do not bind the AAS to the asset through AID + AIMC

OPC UA Server:
  --host HOST                   Host address to bind (default: 0.0.0.0)
  --port PORT                   OPC UA server port (default: 4840)
  --server-discovery URL        OPC UA LDS URL for automatic registration
  --discovery-url URL           External URL advertised to the LDS
  --gds-url URL                 GDS URL for registration and certificate management
  --renew-interval SEC          LDS/GDS renewal interval in seconds (default: 60)

HTTP/REST API (IDTA-01002-3-2) — optional:
  --http-host HOST              Host address to bind (default: 0.0.0.0)
  --http-port PORT              Enable the HTTP/REST API on this port (disabled if omitted)
  --http-base-path PATH         Endpoint prefix (default: /api/v3)

Security:
  --pki-dir PATH                PKI directory (OPC 10000-12 Annex F layout)
  --security-policy POLICY      Security policy: basic256 | aes128 | aes256
                                  basic256  →  Basic256Sha256
                                  aes128    →  Aes128_Sha256_RsaOaep
                                  aes256    →  Aes256_Sha256_RsaPss
                                Repeatable. Requires --pki-dir.
  --security-mode MODE          sign | sign-and-encrypt (default: sign-and-encrypt)
  --allow-anonymous             Keep a NoSecurity endpoint alongside secure ones
  --auto-accept-clients         Auto-trust any client certificate (dev only)
  --gds-username NAME           GDS username (ApplicationSelfAdmin role)
  --gds-password PASS           GDS password
  --cert-common-name CN         Certificate CN (default: --product-name)
  --cert-san-dns DNS            DNS SAN for the certificate (repeatable)
  --cert-san-ip IP              IP SAN for the certificate (repeatable)

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
├── api/                 — AAS HTTP/REST API (IDTA-01002-3-2) over FastAPI
├── binding/             — Asset binding from AID (IDTA 02017) + AIMC (IDTA 02027)
│   ├── model.py         — reads AID/AIMC from the AAS document
│   ├── binder.py        — AssetBinder: asset → AAS and AAS → asset mappings
│   └── drivers/         — IAssetDriver, OPC UA client driver, entry-point plugins
├── cli/                 — CLI argument parsing
├── extensions/          — Extension loader, context and interfaces
├── gds/                 — GDS client, registration manager, certificate client
│   ├── client.py        — GDSClient: DirectoryType methods (§6.5)
│   ├── certificate_client.py  — GDSCertificateClient: Pull Management methods (§7.9)
│   ├── manager.py       — GDSRegistrationManager: registration lifecycle
│   └── models.py        — ApplicationRecord dataclass
├── hda/                 — HDA manager, storage, policies and factory
├── infra/               — asyncua server and address space implementations
├── interfaces/          — IOPCUAServer, IAddressSpace, INode, IDatabase, types
├── loader/              — AAS file loaders (JSON, XML, AASX)
├── log/                 — structlog configuration
├── parser/              — AAS parser, element creators, node registry
├── security/            — PKI store, certificate management, server security
│   ├── certificate_store.py   — CertificateStore: PKI directory (Annex F)
│   ├── certificate_manager.py — CertificateManager: Pull Management workflow
│   ├── crypto_utils.py        — RSA key/cert generation, CSR, thumbprint
│   └── server_security.py     — Security policy mapping, TrustStore, auto-accept
├── asset_administration_shell.py  — dependency container
models/                  — place your AAS JSON models here
sources/                 — place your submodel extension scripts or packages here
server.py                — entry point
```

---

## Roadmap

- [ ] Semantic mapping based on OPC UA ObjectTypes and Interfaces (Braunisch et al., 2025)
- [x] Declarative asset binding from AID (IDTA 02017) + AIMC (IDTA 02027), OPC UA driver
- [ ] AIMC Lua transformations, AAS → AAS mappings and secure (`uav_channelsec`) asset connections
- [ ] Further asset drivers (Modbus, MQTT) as `faaster.bindings` plugins
- [ ] OPC UA events based on `Range` and `BasicEventElement` metamodel elements
- [ ] Machine Learning integration at the edge for anomaly detection in historized variables
- [x] OPC UA security with X.509 certificates (standalone PKI + GDS Pull Management)
- [x] Global Discovery Server integration (OPC UA Part 12 §6–7)
- [ ] Horizontal scaling of Faaster instances in distributed industrial environments
- [ ] MongoDB HDA backend
- [ ] Full AAS HTTP/REST API (IDTA-01002-3-2) — AAS and Submodel Repository read profiles, Property value writes, Operation invocation and Submodel structural writes available

---

## Contributing

Contributions are welcome. Please open an issue or submit a pull request on [GitHub](https://github.com/open-aas/faaster).

---

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.

Copyright 2026 Open AAS Contributors