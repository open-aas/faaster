# Development

## Setup

Python 3.12 (`requires-python >= 3.12`), Poetry, dependency groups `system`, `cobot` and `tests`.

```bash
python3.12 -m venv venv
source venv/bin/activate
poetry install --with system,tests
```

## Running

```bash
python server.py -m models/my_asset.json --validate-only      # check the model
python server.py -m models/my_asset.json --host 0.0.0.0 --port 4840
```

`models/` (AAS models) and `sources/` (extensions) are gitignored; they belong to each deployment.
See [CLI reference](cli.md) for every option.

## Docker

- `Dockerfile` — `python:3.12.2-slim`, `poetry install --only system`, `ENTRYPOINT python server.py`.
  Pass the CLI options as the container command.
- `docker-compose-dev.yaml` — TimescaleDB (`timescale/timescaledb-ha:pg15`, user and password
  `faaster`) on the **external** network `faaster-network`:

```bash
docker network create faaster-network   # once
docker-compose -f docker-compose-dev.yaml up
```

## Tests

| Folder | Content |
|---|---|
| `tests/unit/` | parser routing, AASd constraints, CLI, HDA policies/buffer/storage, registry, operations, PKI, GDS |
| `tests/integration/` | address space, operation chain, HDA over OPC UA, HDA on TimescaleDB |
| `tests/asset_administration_shell/` | container wiring |
| `tests/json-models/` | minimal/maximal JSON per AAS element type |
| `tests/json_aas_samples/` | full vendor models (Festo, Bosch, …) |
| `tests/interfaces/` | legacy; imports the old `core` module and is broken |

```bash
pytest tests/unit tests/integration
pytest tests/unit/test_hda_policies.py      # single file
```

HDA tests need TimescaleDB: they start a container through Docker, or use the database in
`FAASTER_TEST_TIMESCALE_URL` when set.

## Versioning

Commitizen with `cz_conventional_commits` and PEP 440 versions (currently `1.0.0a3`). Commits follow
Conventional Commits; `cz bump` cuts a version and updates `CHANGELOG.md`. Do not bump as a side
effect of other work.

## Conventions

- Infrastructure goes behind `faaster/interfaces/`; only `faaster/infra/` and
  `asset_administration_shell.py` import concrete asyncua/asyncpg classes. See
  [architecture](architecture.md).
- Logs are structlog events with dotted names and keyword fields.
- Context for agents: `.kiro/steering/` (product, tech, structure, conventions),
  `.claude/skills/` (`faaster-extension`, `faaster-hda-policy`, `faaster-element-creator`) and
  `.claude/agents/` (`aas-model-validator`, `faaster-reviewer`).

## Gotchas

- The `.gitignore` rule `models/` also matches `faaster/aas_metamodel/models/`; new files there
  need `git add -f`.
- Only `category: VARIABLE` data elements are in the `NodeRegistry`; others cannot be found by
  `SubmodelContext.get_node()` nor historized.
- An Operation without a matching extension method returns `[]` silently.
- `--db-name` defaults to `--aas_id`, whose own default is `FaasterAASUniqueId`: set one of them,
  or every deployment shares the same database.

## Documentation

`docs/` is the source. `scripts/build_vault.py` generates the Obsidian vault (`obsidian-vault/`,
gitignored) from `docs/` and the package tree; re-run it after changing docs or modules:

```bash
python scripts/build_vault.py
```
