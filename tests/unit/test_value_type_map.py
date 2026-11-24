"""XSD integer types map to OPC UA types of the same range (XML Schema Part 2)."""
import pytest

from faaster.interfaces.types import FaasterVariantType as T
from faaster.parser.creators.base import resolve_variant_type


@pytest.mark.parametrize(
    ("xsd", "expected"),
    [
        ("xs:short", T.Int16),
        ("xs:int", T.Int32),        # was Int16: 32-bit values overflowed / BadTypeMismatch
        ("xs:long", T.Int64),
        ("xs:integer", T.Int64),    # unbounded: widest signed type
        ("xs:unsignedShort", T.UInt16),
        ("xs:unsignedInt", T.UInt32),
        ("xs:unsignedLong", T.UInt64),
        # camelCase keys were looked up lowercased and silently fell back to String
        ("xs:dateTime", T.DateTime),
        ("xs:nonNegativeInteger", T.UInt64),
        ("xs:byteString", T.ByteString),
    ],
)
def test_integer_types(xsd, expected):
    assert resolve_variant_type(xsd) == expected
