# Historical Data Access (HDA)

HDA stores the history of dynamic properties in TimescaleDB and serves it through the standard
OPC UA HistoryRead service. It is enabled with `--url-database`; without it the server runs with no
history.

## Components

| File | Role |
|---|---|
| `faaster/hda/policies.py` | Parses `faaster:hda:*` extensions into `AggregationPolicy`; defaults and validation |
| `faaster/hda/factory.py` | `HDAManagerFactory` — picks the backend from `--db-backend` |
| `faaster/hda/manager.py` | `HDAManager` — initializes storage, historizes nodes, enables reads on `Value@level` |
| `faaster/hda/storage.py` | `TimescaleHDAStorage` — asyncua history storage: write queue, aggregate windows, HistoryRead |
| `faaster/hda/buffer.py` | `AggregateBuffer` — in-memory windows of the aggregate mode |
| `faaster/infra/database_timescale.py` | `TimescaleDatabase` — DB creation, hypertables, continuous aggregates, policies |

## Flow

1. The parser returns the `Value` nodes of dynamic variables and registers their policy in the `NodeRegistry`.
2. `HDAManager.init()` initializes the storage (connect, create the database if missing,
   reconcile tables/views/policies) and installs it as asyncua's history storage.
3. For each node, `OPCUAServer.historize_node()` sets `Historizing` and `HistoryRead` access and
   registers an address-space **data-change callback**. Every write — by an OPC UA client or an
   extension, including repeated values and bursts — is queued and stored with its
   `SourceTimestamp` (server time if absent). asyncua's own history subscription is not used
   because it drops repeated values.
4. Virtual `Value@<level>` nodes only get `HistoryRead`; their history is read from the level's view.
5. On shutdown the queue is drained and open aggregate windows are persisted.

## Policy extensions

Declared as `Extension` elements on a dynamic property (Qualifier `faaster:dynamic`, see
[mapping](aas-opcua-mapping.md#dynamic-variables)); a policy on a non-dynamic property fails
`--validate-only`. A variable without any `faaster:hda:*`
extension is stored raw with default retention.

| Name | Values | Mode |
|---|---|---|
| `faaster:hda:mode` | `sample` (default), `aggregate` | both |
| `faaster:hda:levels` | comma list of `1min,5min,10min,15min,1hour,1day` (default `1min,1hour,1day`) | sample |
| `faaster:hda:retention:raw` | retention of raw samples | sample |
| `faaster:hda:retention:<level>` | retention of one level | sample |
| `faaster:hda:window` | one window size (required) | aggregate |
| `faaster:hda:function` | `mean`, `sum`, `max`, `min`, `last` | aggregate |
| `faaster:hda:retention` | retention of the window rows | aggregate |

Retention: `<n> <minute|hour|day|week|month|year>[s]` or `none`. Defaults: raw 30 days, `1min`
1 year, `1hour` 5 years, `1day` none; aggregate mode 5 years. A level is refreshed from the last
period of raw data (`1day`: 4 days), so the raw retention must be longer — otherwise the model is
rejected at startup.

```json
{
  "idShort": "Voltage",
  "valueType": "xs:double",
  "qualifiers": [
    { "type": "faaster:dynamic", "kind": "ValueQualifier", "valueType": "xs:boolean", "value": "true" }
  ],
  "extensions": [
    { "name": "faaster:hda:mode", "value": "sample" },
    { "name": "faaster:hda:levels", "value": "1min,1hour,1day" },
    { "name": "faaster:hda:retention:raw", "value": "30 days" }
  ]
}
```

## Storage model

- **Sample mode**: a raw hypertable per variable (compressed after 7 days) plus one TimescaleDB
  continuous aggregate per level, each computed directly from raw (`avg`, `max`, `min`, `stddev`,
  `count`). Real-time aggregation completes the buckets not yet materialized. `Value@<level>` returns
  the bucket average as `Double`.
- **Aggregate mode**: windows aligned to the UTC clock (a `15min` window closes at :00, :15, :30,
  :45), one row per window written right after it closes. A late sample for a persisted window is
  merged into it. If the database is down, results are retried on the next window. The `Value`
  history returns window values as `Double`, timestamped with the window start.
- **Database name**: `--db-name`, else the `--aas_id` argument (default `FaasterAASUniqueId`, not
  the id in the model). Created if missing.
- **HistoryRead**: `NumValuesPerNode = 0` means unlimited; reverse reads and continuation points are
  supported.

## Changing a policy

Policies are reconciled on every startup. Refresh and retention jobs are always recreated; a level's
view is rebuilt only when its definition changes (stored in `faaster_aggregates.definition`).

| Change in the model | Effect |
|---|---|
| Level unchanged | View and data kept |
| Level added | View created; retained raw history materialized in the background |
| Level removed | View and its history dropped |
| Retention changed | Retention job recreated; dropped data is not recovered |
| `sample` ↔ `aggregate` | Each mode has its own table; the other one is kept |
| Policy removed | Raw table kept, with no retention |

Aggregated history older than the raw retention cannot be rebuilt, which is why unchanged views are
never recreated.

## Running TimescaleDB locally

```bash
docker network create faaster-network      # once; the compose file uses an external network
docker-compose -f docker-compose-dev.yaml up
python server.py -m models/my_asset.json \
  --url-database postgresql://faaster:faaster@localhost:5432 --db-backend timescaledb
```

The project skill `.claude/skills/faaster-hda-policy/` covers policy authoring for agents.
