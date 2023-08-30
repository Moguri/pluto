from dataclasses import (
    dataclass,
    field,
)
import random

import panda3d.core as p3d


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
