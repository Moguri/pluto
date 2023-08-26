from dataclasses import (
    dataclass,
    field,
    InitVar,
)
from enum import Enum
import inspect
import struct
from typing import (
    Any,
    Callable,
)

from .networking_transport import (
    NetworkTransport,
    PandaNetworkTransport,
)
from .networking_serializers import (
    NetworkSerializer,
    MsgspecNetworkSerializer,
)
from .networking_message import ( # pylint: disable=unused-import
    NetworkMessage,
    Vec2H,
    Vec3H,
    Vec4H,
)


class NetRole(Enum):
    CLIENT = 1
    SERVER = 2
    DUAL = 3


@dataclass(kw_only=True)
class NetworkManager:
    net_role: NetRole
    new_connection_handler: Callable[[int], None] = lambda _conn_id: None
    disconnect_handler: Callable[[int], None] = lambda _conn_id: None
    transport_type: InitVar[type[NetworkTransport]] = PandaNetworkTransport
    serializer: NetworkSerializer = field(default_factory=MsgspecNetworkSerializer)
    host: str = 'localhost'
    port: int = 8080

    _client_transport: NetworkTransport | None = field(init=False, default=None)
    _server_transport: NetworkTransport | None = field(init=False, default=None)
    _message_types: list[type[NetworkMessage]] = field(init=False, default_factory=list)

    def __post_init__(self, transport_type: type[NetworkTransport]) -> None:
        start_server = False
        start_client = False
        match self.net_role:
            case NetRole.CLIENT:
                start_client = True
            case NetRole.SERVER:
                start_server = True
            case NetRole.DUAL:
                start_client = True
                start_server = True
            case _:
                raise RuntimeError(f'Unspported NetRole: {self.net_role}')

        if start_server:
            self._server_transport = transport_type()
            self._server_transport.start_server(self.port)
        if start_client:
            self._client_transport = transport_type()
            self._client_transport.start_client(self.host, self.port)

        self.update()

    def register_message_types(self, *message_types: type[NetworkMessage]) -> None:
        for message_type in message_types:
            try:
                self._message_types.index(message_type)
                raise RuntimeError(
                    f'Cannot register NetworkMessage type {message_type}: already registered'
                )
            except ValueError:
                pass

            if not issubclass(message_type, NetworkMessage):
                raise RuntimeError(
                    f'Cannot register NetworkMessage type {message_type}: '
                    'must be a subclass of NetworkMessage'
                )

            self._message_types.append(message_type)

    def register_message_module(self, module: Any) -> None:
        msgtypes = [
            clsobj
            for _, clsobj in inspect.getmembers(module, inspect.isclass)
            if issubclass(clsobj, NetworkMessage)
        ]
        self.register_message_types(*msgtypes)

    def update(self) -> None:
        for transport in [self._server_transport, self._client_transport]:
            if not transport:
                continue
            ids = transport.get_new_connections()
            for conn_id in ids:
                self.new_connection_handler(conn_id)
            ids = transport.get_disconnects()
            for conn_id in ids:
                self.disconnect_handler(conn_id)

    def _serialize_net_msg(self, message: NetworkMessage) -> bytes:
        msgtype = type(message)

        try:
            type_id = self._message_types.index(msgtype)
        except ValueError as exc:
            raise RuntimeError(
                f'Attempted to send message of unregistered type: {msgtype}'
            ) from exc

        msgbytes = self.serializer.serialize(message)
        return struct.pack('!B', type_id) + msgbytes

    def _deserialize_net_msg(self, connid: int, message: bytes) -> NetworkMessage:
        type_id = struct.unpack_from('!B', message)[0]
        msgtype = self._message_types[type_id]

        msgbytes = message[struct.calcsize('!B'):]
        msgobj = self.serializer.deserialize(msgbytes, msgtype)
        msgobj.connection_id = connid
        return msgobj

    def _transport_from_netrole(self, netrole: NetRole = NetRole.DUAL) -> NetworkTransport:
        if self.net_role == NetRole.DUAL and netrole == NetRole.DUAL:
            raise RuntimeError('Must specify a netrole when running as NetRole.DUAL')
        if self.net_role != NetRole.DUAL:
            netrole = self.net_role

        if netrole == NetRole.CLIENT:
            return self._client_transport
        if netrole == NetRole.SERVER:
            return self._server_transport

        raise RuntimeError('Could not find a transport object for netrole')

    def send(self, message: NetworkMessage, netrole: NetRole = NetRole.DUAL) -> None:
        msgbytes = self._serialize_net_msg(message)
        self._transport_from_netrole(netrole).send(msgbytes, message.connection_id)

    def get_messages(self, netrole: NetRole = NetRole.DUAL) -> list[NetworkMessage]:
        transport = self._transport_from_netrole(netrole)
        return [
            self._deserialize_net_msg(connid, msg)
            for connid, msg in transport.get_messages()
        ]
