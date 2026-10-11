"""AASd-117 (idShort obrigatório fora de listas) e AASd-120 (proibido em listas)."""
import pytest
from pydantic import ValidationError

from faaster.aas_metamodel.exceptions import InvalidFieldException
from faaster.aas_metamodel.models.submodel import Submodel
from faaster.aas_metamodel.models.submodel_element_collection import SubmodelElementCollection
from faaster.aas_metamodel.models.submodel_element_list import SubmodelElementList


def _prop(id_short=None):
    p = {"modelType": "Property", "valueType": "xs:string", "value": "x"}
    if id_short:
        p["idShort"] = id_short
    return p


def _list(*items):
    return {"idShort": "L", "modelType": "SubmodelElementList",
            "typeValueListElement": "Property", "valueTypeListElement": "xs:string",
            "value": list(items)}


def test_list_elements_without_id_short_are_accepted():
    sml = SubmodelElementList(**_list(_prop(), _prop()))
    assert len(sml.value) == 2


def test_list_of_reference_elements_without_id_short_as_in_aid_1_2():
    ref = {"modelType": "ReferenceElement",
           "value": {"type": "ModelReference", "keys": [{"type": "Submodel", "value": "urn:x"}]}}
    sml = SubmodelElementList(idShort="security", modelType="SubmodelElementList",
                              typeValueListElement="ReferenceElement", value=[ref])
    assert sml.value[0]["idShort"] is None


def test_list_elements_with_id_short_are_still_accepted(caplog):
    # AASd-120 violada por muitos modelos existentes: só aviso
    sml = SubmodelElementList(**_list(_prop("a"), _prop("b")))
    assert [e["idShort"] for e in sml.value] == ["a", "b"]


def test_collection_requires_id_short():
    with pytest.raises((InvalidFieldException, ValidationError), match="AASd-117"):
        SubmodelElementCollection(idShort="C", modelType="SubmodelElementCollection", value=[_prop()])


def test_submodel_requires_id_short():
    with pytest.raises((InvalidFieldException, ValidationError), match="AASd-117"):
        Submodel(id="urn:sm", modelType="Submodel", submodelElements=[_prop()])


def test_submodel_with_list_inside_collection():
    sm = Submodel(id="urn:sm", modelType="Submodel", submodelElements=[
        {"idShort": "C", "modelType": "SubmodelElementCollection", "value": [_list(_prop())]},
    ])
    assert sm.submodel_elements[0].id_short == "C"
