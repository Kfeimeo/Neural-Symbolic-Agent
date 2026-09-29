"""RegionExpr -> PixelSet, evaluated relative to an object (object-local).

Regions are nominal symbols; ``evaluate_region`` turns them into global pixel
coordinates for a given token.  ``row_span``/``column_span`` use the token's
grid shape (tokens live in a grid), everything else is purely local.
"""
from __future__ import annotations

from ..ontology.geometry import Pixel, neighbors4, neighbors8
from ..ontology.object import ObjectToken

REGION_NAMES = ("support", "bbox", "bbox_minus_support", "boundary", "neighbors4",
                "neighbors8", "row_span", "column_span", "minimal_square_hull")


def evaluate_region(name: str, o: ObjectToken) -> frozenset[Pixel]:
    s = o.global_support
    top, left, bottom, right = o.bbox
    if name == "support":
        return s
    if name == "bbox":
        return frozenset((r, c) for r in range(top, bottom + 1) for c in range(left, right + 1))
    if name == "bbox_minus_support":
        return evaluate_region("bbox", o) - s
    if name == "boundary":
        return frozenset(p for p in s if any(n not in s for n in neighbors4(p)))
    if name == "neighbors4":
        return frozenset(n for p in s for n in neighbors4(p) if n not in s)
    if name == "neighbors8":
        return frozenset(n for p in s for n in neighbors8(p) if n not in s)
    if name == "row_span":
        H, W = o.grid_shape
        rows = {r for r, _ in s}
        return frozenset((r, c) for r in rows for c in range(W))
    if name == "column_span":
        H, W = o.grid_shape
        cols = {c for _, c in s}
        return frozenset((r, c) for c in cols for r in range(H))
    if name == "minimal_square_hull":
        side = max(bottom - top + 1, right - left + 1)
        return frozenset((r, c) for r in range(top, top + side) for c in range(left, left + side))
    raise ValueError(f"Unknown region {name!r}")
