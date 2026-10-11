from typing import Optional
from faaster.interfaces import IAddressSpace, INode
from faaster.interfaces.types import FaasterVariantType
from faaster.aas_metamodel.models.blob import Blob
from .base import BaseCreator
from faaster.log import get_logger

import base64
import binascii


logger = get_logger(__name__)


class BlobCreator(BaseCreator):
    """Object com ContentType e o conteúdo (base64 no JSON) como ByteString em Value."""

    async def create(
        self,
        parent: INode,
        element: Blob,
        address_space: IAddressSpace,
        name: Optional[str] = None,
    ) -> INode:
        name = name or element.id_short or "Blob"
        node = await address_space.add_object(parent, name)

        await self.add_id_short(node, element, address_space)
        await address_space.add_property(node, "ModelType", element.type_model)
        await address_space.add_property(node, "Category", element.category)
        await address_space.add_property(node, "ContentType", element.content_type)

        await address_space.add_variable(
            parent=node,
            name="Value",
            value=_decode(element, name),
            variant_type=FaasterVariantType.ByteString,
        )

        if element.semantic_id:
            await self.add_semantic_id(node, element.semantic_id, address_space)

        if element.description:
            await self.add_descriptions(node, element.description, address_space)

        return node


def _decode(element: Blob, name: str) -> Optional[bytes]:
    if not element.value:
        return None
    try:
        return base64.b64decode(element.value, validate=True)
    except (binascii.Error, ValueError):
        logger.warning("blob_creator.invalid_base64", id_short=name)
        return None
