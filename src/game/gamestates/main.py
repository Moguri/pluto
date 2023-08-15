import math
from dataclasses import dataclass, field

import panda3d.core as p3d
from direct.showbase.ShowBase import ShowBase
from direct.showbase.DirectObject import DirectObject

from lib.gamestates import GameState


@dataclass(kw_only=True)
class Level:
    name: str
    root: p3d.NodePath
    player_starts: list[p3d.Vec3]


def load_level(levelname: str) -> Level:
    leveldir = p3d.Filename('levels')
    levelpath = leveldir / levelname
    levelpath.set_extension('bam')

    loader = p3d.Loader.get_global_ptr()
    modelroot = loader.load_sync(levelpath)
    root = p3d.NodePath(modelroot)

    player_starts = [
        i.parent.get_pos()
        for i in root.find_all_matches('**/=type=player_start')
    ]

    level = Level(
        name=levelname,
        root=root,
        player_starts=player_starts
    )

    return level


@dataclass(kw_only=True)
class CameraController:
    cam_node: p3d.NodePath
    angle: int
    distance: int

    def update(self, _dt) -> None:
        rad = math.radians(self.angle)
        camy = math.cos(rad) * self.distance
        camz = math.sin(rad) * self.distance
        self.cam_node.set_hpr(0, -self.angle, 0)
        self.cam_node.set_pos(0, -camy, camz)


@dataclass(kw_only=True)
class PlayerController:
    events: DirectObject
    player_node: p3d.NodePath
    speed: int
    move_dir: p3d.Vec2 = field(init=False, default_factory=p3d.Vec2)

    def __post_init__(self):
        self.events.accept('move-forward', self.move, [p3d.Vec2(0, 1)])
        self.events.accept('move-forward-up', self.move, [p3d.Vec2(0, -1)])
        self.events.accept('move-backward', self.move, [p3d.Vec2(0, -1)])
        self.events.accept('move-backward-up', self.move, [p3d.Vec2(0, 1)])
        self.events.accept('move-left', self.move, [p3d.Vec2(-1, 0)])
        self.events.accept('move-left-up', self.move, [p3d.Vec2(1, 0)])
        self.events.accept('move-right', self.move, [p3d.Vec2(1, 0)])
        self.events.accept('move-right-up', self.move, [p3d.Vec2(-1, 0)])

    def move(self, dir_vec):
        self.move_dir += dir_vec

    def update(self, dt):
        prevpos = self.player_node.get_pos()
        movedir = p3d.Vec3(self.move_dir.x, self.move_dir.y, 0).normalized()
        newpos = prevpos + movedir * dt * self.speed
        self.player_node.set_pos(newpos)


class Main(GameState):
    def __init__(self, base: ShowBase):
        super().__init__(base)

        loader = p3d.Loader.get_global_ptr()
        self.level = load_level('testenv')
        self.level.root.reparent_to(self.root_node)

        player_model = loader.load_sync('skeleton.bam')
        player_node = p3d.NodePath(player_model)
        player_node.reparent_to(self.level.root)
        player_node.set_pos(self.level.player_starts[0])

        self.cam_contr = CameraController(
            cam_node=base.cam,
            angle=45,
            distance=40,
        )
        self.player_contr = PlayerController(
            events=self.events,
            player_node=player_node,
            speed=10,
        )

    def update(self, dt):
        self.player_contr.update(dt)
        self.cam_contr.update(dt)
