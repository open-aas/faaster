"""Element that can be extended by proprietary extensions."""

from typing import List, Optional
from faaster.aas_metamodel.dto import DTO
from faaster.aas_metamodel.models.extension import Extension


class HasExtensions(DTO):
    """Element that can be extended by proprietary extensions.

    Note: Extensions are proprietary, i.e. they do not support global interoperability.

    :param extensions: An extension of the element.
    """

    extensions: Optional[List[Extension]] = []
