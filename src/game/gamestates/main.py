from dataclasses import (
    dataclass,
    field,
)
import math
import random
from typing import (
    cast,
)

import panda3d.core as p3d
from direct.showbase.ShowBase import ShowBase
from direct.showbase.DirectObject import DirectObject
from direct.actor.Actor import Actor

from lib.gamestates import GameState
from lib.networking import (
    NetworkManager,
    NetworkMessage,
    NetRole,
)

from game.ai import (
    AiController,
)
from game import config
from game.level import (
    Level,
)
from game.network_messages import (
    PlayerInputMsg,
    PlayerUpdateMsg,
    PlayerActionMsg,
    PlayerAction,
)
from game.player import (
    AnimController,
    PlayerController,
    Projectile,
)


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


class MainClient(GameState):
    RESOURCES = {
        'player': 'characters/skeleton.bam',
        'animations': 'animations/animations.bam',
    }

    def __init__(self, base: ShowBase, network: NetworkManager):
        super().__init__(base)

        self.network = network
        self.level: Level = cast(Level, None)
        self.player_model: p3d.NodePath = cast(p3d.NodePath, None)
        self.RESOURCES['level'] = f'levels/{config.level_name.value}.bam'

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
        self.traverser = p3d.CollisionTraverser('Traverser')
        self.projectile_collisions = p3d.CollisionHandlerQueue()

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
                case PlayerActionMsg():
                    if msg.action == PlayerAction.REGISTER:
                        self.playerid = msg.playerid
                    elif msg.action == PlayerAction.REMOVE:
                        self.remove_player(msg.playerid)
                    elif msg.action == PlayerAction.FIRE:
                        playerid = msg.playerid
                        projectile = Projectile(
                            model=self.resources['player'],
                            for_player=playerid,
                            player_node=self.player_nodes[playerid],
                            render_node=self.root_node,
                        )
                        collpath = projectile.root.find('**/+CollisionNode')
                        self.traverser.add_collider(collpath, self.projectile_collisions)
                    else:
                        print(f'Unknown player action: {msg.action}')
                case PlayerUpdateMsg():
                    playerid = msg.playerid
                    if playerid not in self.player_nodes:
                        self.add_new_player(playerid)
                    self.player_nodes[playerid].set_pos_hpr(
                        msg.position,
                        msg.hpr
                    )
                    if msg.alive:
                        self.player_nodes[playerid].show()
                    else:
                        self.player_nodes[playerid].hide()

                    player_info = self.player_infos[playerid]
                    player_info.name = msg.name
                    player_info.kills = msg.kills
                    player_info.deaths = msg.deaths
                case _:
                    print(f'Unknown message type: {type(msg)}')

    def update(self, dt: float) -> None:
        self.traverser.traverse(self.root_node)
        if self.playerid is not None and self.playerid in self.player_nodes:
            self.camera_target.set_pos(self.player_nodes[self.playerid].get_pos())
        self.cursor.update()
        self.player_input.update()
        self.cam_contr.update(dt)
        for anim_contr in self.anim_contrs.values():
            anim_contr.update()

        for collision in self.projectile_collisions.entries:
            projectile = collision.get_from_node_path().get_parent().get_python_tag('projectile')

            if projectile:
                projectile.destroy()

        player_update = PlayerInputMsg(
            move_dir=self.player_input.move_dir,
            aim_pos=self.player_input.aim_pos,
            actions=self.player_input.actions,
        )
        self.network.send(player_update, NetRole.CLIENT)
        self.player_input.actions.clear()


