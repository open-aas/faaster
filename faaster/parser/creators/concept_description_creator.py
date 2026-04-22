from typing import Optional
from faaster.interfaces import IAddressSpace, INode
from faaster.aas_metamodel.models.concept_description import ConceptDescription
from .base import BaseCreator
from faaster.log import get_logger


logger = get_logger(__name__)


class ConceptDescriptionCreator(BaseCreator):

    async def create(
        self,
        parent: INode,
        element: ConceptDescription,
        address_space: IAddressSpace,
    ) -> Optional[INode]:
        """
        ConceptDescription não gera nós OPC UA por enquanto.
        Reservado para implementação futura.
        """

        return None
