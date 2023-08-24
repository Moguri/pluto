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
    RegisterPlayerIdMsg,
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

        for caster in model.find_all_matches('**/=type=shadow_caster/+Light'):
            caster.node().set_shadow_caster(True, 1024, 1024)
            caster.node().set_camera_mask(p3d.BitMask32.bit(1))
            level.recalc_light_bounds(caster)

        return level

    def recalc_light_bounds(self, lightnp: p3d.NodePath):
        bounds = self.root.get_tight_bounds(lightnp)
        light_lens = lightnp.node().get_lens()
        if bounds:
            bmin, bmax = bounds
            light_lens.set_film_offset((bmin.xz + bmax.xz) * 0.5)
            light_lens.set_film_size(bmax.xz - bmin.xz)
            light_lens.set_near_far(bmin.y, bmax.y)
        else:
            print('Warning: Unable to calculate scene bounds for optimized shadows')
            light_lens.set_film_size(100, 100)


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
    speed: int = 25
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

        self.root_node.show(p3d.BitMask32.bit(1))

        # Set confined mouse mode
        self.window = base.win
        self.prev_win_props = self.window.requested_properties
        props = p3d.WindowProperties()
        props.set_mouse_mode(p3d.WindowProperties.M_confined)
        self.window.request_properties(props)

        base.camLens.set_fov(70)

        # Build a targeting line visual for player
        line_segs = p3d.LineSegs()
        line_segs.set_color(1, 0, 0, 0.5)
        line_segs.set_thickness(2.5)
        line_segs.move_to(0, 0, 0.5)
        line_segs.draw_to(0, -100, 0.5)
        self.target_line = p3d.NodePath(line_segs.create())
        mat = p3d.Material('Target Line')
        mat.set_base_color(p3d.LColor(1, 0, 0, 1))
        self.target_line.set_transparency(p3d.TransparencyAttrib.M_alpha)
        self.target_line.set_light_off(1)
        self.target_line.set_material(mat)
        self.target_line.hide(p3d.BitMask32.bit(1))

        # Ambient lighting
        self.ambient_light = self.root_node.attach_new_node(p3d.AmbientLight('Ambient'))
        ambstr = 0.2
        self.ambient_light.node().set_color((ambstr, ambstr, ambstr, 1.0))
        self.root_node.set_light(self.ambient_light)


        self.camera_target = self.root_node.attach_new_node('Camera Target')
        self.playerid = None
        self.player_nodes: dict[int, p3d.NodePath] = {}
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
            target=self.camera_target,
            angle=45,
            distance=25,
        )

    def start(self):
        self.level = Level.create(self.resources['level'])
        self.level.root.reparent_to(self.root_node)
        for light in self.level.root.find_all_matches('**/+Light'):
            light.parent.wrt_reparent_to(self.root_node)
            self.root_node.set_light(light)

    def cleanup(self):
        super().cleanup()

        self.window.request_properties(self.prev_win_props)

    def add_new_player(self, playerid):
        player_node = self.root_node.attach_new_node(f'Player {playerid}')
        self.resources['player'].instance_to(player_node)

        self.player_nodes[playerid] = player_node
        if playerid == self.playerid:
            self.target_line.reparent_to(player_node)

    def handle_messages(self, messages):
        for msg in messages:
            match msg:
                case RegisterPlayerIdMsg():
                    self.playerid = msg.playerid
                case PlayerUpdateMsg():
                    playerid = msg.playerid
                    if playerid not in self.player_nodes:
                        self.add_new_player(playerid)
                    self.player_nodes[playerid].set_pos_hpr(
                        msg.position,
                        msg.hpr
                    )
                case _:
                    print(f'Unknown message type: {type(msg)}')

    def update(self, dt: float):
        if self.playerid is not None and self.playerid in self.player_nodes:
            self.camera_target.set_pos(self.player_nodes[self.playerid].get_pos())
        self.cursor.update()
        self.player_input.update()
        self.cam_contr.update(dt)

        player_update = PlayerInputMsg(
            move_dir=self.player_input.move_dir,
            aim_pos=self.player_input.aim_pos
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

        self.player_contrs: dict[int, PlayerController] = {}
        self.player_nodes: dict[int, p3d.NodePath] = {}

    def start(self) -> None:
        self.level = Level.create(self.resources['level'])
        self.level.root.reparent_to(self.root_node)


    def add_new_player(self, connid):
        playerid = connid

        self.player_nodes[playerid] = self.root_node.attach_new_node(f'Player {playerid}')
        self.player_contrs[playerid] = PlayerController(
            player_node=self.player_nodes[playerid]
        )

        register_player = RegisterPlayerIdMsg(playerid=playerid)
        register_player.connection_id = connid
        self.network.send(register_player, NetRole.SERVER)

    def handle_messages(self, messages) -> None:
        for msg in messages:
            match msg:
                case PlayerInputMsg():
                    playerid = msg.connection_id
                    if playerid not in self.player_contrs:
                        self.add_new_player(playerid)
                    player_contr = self.player_contrs[playerid]
                    player_contr.move_dir = msg.move_dir
                    player_contr.aim_pos = msg.aim_pos
                case _:
                    print(f'Unknown message type: {type(msg)}')

    def update(self, dt: float) -> None:
        for playerid, player_contr in self.player_contrs.items():
            player_contr.update(dt)

            player_update = PlayerUpdateMsg(
                playerid=playerid,
                position=player_contr.player_node.get_pos(),
                hpr=player_contr.player_node.get_hpr()
            )
            self.network.send(player_update, NetRole.SERVER)
