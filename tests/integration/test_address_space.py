"""
Testes de integração do AddressSpaceAdapter com asyncua.Server real (sem rede).

Verifica que o adaptador cria, lê e escreve nós corretamente
usando o address space in-memory do asyncua.
"""
import pytest
from asyncua import ua

from faaster.infra.address_space import AddressSpaceAdapter, NodeAdapter
from faaster.interfaces.types import FaasterVariantType, FaasterLocalizedText


# ------------------------------------------------------------------
# Namespace e get_objects_node
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_namespace_registered(opcua_server):
    ns = await opcua_server.register_namespace("urn:faaster:ns:test")
    assert isinstance(ns, int)
    assert ns >= 2  # 0=OPC UA, 1=local


@pytest.mark.asyncio
async def test_get_objects_node_returns_node_adapter(address_space):
    objects = await address_space.get_objects_node()
    assert isinstance(objects, NodeAdapter)
    assert objects.node_id  # não-vazio


# ------------------------------------------------------------------
# add_folder
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_folder_returns_node_adapter(address_space, objects_node):
    folder = await address_space.add_folder(objects_node, "MyFolder")
    assert isinstance(folder, NodeAdapter)


@pytest.mark.asyncio
async def test_add_folder_has_node_id_with_namespace(address_space, objects_node):
    folder = await address_space.add_folder(objects_node, "FolderNS")
    # asyncua serializa NodeId como "NodeId(Identifier=X, NamespaceIndex=Y, ...)"
    assert folder.raw.nodeid.NamespaceIndex != 0


@pytest.mark.asyncio
async def test_nested_folder(address_space, objects_node):
    parent_folder = await address_space.add_folder(objects_node, "Parent")
    child_folder = await address_space.add_folder(parent_folder, "Child")
    assert isinstance(child_folder, NodeAdapter)
    assert child_folder.node_id != parent_folder.node_id


# ------------------------------------------------------------------
# add_object
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_object_returns_node_adapter(address_space, objects_node):
    obj = await address_space.add_object(objects_node, "MyObject")
    assert isinstance(obj, NodeAdapter)


@pytest.mark.asyncio
async def test_add_object_different_ids(address_space, objects_node):
    obj1 = await address_space.add_object(objects_node, "Obj1")
    obj2 = await address_space.add_object(objects_node, "Obj2")
    assert obj1.node_id != obj2.node_id


# ------------------------------------------------------------------
# add_variable
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_variable_float_read_back(address_space, objects_node):
    node = await address_space.add_variable(
        objects_node, "Temperature", 22.5, FaasterVariantType.Float
    )
    value = await node.get_value()
    assert abs(value - 22.5) < 0.001


@pytest.mark.asyncio
async def test_add_variable_double(address_space, objects_node):
    node = await address_space.add_variable(
        objects_node, "Voltage", 220.001, FaasterVariantType.Double
    )
    value = await node.get_value()
    assert abs(value - 220.001) < 0.0001


@pytest.mark.asyncio
async def test_add_variable_string(address_space, objects_node):
    node = await address_space.add_variable(
        objects_node, "Status", "running", FaasterVariantType.String
    )
    assert await node.get_value() == "running"


@pytest.mark.asyncio
async def test_add_variable_boolean(address_space, objects_node):
    node = await address_space.add_variable(
        objects_node, "Active", True, FaasterVariantType.Boolean
    )
    assert await node.get_value() is True


@pytest.mark.asyncio
async def test_add_variable_int32(address_space, objects_node):
    node = await address_space.add_variable(
        objects_node, "Count", 42, FaasterVariantType.Int32
    )
    assert await node.get_value() == 42


@pytest.mark.asyncio
async def test_add_variable_writable_allows_write(address_space, objects_node):
    node = await address_space.add_variable(
        objects_node, "WritableVar", 0.0, FaasterVariantType.Float, writable=True
    )
    await node.set_value(3.14, FaasterVariantType.Float)
    value = await node.get_value()
    assert abs(value - 3.14) < 0.001


