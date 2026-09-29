"""Fixed binary relations between object tokens.  Semantics are not
task-modifiable."""
from __future__ import annotations

from fractions import Fraction

from ..ontology.geometry import neighbors4, neighbors8
from ..ontology.object import ObjectToken


def same_shape(a: ObjectToken, b: ObjectToken) -> bool:
    return a.shape_id == b.shape_id


def same_color(a: ObjectToken, b: ObjectToken) -> bool:
    return a.dominant_color == b.dominant_color


def left_of(a: ObjectToken, b: ObjectToken) -> bool:
    return a.bbox[3] < b.bbox[1]


def right_of(a: ObjectToken, b: ObjectToken) -> bool:
    return a.bbox[1] > b.bbox[3]


def above(a: ObjectToken, b: ObjectToken) -> bool:
    return a.bbox[2] < b.bbox[0]


def below(a: ObjectToken, b: ObjectToken) -> bool:
    return a.bbox[0] > b.bbox[2]


def _touch(a: ObjectToken, b: ObjectToken, nbrs) -> bool:
    sa, sb = a.global_support, b.global_support
    if sa & sb:
        return False
    return any(n in sb for p in sa for n in nbrs(p))


def touch4(a: ObjectToken, b: ObjectToken) -> bool:
    return _touch(a, b, neighbors4)


def touch8(a: ObjectToken, b: ObjectToken) -> bool:
    return _touch(a, b, neighbors8)


def distance(a: ObjectToken, b: ObjectToken) -> int:
    """Minimum Manhattan distance between any pixel of a and any pixel of b."""
    return min(abs(r1 - r2) + abs(c1 - c2) for r1, c1 in a.global_support for r2, c2 in b.global_support)


def center_delta(a: ObjectToken, b: ObjectToken) -> tuple[Fraction, Fraction]:
    (ar, ac), (br, bc) = a.center, b.center
    return (br - ar, bc - ac)
