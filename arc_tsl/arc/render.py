"""ObjectSet -> Grid.  Objects are painted in the ObjectSet's (canonical)
order; later objects overwrite earlier ones; pixels outside the grid are
clipped."""
from __future__ import annotations

from ..ontology.object import ObjectSet
from .grid import Grid


def render(objects: ObjectSet, grid_shape: tuple[int, int], background: int) -> Grid:
    H, W = grid_shape
    rows = [[background] * W for _ in range(H)]
    for o in objects:
        for r, c, col in sorted(o.pixels):
            if 0 <= r < H and 0 <= c < W:
                rows[r][c] = col
    return tuple(tuple(r) for r in rows)
