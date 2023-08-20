import pytest

from lib import networking
from lib.networking_transport import PandaNetworkTransport

@networking.replicatable
class RepData:
    intval: int = networking.repfield(default=5)


class NetMsg(networking.NetworkMessage):
    data: str


def test_networking_rep_metadata():
    data = RepData()
    fields = networking.get_replicated_fields(data)
    assert fields
    assert fields[0].name == 'intval'


def test_networking_panda_transport_setup():
    server = PandaNetworkTransport()
    server.start_server(8080)

    client = PandaNetworkTransport()
    client.start_client('localhost', 8080)
    server.update()

    # Send a message from client to server
    msg = b'Hello world'
    client.send(msg)

    # Check server received message
    msgs = server.get_messages()
    assert msgs
    assert msgs[0] == msg

    # Send a message from server to client
    msg = b'foo'
    server.send(msg)

    # Check client received message
    msgs = client.get_messages()
    assert msgs
    assert msgs[0] == msg


def test_networking_manager_setup():
    manager = networking.NetworkManager(net_role=networking.NetRole.SERVER, port=8080)
    assert manager

    manager = networking.NetworkManager(net_role=networking.NetRole.CLIENT, port=8080)
    assert manager

    manager = networking.NetworkManager(net_role=networking.NetRole.DUAL, port=8083)
    assert manager


def test_networking_manager_register_types():
    manager = networking.NetworkManager(net_role=networking.NetRole.DUAL)

    manager.register_message_types(NetMsg)

    with pytest.raises(RuntimeError):
        manager.register_message_types(NetMsg)

def test_networking_manager_send():
    manager = networking.NetworkManager(net_role=networking.NetRole.DUAL)

    msgstr = 'Hello World'
    msg = NetMsg(data=msgstr)

    with pytest.raises(RuntimeError):
        manager.send(msg, networking.NetRole.CLIENT)

    manager.register_message_types(NetMsg)
    manager.send(msg, networking.NetRole.CLIENT)

    messages = manager.get_messages(networking.NetRole.SERVER)
    assert messages
    assert isinstance(messages[0], NetMsg)
    assert messages[0].data == msgstr
