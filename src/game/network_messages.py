from lib.networking import (
    NetworkMessage,
    Vec2H,
    Vec3H,
)


class PlayerInputMsg(NetworkMessage):
    move_dir: Vec2H
    aim_pos: Vec3H


class PlayerUpdateMsg(NetworkMessage):
    position: Vec3H
    hpr: Vec3H
