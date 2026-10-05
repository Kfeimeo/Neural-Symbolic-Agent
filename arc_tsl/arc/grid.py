"""ARC grid representation: Grid : [0,H) x [0,W) -> Color.

Colors are nominal symbols.  They are stored as ints for convenience only;
no DSA primitive performs arithmetic on them.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable

Grid = tuple[tuple[int, ...], ...]
Color = int
Position = tuple[int, int]  # (row, col)


def to_grid(rows: Iterable[Iterable[int]]) -> Grid:
    g = tuple(tuple(int(c) for c in row) for row in rows)
    if g and any(len(r) != len(g[0]) for r in g):
        raise ValueError("Ragged grid")
    return g


def height(g: Grid) -> int:
    return len(g)


def width(g: Grid) -> int:
    return len(g[0]) if g else 0


def shape(g: Grid) -> tuple[int, int]:
    return height(g), width(g)


def color_histogram(g: Grid) -> Counter[int]:
    return Counter(c for row in g for c in row)


def pixels(g: Grid) -> Iterable[tuple[Position, Color]]:
    for r, row in enumerate(g):
        for c, color in enumerate(row):
            yield (r, c), color


def load_arc_task(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        "train": [(to_grid(p["input"]), to_grid(p["output"])) for p in data["train"]],
        "test": [(to_grid(p["input"]), to_grid(p["output"]) if "output" in p else None) for p in data["test"]],
    }


def grid_to_text(g: Grid) -> str:
    return "\n".join("".join(str(c) for c in row) for row in g)
