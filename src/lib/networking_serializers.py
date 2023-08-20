import json
from typing import (
    Any,
    Mapping,
    Protocol,
)


class NetworkSerializer(Protocol):
    def serialize(self, msgdict: Mapping[str, Any]) -> bytes: ...
    def deserialize(self, msgbytes: bytes) -> Mapping[str, Any]: ...


class JsonNetworkSerializer(NetworkSerializer):
    def __init__(self):
        pass

    def serialize(self, msgdict: Mapping[str, Any]) -> bytes:
        msgstr = json.dumps(msgdict)
        return msgstr.encode('utf8')

    def deserialize(self, msgbytes: bytes) -> Mapping[str, Any]:
        msgdict = json.loads(msgbytes)
        return msgdict
