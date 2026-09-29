"""Pure pixel-set geometry: translation, quarter-turn rotation, reflection.

Coordinates are (row, col).  A support is a frozenset of (row, col).
"""
from __future__ import annotations

from fractions import Fraction

Pixel = tuple[int, int]
Support = frozenset[Pixel]


def translate(support: Support, dr: int, dc: int) -> Support:
    return frozenset((r + dr, c + dc) for r, c in support)


def bbox(support: Support) -> tuple[int, int, int, int]:
    """(top, left, bottom, right), all inclusive."""
    rows = [r for r, _ in support]
    cols = [c for _, c in support]
    return min(rows), min(cols), max(rows), max(cols)


def normalize(support: Support) -> Support:
    """Translate so that the bounding-box top-left is (0, 0)."""
    if not support:
        return support
    top, left, _, _ = bbox(support)
    return translate(support, -top, -left)


def rotate_local(support: Support, quarter_turns: int) -> Support:
    """Rotate a *normalized* support clockwise by ``quarter_turns`` quarter turns
    and normalize again.  Rotation is about the local origin; because the
    result is normalized, the anchor is the bbox top-left."""
    k = quarter_turns % 4
    s = normalize(support)
    for _ in range(k):
        # clockwise: (r, c) -> (c, H-1-r) with H = height of current bbox
        _, _, bottom, _ = bbox(s)
        h = bottom + 1
        s = normalize(frozenset((c, h - 1 - r) for r, c in s))
    return s


def reflect_local(support: Support, axis: str) -> Support:
    """Reflect a *normalized* support. axis in {"h", "v", "d"}:
    "h" flips across the horizontal midline (rows reversed),
    "v" flips across the vertical midline (cols reversed),
    "d" transposes (main diagonal)."""
    s = normalize(support)
    if not s:
        return s
    _, _, bottom, right = bbox(s)
    if axis == "h":
        return normalize(frozenset((bottom - r, c) for r, c in s))
    if axis == "v":
        return normalize(frozenset((r, right - c) for r, c in s))
    if axis == "d":
        return normalize(frozenset((c, r) for r, c in s))
    raise ValueError(f"Unknown axis {axis!r}")


def bbox_center(support: Support) -> tuple[Fraction, Fraction]:
    top, left, bottom, right = bbox(support)
    return Fraction(top + bottom, 2), Fraction(left + right, 2)


def pixel_centroid(support: Support) -> tuple[Fraction, Fraction]:
    """Observer only: mean pixel position.  Not the DSA center."""
    n = len(support)
    return (Fraction(sum(r for r, _ in support), n), Fraction(sum(c for _, c in support), n))


def neighbors4(p: Pixel) -> tuple[Pixel, ...]:
    r, c = p
    return ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1))


def neighbors8(p: Pixel) -> tuple[Pixel, ...]:
    r, c = p
    return ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1),
            (r - 1, c - 1), (r - 1, c + 1), (r + 1, c - 1), (r + 1, c + 1))
