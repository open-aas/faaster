# Faaster documentation

Faaster (**Fa**ster **A**sset **A**dministration **S**hell **T**ype 2 ov**er** OPC UA) deploys a
Reactive AAS (Type 2) over OPC UA from an AAS V3 model file. It parses the model, builds the OPC UA
address space, historizes the variables the model asks for (HDA) and loads user extensions that
connect the AAS to the real device.

The [README](../README.md) is the product overview. These pages go deeper, one subject each.

| Page | What it covers |
|---|---|
| [Architecture](architecture.md) | Startup lifecycle, the dependency container, layers and interfaces |
| [AAS → OPC UA mapping](aas-opcua-mapping.md) | Loaders, parser, element creators, node registry, address-space layout |
| [Submodel extensions](extensions.md) | Writing `sources/` extensions, `SubmodelContext`, binding Operations |
| [Validation](validation.md) | `--validate-only` pipeline stages, report formats, exit code |
| [Historical Data Access](hda.md) | `faaster:hda:*` policies, storage in TimescaleDB, HistoryRead |
| [Security and discovery](security-and-discovery.md) | PKI, security policies, client approval, LDS and GDS |
| [CLI reference](cli.md) | Every `server.py` option, grouped |
| [Development](development.md) | Setup, tests, Docker, versioning, conventions and gotchas |
| [Known gaps](known-gaps.md) | Where the code and the README disagree, features not implemented |
| [Backlog](backlog.md) | Open and done work items |

Reference material:

- `docs/OPC 10000-12 - UA Specification Part 12 - Discovery and Global Services 1.05.05.pdf` —
  basis for the GDS and PKI layout.
- [IDTA-01001-3-0](https://industrialdigitaltwin.org) — AAS V3 metamodel validated by
  `faaster/aas_metamodel/`.
