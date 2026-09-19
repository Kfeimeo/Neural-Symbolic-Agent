"""Immutable symbolic grids; all domain-specific code stays in this plugin."""
from __future__ import annotations

import random
from dataclasses import dataclass

from ...language import INPUT, FunctionType, Language, Primitive, Program, Type
from ...tasks import Example, Task

Grid = tuple[tuple[int, ...], ...]
GRID, COLOR, INT, BOOL, OBJECT, OBJECTS = map(Type, ("Grid", "Color", "Int", "Bool", "Object", "Objects"))


@dataclass(frozen=True)
class Object:
    cells: tuple[tuple[int, int, int], ...]


def rotate90(g: Grid) -> Grid:
    return tuple(tuple(row) for row in zip(*g[::-1]))


def objects(g: Grid) -> tuple[Object, ...]:
    remaining = {(r, c) for r, row in enumerate(g) for c, v in enumerate(row) if v}
    found = []
    while remaining:
        seed = min(remaining)
        remaining.remove(seed)
        stack, cells = [seed], []
        while stack:
            r, c = stack.pop()
            cells.append((r, c, g[r][c]))
            for neighbor in ((r-1, c), (r+1, c), (r, c-1), (r, c+1)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
        found.append(Object(tuple(sorted(cells))))
    return tuple(found)


def crop(obj: Object) -> Grid:
    if not obj.cells:
        return ((0,),)
    lo_r, lo_c = min(r for r, _, _ in obj.cells), min(c for _, c, _ in obj.cells)
    out = [[0] * (max(c for _, c, _ in obj.cells)-lo_c+1)
           for _ in range(max(r for r, _, _ in obj.cells)-lo_r+1)]
    for r, c, v in obj.cells:
        out[r-lo_r][c-lo_c] = v
    return tuple(map(tuple, out))


def trim(g: Grid) -> Grid:
    return crop(Object(tuple((r, c, v) for r, row in enumerate(g) for c, v in enumerate(row) if v)))


def translate(g: Grid, dr: int, dc: int) -> Grid:
    h, w = len(g), len(g[0])
    return tuple(tuple(g[r-dr][c-dc] if 0 <= r-dr < h and 0 <= c-dc < w else 0
                       for c in range(w)) for r in range(h))


def make_language() -> Language:
    primitives = {}
    def add(name, args, result, fn):
        primitives[name] = Primitive(name, FunctionType(tuple(args), result), fn)
    add("identity", [GRID], GRID, lambda g: g)
    add("rotate90", [GRID], GRID, rotate90)
    add("rotate180", [GRID], GRID, lambda g: rotate90(rotate90(g)))
    add("flipH", [GRID], GRID, lambda g: tuple(row[::-1] for row in g))
    add("flipV", [GRID], GRID, lambda g: g[::-1])
    add("transpose", [GRID], GRID, lambda g: tuple(zip(*g)))
    add("trim", [GRID], GRID, trim)
    add("invert", [GRID], GRID, lambda g: tuple(tuple(0 if v == 0 else 4-v for v in row) for row in g))
    add("recolor", [GRID, COLOR, COLOR], GRID,
        lambda g, a, b: tuple(tuple(b if v == a else v for v in row) for row in g))
    add("objects", [GRID], OBJECTS, objects)
    add("largest", [OBJECTS], OBJECT, lambda os: max(os, key=lambda o: len(o.cells), default=Object(())))
    add("crop", [OBJECT], GRID, crop)
    add("translate", [GRID, INT, INT], GRID, translate)
    add("count", [OBJECTS], INT, len)
    add("is_empty", [OBJECTS], BOOL, lambda os: not os)
    add("if_grid", [BOOL, GRID, GRID], GRID, lambda b, a, c: a if b else c)
    add("border", [GRID], GRID, lambda g: ((0,) * (len(g[0])+2),) + tuple((0,)+r+(0,) for r in g) + ((0,)*(len(g[0])+2),))
    add("solid", [GRID, COLOR], GRID, lambda g, c: tuple(tuple(c if v else 0 for v in row) for row in g))
    for name, typ, value in [("red", COLOR, 1), ("blue", COLOR, 2), ("green", COLOR, 3),
                             ("zero", INT, 0), ("one", INT, 1), ("minus_one", INT, -1)]:
        add(name, [], typ, lambda value=value: value)
    return Language(GRID, GRID, primitives)


def sample_grid(rng: random.Random) -> Grid:
    h, w = rng.randint(2, 5), rng.randint(2, 5)
    core = tuple(tuple(rng.randint(1, 3) if rng.random() < .8 else 0 for _ in range(w)) for _ in range(h))
    # Unequal random margins make trim nontrivial and avoid accidental symmetries.
    top, bottom, left, right = [rng.randint(0, 2) for _ in range(4)]
    width = w+left+right
    return ((0,)*width,) * top + tuple((0,)*left+r+(0,)*right for r in core) + ((0,)*width,) * bottom


def task_programs() -> list[Program]:
    return [Program(n, (Program("trim", (INPUT,)),)) for n in ("rotate90", "flipH", "invert")]


def synthetic_tasks(language: Language, rng: random.Random, count: int, prefix: str = "task") -> list[Task]:
    programs = task_programs()
    tasks = []
    for i in range(count):
        p = programs[i % len(programs)]
        inputs = [sample_grid(rng) for _ in range(4)]
        tasks.append(Task(f"{prefix}_{i}", tuple(Example(x, language.evaluate(p, x)) for x in inputs), p))
    return tasks
