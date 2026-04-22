from datetime import datetime, timezone
from typing import Any, Callable, List, Optional
from asyncua import Server, Node, ua

from faaster.interfaces import IAddressSpace, INode
from faaster.interfaces.types import FaasterVariantType, MethodArgument, FaasterLocalizedText
from faaster.log import get_logger


logger = get_logger(__name__)

FAASTER_NAMESPACE_URI = "urn:faaster:server"

_VARIANT_TYPE_MAP = {
    FaasterVariantType.Float: ua.VariantType.Float,
    FaasterVariantType.Double: ua.VariantType.Double,
    FaasterVariantType.String: ua.VariantType.String,
    FaasterVariantType.Boolean: ua.VariantType.Boolean,
    FaasterVariantType.Int16: ua.VariantType.Int16,
    FaasterVariantType.Int32: ua.VariantType.Int32,
    FaasterVariantType.Int64: ua.VariantType.Int64,
    FaasterVariantType.UInt16: ua.VariantType.UInt16,
    FaasterVariantType.UInt32: ua.VariantType.UInt32,
    FaasterVariantType.UInt64: ua.VariantType.UInt64,
    FaasterVariantType.ByteString: ua.VariantType.ByteString,
    FaasterVariantType.DateTime: ua.VariantType.DateTime,
    FaasterVariantType.LocalizedText: ua.VariantType.LocalizedText,
}


def _to_ua_localized_text(value: FaasterLocalizedText) -> ua.LocalizedText:
    return ua.LocalizedText(Text=value.text, Locale=value.locale)


def _convert_value(
    value: Any,
    variant_type: Optional[FaasterVariantType],
    is_array: bool,
) -> Any:
    """
    Converte o valor para o tipo asyncua correspondente.
    Trata o caso especial de arrays de LocalizedText.
    """
    if variant_type == FaasterVariantType.LocalizedText:
        if is_array:
            return [_to_ua_localized_text(v) for v in value]
        return _to_ua_localized_text(value)

    return value


def _to_ua_variant_type(
    variant_type: Optional[FaasterVariantType],
) -> Optional[ua.VariantType]:
    if variant_type is None:
        return None
    return _VARIANT_TYPE_MAP[variant_type]


def _to_ua_argument(arg: MethodArgument) -> ua.Argument:
    ua_arg = ua.Argument()
    ua_arg.Name = arg.name
    ua_arg.DataType = _VARIANT_TYPE_MAP[arg.variant_type].value
    ua_arg.ValueRank = arg.value_rank
    ua_arg.ArrayDimensions = arg.array_dimensions
    ua_arg.Description = ua.LocalizedText(arg.description)
    return ua_arg


class NodeAdapter(INode):
    """
    Implementação concreta de INode usando asyncua.Node.
    """

    def __init__(self, node: Node) -> None:
        self._node = node

    @property
    def raw(self) -> Node:
        """Acesso ao Node asyncua — uso interno apenas."""
        return self._node

    @property
    def node_id(self) -> str:
        return str(self._node.nodeid)

    @property
    def name(self) -> str:
        return self._node.nodeid.Identifier

    async def get_value(self) -> Any:
        return await self._node.get_value()

    async def set_value(
        self,
        value: Any,
        variant_type: Optional[FaasterVariantType] = None,
    ) -> None:
        ua_vt = _to_ua_variant_type(variant_type)
        if ua_vt:
            await self._node.set_value(ua.DataValue(ua.Variant(value, ua_vt)))
        else:
            await self._node.set_value(value)

    async def get_parent(self) -> "NodeAdapter":
        parent = await self._node.get_parent()
        return NodeAdapter(parent)

    async def get_children(self) -> List["NodeAdapter"]:
        children = await self._node.get_children()
        return [NodeAdapter(child) for child in children]

    async def get_child(self, name: str) -> "NodeAdapter":
        child = await self._node.get_child(name)
        return NodeAdapter(child)

    async def read_data_value(self) -> ua.DataValue:
        return await self._node.read_data_value()

    async def write_data_value(self, data_value: ua.DataValue) -> None:
        await self._node.write_value(data_value)


