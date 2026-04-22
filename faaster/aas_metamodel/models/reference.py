"""Reference to either a model element of the same or another AAS or to an external entity."""

from typing import Optional
from faaster.aas_metamodel.models.reference_parent import ReferenceParent


class Reference(ReferenceParent):
    """Reference to either a model element of the same or another AAS or to an external entity.

    A reference is an ordered list of keys.
    A model reference is an ordered list of keys, each key referencing an element.
    The complete list of keys may for example be concatenated to a path that then
    gives unique access to an element.
    A global reference is a reference to an external entity.

    :param referred_semantic_id: SemanticID of the referenced model element
    (Reference/type = Model Reference). For global references there typically is no semantic ID.
    """

    referred_semantic_id: Optional[ReferenceParent] = None
