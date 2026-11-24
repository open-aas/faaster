# Security and discovery

## Modules

| File | Role |
|---|---|
| `faaster/security/certificate_store.py` | `CertificateStore` — PKI directory (OPC 10000-12 Annex F) |
| `faaster/security/crypto_utils.py` | RSA keys, self-signed certs, CSR, thumbprints |
| `faaster/security/server_security.py` | Policy mapping, `bootstrap_pki`, `configure_server_security`, TrustStore, `auto_accept_task` |
| `faaster/security/certificate_manager.py` | `CertificateManager` — GDS Pull Management loop |
| `faaster/gds/client.py` | `GDSClient` — Directory methods (§6.5) |
| `faaster/gds/certificate_client.py` | `GDSCertificateClient` — Pull Management methods (§7.9) |
| `faaster/gds/manager.py` | `GDSRegistrationManager` — register, renew, unregister |
| `faaster/gds/models.py` | `ApplicationRecord` |

Security is configured in `OPCUAServer.setup()` only when `--pki-dir` is given. Without it the
server exposes a single NoSecurity endpoint.

## PKI layout

```
pki/
├── own/certs/         server certificate (DER)
├── own/private/       private key (PEM, chmod 600)
├── trusted/certs/     trusted peers        trusted/crl/
├── issuers/certs/     CA chain             issuers/crl/
└── rejected/          untrusted client certificates awaiting approval
```

First start: a self-signed RSA-2048 certificate is generated (CN = `--cert-common-name` or
`--product-name`, SANs from `--cert-san-dns` / `--cert-san-ip`, application URI from
`--product-uri`). Later starts load it.

## Policies

| `--security-policy` | OPC UA policy |
|---|---|
| `basic256` | Basic256Sha256 |
| `aes128` | Aes128_Sha256_RsaOaep |
| `aes256` | Aes256_Sha256_RsaPss |

Repeatable. `--security-mode` (`sign`, `sign-and-encrypt` default) applies to all of them.
`--allow-anonymous` keeps a NoSecurity endpoint as well.

## Client approval

An untrusted client certificate is rejected and copied to `pki/rejected/`. Move it to
`pki/trusted/certs/` to approve it. `--auto-accept-clients` runs a background task that trusts any
rejected certificate — development only.

## LDS registration

With `--server-discovery <url>`, `_register_lds()` registers the server (`RegisterServer`) with the
Local Discovery Server every `--renew-interval` seconds (OPC UA requires at least every 10 minutes),
advertising `--discovery-url`. Failures are logged and retried.

## GDS

With `--gds-url`:

- **Registration** (§6.4): `GDSRegistrationManager` registers the application, keeps it alive with
  `UpdateApplication` every `--renew-interval` and unregisters on shutdown.
- **Pull Certificate Management** (§7.9), when `--pki-dir` is also set: `GetCertificateGroups` →
  `GetCertificateStatus` → `StartSigningRequest` (CSR; the key never leaves the host) →
  `FinishRequest` → `GetTrustList` → apply the TrustList to the local store. Repeats every
  `--renew-interval`, or at once when the GDS reports an update is required.

The GDS user needs the `ApplicationSelfAdmin` or `DiscoveryAdmin` role
(`--gds-username` / `--gds-password`).
