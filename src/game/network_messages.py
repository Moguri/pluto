import panda3d.core as p3d

from lib.networking import NetworkMessage


class PlayerInputMsg(NetworkMessage):
    move_dir: p3d.Vec2
    aim_pos: p3d.Vec3


class PlayerUpdateMsg(NetworkMessage):
    position: p3d.Vec3
    hpr: p3d.Vec3
