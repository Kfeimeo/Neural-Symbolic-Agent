"""ObjectToken (concrete instance in a grid) vs ObjectClass (geometric class).

Two tokens with the same shape_id share an ObjectClass but remain distinct
tokens (multiplicity is never lost: an ObjectSet is an ordered multiset).

Intrinsic geometry (shape_id) is separated from extrinsic geometry
(position, orientation) and appearance (colors).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from fractions import Fraction
from functools import cached_property

from .canonicalize import ShapeId, orientation as _orientation, shape_id as _shape_id
from .geometry import Pixel, Support, bbox as _bbox, bbox_center, normalize, pixel_centroid

ColoredPixel = tuple[int, int, int]  # (row, col, color)


@dataclass(frozen=True)
class ObjectClass:
    shape_id: ShapeId

    @property
    def size(self) -> int:
        return len(self.shape_id)


@dataclass(frozen=True, eq=False)
class ObjectToken:
    """A concrete object inside a grid of shape ``grid_shape``.

    Equality/hash are structural (pixels + grid shape); ``token_id`` is
    provenance only (which parsed instance this token descends from).
    """
    pixels: frozenset[ColoredPixel]
    grid_shape: tuple[int, int]
    token_id: int = field(default=-1, compare=False)

    def __post_init__(self):
        if not self.pixels:
            raise ValueError("ObjectToken must have a non-empty support")

    # --- identity -------------------------------------------------------
    def __eq__(self, other):
        return isinstance(other, ObjectToken) and self.pixels == other.pixels and self.grid_shape == other.grid_shape

    def __hash__(self):
        return hash((self.pixels, self.grid_shape))

    def __repr__(self):
        t, l, b, r = self.bbox
        return f"Obj#{self.token_id}(shape={self.size}px@({t},{l})-({b},{r}) colors={sorted(self.color_set)})"

    # --- geometry -------------------------------------------------------
    @cached_property
    def global_support(self) -> Support:
        return frozenset((r, c) for r, c, _ in self.pixels)

    @cached_property
    def local_support(self) -> Support:
        return normalize(self.global_support)

    @cached_property
    def bbox(self) -> tuple[int, int, int, int]:
        return _bbox(self.global_support)

    @property
    def position(self) -> Pixel:
        """bbox top-left anchor."""
        return self.bbox[0], self.bbox[1]

    @cached_property
    def center(self) -> tuple[Fraction, Fraction]:
        return bbox_center(self.global_support)

    @cached_property
    def centroid(self) -> tuple[Fraction, Fraction]:
        return pixel_centroid(self.global_support)

    @cached_property
    def shape_id(self) -> ShapeId:
        return _shape_id(self.global_support)

    @property
    def object_class(self) -> ObjectClass:
        return ObjectClass(self.shape_id)

    @cached_property
    def orientation(self) -> int:
        return _orientation(self.global_support)

    @property
    def size(self) -> int:
        return len(self.pixels)

    @property
    def height(self) -> int:
        t, _, b, _ = self.bbox
        return b - t + 1

    @property
    def width(self) -> int:
        _, l, _, r = self.bbox
        return r - l + 1

    # --- appearance -----------------------------------------------------
    @cached_property
    def color_set(self) -> frozenset[int]:
        return frozenset(col for _, _, col in self.pixels)

    @cached_property
    def dominant_color(self) -> int:
        hist = Counter(col for _, _, col in self.pixels)
        best = max(hist.values())
        return min(c for c, n in hist.items() if n == best)

    def color_at(self, r: int, c: int) -> int | None:
        for pr, pc, col in self.pixels:
            if pr == r and pc == c:
                return col
        return None

    # --- constructors ---------------------------------------------------
    def with_pixels(self, pixels: frozenset[ColoredPixel]) -> "ObjectToken":
        return ObjectToken(frozenset(pixels), self.grid_shape, self.token_id)


def sort_key(o: ObjectToken):
    return (o.bbox[0], o.bbox[1], o.bbox[2], o.bbox[3], tuple(sorted(o.pixels)))


ObjectSet = tuple[ObjectToken, ...]


def make_object_set(objects) -> ObjectSet:
    """Canonically ordered multiset of tokens (deterministic paint order)."""
    return tuple(sorted(objects, key=sort_key))
