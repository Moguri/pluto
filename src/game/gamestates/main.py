from dataclasses import (
    dataclass,
    field,
    InitVar,
)
import math
import random
from typing import (
    cast,
    Self,
)

import panda3d.core as p3d
from direct.showbase.ShowBase import ShowBase
from direct.showbase.DirectObject import DirectObject
from direct.actor.Actor import Actor
from direct.interval.IntervalGlobal import (
    FunctionInterval,
    Sequence,
)
from direct.interval.LerpInterval import LerpPosInterval

from lib.gamestates import GameState
from lib.networking import (
    NetworkManager,
    NetworkMessage,
    NetRole,
)
from game.network_messages import (
    PlayerInputMsg,
    PlayerUpdateMsg,
    RegisterPlayerIdMsg,
    RemovePlayerMsg,
    SpawnProjectileMsg,
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

    def __post_init__(self) -> None:
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
    actions: set[str] = field(init=False, default_factory=set)

    def __post_init__(self) -> None:
        def move(dir_vec: p3d.Vec2) -> None:
            self.move_dir += dir_vec
        def add_action(action: str) -> None:
            self.actions.add(action)
        self.events.accept('move-up', move, [p3d.Vec2(0, 1)])
        self.events.accept('move-up-up', move, [p3d.Vec2(0, -1)])
        self.events.accept('move-down', move, [p3d.Vec2(0, -1)])
        self.events.accept('move-down-up', move, [p3d.Vec2(0, 1)])
        self.events.accept('move-left', move, [p3d.Vec2(-1, 0)])
        self.events.accept('move-left-up', move, [p3d.Vec2(1, 0)])
        self.events.accept('move-right', move, [p3d.Vec2(1, 0)])
        self.events.accept('move-right-up', move, [p3d.Vec2(-1, 0)])
        self.events.accept('fire', add_action, ['fire'])

    def update(self) -> None:
        self.aim_pos = self.cursor.get_pos()


@dataclass(kw_only=True)
class PlayerController:
    speed: int = 20
    player_node: p3d.NodePath
    move_dir: p3d.Vec2 = field(init=False, default_factory=p3d.Vec2)
    aim_pos: p3d.Vec3 = field(init=False, default_factory=p3d.Vec3)

    def update(self, dt: float) -> None:
        # Update player position
        prevpos = self.player_node.get_pos()
        movedir = p3d.Vec3(self.move_dir.x, self.move_dir.y, 0).normalized()
        newpos = prevpos + movedir * dt * self.speed
        self.player_node.set_pos(newpos)

        # Face player toward aim location
        self.player_node.heads_up(self.aim_pos, p3d.Vec3(0, 0, 1))

        # Character models are facing -Y, so flip them around now
        self.player_node.set_h(self.player_node.get_h() - 180)


@dataclass(kw_only=True)
class AnimController:
    ANIM_MAP = {
        'idle': 'Idle',
        'move': 'Run',
    }
    player_node: p3d.NodePath
    actor: Actor
    prev_pos: p3d.Vec3 = field(init=False)

    def __post_init__(self) -> None:
        self.prev_pos = self.player_node.get_pos()

    def update(self) -> None:
        distmoved = self.player_node.get_pos() - self.prev_pos
        if distmoved.length_squared() > 0.01:
            self.start_loop('move')
        else:
            self.start_loop('idle')

        self.prev_pos = self.player_node.get_pos()

    def start_loop(self, anim: str) -> None:
        anim = self.ANIM_MAP[anim]
        if self.actor.get_current_anim() != anim:
            self.actor.loop(anim)


@dataclass(kw_only=True)
class Projectile:
    distance: int = 75
    model: InitVar[p3d.NodePath]
    render_node: InitVar[p3d.NodePath]
    player_node: InitVar[p3d.NodePath]
    root: p3d.NodePath = field(init=False)
    is_done: bool = field(init=False)

    def __post_init__(
        self,
        model: p3d.NodePath,
        render_node: p3d.NodePath,
        player_node: p3d.NodePath
    ) -> None:
        self.root = render_node.attach_new_node('Projectile')
        model.instance_to(self.root)
        self.root.hide(p3d.BitMask32.bit(1))

        self.root.set_pos_hpr(
            player_node.get_pos(),
            player_node.get_hpr()
        )

        def end():
            self.root.remove_node()
            self.is_done = True

        Sequence(
            LerpPosInterval(
                nodePath=self.root,
                duration=1.0,
                pos=render_node.get_relative_point(player_node, (0, -self.distance, 0))
            ),
            FunctionInterval(
                function=end
            )
        ).start()


@dataclass(kw_only=True)
class AiController:
    playerid: int
    _accum: float = field(init=False, default=0)
    move_dir: p3d.Vec2 = field(init=False, default_factory=p3d.Vec2)
    aim_pos: p3d.Vec3 = field(init=False, default_factory=p3d.Vec3)
    actions: set[str] = field(init=False, default_factory=set)

    def update(self, dt: float) -> None:
        self._accum += dt
        if self._accum > 0.25:
            if random.random() > 0.5:
                self.move_dir = p3d.Vec2(
                    random.random() * 2.0 - 1.0,
                    random.random() * 2.0 - 1.0
                ).normalized()
            else:
                self.move_dir = p3d.Vec2.zero()
            self.aim_pos = p3d.Vec3(
                random.random() * 2.0 - 1.0,
                random.random() * 2.0 - 1.0,
                random.random() * 2.0 - 1.0
            ).normalized()
            self._accum = 0.0


class MainClient(GameState):
    RESOURCES = {
        'level': 'levels/testenv.bam',
        'player': 'characters/skeleton.bam',
        'animations': 'animations/animations.bam',
    }

    def __init__(self, base: ShowBase, network: NetworkManager):
        super().__init__(base)

        self.network = network
        self.level: Level = cast(Level, None)
        self.player_model: p3d.NodePath = cast(p3d.NodePath, None)

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

        self.projectiles: list[Projectile] = []

        # Ambient lighting
        self.ambient_light = self.root_node.attach_new_node(p3d.AmbientLight('Ambient'))
        ambstr = 0.2
        self.ambient_light.node().set_color((ambstr, ambstr, ambstr, 1.0))
        self.root_node.set_light(self.ambient_light)


        self.camera_target = self.root_node.attach_new_node('Camera Target')
        self.playerid: int | None = None
        self.player_nodes: dict[int, p3d.NodePath] = {}
        self.anim_contrs: dict[int, AnimController] = {}
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

    def start(self) -> None:
        self.level = Level.create(self.resources['level'])
        self.level.root.reparent_to(self.root_node)
        for light in self.level.root.find_all_matches('**/+Light'):
            light.parent.wrt_reparent_to(self.root_node)
            self.root_node.set_light(light)

        anims = self.resources['animations']
        animbundle = p3d.NodePath('Player Animations')
        for bundle in anims.find_all_matches('**/+AnimBundleNode'):
            bundle.reparent_to(animbundle)

        player = self.resources['player']
        char = player.find('**/+Character')
        animbundle.instance_to(char)

        self.player_model = player


    def cleanup(self) -> None:
        super().cleanup()

        self.window.request_properties(self.prev_win_props)

    def add_new_player(self, playerid: int) -> None:
        player_node = self.root_node.attach_new_node(f'Player {playerid}')
        if self.player_model:
            actor = Actor(self.player_model)
            actor.reparent_to(player_node)
            anim_contr = AnimController(
                player_node=player_node,
                actor=actor,
            )
            self.anim_contrs[playerid] = anim_contr

        self.player_nodes[playerid] = player_node
        if playerid == self.playerid:
            self.target_line.reparent_to(player_node)

    def remove_player(self, playerid: int) -> None:
        self.player_nodes[playerid].remove_node()
        del self.player_nodes[playerid]
        del self.anim_contrs[playerid]

    def handle_messages(self, messages: list[NetworkMessage]) -> None:
        for msg in messages:
            match msg:
                case RegisterPlayerIdMsg():
                    self.playerid = msg.playerid
                case RemovePlayerMsg():
                    self.remove_player(msg.playerid)
                case PlayerUpdateMsg():
                    playerid = msg.playerid
                    if playerid not in self.player_nodes:
                        self.add_new_player(playerid)
                    self.player_nodes[playerid].set_pos_hpr(
                        msg.position,
                        msg.hpr
                    )
                case SpawnProjectileMsg():
                    playerid = msg.playerid
                    proj = Projectile(
                        model=self.resources['player'],
                        player_node=self.player_nodes[playerid],
                        render_node=self.root_node,
                    )
                    self.projectiles.append(proj)
                case _:
                    print(f'Unknown message type: {type(msg)}')

    def update(self, dt: float) -> None:
        if self.playerid is not None and self.playerid in self.player_nodes:
            self.camera_target.set_pos(self.player_nodes[self.playerid].get_pos())
        self.cursor.update()
        self.player_input.update()
        self.cam_contr.update(dt)
        for anim_contr in self.anim_contrs.values():
            anim_contr.update()

        player_update = PlayerInputMsg(
            move_dir=self.player_input.move_dir,
            aim_pos=self.player_input.aim_pos,
            actions=self.player_input.actions,
        )
        self.network.send(player_update, NetRole.CLIENT)
        self.player_input.actions.clear()


class MainServer(GameState):
    RESOURCES = {
        'level': 'levels/testenv.bam',
    }
    NUM_BOTS = 1
    BOT_ID_START = 1000

    def __init__(self, base: ShowBase, network: NetworkManager) -> None:
        super().__init__(base)

        self.network = network
        self.level: Level = cast(Level, None)

        self.player_contrs: dict[int, PlayerController] = {}
        self.player_nodes: dict[int, p3d.NodePath] = {}
        self.ai_contrs: dict[int, AiController] = {}
        self.projectiles: list[Projectile] = []

    def start(self) -> None:
        self.level = Level.create(self.resources['level'])
        self.level.root.reparent_to(self.root_node)

        for idx in range(self.NUM_BOTS):
            botid = self.BOT_ID_START + idx
            self.add_new_player(botid)
            self.ai_contrs[botid] = AiController(
                playerid=botid
            )

    def add_new_player(self, connid: int) -> None:
        playerid = connid

        self.player_nodes[playerid] = self.root_node.attach_new_node(f'Player {playerid}')
        self.player_contrs[playerid] = PlayerController(
            player_node=self.player_nodes[playerid]
        )

        if connid < self.BOT_ID_START:
            register_player = RegisterPlayerIdMsg(playerid=playerid)
            register_player.connection_id = connid
            self.network.send(register_player, NetRole.SERVER)

    def remove_player(self, connid: int) -> None:
        playerid = connid

        self.player_nodes[playerid].remove_node()
        del self.player_nodes[playerid]
        del self.player_contrs[playerid]
        self.network.send(RemovePlayerMsg(playerid=playerid), NetRole.CLIENT)

    def handle_messages(self, messages: list[NetworkMessage]) -> None:
        for msg in messages:
            match msg:
                case PlayerInputMsg():
                    playerid = msg.connection_id
                    if playerid not in self.player_contrs:
                        self.add_new_player(playerid)
                    player_contr = self.player_contrs[playerid]
                    player_contr.move_dir = msg.move_dir
                    player_contr.aim_pos = msg.aim_pos

                    if 'fire' in msg.actions:
                        self.network.send(SpawnProjectileMsg(playerid), NetRole.SERVER)
                case _:
                    print(f'Unknown message type: {type(msg)}')

    def handle_disconnect(self, conn_id: int)-> None:
        self.remove_player(conn_id)

    def update(self, dt: float) -> None:
        for playerid, ai_contr in self.ai_contrs.items():
            ai_contr.update(dt)
            player_contr = self.player_contrs[playerid]
            player_contr.move_dir = ai_contr.move_dir
            player_contr.aim_pos = ai_contr.aim_pos

        for playerid, player_contr in self.player_contrs.items():
            player_contr.update(dt)

            player_update = PlayerUpdateMsg(
                playerid=playerid,
                position=player_contr.player_node.get_pos(),
                hpr=player_contr.player_node.get_hpr()
            )
            self.network.send(player_update, NetRole.SERVER)
