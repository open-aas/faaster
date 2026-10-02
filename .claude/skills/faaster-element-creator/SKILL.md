---
name: faaster-element-creator
description: Use ao adicionar ou alterar o mapeamento de um elemento do metamodelo AAS V3 para nós OPC UA (parser/creators, element_creator, node_registry) no Faaster.
---
# Mapeando um novo elemento AAS → OPC UA

1. **Modelo**: confirme que o elemento existe em `faaster/aas_metamodel/models/` (Pydantic). Se faltar, adicione o modelo e exporte em `models/__init__.py`; constraints `AASd-*` vão em `aas_metamodel/validators.py`.
2. **Creator**: crie `faaster/parser/creators/<elemento>_creator.py` herdando de `creators/base.py` / implementando `IElementCreator`. Use **apenas** `IAddressSpace`/`INode` — nunca `asyncua`.
3. **Despacho**: registre o creator em `faaster/parser/element_creator.py` (e em `creators/__init__.py`).
4. **Registry**: se o elemento precisa ser acessível por extensões/HDA, registre `NodeMetadata` no `NodeRegistry` (path `Submodel/Collection/.../Elemento`, semanticId, submodelo). Operations usam `register_operation` + `MethodBinder`.
5. **Testes**:
   - unidade em `tests/unit/` com `AsyncMock` do address space (ver `test_operation_creator.py`, `test_aas_parser_routing.py`);
   - modelo JSON mínimo/máximo em `tests/json-models/` (já há `*-minimal.json` / `*-maximal.json` para a maioria dos tipos);
   - integração em `tests/integration/` se envolver o servidor real.
6. Atualize a tabela "AAS V3 → OPC UA Mapping" do `README.md` e a seção de arquitetura do `CLAUDE.md`.

Mapeamentos atuais: AAS/Submodel/SMC → Object/Folder; Property → DataVariable (VARIABLE → registry + HDA); Operation → Method; demais criadores: range, file, reference_element, multi_language_property, basic_event_element, concept_description.
