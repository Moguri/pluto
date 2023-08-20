from dataclasses import dataclass, field
import math

from typing import (
    Self,
)

import panda3d.core as p3d
from direct.showbase.ShowBase import ShowBase
from direct.showbase.DirectObject import DirectObject

from lib.gamestates import GameState
from lib.networking import (
    NetworkManager,
    NetRole,
)
from game.network_messages import (
    PlayerInputMsg,
    PlayerUpdateMsg,
)


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
class PlayerInput:
    events: DirectObject
    cursor: CursorInput
    move_dir: p3d.Vec2 = field(init=False, default_factory=p3d.Vec2)
    aim_pos: p3d.Vec3 = field(init=False, default_factory=p3d.Vec3)

    def __post_init__(self):
        def move(dir_vec):
            self.move_dir += dir_vec
        self.events.accept('move-up', move, [p3d.Vec2(0, 1)])
        self.events.accept('move-up-up', move, [p3d.Vec2(0, -1)])
        self.events.accept('move-down', move, [p3d.Vec2(0, -1)])
        self.events.accept('move-down-up', move, [p3d.Vec2(0, 1)])
        self.events.accept('move-left', move, [p3d.Vec2(-1, 0)])
        self.events.accept('move-left-up', move, [p3d.Vec2(1, 0)])
        self.events.accept('move-right', move, [p3d.Vec2(1, 0)])
        self.events.accept('move-right-up', move, [p3d.Vec2(-1, 0)])

    def update(self) -> None:
        self.aim_pos = self.cursor.get_pos()


@dataclass(kw_only=True)
class PlayerController:
    speed: int
    player_node: p3d.NodePath
    move_dir: p3d.Vec2 = field(init=False, default_factory=p3d.Vec2)
    aim_pos: p3d.Vec3 = field(init=False, default_factory=p3d.Vec3)

    def update(self, dt):
        # Update player position
        prevpos = self.player_node.get_pos()
        movedir = p3d.Vec3(self.move_dir.x, self.move_dir.y, 0).normalized()
        newpos = prevpos + movedir * dt * self.speed
        self.player_node.set_pos(newpos)

        # Face player toward aim location
        self.player_node.heads_up(self.aim_pos, p3d.Vec3(0, 0, 1))

        # Character models are facing -Y, so flip them around now
        self.player_node.set_h(self.player_node.get_h() - 180)


class MainClient(GameState):
    RESOURCES = {
        'level': 'levels/testenv.bam',
        'player': 'skeleton.bam',
    }

    def __init__(self, base: ShowBase, network: NetworkManager):
        super().__init__(base)

        self.network = network
        self.level = None

        # Set confined mouse mode
        self.window = base.win
        self.prev_win_props = self.window.requested_properties
        props = p3d.WindowProperties()
        props.set_mouse_mode(p3d.WindowProperties.M_confined)
        self.window.request_properties(props)

        base.camLens.set_fov(70)


        self.player_node = self.root_node.attach_new_node('Player')
        self.cursor = CursorInput(
            mouse_watcher=base.mouseWatcherNode,
            camera_node=base.cam,
            root_node=self.root_node,
        )
        self.player_input = PlayerInput(
            events=self.events,
            cursor=self.cursor,
        )
        self.cam_contr = CameraController(
            cam_node=base.camera,
            target=self.player_node,
            angle=45,
            distance=25,
        )

    def start(self):
        self.level = Level.create(self.resources['level'])
        self.level.root.reparent_to(self.root_node)

        player_model = self.resources['player']
        player_model.reparent_to(self.player_node)


    def cleanup(self):
        super().cleanup()

        self.window.request_properties(self.prev_win_props)

    def handle_messages(self, messages):
        for msg in messages:
            match msg:
                case PlayerUpdateMsg():
                    self.player_node.set_pos_hpr(
                        *msg.position,
                        *msg.hpr
                    )
                case _:
                    print(f'Unknown message type: {type(msg)}')

    def update(self, dt: float):
        self.cursor.update()
        self.player_input.update()
        self.cam_contr.update(dt)

        player_update = PlayerInputMsg(
            move_dir=(
                self.player_input.move_dir.x,
                self.player_input.move_dir.y
            ),
            aim_pos=(
                self.player_input.aim_pos.x,
                self.player_input.aim_pos.y,
                self.player_input.aim_pos.z
            )
        )
        self.network.send(player_update, NetRole.CLIENT)


class MainServer(GameState):
    RESOURCES = {
        'level': 'levels/testenv.bam',
    }

    def __init__(self, base: ShowBase, network: NetworkManager):
        super().__init__(base)

        self.network = network
        self.level = None

        self.player_node = self.root_node.attach_new_node('Player')
        self.player_contr = PlayerController(
            player_node=self.player_node,
            speed=25,
        )

    def start(self) -> None:
        self.level = Level.create(self.resources['level'])
        self.level.root.reparent_to(self.root_node)

    def handle_messages(self, messages) -> None:
        for msg in messages:
            match msg:
                case PlayerInputMsg():
                    self.player_contr.move_dir = p3d.Vec2(*msg.move_dir)
                    self.player_contr.aim_pos = p3d.Vec3(*msg.aim_pos)
                case _:
                    print(f'Unknown message type: {type(msg)}')

    def update(self, dt: float) -> None:
        self.player_contr.update(dt)

        player_pos = self.player_contr.player_node.get_pos()
        player_hpr = self.player_contr.player_node.get_hpr()
        player_update = PlayerUpdateMsg(
            position=(
                player_pos.x,
                player_pos.y,
                player_pos.z
            ),
            hpr=(
                player_hpr.x,
                player_hpr.y,
                player_hpr.z
            )
        )
        self.network.send(player_update, NetRole.SERVER)
