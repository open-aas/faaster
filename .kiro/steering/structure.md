---
inclusion: always
---
# Estrutura e arquitetura

```
server.py                         entrypoint (CLI → AssetAdministrationShell → ciclo de vida)
faaster/
  asset_administration_shell.py   container de dependências (única peça que conhece as implementações concretas)
  cli/                            argparse + validação cruzada de argumentos (segurança/GDS)
  loader/                         LoaderFactory → JSON / XML / AASX (ILoader)
  aas_metamodel/                  modelos Pydantic AAS V3, validators (AASd-*), DTOs
  parser/
    aas_parser.py                 percorre o metamodelo e despacha criadores
    element_creator.py            roteia cada tipo de elemento ao seu IElementCreator
    creators/                     um criador por tipo (property, operation, collection, range, file…)
    node_registry.py              NodeRegistry: índice por path, semanticId, submodelo + operações
  extensions/                     ExtensionLoader, SubmodelContext, ISubmodelExtension, MethodBinder
  hda/                            policies (faaster:hda:*), manager, storage, factory
  infra/                          asyncua: OPCUAServer, AddressSpaceAdapter, TimescaleDB
  interfaces/                     IOPCUAServer, IAddressSpace, INode, IDatabase, IHDA, IElementCreator
  security/                       CertificateStore (Annex F), CertificateManager, crypto_utils, server_security
  gds/                            GDSClient (§6.5), GDSCertificateClient (§7.9), GDSRegistrationManager
  log/                            configuração structlog
tests/unit | tests/integration | tests/interfaces | tests/json-models
docs/                             especificação OPC 10000-12 (PDF)
```

## Ciclo de vida (server.py)
1. `AssetAdministrationShell(args)` — monta dependências
2. `server.setup(args)` — endpoint, BuildInfo, segurança
3. `server.build_address_space` — parser → nós OPC UA
4. `server.init_hda()` — conecta TimescaleDB e cria hypertables
5. `server.load_extension()` — carrega `sources/`, chama `init()`, faz bind das Operations
6. `server.run()` — loop + re-registro LDS/GDS

## Princípios
- **Desacoplamento por interfaces**: parser, HDA e extensões dependem só de `faaster/interfaces/`. Nada fora de `infra/` importa `asyncua` diretamente (exceção pontual: `uamethod` no ExtensionLoader).
- **Novo backend HDA** = implementar `IHDAStorage` + registrar em `HDAManagerFactory`.
- **Novo tipo de elemento AAS** = novo `IElementCreator` em `parser/creators/` + registro em `element_creator.py`.
- **Mapeamento**: `Property` com `category = VARIABLE` vai para o `NodeRegistry` e pode ser historizada; nós virtuais `Value@1min/@1hour/@1day` são criados automaticamente quando há política HDA.
- **Operations**: `OperationCreator` cria o Method com um `MethodBinder` (proxy); o handler real é vinculado depois pela extensão (IdShort PascalCase → método snake_case). Sem handler → retorna `[]`, sem erro.
- Imports circulares em `faaster.hda` são evitados com `__getattr__` preguiçoso — manter esse padrão.
