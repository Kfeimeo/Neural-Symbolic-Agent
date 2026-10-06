"""Integer list domain with Python execution semantics.

The same tutorial DSL as ``faithful/domains/official.py`` (``map``, ``+``, ``-``,
``0``, ``1`` plus ``incr``/``incr2``), but every primitive is an ordinary Python
callable run by :mod:`faithful.lib.evaluate`; no domain-specific Haskell build.
"""
from __future__ import annotations
import torch
from .. import ast
from ..domain import Domain, Primitive, Task

INT = ast.base("int")
def lst(t: ast.Type) -> ast.Type: return ast.base("list", t)
A, B = ast.variable(0), ast.variable(1)

def features(task: Task) -> torch.Tensor:
    vectors = []
    for xs, y in task.examples:
        row = []
        for value in (xs[0], y):
            v = value if isinstance(value, list) else [value]
            row += [len(v) / 10, sum(v) / max(1, len(v)) / 10] + [float(x) / 10 for x in v[:18]] + [0.] * (18 - len(v[:18]))
        vectors.append(row)
    return torch.tensor(vectors, dtype=torch.float32).mean(0)

PRIMITIVES = {
    "map": Primitive("map", ast.arrows(ast.arrow(A, B), lst(A), lst(B)), lambda f, xs: [f(x) for x in xs]),
    "+": Primitive("+", ast.arrows(INT, INT, INT), lambda a, b: a + b),
    "-": Primitive("-", ast.arrows(INT, INT, INT), lambda a, b: a - b),
    "0": Primitive("0", INT, 0),
    "1": Primitive("1", INT, 1),
    "incr": Primitive("incr", ast.arrow(INT, INT), lambda n: n + 1),
    "incr2": Primitive("incr2", ast.arrow(INT, INT), lambda n: n + 2),
    "reverse": Primitive("reverse", ast.arrow(lst(A), lst(A)), lambda xs: list(reversed(xs))),
    "cdr": Primitive("cdr", ast.arrow(lst(A), lst(A)), lambda xs: xs[1:]),
}

class ListDomain(Domain):
    name = "lists"
    request = ast.arrow(lst(INT), lst(INT))
    feature_dim = 40
    def __init__(self, names=("map", "+", "-", "0", "1")):
        self.primitives = [PRIMITIVES[n] for n in names]
        super().__init__()
    def features(self, task): return features(task)

class ArithmeticDomain(ListDomain):
    name = "arithmetic"
    request = ast.arrow(INT, INT)
    def __init__(self, names=("incr", "incr2")):
        super().__init__(names)

def list_tasks(domain: ListDomain):
    xs = [[], [-2, 0, 3], [1], [5, -3, 2, 0], [2, 2, -1]]
    funcs = [("map double", lambda n: n * 2), ("map increment", lambda n: n + 1), ("map negation", lambda n: -n),
             ("map quadruple", lambda n: n * 4), ("map add 3", lambda n: n + 3)]
    tasks = [domain.unary_task(name, [(x, [f(y) for y in x]) for x in xs]) for name, f in funcs]
    return tasks[:3], tasks[3:]

def arithmetic_tasks(domain: ArithmeticDomain):
    tasks = [domain.unary_task(f"add{n}", [(x, x + n) for x in [-7, -1, 0, 2, 9]]) for n in range(1, 5)]
    return tasks[:3], tasks[3:]
