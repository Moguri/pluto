from dataclasses import (
    dataclass,
    field,
    InitVar,
)

import panda3d.core as p3d

from direct.actor.Actor import Actor
from direct.interval.IntervalGlobal import (
    FunctionInterval,
    Sequence,
)
from direct.interval.LerpInterval import LerpPosInterval


@dataclass(kw_only=True)
class Projectile:
    distance: int = 75
    damage: int = 1
    for_player: int
    model: InitVar[p3d.NodePath | None] = None
    render_node: InitVar[p3d.NodePath]
    player_node: InitVar[p3d.NodePath]
    root: p3d.NodePath = field(init=False)
    is_done: bool = field(init=False, default=False)

    def __post_init__(
        self,
        model: p3d.NodePath,
        render_node: p3d.NodePath,
        player_node: p3d.NodePath
    ) -> None:
        self.root = render_node.attach_new_node('Projectile')
        collider = p3d.CollisionNode('Collider')
        collider.add_solid(p3d.CollisionSphere(0, 0, 0.5, 0.75))
        collider.set_into_collide_mask(0)
        self.root.attach_new_node(collider)
        self.root.set_python_tag('projectile', self)
        if model:
            model.instance_to(self.root)
        self.root.hide(p3d.BitMask32.bit(1))

        self.root.set_pos_hpr(
            player_node.get_pos(),
            player_node.get_hpr()
        )

        Sequence(
            LerpPosInterval(
                nodePath=self.root,
                duration=1.0,
                pos=render_node.get_relative_point(player_node, (0, -self.distance, 0))
            ),
            FunctionInterval(
                function=self.destroy
            )
        ).start()

    def destroy(self) -> None:
        if self.is_done:
            return
        self.root.clear_python_tag('projectile')
        self.root.remove_node()
        self.is_done = True


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
class PlayerController:
    speed: int = 20
    max_health: int = 1

    playerid: int
    render_node: InitVar[p3d.NodePath]
    character_mesh: InitVar[p3d.NodePath | None] = None
    player_node: p3d.NodePath = field(init=False)
    anim_contr: AnimController | None = field(init=False)
    alive: bool = field(init=False, default=False)
    move_dir: p3d.Vec2 = field(init=False, default_factory=p3d.Vec2)
    aim_pos: p3d.Vec3 = field(init=False, default_factory=p3d.Vec3)
    health: int = field(init=False)

    def __post_init__(self, render_node, character_mesh=None) -> None:
        self.player_node = render_node.attach_new_node(f'Player {self.playerid}')
        self.anim_contr = None
        if character_mesh is not None:
            actor = Actor(character_mesh)
            actor.reparent_to(self.player_node)
            self.anim_contr = AnimController(
                player_node=self.player_node,
                actor=actor,
            )
        collider = p3d.CollisionNode('Collider')
        collider.add_solid(p3d.CollisionSphere(0, 0, 0.5, 0.5))
        self.player_node.attach_new_node(collider)
        self.player_node.set_python_tag('contr', self)
        self.player_node.hide()
        self.health = self.max_health

    def destroy(self):
        self.player_node.clear_python_tag('contr')
        self.player_node.remove_node()

    def spawn(self, spawn_pos: p3d.Vec3) -> None:
        self.player_node.set_pos(spawn_pos)
        self.player_node.show()
        self.health = self.max_health
        self.alive = True

    def kill(self) -> None:
        self.player_node.hide()
        self.alive = False

    def update_move_aim(self, move_dir: p3d.Vec2, aim_pos: p3d.Vec3):
        if not self.alive:
            return

        self.move_dir = move_dir
        self.aim_pos = aim_pos

    def set_pos_hpr(self, pos: p3d.Vec3, hpr: p3d.Vec3):
        return self.player_node.set_pos_hpr(pos, hpr)

    def update_server(self, dt: float) -> None:
        # Check player health
        if self.health <= 0 and self.alive:
            self.kill()

        if not self.alive:
            return

        # Update player position
        prevpos = self.player_node.get_pos()
        movedir = p3d.Vec3(self.move_dir.x, self.move_dir.y, 0).normalized()
        newpos = prevpos + movedir * dt * self.speed
        self.player_node.set_pos(newpos)

        # Face player toward aim location
        self.player_node.heads_up(self.aim_pos, p3d.Vec3(0, 0, 1))

        # Character models are facing -Y, so flip them around now
        self.player_node.set_h(self.player_node.get_h() - 180)

    def update_client(self, _dt: float) -> None:
        if self.anim_contr:
            self.anim_contr.update()
