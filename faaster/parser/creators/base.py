from typing import Any, Optional
from faaster.interfaces import IAddressSpace, INode
from faaster.aas_metamodel.models.reference import Reference
from faaster.interfaces.types import FaasterVariantType, FaasterLocalizedText
from faaster.log import get_logger


logger = get_logger(__name__)


_VALUE_TYPE_MAP = {
    "xs:float": FaasterVariantType.Float,
    "xs:double": FaasterVariantType.Double,
    "xs:string": FaasterVariantType.String,
    "xs:anyURI": FaasterVariantType.String,
    "xs:boolean": FaasterVariantType.Boolean,
    "xs:byteString": FaasterVariantType.ByteString,
    "xs:decimal": FaasterVariantType.Double,
    "xs:int": FaasterVariantType.Int16,
    "xs:integer": FaasterVariantType.Int32,
    "xs:long": FaasterVariantType.Int64,
    "xs:negativeInteger": FaasterVariantType.Int64,
    "xs:nonNegativeInteger": FaasterVariantType.UInt64,
    "xs:nonPositiveInteger": FaasterVariantType.Int64,
    "xs:positiveInteger": FaasterVariantType.UInt64,
    "xs:short": FaasterVariantType.Int16,
    "xs:dateTime": FaasterVariantType.DateTime,
}


_VALUE_CONVERTER = {
    FaasterVariantType.Float: float,
    FaasterVariantType.Double: float,
    FaasterVariantType.String: str,
    FaasterVariantType.Boolean: lambda x: str(x).lower() in ("true", "1", "t", "y", "yes"),
    FaasterVariantType.ByteString: str,
    FaasterVariantType.Int16: int,
    FaasterVariantType.Int32: int,
    FaasterVariantType.Int64: int,
    FaasterVariantType.UInt16: int,
    FaasterVariantType.UInt32: int,
    FaasterVariantType.UInt64: int,
    FaasterVariantType.DateTime: str,
}


def resolve_variant_type(value_type: Optional[str]) -> FaasterVariantType:
    if value_type is None:
        return FaasterVariantType.String
    return _VALUE_TYPE_MAP.get(value_type.strip().lower(), FaasterVariantType.String)


def cast_value(value: Any, variant_type: FaasterVariantType) -> Any:
    if value is None:
        return None
    converter = _VALUE_CONVERTER.get(variant_type, str)
    try:
        return converter(value)

    except Exception:
        return value


class BaseCreator:
    """
    Classe base com helpers compartilhados por todos os creators.
    """

    async def create(
        self,
        parent: INode,
        element: Any,
        address_space: IAddressSpace,
    ) -> Optional[INode]:
        raise NotImplementedError

    @staticmethod
    async def add_semantic_id(
        parent: INode,
        semantic_id: Reference,
        address_space: IAddressSpace,
    ) -> None:
        semantic_node = await address_space.add_folder(parent, "SemanticId")

        for key in semantic_id.keys:
            await address_space.add_property(
                semantic_node,
                key.type,
                key.value
                # key.get("type", "Key"),
                # key.get("value", ""),
            )

    @staticmethod
    async def add_descriptions(
        parent: INode,
        descriptions: list,
        address_space: IAddressSpace,
    ) -> None:
        desc_folder = await address_space.add_folder(parent, "Description")
        for desc in descriptions:
            await address_space.add_property(
                desc_folder,
                desc.language,
                desc.text
            )

    @staticmethod
    async def add_administrative_information(
        parent: INode,
        admin_info: Any,
        address_space: IAddressSpace,
    ) -> None:
        node = await address_space.add_object(parent, "AdministrativeInformation")

        if admin_info.version:
            await address_space.add_property(node, "Version", admin_info.version)

        if admin_info.revision:
            await address_space.add_property(node, "Revision", admin_info.revision)

    @staticmethod
    async def add_display_name(
            node: INode,
            display_names: list,
            address_space: IAddressSpace,
    ) -> None:
        if not display_names:
            return

        # 1. atributo nativo do nó — primeiro item apenas
        first = display_names[0]
        await address_space.set_display_name(
            node=node,
            value=FaasterLocalizedText(
                text=first.text or "",
                locale=first.language or "en",
            ),
        )

        # 2. Variable filha — array completo de LocalizedText
        localized_texts = [
            FaasterLocalizedText(
                text=dn.text or "",
                locale=dn.language or "en",
            )
            for dn in display_names
        ]

        await address_space.add_variable(
            parent=node,
            name="DisplayName",
            value=localized_texts,
            variant_type=FaasterVariantType.LocalizedText,
            is_array=True,
        )

    # @staticmethod
    # async def add_descriptions(
    #         node: INode,
    #         descriptions: list,
    #         address_space: IAddressSpace,
    # ) -> None:
    #     if not descriptions:
    #         return
    #
    #     # 1. atributo nativo do nó — primeiro item apenas
    #     first = descriptions[0]
    #     await address_space.set_description(
    #         node=node,
    #         value=FaasterLocalizedText(
    #             text=first.text or "",
    #             locale=first.language or "en",
    #         ),
    #     )
    #
    #     # 2. Variable filha — array completo de LocalizedText
    #     localized_texts = [
    #         FaasterLocalizedText(
    #             text=desc.text or "",
    #             locale=desc.language or "en",
    #         )
    #         for desc in descriptions
    #     ]
    #
    #     await address_space.add_variable(
    #         parent=node,
    #         name="Description",
    #         value=localized_texts,
    #         variant_type=FaasterVariantType.LocalizedText,
    #         is_array=True,
    #     )