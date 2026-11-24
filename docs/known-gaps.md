# Known gaps

Differences between the README and the code, and features not yet implemented. Checked against
`dev`.

## README vs. code

| README says | Code does |
|---|---|
| Python 3.11+ (badge and requirements) | `pyproject.toml` requires Python >= 3.12 |
| Startup stages: extension loading (6) before HDA initialization (7) | `server.py` runs `init_hda()` before `load_extension()` |
| Selective HDA for variables marked as `VARIABLE` (Key features) | Dynamic variables use the Qualifier `faaster:dynamic`; `VARIABLE` is deprecated |

## Not implemented

- `--db-backend mongodb` raises `NotImplementedError`.
- `--url-amqp` is parsed but not used.
- `tests/interfaces/` imports the legacy `core` module and does not run.
