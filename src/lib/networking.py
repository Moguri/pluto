import dataclasses
from dataclasses import (
    dataclass,
    field,
    InitVar,
)
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Protocol,
    Self,
)

import panda3d.core as p3d

from .networking_transport import (
    NetworkTransport,
    PandaNetworkTransport,
)
from .networking_serializers import (
    NetworkSerializer,
    JsonNetworkSerializer,
)


# mostly alias for now, we might need to expand on this later
network_message = dataclass(kw_only=True)


class NetworkMessage(Protocol):
    @classmethod
    def from_dict(cls, data) -> Self: ...


class NetRole(Enum):
    CLIENT = 1
    SERVER = 2
    DUAL = 3


# alias for now, we might need to expand on this later
replicatable = dataclass


@dataclasses.dataclass(kw_only=True)
class RepInfo:
    is_replicated: bool = field(default=True, init=False)


def repfield(**kwargs):
    repinfo = RepInfo()
    kwargs['metadata'] = dataclasses.asdict(repinfo)
    return dataclasses.field(**kwargs)


def get_replicated_fields(replicatable_object: Any):
    return [
        field
        for field in
        dataclasses.fields(replicatable_object)
        if field.metadata.get('is_replicated', False)
    ]


@dataclasses.dataclass(kw_only=True)
class NetworkManager:
    net_role: NetRole
    transport_type: InitVar[ClassVar[NetworkTransport]] = PandaNetworkTransport
    serializer: NetworkSerializer = field(default_factory=JsonNetworkSerializer)
    host: str = 'localhost'
    port: int = 8080

    _client_transport: NetworkTransport | None = field(init=False, default=None)
    _server_transport: NetworkTransport | None = field(init=False, default=None)
    _message_types: list[ClassVar[NetworkMessage]] = field(init=False, default_factory=list)

    def __post_init__(self, transport_type: ClassVar[NetworkTransport]) -> None:
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

    def register_message_type(self, message_type: ClassVar[NetworkMessage]) -> None:
        try:
            self._message_types.index(message_type)
            raise RuntimeError(
                f'Cannot register NetworkMessage type {message_type}: already registered'
            )
        except ValueError:
            pass

        if not dataclasses.is_dataclass(message_type):
            raise RuntimeError(
                f'Cannot serialize message of type {message_type}: must be a dataclass'
            )

        self._message_types.append(message_type)

    def update(self) -> None:
        if self._server_transport:
            self._server_transport.update()
        if self._client_transport:
            self._client_transport.update()

    def _serialize_net_msg(self, message: NetworkMessage) -> bytes:
        msgtype = type(message)

        try:
            type_id = self._message_types.index(msgtype)
        except ValueError as exc:
            raise RuntimeError(
                f'Attempted to send message of unregistered type: {msgtype}'
            ) from exc

        msgdict = dataclasses.asdict(message)
        for key, value in msgdict.items():
            match value:
                case p3d.LVecBase2():
                    msgdict[key] = (value.x, value.y)
                case p3d.LVecBase3():
                    msgdict[key] = (value.x, value.y, value.z)
                case p3d.LVecBase4():
                    msgdict[key] = (value.x, value.y, value.z, value.w)
        msgdict['__typeid__'] = type_id
        return self.serializer.serialize(msgdict)

    def _deserialize_net_msg(self, message: bytes) -> NetworkMessage:
        msgdict = self.serializer.deserialize(message)
        type_id = msgdict['__typeid__']
        del msgdict['__typeid__']
        msgtype = self._message_types[type_id]

        for key, value in msgdict.items():
            vtype = msgtype.__annotations__[key]
            if issubclass(vtype, p3d.LVecBase2 | p3d.LVecBase3 | p3d.LVecBase4):
                msgdict[key] = vtype(*value)

        if hasattr(msgtype, 'from_dict'):
            return msgtype.from_dict(msgdict)

        return msgtype(**msgdict)

    def _transport_from_netrole(self, netrole: NetRole = NetRole):
        if self.net_role == NetRole.DUAL and netrole == NetRole.DUAL:
            raise RuntimeError('Must specify a netrole when running as NetRole.DUAL')
        if self.net_role != NetRole.DUAL:
            netrole = self.net_role

        if netrole == NetRole.CLIENT:
            return self._client_transport
        if netrole == NetRole.SERVER:
            return self._server_transport

        raise RuntimeError('Could not find a transport object for netrole')

    def send(self, message: NetworkMessage, netrole: NetRole = NetRole.DUAL):
        msgbytes = self._serialize_net_msg(message)
        self._transport_from_netrole(netrole).send(msgbytes)

    def get_messages(self, netrole: NetRole = NetRole.DUAL) -> list[NetworkMessage]:
        transport = self._transport_from_netrole(netrole)
        return [
            self._deserialize_net_msg(msg)
            for msg in transport.get_messages()
        ]
