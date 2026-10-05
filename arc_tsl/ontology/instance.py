"""Deterministic instance extraction.

Instance = maximal connected foreground pixel set.  Connectivity (4/8), the
background policy and whether components may span several colors are all
configuration, so they can be ablated.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..arc.grid import Grid, color_histogram, height, width
from .geometry import Pixel, neighbors4, neighbors8


class BackgroundPolicy(Protocol):
    name: str

    def background(self, grid: Grid) -> int: ...


@dataclass(frozen=True)
class ZeroBackground:
    name: str = "color0"

    def background(self, grid: Grid) -> int:
        return 0


@dataclass(frozen=True)
class MostFrequentBackground:
    name: str = "most_frequent"

    def background(self, grid: Grid) -> int:
        hist = color_histogram(grid)
        best = max(hist.values())
        # deterministic tie-break: smallest color value
        return min(c for c, n in hist.items() if n == best)


BACKGROUND_POLICIES: dict[str, BackgroundPolicy] = {
    "color0": ZeroBackground(),
    "most_frequent": MostFrequentBackground(),
}


@dataclass(frozen=True)
class ExtractionConfig:
    connectivity: int = 8            # 4 or 8
    background: str = "color0"       # key of BACKGROUND_POLICIES
    same_color_only: bool = False    # components may not span colors if True

    def policy(self) -> BackgroundPolicy:
        return BACKGROUND_POLICIES[self.background]


@dataclass(frozen=True)
class Instance:
    pixels: frozenset[tuple[int, int, int]]  # (row, col, color)

    @property
    def support(self) -> frozenset[Pixel]:
        return frozenset((r, c) for r, c, _ in self.pixels)


def extract_instances(grid: Grid, config: ExtractionConfig = ExtractionConfig()) -> tuple[list[Instance], int]:
    """Return (instances in deterministic scan order, background color)."""
    if config.connectivity not in (4, 8):
        raise ValueError("connectivity must be 4 or 8")
    bg = config.policy().background(grid)
    H, W = height(grid), width(grid)
    nbrs = neighbors4 if config.connectivity == 4 else neighbors8
    seen: set[Pixel] = set()
    instances: list[Instance] = []
    for r in range(H):
        for c in range(W):
            if grid[r][c] == bg or (r, c) in seen:
                continue
            color = grid[r][c]
            stack = [(r, c)]
            seen.add((r, c))
            comp: list[tuple[int, int, int]] = []
            while stack:
                pr, pc = stack.pop()
                comp.append((pr, pc, grid[pr][pc]))
                for nr, nc in nbrs((pr, pc)):
                    if 0 <= nr < H and 0 <= nc < W and (nr, nc) not in seen and grid[nr][nc] != bg:
                        if config.same_color_only and grid[nr][nc] != color:
                            continue
                        seen.add((nr, nc))
                        stack.append((nr, nc))
            instances.append(Instance(frozenset(comp)))
    return instances, bg
