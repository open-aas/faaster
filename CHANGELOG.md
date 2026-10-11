## v1.0.0a3 (2026-10-11)

### Fix

- **server**: shut down gracefully on SIGINT and SIGTERM
- **hda**: make TimescaleDB storage follow the model policies
- **infra**: keep the measurement time as the value SourceTimestamp
- **parser**: register Value@level nodes as virtual HDA nodes
- **infra**: create typed null variables for properties without value
- accept supplementary Unicode planes in AASd-130 pattern
- align idShort regex with AASd-002 of AAS v3.2
- make idShort optional for SubmodelElementList children (AASd-117)

## v1.0.0a2 (2026-06-15)

### Feat

- add security and GDS CLI arguments with cross-validation
- integrate security and GDS into OPC UA server lifecycle
- add GDS registration manager (OPC 10000-12 §6-7)
- add OPC UA security module with PKI, X.509 and TLS support
- register and bind OPC UA operations to extension instances
- add MethodBinder for deferred async OPC UA method binding

### Fix

- resolve circular import in faaster.hda via lazy __getattr__

## v1.0.0a1 (2026-05-28)

### Feat

- support Python packages as extensions in ExtensionLoader
- adding item http in regex validator

## v1.0.0a0 (2026-05-22)

### Feat

- refactor LDS registration and improve HDA type safety
- first commit
