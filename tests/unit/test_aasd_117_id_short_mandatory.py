"""
Constraint AASd-117 (IDTA-01001 v3.2): idShort é obrigatório para todos os
Referables, exceto filhos diretos de SubmodelElementList.
"""
import pytest

from faaster.aas_metamodel.models.submodel import Submodel


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _prop(id_short=None, value="x"):
    prop = {"modelType": "Property", "valueType": "xs:string", "value": value}
    if id_short is not None:
        prop["idShort"] = id_short
    return prop


def _submodel(*elements):
    return {
        "modelType": "Submodel",
        "id": "https://example.com/sm/1",
        "idShort": "Sm",
        "submodelElements": list(elements),
    }


def _list(*children):
    return {
        "modelType": "SubmodelElementList",
        "idShort": "MyList",
        "typeValueListElement": "Property",
        "valueTypeListElement": "xs:string",
        "value": list(children),
    }


# ------------------------------------------------------------------
# AASd-117
# ------------------------------------------------------------------

def test_aasd_117_list_children_without_id_short_are_valid():
    sm = Submodel(**_submodel(_list(_prop(), _prop())))
    assert len(sm.submodel_elements) == 1


def test_aasd_117_submodel_element_without_id_short_is_rejected():
    with pytest.raises(Exception, match="AASd-117"):
        Submodel(**_submodel(_prop()))


def test_aasd_117_collection_child_without_id_short_is_rejected():
    smc = {
        "modelType": "SubmodelElementCollection",
        "idShort": "Coll",
        "value": [_prop()],
    }
    with pytest.raises(Exception, match="AASd-117"):
        Submodel(**_submodel(smc))


def test_aasd_117_collection_inside_list_keeps_rule_for_its_children():
    smc_in_list = {
        "modelType": "SubmodelElementCollection",
        "value": [_prop()],
    }
    sml = {
        "modelType": "SubmodelElementList",
        "idShort": "MyList",
        "typeValueListElement": "SubmodelElementCollection",
        "value": [smc_in_list],
    }
    with pytest.raises(Exception, match="AASd-117"):
        Submodel(**_submodel(sml))
