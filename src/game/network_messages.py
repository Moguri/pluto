import panda3d.core as p3d

from lib.networking import network_message

@network_message
class PlayerInputMsg:
    move_dir: p3d.Vec2
    aim_pos: p3d.Vec3

@network_message
class PlayerUpdateMsg:
    position: p3d.Vec3
    hpr: p3d.Vec3
