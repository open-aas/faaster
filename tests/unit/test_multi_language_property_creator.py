"""
Testes do MultiLanguagePropertyCreator com IAddressSpace mockado.

Regressão: o creator usava o nome ``IdShort`` sem aspas (NameError), o que derrubava o
servidor para qualquer modelo com MultiLanguageProperty (ex.: Nameplate da IDTA).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from faaster.aas_metamodel.models.multi_language_property import MultiLanguageProperty
from faaster.parser.creators.multi_language_property_creator import (
    MultiLanguagePropertyCreator,
)


def _make_address_space():
    as_ = AsyncMock()
    as_.add_object.return_value = MagicMock(node_id="ns=1;i=10")
    as_.add_property.return_value = MagicMock(node_id="ns=1;i=11")
    return as_


def _element(**extra):
    return MultiLanguageProperty.model_validate(
        {
            "idShort": "ManufacturerName",
            "modelType": "MultiLanguageProperty",
            "value": [
                {"language": "en", "text": "ACME"},
                {"language": "pt-BR", "text": "ACME Brasil"},
            ],
            **extra,
        }
    )


@pytest.mark.asyncio
async def test_creates_object_with_id_short_and_one_property_per_language():
    as_ = _make_address_space()
    parent = MagicMock()

    node = await MultiLanguagePropertyCreator().create(parent, _element(), as_)

    as_.add_object.assert_awaited_once_with(parent, "ManufacturerName")
    assert node is as_.add_object.return_value
    props = {c.args[1]: c.args[2] for c in as_.add_property.await_args_list}
    assert props["IdShort"] == "ManufacturerName"
    assert props["ModelType"] == "MultiLanguageProperty"
    assert props["en"] == "ACME"
    assert props["pt-BR"] == "ACME Brasil"


@pytest.mark.asyncio
async def test_empty_value_creates_only_the_metadata_properties():
    as_ = _make_address_space()

    await MultiLanguagePropertyCreator().create(MagicMock(), _element(value=None), as_)

    names = [c.args[1] for c in as_.add_property.await_args_list]
    assert names == ["IdShort", "ModelType", "Category"]
