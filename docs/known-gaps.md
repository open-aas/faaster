# Known gaps

Differences between the README and the code, and features not yet implemented. Checked against
`main`.

## README vs. code

| README says | Code does |
|---|---|
| Python 3.11+ (badge and requirements) | `pyproject.toml` requires Python >= 3.12 |
| Extensions are loaded before HDA starts | `server.py` runs `init_hda()` before `load_extension()` |
| SubmodelElementList is mapped | No creator; the parser skips it |

## Unsupported AAS elements

The parser logs these as `aas_parser.element.unknown_type` (or `data_element.unknown_type`) and
creates no node:

- SubmodelElementList
- Entity
- RelationshipElement and AnnotatedRelationshipElement
- Capability
- Blob (recognized as a data element, but has no creator)

## Not implemented

- `--db-backend mongodb` raises `NotImplementedError`.
- `--url-amqp` is parsed but not used.
- `tests/interfaces/` imports the legacy `core` module and does not run.
