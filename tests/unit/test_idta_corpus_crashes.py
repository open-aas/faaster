"""Crashes found by running the official IDTA Submodel Templates (FTM experiment E3)."""
import json
from unittest.mock import AsyncMock, MagicMock

from faaster.aas_metamodel.models.multi_language_property import MultiLanguageProperty
from faaster.loader.json.loader import JsonLoader
from faaster.parser.creators.multi_language_property_creator import MultiLanguagePropertyCreator


async def test_multi_language_property_is_created():
    address_space = AsyncMock()
    address_space.add_object.return_value = MagicMock()
    element = MultiLanguageProperty.model_validate({
        "modelType": "MultiLanguageProperty", "idShort": "ManufacturerName",
        "value": [{"language": "en", "text": "ACME"}],
    })

    await MultiLanguagePropertyCreator().create(MagicMock(), element, address_space)

    names = [c.args[1] for c in address_space.add_property.call_args_list]
    assert names[:2] == ["IdShort", "ModelType"] and "en" in names


async def test_environment_lists_are_optional(tmp_path):
    """AAS Part 1: every list of the Environment is optional (templates omit conceptDescriptions)."""
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"submodels": []}))

    environment = await JsonLoader().load(path)

    assert environment.asset_administration_shells == [] and environment.concept_descriptions == []


async def test_operation_is_created_from_the_real_model():
    """The creator read camelCase aliases (``inputVariables``) the pydantic model does not expose."""
    from faaster.aas_metamodel.models.operation import Operation
    from faaster.parser.creators.operation_creator import OperationCreator

    address_space = AsyncMock()
    address_space.add_object.return_value = MagicMock()
    element = Operation.model_validate({
        "modelType": "Operation", "idShort": "Start",
        "inputVariables": [{"value": {"modelType": "Property", "idShort": "Speed",
                                      "valueType": "xs:int"}}],
        "outputVariables": [{"value": {"modelType": "Property", "idShort": "Done",
                                       "valueType": "xs:boolean"}}],
    })

    await OperationCreator().create(MagicMock(), element, address_space)

    kwargs = address_space.add_method.call_args.kwargs
    assert [a.name for a in kwargs["input_args"]] == ["Speed"]
    assert [a.name for a in kwargs["output_args"]] == ["Done"]


def test_file_and_blob_content_type_is_optional():
    """AAS v3.1 made File/contentType and Blob/contentType optional (#412)."""
    from faaster.aas_metamodel.models.blob import Blob
    from faaster.aas_metamodel.models.file import File

    assert File.model_validate({"modelType": "File", "idShort": "Manual"}).content_type is None
    assert Blob.model_validate({"modelType": "Blob", "idShort": "Logo"}).content_type is None


def test_unsigned_int_and_byte_value_types():
    """basyx 2.0.0 has no xs:unsignedInt and maps xs:unsignedByte to UnsignedInt."""
    import pytest

    from faaster.aas_metamodel.exceptions import InvalidFieldException
    from faaster.aas_metamodel.validators import validate_value_type

    validate_value_type("600", "xs:unsignedInt")
    validate_value_type("255", "xs:unsignedByte")
    with pytest.raises(InvalidFieldException):
        validate_value_type("256", "xs:unsignedByte")
