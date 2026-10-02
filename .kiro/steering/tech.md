---
inclusion: always
---
# Stack técnica

- **Python ≥ 3.12**, totalmente `async` (event loop `uvloop`).
- **asyncua[crypto]** — servidor OPC UA (encapsulado em `faaster/infra/`, nunca usado fora dele).
- **pydantic v2** — metamodelo AAS V3 (`faaster/aas_metamodel/models/`).
- **basyx-python-sdk** — apoio a carga de XML/AASX.
- **asyncpg** + **TimescaleDB** (hypertables + continuous aggregates) — HDA.
- **structlog** — logs estruturados (`faaster.log.get_logger`); eventos no formato `"modulo.evento"` com kwargs.
- **cryptography** — PKI, CSR, certificados.
- Grupos de dependência Poetry: `system` (runtime), `cobot` (ur-rtde, pymodbus), `tests` (pytest, pytest-asyncio).

## Comandos
```bash
poetry install --with system,tests          # ou: poetry install -G system
python server.py -m models/x.json --validate-only
python server.py -m models/x.json --host 0.0.0.0 --port 4840
docker compose -f docker-compose-dev.yaml up  # TimescaleDB (rede externa faaster-network)
python server.py -m models/x.json --url-database postgresql://faaster:faaster@localhost:5432 --db-backend timescaledb
pytest tests/                                 # asyncio_mode = auto
pytest tests/unit/test_hda_policies.py
cz bump                                       # commitizen, PEP 440, tag v$version
```

## Regras
- Commits em **Conventional Commits** (`feat:`, `fix:`, `docs:`, `test:`, `build:`); o CHANGELOG é gerado pelo commitizen — não editar à mão.
- `models/` e `sources/` são **gitignored** (artefatos do usuário). Exemplos de modelos de teste ficam em `tests/json-models/`.
- Docker: imagem `python:3.12.2-slim`, instala apenas o grupo `system`, entrypoint `python server.py`.
