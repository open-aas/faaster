from enum import Enum
from dataclasses import dataclass, field

class FaasterVariantType(str, Enum):
    """
    Tipos de dados suportados pelo Faaster para variáveis OPC UA.
    Mapeados internamente para ua.VariantType na implementação asyncua.
    """
    Float = "Float"
    Double = "Double"
    String = "String"
    Boolean = "Boolean"
    Int16 = "Int16"
    Int32 = "Int32"
    Int64 = "Int64"
    UInt16 = "UInt16"
    UInt32 = "UInt32"
    UInt64 = "UInt64"
    ByteString = "ByteString"
    DateTime = "DateTime"
    LocalizedText = "LocalizedText"


@dataclass
class FaasterLocalizedText:
    """
    Tipo próprio para LocalizedText — sem acoplar ao asyncua.
    """
    text: str
    locale: str = "en"


@dataclass
class MethodArgument:
    """
    Representa um argumento de entrada ou saída de um método OPC UA.
    Substitui ua.Argument sem acoplar ao asyncua.
    """
    name: str
    variant_type: FaasterVariantType
    description: str = ""
    array_dimensions: list = field(default_factory=list)
    value_rank: int = -1  # -1 = escalar, 0 = array unidimensional