class MainServer(GameState):
    RESOURCES = {
    }
    NUM_BOTS = 1
    BOT_ID_START = 1000

    def __init__(self, base: ShowBase, network: NetworkManager) -> None:
        super().__init__(base)

        self.network = network
        self.level: Level = cast(Level, None)
        self.RESOURCES['level'] = f'levels/{config.level_name.value}.bam'

        self.traverser = p3d.CollisionTraverser('Traverser')
        self.projectile_collisions = p3d.CollisionHandlerQueue()
        self.player_pusher = p3d.CollisionHandlerPusher()
        self.player_pusher.horizontal = True
        self.player_contrs: dict[int, PlayerController] = {}
        self.ai_contrs: dict[int, AiController] = {}

    def start(self) -> None:
        self.level = Level.create(self.resources['level'])
        self.level.root.reparent_to(self.root_node)

        for idx in range(config.num_bots.value):
            botid = self.BOT_ID_START + idx
            self.add_new_player(botid)
            self.ai_contrs[botid] = AiController(
                playerid=botid
            )

    def add_new_player(self, connid: int) -> None:
        playerid = connid

        self.player_contrs[playerid] = PlayerController(
            playerid=playerid,
            render_node=self.root_node,
        )

        player_node = self.player_contrs[playerid].player_node
        collpath = player_node.find('**/+CollisionNode')
        self.player_pusher.add_collider(collpath, player_node)
        self.traverser.add_collider(collpath, self.player_pusher)

        if connid < self.BOT_ID_START:
            register_player = PlayerActionMsg(
                playerid=playerid,
                action=PlayerAction.REGISTER
            )
            register_player.connection_id = connid
            self.network.send(register_player, NetRole.SERVER)

    def spawn_projectile(self, playerid: int) -> None:
        projectile = Projectile(
            for_player=playerid,
            player_node=self.player_contrs[playerid].player_node,
            render_node=self.root_node,
        )
        collpath = projectile.root.find('**/+CollisionNode')
        self.traverser.add_collider(collpath, self.projectile_collisions)
        self.network.send(
            PlayerActionMsg(playerid=playerid, action=PlayerAction.FIRE),
            NetRole.SERVER
        )

    def remove_player(self, connid: int) -> None:
        playerid = connid

        self.player_contrs[playerid].destroy()
        del self.player_contrs[playerid]
        msg = PlayerActionMsg(
            playerid=playerid,
            action=PlayerAction.REMOVE
        )
        self.network.send(msg, NetRole.CLIENT)

    def handle_messages(self, messages: list[NetworkMessage]) -> None:
        for msg in messages:
            match msg:
                case PlayerInputMsg():
                    playerid = msg.connection_id
                    if playerid not in self.player_contrs:
                        self.add_new_player(playerid)
                    player_contr = self.player_contrs[playerid]
                    player_contr.update_move_aim(msg.move_dir, msg.aim_pos)

                    if player_contr.alive:
                        if 'fire' in msg.actions:
                            self.spawn_projectile(playerid)
                case _:
                    print(f'Unknown message type: {type(msg)}')

    def handle_disconnect(self, conn_id: int)-> None:
        self.remove_player(conn_id)

    def update(self, dt: float) -> None:
        self.traverser.traverse(self.root_node)

        for collision in self.projectile_collisions.entries:
            projectile = collision.get_from_node_path().get_parent().get_python_tag('projectile')
            player_contr = collision.get_into_node_path().get_parent().get_python_tag('contr')

            if projectile is None:
                continue

            if player_contr:
                if player_contr.playerid == projectile.for_player:
                    continue

                player_contr.health -= projectile.damage
            projectile.destroy()

        for playerid, ai_contr in self.ai_contrs.items():
            ai_contr.update(dt)
            player_contr = self.player_contrs[playerid]
            player_contr.move_dir = ai_contr.move_dir
            player_contr.aim_pos = ai_contr.aim_pos

        for playerid, player_contr in self.player_contrs.items():
            if not player_contr.alive:
                self.player_contrs[playerid].spawn(
                    random.choice(self.level.player_starts)
                )
            player_contr.update(dt)

            player_update = PlayerUpdateMsg(
                playerid=playerid,
                position=player_contr.player_node.get_pos(),
                hpr=player_contr.player_node.get_hpr(),
                alive=not player_contr.player_node.is_hidden()
            )
            self.network.send(player_update, NetRole.SERVER)
