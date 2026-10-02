"""
Constraint AASd-002 (IDTA-01001 v3.2): formato do idShort
^[a-zA-Z][a-zA-Z0-9_-]*[a-zA-Z0-9_]+$
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
# AASd-002
# ------------------------------------------------------------------

@pytest.mark.parametrize("id_short", ["ab", "Motor-01", "my_prop", "A1-b_2"])
def test_aasd_002_valid_id_shorts(id_short):
    assert Property(**_prop(id_short)).id_short == id_short


@pytest.mark.parametrize("id_short", ["a", "1ab", "ab-", "-ab", "a b", "a.b"])
def test_aasd_002_invalid_id_shorts(id_short):
    with pytest.raises(Exception, match="AASd-002"):
        Property(**_prop(id_short))
