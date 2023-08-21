import functools
import struct
from typing import (
    Any,
    ClassVar,
    Mapping,
    Protocol,
    Type,
    TypeAlias,
)

import msgspec
import panda3d.core as p3d

from .networking_message import (
    NetworkMessage,
    Vec2H,
    Vec3H,
    Vec4H,
)


class NetworkSerializer(Protocol):
    def serialize(self, message: NetworkMessage) -> bytes: ...
    def deserialize(
        self,
        msgbytes: bytes,
        msgtype: ClassVar[NetworkMessage]
    ) -> NetworkMessage: ...


class MsgspecNetworkSerializer(NetworkSerializer):
    def __init__(self):
        protocol = msgspec.msgpack
        self._encoder = protocol.Encoder(
            enc_hook=self._enc_hook
        )
        self._encode = self._encoder.encode
        self._decode = functools.partial(protocol.decode, dec_hook=self._dec_hook)

    def _enc_hook(self, obj: Any) -> Any:
        if isinstance(obj, p3d.LVecBase2d | p3d.LVecBase3d | p3d.LVecBase4d):
            return tuple(obj)
        if isinstance(obj, Vec2H | Vec3H | Vec4H):
            return struct.pack('!' + 'e' * obj.get_num_components(), *obj)
        if isinstance(obj, p3d.LVecBase2f | p3d.LVecBase3f | p3d.LVecBase4f):
            return struct.pack('!' + 'f' * obj.get_num_components(), *obj)

    def _dec_hook(self, objtype: Type, obj: Any) -> Any:
        if issubclass(objtype, p3d.LVecBase2d | p3d.LVecBase3d | p3d.LVecBase4d):
            return objtype(*obj)
        if issubclass(objtype, Vec2H | Vec3H | Vec4H):
            vec = struct.unpack('!' + 'e' * objtype.get_num_components(), obj)
            return objtype(*vec)
        if issubclass(objtype, p3d.LVecBase2f | p3d.LVecBase3f | p3d.LVecBase4f):
            vec = struct.unpack('!' + 'f' * objtype.get_num_components(), obj)
            return objtype(*vec)

    def serialize(self, message: NetworkMessage) -> bytes:
        return self._encode(message)

    def deserialize(
        self,
        msgbytes: bytes,
        msgtype: ClassVar[NetworkMessage]
    ) -> NetworkMessage:
        return self._decode(msgbytes, type=msgtype)
