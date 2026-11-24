"""
Marcação de variáveis dinâmicas (decisão D3 da proposta de dissertação).

O mecanismo normativo é o Qualifier ``faaster:dynamic``; ``category: VARIABLE`` foi
descontinuado na v3.1 do metamodelo e continua aceito apenas com aviso.
"""
from faaster.aas_metamodel.models.property import Property
from faaster.parser.dynamic import DYNAMIC_QUALIFIER, is_dynamic


def _prop(**extra):
    return Property.model_validate(
        {"idShort": "Voltage", "modelType": "Property", "valueType": "xs:double", **extra}
    )


def _qualifier(value="true"):
    return {"type": DYNAMIC_QUALIFIER, "kind": "ValueQualifier",
            "valueType": "xs:boolean", "value": value}


def test_qualifier_marks_the_property_as_dynamic():
    assert is_dynamic(_prop(qualifiers=[_qualifier()])) == (True, False)


def test_qualifier_with_false_value_does_not_mark():
    assert is_dynamic(_prop(qualifiers=[_qualifier("false")])) == (False, False)


def test_legacy_category_still_works_but_is_deprecated():
    assert is_dynamic(_prop(category="VARIABLE")) == (True, True)


def test_plain_property_is_static():
    assert is_dynamic(_prop()) == (False, False)


def test_qualifier_wins_over_category_without_deprecation_flag():
    element = _prop(category="VARIABLE", qualifiers=[_qualifier()])

    assert is_dynamic(element) == (True, False)
