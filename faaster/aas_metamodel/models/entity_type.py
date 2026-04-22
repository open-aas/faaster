"""Enumeration for denoting whether an entity is a self-managed entity or a co-managed entity."""

from enum import Enum


class EntityType(str, Enum):
    """Enumeration for denoting whether an entity is a self-managed entity or a co-managed entity.

    :param CO_MANAGED_ENTITY: For co-managed entities there is no separate AAS. Co-managed
    entities need to be part of a self-managed entity.
    :param SELF_MANAGED_ENTITY: Self-Managed Entities have their own AAS but can be part of the bill
    of material (BOM) of a composite self-managed entity.
    The asset of an I4.0 Component is a self-managed entity per definition.
    """

    CO_MANAGED_ENTITY = "CoManagedEntity"
    SELF_MANAGED_ENTITY = "SelfManagedEntity"
