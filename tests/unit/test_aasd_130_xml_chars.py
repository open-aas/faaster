"""
Constraint AASd-130 (IDTA-01001 v3.2): strings restritas aos caracteres
permitidos pelo XML Schema 1.0, incluindo o plano suplementar (U+10000..U+10FFFF).
"""
import pytest

from faaster.aas_metamodel.models.property import Property

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _prop(id_short=None, value="x"):
    prop = {"modelType": "Property", "valueType": "xs:string", "value": value}
    if id_short is not None:
        prop["idShort"] = id_short
    return prop


# ------------------------------------------------------------------
# AASd-130
# ------------------------------------------------------------------

@pytest.mark.parametrize("text", ["ação", "温度", "😀", "\U0010FFFF", "tab\tok"])
def test_aasd_130_valid_strings(text):
    prop = _prop("Prop")
    prop["category"] = text
    assert Property(**prop).category == text


@pytest.mark.parametrize("text", ["\x00", "\x01", "￾", "\uD800"])
def test_aasd_130_invalid_strings(text):
    prop = _prop("Prop")
    prop["category"] = text
    with pytest.raises(Exception):
        Property(**prop)
