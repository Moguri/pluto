import math
from dataclasses import dataclass, field

from typing import (
    Self,
)

import panda3d.core as p3d
from direct.showbase.ShowBase import ShowBase
from direct.showbase.DirectObject import DirectObject

from lib.gamestates import GameState


@dataclass(kw_only=True)
class Level:
    root: p3d.NodePath
    player_starts: list[p3d.Vec3]

    @classmethod
    def create(cls, model: p3d.NodePath) -> Self:
        player_starts = [
            i.parent.get_pos()
            for i in model.find_all_matches('**/=type=player_start')
        ]

        level = cls(
            root=model,
            player_starts=player_starts
        )

        return level


@dataclass(kw_only=True)
class CameraController:
    cam_node: p3d.NodePath
    target: p3d.NodePath
    angle: int
    distance: int

    def update(self, _dt) -> None:
        rad = math.radians(self.angle)
        camy = math.cos(rad) * self.distance
        camz = math.sin(rad) * self.distance
        self.cam_node.set_hpr(0, -self.angle, 0)

        campos = self.target.get_pos() + p3d.Vec3(0, -camy, camz)
        self.cam_node.set_pos(campos)


@dataclass(kw_only=True)
class CursorInput:
    mouse_watcher: p3d.MouseWatcher
    camera_node: p3d.NodePath
    root_node: p3d.NodePath
    _last_pos: p3d.Vec3 = field(init=False, default_factory=p3d.Vec3)
    _ground_plane: p3d.Plane = field(init=False)

    def __post_init__(self):
        self.ground_plane = p3d.Plane(p3d.Vec3(0, 0, 1), p3d.Vec3(0, 0, 0))

    def update(self) -> None:
        if not self.mouse_watcher.has_mouse():
            return

        near = p3d.Point3()
        far = p3d.Point3()
        pos3d = p3d.Point3()
        camlens = self.camera_node.node().get_lens()
        camlens.extrude(self.mouse_watcher.get_mouse(), near, far)

        relnear = self.root_node.get_relative_point(self.camera_node, near)
        relfar = self.root_node.get_relative_point(self.camera_node, far)
        if self.ground_plane.intersects_line(pos3d, relnear, relfar):
            self._last_pos = pos3d

    def get_pos(self) -> p3d.Vec3:
        return self._last_pos


@dataclass(kw_only=True)
class PlayerController:
    events: DirectObject
    player_node: p3d.NodePath
    cursor: CursorInput
    speed: int
    move_dir: p3d.Vec2 = field(init=False, default_factory=p3d.Vec2)

    def __post_init__(self):
        self.events.accept('move-up', self.move, [p3d.Vec2(0, 1)])
        self.events.accept('move-up-up', self.move, [p3d.Vec2(0, -1)])
        self.events.accept('move-down', self.move, [p3d.Vec2(0, -1)])
        self.events.accept('move-down-up', self.move, [p3d.Vec2(0, 1)])
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

        # Face player toward cursor
        cursorpos = self.cursor.get_pos()
        self.player_node.heads_up(cursorpos, p3d.Vec3(0, 0, 1))

        # Character models are facing -Y, so flip them around now
        self.player_node.set_h(self.player_node.get_h() - 180)


class Main(GameState):
    RESOURCES = {
        'level': 'levels/testenv.bam',
        'player': 'skeleton.bam',
    }

    def __init__(self, base: ShowBase):
        super().__init__(base)

        self.level = None

        self.player_node = self.root_node.attach_new_node('Player')

        # Set confined mouse mode
        self.window = base.win
        self.prev_win_props = self.window.requested_properties
        props = p3d.WindowProperties()
        props.set_mouse_mode(p3d.WindowProperties.M_confined)
        self.window.request_properties(props)

        base.camLens.set_fov(70)


        self.cursor = CursorInput(
            mouse_watcher=base.mouseWatcherNode,
            camera_node=base.cam,
            root_node=self.root_node,
        )
        self.cam_contr = CameraController(
            cam_node=base.camera,
            target=self.player_node,
            angle=45,
            distance=25,
        )
        self.player_contr = PlayerController(
            events=self.events,
            player_node=self.player_node,
            cursor=self.cursor,
            speed=25,
        )

    def start(self):
        self.level = Level.create(self.resources['level'])
        self.level.root.reparent_to(self.root_node)

        player_model = self.resources['player']
        player_model.reparent_to(self.player_node)


    def cleanup(self):
        super().cleanup()

        self.window.request_properties(self.prev_win_props)

    def update(self, dt):
        self.cursor.update()
        self.player_contr.update(dt)
        self.cam_contr.update(dt)
