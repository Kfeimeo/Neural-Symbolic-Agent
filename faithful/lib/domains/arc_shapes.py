"""ARC-TSL Grid DSL adapter: Haskell enumeration, Python primitive semantics."""
import torch

from arc_tsl.language import grid_library
from arc_tsl.ml.types import Arrow
from .. import ast
from ..domain import Domain, Primitive


def convert_type(typ):
    if isinstance(typ, Arrow):
        return ast.arrows(*(convert_type(t) for t in typ.arguments), convert_type(typ.result))
    return ast.base(typ.name)


def convert_term(term):
    """Convert a base ARC-TSL expression; wrap with a lambda for a full program."""
    from arc_tsl.ml.ast import Var, Prim, App, Abs
    if isinstance(term, Var):
        return ast.index(term.index)
    if isinstance(term, Prim):
        return ast.primitive(term.name)
    if isinstance(term, Abs):
        return ast.abstraction(convert_term(term.body))
    if isinstance(term, App):
        value = ast.primitive(term.name)
        for arg in term.args:
            value = ast.application(value, convert_term(arg))
        return value
    raise TypeError("Expand ARC-TSL inventions before converting a term")


def _grid_features(grid):
    h, w = len(grid), len(grid[0]) if grid else 0
    counts = [sum(row.count(c) for row in grid) / max(1, h * w) for c in range(10)]
    return [h / 30, w / 30] + counts


class ARCShapesDomain(Domain):
    name = "arc_grid_shapes_v1"
    request = ast.arrow(ast.base("Grid"), ast.base("Grid"))
    feature_dim = 24

    def __init__(self):
        self.primitives = [Primitive(p.name, convert_type(p.signature),
                           p.implementation if p.arguments else p.implementation())
                           for p in grid_library().primitives.values()]
        super().__init__()

    def features(self, task):
        if not task.examples:
            raise ValueError("ARC tasks need at least one example")
        return torch.tensor([_grid_features(xs[0]) + _grid_features(y)
                             for xs, y in task.examples], dtype=torch.float32).mean(0)

    def dream(self, program, request, tasks, rng, kernel=None, name="dream"):
        # Only training task inputs are sampled; no held-out answers enter dreams.
        task = super().dream(program, request, tasks, rng, kernel, name)
        if task is None:
            return None
        for grid in task.outputs:
            if not isinstance(grid, tuple) or not 1 <= len(grid) <= 30:
                return None
            if not 1 <= len(grid[0]) <= 30 or any(len(row) != len(grid[0]) for row in grid):
                return None
            if any(type(c) is not int or not 0 <= c <= 9 for row in grid for c in row):
                return None
        return task
