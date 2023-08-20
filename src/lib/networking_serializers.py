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
)


MsgDict: TypeAlias = Mapping[str, Any]


class NetworkSerializer(Protocol):
    def serialize(self, message: NetworkMessage) -> bytes: ...
    def deserialize(
        self,
        msgbytes: bytes,
        msgtype: ClassVar[NetworkMessage]
    ) -> NetworkMessage: ...


class MsgspecNetworkSerializer(NetworkSerializer):
    def __init__(self):
        self._encoder = msgspec.msgpack.Encoder(
            enc_hook=self._enc_hook
        )

    def _enc_hook(self, obj: Any) -> Any:
        if isinstance(obj, p3d.LVecBase2 | p3d.LVecBase3 | p3d.LVecBase4):
            return tuple(obj)

    def _dec_hook(self, objtype: Type, obj: Any) -> Any:
        if issubclass(objtype, p3d.LVecBase2 | p3d.LVecBase3 | p3d.LVecBase4):
            return objtype(*obj)

    def serialize(self, message: NetworkMessage) -> bytes:
        return self._encoder.encode(message)

    def deserialize(
        self,
        msgbytes: bytes,
        msgtype: ClassVar[NetworkMessage]
    ) -> NetworkMessage:
        return msgspec.msgpack.decode(msgbytes, type=msgtype, dec_hook=self._dec_hook)
