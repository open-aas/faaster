import pytest

from faaster.api.encoding import b64url_decode, b64url_encode
from faaster.api.errors import BadRequestError
from faaster.api.pagination import paginate
from faaster.api.repository import parse_id_short_path
from faaster.api.serializer import format_xs_value


# -----------------------------------------------------------------------------
# base64url
# -----------------------------------------------------------------------------

def test_b64url_roundtrip_without_padding():
    encoded = b64url_encode("https://admin-shell.io/sampleSM")
    assert encoded == "aHR0cHM6Ly9hZG1pbi1zaGVsbC5pby9zYW1wbGVTTQ"
    assert "=" not in encoded
    assert b64url_decode(encoded) == "https://admin-shell.io/sampleSM"


def test_b64url_decode_rejects_invalid_characters():
    with pytest.raises(BadRequestError):
        b64url_decode("not/valid+base64")


# -----------------------------------------------------------------------------
# idShortPath
# -----------------------------------------------------------------------------

@pytest.mark.parametrize(
    "path,tokens",
    [
        ("p1", ["p1"]),
        ("sme1.sme2[0].p1", ["sme1", "sme2", 0, "p1"]),
        ("list[0][2]", ["list", 0, 2]),
    ],
)
def test_parse_id_short_path(path, tokens):
    assert parse_id_short_path(path) == tokens


@pytest.mark.parametrize("path", ["", "a..b", ".a", "a.", "[0]", "a.[0]", "1abc", "a[x]"])
def test_parse_id_short_path_rejects_malformed(path):
    with pytest.raises(BadRequestError):
        parse_id_short_path(path)


# -----------------------------------------------------------------------------
# paginação
# -----------------------------------------------------------------------------

def test_paginate_walks_all_pages():
    items = list(range(5))
    page, cursor = paginate(items, limit=2, cursor=None)
    seen = list(page)
    while cursor:
        page, cursor = paginate(items, limit=2, cursor=cursor)
        seen.extend(page)
    assert seen == items


def test_paginate_rejects_empty_cursor():
    with pytest.raises(BadRequestError):
        paginate([1], limit=None, cursor="")


# -----------------------------------------------------------------------------
# forma léxica xsd
# -----------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [(True, "true"), (False, "false"), (42, "42"), (1.5, "1.5"), ("abc", "abc"), (None, None)],
)
def test_format_xs_value(value, expected):
    assert format_xs_value(value) == expected
