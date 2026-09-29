"""Deterministic object observers."""
from __future__ import annotations

from fractions import Fraction

from ..ontology.object import ObjectToken


def size(o: ObjectToken) -> int:
    return o.size


def center(o: ObjectToken) -> tuple[Fraction, Fraction]:
    return o.center


def bbox_top(o: ObjectToken) -> int:
    return o.bbox[0]


def bbox_left(o: ObjectToken) -> int:
    return o.bbox[1]


def bbox_bottom(o: ObjectToken) -> int:
    return o.bbox[2]


def bbox_right(o: ObjectToken) -> int:
    return o.bbox[3]


def height(o: ObjectToken) -> int:
    return o.height


def width(o: ObjectToken) -> int:
    return o.width


def color_set(o: ObjectToken) -> frozenset[int]:
    return o.color_set


def dominant_color(o: ObjectToken) -> int:
    return o.dominant_color


def num_colors(o: ObjectToken) -> int:
    return len(o.color_set)


def shape_id(o: ObjectToken):
    return o.shape_id


def orientation(o: ObjectToken) -> int:
    return o.orientation
