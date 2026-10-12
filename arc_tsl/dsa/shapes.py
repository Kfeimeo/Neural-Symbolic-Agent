"""Finite colored patches and explicit grid composition (ARC bounds: 1..30).

None is transparent; color 0 is an ordinary opaque pixel. Geometry equality
retains orientation unless a rotation/reflection predicate is requested.
"""
from dataclasses import dataclass

from ..arc.grid import shape as grid_dims
from ..ontology.instance import ExtractionConfig
from ..ontology.geometry import normalize, rotate_local


def dimensions(h, w):
    if type(h) is not int or type(w) is not int or not (1 <= h <= 30 and 1 <= w <= 30):
        raise ValueError("dimensions must be integers in 1..30")
    return h, w


def position(r, c):
    if type(r) is not int or type(c) is not int or r < 0 or c < 0:
        raise ValueError("position must contain nonnegative integers")
    return r, c


def color(c):
    if type(c) is not int or not 0 <= c <= 9:
        raise ValueError("color must be in 0..9")
    return c


@dataclass(frozen=True)
class Shape:
    pixels: tuple[tuple[int | None, ...], ...]

    def __post_init__(self):
        dimensions(len(self.pixels), len(self.pixels[0]) if self.pixels else 0)
        if not isinstance(self.pixels, tuple) or any(not isinstance(row, tuple) for row in self.pixels):
            raise ValueError("shape pixels must be immutable tuples")
        if any(len(row) != len(self.pixels[0]) for row in self.pixels):
            raise ValueError("ragged shape")
        for row in self.pixels:
            for c in row:
                if c is not None:
                    color(c)

    @property
    def dims(self):
        return len(self.pixels), len(self.pixels[0])


def local_shape(obj):
    top, left = obj.position
    rows = [[None] * obj.width for _ in range(obj.height)]
    for r, c, value in obj.pixels:
        rows[r - top][c - left] = value
    return Shape(tuple(tuple(row) for row in rows))


def support(patch):
    return frozenset((r, c) for r, row in enumerate(patch.pixels)
                     for c, value in enumerate(row) if value is not None)


def _normalized(mask):
    return normalize(mask) if mask else frozenset()


def same_geometry(a, b):
    return _normalized(a) == _normalized(b)


def same_geometry_rot(a, b):
    a, b = _normalized(a), _normalized(b)
    return any(a == frozenset(rotate_local(b, k)) for k in range(4)) if b else not a


def same_geometry_dihedral(a, b):
    return same_geometry_rot(a, b) or same_geometry_rot(a, frozenset((r, -c) for r, c in b))


def canvas(dims, fill):
    h, w = dimensions(*dims)
    color(fill)
    return tuple((fill,) * w for _ in range(h))


def paint(patch, at, grid):
    r, c = position(*at)
    h, w = dimensions(*grid_dims(grid))
    rows = [list(row) for row in grid]
    if any(len(row) != w for row in rows):
        raise ValueError("ragged grid")
    for i, row in enumerate(patch.pixels):
        for j, value in enumerate(row):
            if value is not None and r + i < h and c + j < w:
                rows[r + i][c + j] = value
    return tuple(tuple(row) for row in rows)


def objects4(grid, background):
    return _objects(grid, background, 4, True)


def objects8(grid, background):
    return _objects(grid, background, 8, False)


def _objects(grid, background, connectivity, same_color):
    # Reuse extraction while making the background an explicit DSL argument.
    color(background)
    from ..ontology.instance import extract_instances
    from ..ontology.object import ObjectToken, make_object_set
    # Swap background and zero bijectively, then restore colors after extraction.
    def swap(c):
        return background if c == 0 else 0 if c == background else c
    mapped = tuple(tuple(swap(c) for c in row) for row in grid)
    instances, _ = extract_instances(mapped, ExtractionConfig(connectivity, "color0", same_color))
    return make_object_set(ObjectToken(frozenset((r, c, swap(v)) for r, c, v in inst.pixels),
                                      grid_dims(grid), i) for i, inst in enumerate(instances))


def sample_objects(grid):
    """Lambda OE bindings cover both input views and all available backgrounds."""
    return tuple(dict.fromkeys(o for bg in range(10) for view in (objects4, objects8)
                               for o in view(grid, bg)))


def primitives():
    from ..ml.primitives import function
    from ..ml.types import BOOL, INT
    from .types import GRID, POS, DIMS, PATCH, MASK, OBJECT, OBJECTS, COLOR
    specs = [
        ("objects4", (GRID, COLOR), OBJECTS, objects4),
        ("objects8", (GRID, COLOR), OBJECTS, objects8),
        ("pos", (OBJECT,), POS, lambda o: position(*o.position)),
        ("position", (INT, INT), POS, position),
        ("row", (POS,), INT, lambda p: p[0]),
        ("col", (POS,), INT, lambda p: p[1]),
        ("shape", (OBJECT,), PATCH, local_shape),
        ("support", (PATCH,), MASK, support),
        ("dims", (PATCH,), DIMS, lambda s: s.dims),
        ("dimensions", (INT, INT), DIMS, dimensions),
        ("grid_dims", (GRID,), DIMS, grid_dims),
        ("dim_h", (DIMS,), INT, lambda d: d[0]),
        ("dim_w", (DIMS,), INT, lambda d: d[1]),
        ("same_geometry", (MASK, MASK), BOOL, same_geometry),
        ("same_geometry_rot", (MASK, MASK), BOOL, same_geometry_rot),
        ("same_geometry_dihedral", (MASK, MASK), BOOL, same_geometry_dihedral),
        ("canvas", (DIMS, COLOR), GRID, canvas),
        ("paint", (PATCH, POS, GRID), GRID, paint),
    ]
    return [function(name, args, result, impl, "dsa") for name, args, result, impl in specs]
