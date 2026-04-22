"""Enumeration of simple data types for a IEC61360 concept description."""

from enum import Enum


class DataTypeIEC61360(str, Enum):
    """Enumeration of simple data types for a IEC61360 concept description.

    Using the data specification template DataSpecificationIEC61360.

    DATE = Values containing a calendar date, conformant to ISO 8601:2004. Format yyyy-mm-dd.
    STRING = Values consisting of sequence of characters but cannot be translated into other
    languages.
    STRING_TRANSLATABLE = Values containing string but shall be represented as different string in
    different languages.
    INTEGER_MEASURE = Values containing values that are measure of type INTEGER.
    In addiction such a value comes with a physical unit.
    INTEGER_COUNT = Values containing values of type INTEGER but are no currencies or measures.
    INTEGER_CURRENT = Values containing values of type INTEGER that are currencies
    REAL_MEASURE = Values containing values that are measures of type REAL.
    In addiction such a value comes with a physical unit.
    REAL_COUNT = Values containing numbers that can be written as a terminating or
    non-terminating decimal; a rational or irrational number but are no currencies or measures.
    REAL_CURRENT = Values containing values of type REAL that are currencies.
    BOOLEAN = Values representing truth of logic or Boolean algebra (TRUE, FALSE).
    IRI = Values containing values of type STRING conformant to Rfc 3987.
    IRDI = Values conforming to ISO/IEC 11179 series global identifier sequences.
    IRDI can be used instead of the more specific data types ICID or ISO29002_IRDI.
    RATIONAL = Values containing values of type rational.
    RATIONAL_MEASURE = Values containing values of type rational.
    In addiction such a value comes with a physical unit.
    TIME = Values containing a time, conformant to ISO 8601:2004 but restricted to what is
    allowed in the corresponding type in xml. Format hh:mm (ECLASS).
    TIMESTAMP = Values containing a time, conformant to ISO 8601:2004 but restricted to what
    is allowed in the corresponding type in xml. Format yyyy-mm-dd hh:mm (ECLASS).
    HTML = Values containing string with any sequence of characters, using the syntax of HTML5
    (see W3C Recommendation 28:2014).
    BLOB = Values containing the content of a file. Values may be binaries.
    FILE = Values containing an address to a file. The values are of type URI and can represent
    an absolute or relative path.
    """

    DATE = "DATE"
    STRING = "STRING"
    STRING_TRANSLATABLE = "STRING_TRANSLATABLE"
    INTEGER_MEASURE = "INTEGER_MEASURE"
    INTEGER_COUNT = "INTEGER_COUNT"
    INTEGER_CURRENT = "INTEGER_CURRENT"
    REAL_MEASURE = "REAL_MEASURE"
    REAL_COUNT = "REAL_COUNT"
    REAL_CURRENCY = "REAL_CURRENCY"
    BOOLEAN = "BOOLEAN"
    IRI = "IRI"
    IRDI = "IRDI"
    RATIONAL = "RATIONAL"
    RATIONAL_MEASURE = "RATIONAL_MEASURE"
    TIME = "TIME"
    TIMESTAMP = "TIMESTAMP"
    HTML = "HTML"
    BLOB = "BLOB"
    FILE = "FILE"
