"""Enumeration listing all xsd primitive types."""

from enum import Enum


class PrimitiveTypes(str, Enum):
    """Enumeration listing all xsd primitive types."""

    ANY_URI = "xs:anyURI"
    BASE_64_BINARY = "xs:base64Binary"
    BOOLEAN = "xs:boolean"
    DATE = "xs:date"
    DATE_TIME = "xs:dateTime"
    DATE_TIME_STAMP = "xs:dateTimeStamp"
    DECIMAL = "xs:decimal"
    DOUBLE = "xs:double"
    DURATION = "xs:duration"
    FLOAT = "xs:float"
    G_DAY = "xs:gDay"
    G_MONTH = "xs:gMonth"
    G_YEAR = "xs:gYear"
    G_YEAR_MONTH = "xs:gYearMonth"
    HEX_BINARY = "xs:hexBinary"
    STRING = "xs:string"
    TIME = "xs:time"
