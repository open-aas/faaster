from faaster.interfaces import IAddressSpace, INode
from faaster.aas_metamodel.models.basic_event_element import BasicEventElement
from .base import BaseCreator
from faaster.log import get_logger


logger = get_logger(__name__)


class BasicEventElementCreator(BaseCreator):

    async def create(
        self,
        parent: INode,
        element: BasicEventElement,
        address_space: IAddressSpace,
    ) -> INode:
        name = element.id_short or "BasicEventElement"
        node = await address_space.add_object(parent, name)

        await address_space.add_property(node, "IdShort", name)
        await address_space.add_property(node, "ModelType", element.type_model)
        await address_space.add_property(node, "Category", element.category)
        await address_space.add_property(node, "Direction", element.direction)
        await address_space.add_property(node, "State", element.state)
        await address_space.add_property(node, "MessageTopic", element.message_topic)

        if element.min_interval is not None:
            await address_space.add_property(
                node, "MinInterval", element.min_interval
            )
        if element.max_interval is not None:
            await address_space.add_property(
                node, "MaxInterval", element.max_interval
            )

        if element.observed and element.observed.keys:
            observed_folder = await address_space.add_folder(node, "Observed")
            for i, key in enumerate(element.observed.keys):
                await address_space.add_property(
                    observed_folder,
                    f"Key[{i}]:{key.type.value}",
                    key.value
                )

        if element.semantic_id:
            await self.add_semantic_id(node, element.semantic_id, address_space)

        if element.description:
            await self.add_descriptions(node, element.description, address_space)

        return node