# ------------------------------------------------------------------
# add_property
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_property_string(address_space, objects_node):
    folder = await address_space.add_folder(objects_node, "PropFolder")
    prop = await address_space.add_property(folder, "IdShort", "Voltage")
    assert await prop.get_value() == "Voltage"


@pytest.mark.asyncio
async def test_add_property_int(address_space, objects_node):
    folder = await address_space.add_folder(objects_node, "PropFolderInt")
    prop = await address_space.add_property(folder, "Level", 5)
    assert await prop.get_value() == 5


# ------------------------------------------------------------------
# set_value / get_value via adapter
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_value_and_get_value(address_space, objects_node):
    node = await address_space.add_variable(
        objects_node, "SetGet", 0.0, FaasterVariantType.Float, writable=True
    )
    await address_space.set_value(node, 55.5, FaasterVariantType.Float)
    value = await address_space.get_value(node)
    assert abs(value - 55.5) < 0.001


@pytest.mark.asyncio
async def test_set_value_string(address_space, objects_node):
    node = await address_space.add_variable(
        objects_node, "SetGetStr", "initial", FaasterVariantType.String, writable=True
    )
    await address_space.set_value(node, "updated", FaasterVariantType.String)
    assert await address_space.get_value(node) == "updated"


# ------------------------------------------------------------------
# NodeAdapter — navegação e leitura
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_node_adapter_node_id_is_string(address_space, objects_node):
    folder = await address_space.add_folder(objects_node, "NodeIdTest")
    assert isinstance(folder.node_id, str)
    assert len(folder.node_id) > 0


@pytest.mark.asyncio
async def test_node_adapter_get_parent(address_space, objects_node):
    folder = await address_space.add_folder(objects_node, "ParentTest")
    parent = await folder.get_parent()
    assert isinstance(parent, NodeAdapter)
    # O pai do nosso folder é o Objects node
    assert parent.node_id == objects_node.node_id


@pytest.mark.asyncio
async def test_node_adapter_get_children_includes_added(address_space, objects_node):
    parent = await address_space.add_folder(objects_node, "ChildrenParent")
    await address_space.add_folder(parent, "ChildA")
    await address_space.add_folder(parent, "ChildB")

    children = await parent.get_children()
    assert len(children) >= 2


@pytest.mark.asyncio
async def test_node_adapter_get_value(address_space, objects_node):
    node = await address_space.add_variable(
        objects_node, "GetValueTest", 7.0, FaasterVariantType.Float
    )
    assert abs(await node.get_value() - 7.0) < 0.001


@pytest.mark.asyncio
async def test_node_adapter_set_value_with_type(address_space, objects_node):
    node = await address_space.add_variable(
        objects_node, "SetValueTyped", 0.0, FaasterVariantType.Double, writable=True
    )
    await node.set_value(123.456, FaasterVariantType.Double)
    assert abs(await node.get_value() - 123.456) < 0.0001


@pytest.mark.asyncio
async def test_node_adapter_read_data_value(address_space, objects_node):
    node = await address_space.add_variable(
        objects_node, "DataValueTest", 99.0, FaasterVariantType.Float
    )
    dv = await node.read_data_value()
    assert dv is not None
    assert dv.Value is not None


# ------------------------------------------------------------------
# set_display_name
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_display_name(address_space, objects_node):
    folder = await address_space.add_folder(objects_node, "DisplayNameTest")
    # Não deve lançar exceção
    await address_space.set_display_name(
        folder,
        FaasterLocalizedText(text="Meu Folder", locale="pt"),
    )
    # Verifica que o DisplayName foi alterado lendo o atributo
    raw = folder.raw
    dn = await raw.read_attribute(ua.AttributeIds.DisplayName)
    assert dn.Value.Value.Text == "Meu Folder"
