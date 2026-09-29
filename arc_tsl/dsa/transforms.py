"""Object-centric transformation primitives: Object x Param -> Object.

Every transform has deterministic symbolic semantics and never touches
absolute grid coordinates directly: geometry is applied in the object's local
frame and the bbox top-left anchor is preserved (rotate/reflect), or the
object is displaced by a relative Vec2 (translate).
"""
from __future__ import annotations

from fractions import Fraction

from ..ml.primitives import EvalError
from ..ontology.geometry import Pixel
from ..ontology.object import ObjectToken
from .region_expr import evaluate_region

Vec2 = tuple[Fraction, Fraction]


def _int_vec(v: Vec2) -> tuple[int, int]:
    dr, dc = v
    if dr.denominator != 1 or dc.denominator != 1:
        raise EvalError("translate requires an integer vector")
    return int(dr), int(dc)


def translate(o: ObjectToken, v: Vec2) -> ObjectToken:
    dr, dc = _int_vec(v)
    if dr == 0 and dc == 0:
        return o
    return o.with_pixels(frozenset((r + dr, c + dc, col) for r, c, col in o.pixels))


def _local(o: ObjectToken):
    top, left, _, _ = o.bbox
    return top, left, [(r - top, c - left, col) for r, c, col in o.pixels]


def rotate(o: ObjectToken, quarter_turns: int) -> ObjectToken:
    k = quarter_turns % 4
    if k == 0:
        return o
    top, left, px = _local(o)
    for _ in range(k):
        h = max(r for r, _, _ in px) + 1
        px = [(c, h - 1 - r, col) for r, c, col in px]
        mr, mc = min(r for r, _, _ in px), min(c for _, c, _ in px)
        px = [(r - mr, c - mc, col) for r, c, col in px]
    return o.with_pixels(frozenset((r + top, c + left, col) for r, c, col in px))


def reflect(o: ObjectToken, axis: str) -> ObjectToken:
    top, left, px = _local(o)
    h = max(r for r, _, _ in px) + 1
    w = max(c for _, c, _ in px) + 1
    if axis == "h":
        px = [(h - 1 - r, c, col) for r, c, col in px]
    elif axis == "v":
        px = [(r, w - 1 - c, col) for r, c, col in px]
    elif axis == "d":
        px = [(c, r, col) for r, c, col in px]
    else:
        raise EvalError(f"unknown axis {axis}")
    return o.with_pixels(frozenset((r + top, c + left, col) for r, c, col in px))


def recolor(o: ObjectToken, color: int) -> ObjectToken:
    return o.with_pixels(frozenset((r, c, color) for r, c, _ in o.pixels))


def replace_color(o: ObjectToken, old: int, new: int) -> ObjectToken:
    return o.with_pixels(frozenset((r, c, new if col == old else col) for r, c, col in o.pixels))


def add_region(o: ObjectToken, region: str, color: int) -> ObjectToken:
    H, W = o.grid_shape
    region_px = evaluate_region(region, o)
    support = o.global_support
    new = {(r, c, color) for r, c in region_px if (r, c) not in support and 0 <= r < H and 0 <= c < W}
    if not new:
        return o
    return o.with_pixels(o.pixels | frozenset(new))


def remove_region(o: ObjectToken, region: str) -> ObjectToken:
    region_px = evaluate_region(region, o)
    kept = frozenset(p for p in o.pixels if (p[0], p[1]) not in region_px)
    if not kept:
        raise EvalError("remove would empty the object")
    if len(kept) == len(o.pixels):
        return o
    return o.with_pixels(kept)
