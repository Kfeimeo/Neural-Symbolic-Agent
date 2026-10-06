"""Grid domain: the 24-production toy DSL whose semantics live in the Haskell
kernel (``haskell/Evaluation.hs``). Signatures and the task encoder follow the
frozen ``faithful.python.grid`` exactly."""
from __future__ import annotations
import random
import torch
from .. import ast
from ..domain import Domain, KernelEvaluator, Primitive, Task

GRID = ast.base("grid")
COLOR, INT, BOOL, OBJECT, OBJECTS = map(ast.base, ("color", "int", "bool", "object", "objects"))
REQUEST = ast.arrow(GRID, GRID)

SPECS = [("identity", [GRID], GRID), ("rotate90", [GRID], GRID), ("rotate180", [GRID], GRID),
         ("flipH", [GRID], GRID), ("flipV", [GRID], GRID), ("transpose", [GRID], GRID),
         ("trim", [GRID], GRID), ("invert", [GRID], GRID), ("recolor", [GRID, COLOR, COLOR], GRID),
         ("objects", [GRID], OBJECTS), ("largest", [OBJECTS], OBJECT), ("crop", [OBJECT], GRID),
         ("translate", [GRID, INT, INT], GRID), ("count", [OBJECTS], INT), ("is_empty", [OBJECTS], BOOL),
         ("if_grid", [BOOL, GRID, GRID], GRID), ("border", [GRID], GRID), ("solid", [GRID, COLOR], GRID)]
SPECS += [(n, [], t) for n, t in [("red", COLOR), ("blue", COLOR), ("green", COLOR), ("zero", INT), ("one", INT), ("minus_one", INT)]]
SMOKE = ("rotate90", "flipH", "flipV", "transpose", "invert")

def features(task: Task) -> torch.Tensor:
    rows = []
    for inputs, output in task.examples:
        vector = []
        for grid in (inputs[0], output):
            flat = [c for row in grid for c in row]
            vector.extend([len(grid) / 10, len(grid[0]) / 10] + [flat.count(c) / len(flat) for c in range(4)])
            vector.extend([(grid[y][x] / 3 if y < len(grid) and x < len(grid[0]) else -1) for y in range(2) for x in range(7)])
        rows.append(vector)
    return torch.tensor(rows, dtype=torch.float32).mean(0)

def sample_grid(rng: random.Random, colors: int = 4, max_side: int = 5) -> list[list[int]]:
    h, w = rng.randint(1, max_side), rng.randint(1, max_side)
    return [[rng.randrange(colors) for _ in range(w)] for _ in range(h)]

class GridDomain(Domain):
    name = "grid"
    request = REQUEST
    feature_dim = 40
    evaluator = KernelEvaluator()

    def __init__(self, names=None, random_dream_grids: int | None = None):
        """``names`` restricts the DSL; ``random_dream_grids`` draws that many fresh
        random grids per dream instead of reusing training inputs (the default)."""
        selected = [(n, a, r) for n, a, r in SPECS if names is None or n in names]
        self.primitives = [Primitive(n, ast.arrows(*a, r)) for n, a, r in selected]
        self.random_dream_grids = random_dream_grids
        super().__init__()

    def features(self, task): return features(task)

    def dream_inputs(self, request, tasks, rng):
        if self.random_dream_grids: return [[sample_grid(rng)] for _ in range(self.random_dream_grids)]
        return super().dream_inputs(request, tasks, rng)

def smoke_domain() -> GridDomain:
    return GridDomain(SMOKE)
