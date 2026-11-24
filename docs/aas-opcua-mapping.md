# AAS → OPC UA mapping

## Loading

`AASParser.parse()` (`faaster/parser/aas_parser.py`) asks `LoaderFactory`
(`faaster/loader/factory.py`) for a loader by file extension:

| Extension | Loader |
|---|---|
| `.json` | `faaster/loader/json/loader.py` — `JsonLoader` |
| `.xml` | `faaster/loader/xml/loader.py` — `XmlLoader` |
| `.aasx` | `faaster/loader/aasx/loader.py` — `AasxLoader` |

Anything else raises `UnsupportedFormatLoaderError`. The loader returns an `Environment` built from
the Pydantic models in `faaster/aas_metamodel/models/`; the AASd constraints of IDTA-01001-3-0 are
checked there (`faaster/aas_metamodel/validators.py`), so an invalid model fails before any node is
created.

## Parse order

1. Create the `Environment` root object.
2. Shells: one object per AAS (`AASCreator`), with `AssetInformation`, `DisplayName`,
   `DerivedFrom`, `Submodels` references and data specifications.
3. Submodels (`SubmodelCreator`), then their elements recursively.
4. ConceptDescriptions (`ConceptDescriptionCreator`).
5. Return the list of nodes to historize.

## Element mapping

Every element becomes an OPC UA **Object** named after its `idShort`, with child properties for its
metadata (`IdShort`, `ModelType`, `Category`, and per type `ValueType`, `Kind`, `ContentType`…).
`SemanticId` and descriptions are added by `BaseCreator` (`faaster/parser/creators/base.py`).

| AAS element | Creator | OPC UA content |
|---|---|---|
| AssetAdministrationShell | `aas_creator.py` | Object + `AssetInformation`, `Submodels` folder |
| Submodel | `submodel_creator.py` | Object (`Id`, `Kind`, …) |
| SubmodelElementCollection | `collection_creator.py` | Object; children parsed recursively |
| Property | `property_creator.py` | Object + `Value` **DataVariable** typed from `valueType` |
| Range | `range_creator.py` | Object + `Min` and `Max` variables |
| MultiLanguageProperty | `multi_language_property_creator.py` | Object + one property per language |
| File | `file_creator.py` | Object + `ContentType` and value variable |
| ReferenceElement | `reference_element_creator.py` | Object + `Keys` folder |
| BasicEventElement | `basic_event_element_creator.py` | Object + `Direction`, `State`, … |
| Operation | `operation_creator.py` | Object + **Method** (bound to an extension, see [extensions](extensions.md)) |
| ConceptDescription | `concept_description_creator.py` | Object |

Elements not in this table are logged as `aas_parser.element.unknown_type` and skipped — see
[known gaps](known-gaps.md).

## VARIABLE properties

A data element whose `category` is `VARIABLE` is the unit of live data and history:

- its `Value` node is registered in the `NodeRegistry` with path
  `<Submodel>/<Collection…>/<idShort>/Value`, the submodel, the first `semanticId` key, the variant
  type and its HDA policy;
- the node is returned to the server to be historized (when HDA is enabled);
- if it carries a `sample` HDA policy, read-only `Value@<level>` Double variables are created next to
  `Value` and registered as virtual nodes (`level != "raw"`). See [HDA](hda.md).

Properties without `category: VARIABLE` exist in the address space but are not in the registry, so
`SubmodelContext.get_node()` does not find them.

## NodeRegistry

`faaster/parser/node_registry.py` indexes `NodeMetadata` for extensions and HDA:

| Method | Returns |
|---|---|
| `get_by_path(path)` | metadata for `<Submodel>/…/Value` |
| `get_by_node_id(node_id)` | metadata by OPC UA NodeId |
| `get_by_semantic_id(id)` | metadata by semantic ID |
| `get_by_submodel(id_short)` | all nodes of one submodel, keyed by path |
| `get_operations(id_short)` | `OperationEntry` list (id_short, `MethodBinder`) |
| `all` | every registered metadata, raw and virtual |

`NodeMetadata.table_suffix` (`""`, `_1min`, …) names the TimescaleDB table or view of each level.

## Adding a new element type

1. Write a `BaseCreator` subclass in `faaster/parser/creators/` and export it in `__init__.py`.
2. Add a `create_<element>` method to `IElementCreator` and `AASElementCreator`.
3. Pass the creator in `AssetAdministrationShell`.
4. Route the `modelType` in `AASParser._parse_submodel_element` / `_parse_data_element`.

The project skill `.claude/skills/faaster-element-creator/` describes the same steps for agents.
