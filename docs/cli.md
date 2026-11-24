# CLI reference

`python server.py [options]`. Defined in `faaster/cli/cli.py` and
`faaster/cli/cli_identification.py`; `python server.py --help` prints the same list.

## Modeling

| Option | Default | Description |
|---|---|---|
| `-m`, `--modeling-file` | required | AAS V3 model file (`.json`, `.xml`, `.aasx`) |
| `--aas_id_short` | `FaasterAASIdShort` | AAS idShort |
| `--aas_id` | `FaasterAASUniqueId` | AAS id; also the default HDA database name |

## OPC UA server

| Option | Default | Description |
|---|---|---|
| `--host` | `0.0.0.0` | Bind address |
| `--port` | `4840` | Listen port |
| `--server-discovery URL` | — | LDS to register with |
| `--discovery-url URL` | `opc.tcp://0.0.0.0/faaster/server` | External URL advertised to the LDS |
| `--gds-url URL` | — | GDS for registration and certificate management |
| `--renew-interval N` | `60` | Seconds between LDS/GDS renewals and certificate checks |

## Application identification (BuildInfo)

| Option | Default |
|---|---|
| `--product-uri` | `urn:faaster:server` (also the certificate application URI) |
| `--manufacturer-name` | `Faaster` |
| `--product-name` | `Faaster Server` |
| `--software-version` | installed package version |
| `--build-number` | `1` |
| `--build-date` | current UTC time at startup (ISO 8601) |

## Security

| Option | Default | Description |
|---|---|---|
| `--pki-dir DIR` | — | Enables security; PKI root (created if missing) |
| `--cert-common-name` | product name | CN of the generated certificate |
| `--cert-san-dns` | — | DNS SANs (repeatable) |
| `--cert-san-ip` | — | IP SANs (repeatable) |
| `--security-policy` | — | `basic256`, `aes128`, `aes256` (repeatable) |
| `--security-mode` | `sign-and-encrypt` | `sign` or `sign-and-encrypt` |
| `--allow-anonymous` | off | Also expose a NoSecurity endpoint |
| `--auto-accept-clients` | off | Trust every rejected client certificate (development only) |
| `--gds-username`, `--gds-password` | — | GDS credentials |

See [security and discovery](security-and-discovery.md).

## Historical Data Access

| Option | Default | Description |
|---|---|---|
| `--url-database URL` | — | Enables HDA (`postgresql://user:pass@host:port`) |
| `--db-backend` | — | `timescaledb` (`mongodb` is not implemented) |
| `--db-name` | value of `--aas_id` | Database name, created if missing |

See [HDA](hda.md).

## Messaging

| Option | Description |
|---|---|
| `--url-amqp URL` | Planned feature; parsed but not used yet |

## Diagnostics

| Option | Description |
|---|---|
| `--debug` | Debug logging |
| `--log-file PATH` | Also write logs to a file |
| `--validate-only` | Load and validate the model, then exit (no server) |
