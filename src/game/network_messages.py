import enum

from lib.networking import (
    NetworkMessage,
    Vec2H,
    Vec3H,
)

class PlayerAction(enum.Enum):
    REGISTER = 1
    REMOVE = 2
    FIRE = 3


class PlayerInputMsg(NetworkMessage):
    move_dir: Vec2H
    aim_pos: Vec3H
    actions: list[str]


class PlayerActionMsg(NetworkMessage):
    playerid: int
    action: PlayerAction


class PlayerUpdateMsg(NetworkMessage):
    playerid: int
    position: Vec3H
    hpr: Vec3H
    alive: bool