class AddressSpaceAdapter(IAddressSpace):
    """
    Implementação concreta de IAddressSpace usando asyncua.
    """

    def __init__(self, server: Server) -> None:
        self._server = server
        self._namespace: Optional[str] = None
        self._namespace_index: Optional[int] = None

    async def _get_ns(self) -> int:
        if self._namespace_index is None:
            self._namespace_index = await self._server.get_namespace_index(
                self._namespace
            )
        return self._namespace_index

    def set_namespace(self, uri: str) -> None:
        self._namespace = uri

    async def get_objects_node(self) -> NodeAdapter:
        return NodeAdapter(self._server.get_objects_node())

    async def get_node(self, node_id: str) -> NodeAdapter:
        return NodeAdapter(self._server.get_node(node_id))

    async def get_namespace_index(self, uri: str) -> int:
        return await self._server.get_namespace_index(uri)

    async def add_folder(
        self,
        parent: INode,
        name: str,
    ) -> NodeAdapter:
        ns = await self._get_ns()
        raw_parent = self._unwrap(parent)
        node = await raw_parent.add_folder(ns, name)
        return NodeAdapter(node)

    async def add_object(
        self,
        parent: INode,
        name: str,
        object_type_id: Optional[str] = None,
    ) -> NodeAdapter:
        ns = await self._get_ns()
        raw_parent = self._unwrap(parent)

        if object_type_id:
            obj_type = self._server.get_node(object_type_id)
            node = await raw_parent.add_object(ns, name, obj_type.nodeid)
        else:
            node = await raw_parent.add_object(ns, name)

        return NodeAdapter(node)

    async def add_variable(
        self,
        parent: INode,
        name: str,
        value: Any,
        variant_type: Optional[FaasterVariantType] = None,
        writable: bool = False,
        is_array: bool = False,
    ) -> NodeAdapter:
        ns = await self._get_ns()
        raw_parent = self._unwrap(parent)
        ua_vt = _to_ua_variant_type(variant_type)
        converted_value = _convert_value(value, variant_type, is_array)

        node = await raw_parent.add_variable(ns, name, converted_value, ua_vt)

        if is_array:
            await node.write_value_rank(1)
            await node.write_array_dimensions(0)

        if writable:
            await node.set_writable(True)

        return NodeAdapter(node)

    async def add_property(
        self,
        parent: INode,
        name: str,
        value: Any,
        variant_type: Optional[FaasterVariantType] = None,
    ) -> NodeAdapter:
        ns = await self._get_ns()
        raw_parent = self._unwrap(parent)
        ua_vt = _to_ua_variant_type(variant_type)

        node = await raw_parent.add_property(ns, name, value, ua_vt)
        return NodeAdapter(node)

    async def add_method(
        self,
        parent: INode,
        name: str,
        callback: Callable,
        input_args: Optional[List[MethodArgument]] = None,
        output_args: Optional[List[MethodArgument]] = None,
    ) -> NodeAdapter:
        ns = await self._get_ns()
        raw_parent = self._unwrap(parent)

        ua_input = [_to_ua_argument(a) for a in (input_args or [])]
        ua_output = [_to_ua_argument(a) for a in (output_args or [])]

        node = await raw_parent.add_method(
            ns, name, callback, ua_input, ua_output
        )
        return NodeAdapter(node)

    async def set_value(
        self,
        node: INode,
        value: Any,
        variant_type: Optional[FaasterVariantType] = None,
        source_timestamp: Optional[datetime] = None,
    ) -> None:
        ua_vt = _to_ua_variant_type(variant_type)
        raw_node = self._unwrap(node)

        dv = ua.DataValue(
            Value=ua.Variant(value, ua_vt) if ua_vt else ua.Variant(value),
            ServerTimestamp=source_timestamp if source_timestamp else datetime.now(tz=timezone.utc)
        )

        await raw_node.write_value(dv)

    async def set_display_name(self, node: INode, value: FaasterLocalizedText) -> None:
        raw_node = self._unwrap(node)
        await raw_node.write_attribute(
            ua.AttributeIds.DisplayName,
            datavalue=ua.DataValue(Value=ua.Variant(ua.LocalizedText(Text=value.text, Locale=value.locale)))
        )

    async def set_description(self, node: INode, value: FaasterLocalizedText) -> None:
        raw_node = self._unwrap(node)
        await raw_node.write_attribute(
            ua.AttributeIds.Description,
            datavalue=ua.DataValue(Value=ua.Variant(ua.LocalizedText(Text=value.text, Locale=value.locale)))
        )

    async def get_value(self, node: INode) -> Any:
        raw_node = self._unwrap(node)
        return await raw_node.get_value()

    @staticmethod
    def _unwrap(node: INode) -> Node:
        """
        Extrai o Node asyncua de um INode.
        Lança TypeError se o INode não for AsyncUANode.
        """
        if isinstance(node, NodeAdapter):
            return node.raw

        raise TypeError(
            f"Expected NodeAdapter, got {type(node).__name__}. "
            "Mixing INode implementations is not supported."
        )
