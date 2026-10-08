"""
AnnotatedRelationshipElement: the AAS v3 JSON uses ``annotations`` (plural).

IDTA-01001 v3.2, "JSON Mapping Rules": aggregations are named in singular in UML
(``annotation``) and in plural in JSON (``annotations``). The legacy singular key is still
accepted when reading.
"""
import pytest

from faaster.aas_metamodel.models.annotated_relationship_element import (
    AnnotatedRelationshipElement,
)

REF = {"type": "ModelReference", "keys": [{"type": "Submodel", "value": "https://x/sm"}]}


def _are(key, annotations):
    return {
        "modelType": "AnnotatedRelationshipElement",
        "idShort": "Rel",
        "first": REF,
        "second": REF,
        key: annotations,
    }


def _prop(id_short="AppliedRule"):
    prop = {"modelType": "Property", "valueType": "xs:string", "value": "x"}
    if id_short:
        prop["idShort"] = id_short
    return prop


def test_v3_json_annotations_are_read():
    element = AnnotatedRelationshipElement(**_are("annotations", [_prop()]))

    assert [a["idShort"] for a in element.annotations] == ["AppliedRule"]


def test_legacy_singular_key_is_still_accepted():
    element = AnnotatedRelationshipElement(**_are("annotation", [_prop()]))

    assert [a["idShort"] for a in element.annotations] == ["AppliedRule"]


def test_serialized_with_plural_key():
    dumped = AnnotatedRelationshipElement(**_are("annotations", [_prop()])).model_dump(
        by_alias=True
    )

    assert "annotations" in dumped and "annotation" not in dumped


def test_annotations_without_id_short_violate_aasd_117():
    with pytest.raises(Exception, match="AASd-117"):
        AnnotatedRelationshipElement(**_are("annotations", [_prop(id_short=None)]))
