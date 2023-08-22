from lib.networking import (
    NetworkMessage,
    Vec2H,
    Vec3H,
)


class RegisterPlayerIdMsg(NetworkMessage):
    playerid: int


class PlayerInputMsg(NetworkMessage):
    move_dir: Vec2H
    aim_pos: Vec3H


class PlayerUpdateMsg(NetworkMessage):
    playerid: int
    position: Vec3H
    hpr: Vec3H
