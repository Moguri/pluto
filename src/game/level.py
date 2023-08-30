from dataclasses import (
    dataclass,
)
from typing import (
    Self,
)

import panda3d.core as p3d

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

        # Force to ground plane until there is gravity
        for starts in player_starts:
            starts.z = 0

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
