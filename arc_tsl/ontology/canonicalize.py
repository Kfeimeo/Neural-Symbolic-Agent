"""ObjectClass = Instance / (translation + C4 rotation).

shape_id(S) is the lexicographically minimal sorted coordinate tuple over the
four quarter-turn rotations of the normalized support.  Reflection is *not*
quotiented out, so chirality is preserved.
"""
from __future__ import annotations

from functools import lru_cache

from .geometry import Support, normalize, rotate_local

ShapeId = tuple[tuple[int, int], ...]


@lru_cache(maxsize=200_000)
def canonical_forms(support: Support) -> tuple[ShapeId, ...]:
    s = normalize(support)
    forms = []
    for k in range(4):
        forms.append(tuple(sorted(rotate_local(s, k))))
    return tuple(forms)


@lru_cache(maxsize=200_000)
def shape_id(support: Support) -> ShapeId:
    return min(canonical_forms(support))


@lru_cache(maxsize=200_000)
def orientation(support: Support) -> int:
    """Smallest k in {0,1,2,3} such that rotate_local(canonical, k) == normalize(support).
    For symmetric shapes several k match; the smallest is returned."""
    canonical = frozenset(shape_id(support))
    target = tuple(sorted(normalize(support)))
    for k in range(4):
        if tuple(sorted(rotate_local(canonical, k))) == target:
            return k
    raise AssertionError("unreachable: some rotation must match")
