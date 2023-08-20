from typing import (
    TypeAlias,
)
from lib.networking import network_message

NetVec2: TypeAlias = tuple[float, float]
NetVec3: TypeAlias = tuple[float, float, float]

@network_message
class PlayerInputMsg:
    move_dir: NetVec2
    aim_pos: NetVec3

@network_message
class PlayerUpdateMsg:
    position: NetVec3
    hpr: NetVec3
