"""Sound, incomplete rewrite normal form used ONLY by evaluation/split audit.

No observational hashes are called canonical programs. Unsupported identities
remain distinct; equality of these normal forms implies semantic equality.
"""
from itertools import product
import heapq

from ...language import INPUT, Program
from . import rotate90

GEOMETRY = ("rotate90", "rotate180", "flipH", "flipV", "transpose")
COMMUTING = set(GEOMETRY) | {"identity", "trim", "invert", "border"}
COLORS = {"red": 1, "blue": 2, "green": 3}


def _transform(name, g):
    return {"rotate90": lambda: rotate90(g),
            "rotate180": lambda: rotate90(rotate90(g)),
            "flipH": lambda: tuple(r[::-1] for r in g),
            "flipV": lambda: g[::-1], "transpose": lambda: tuple(zip(*g))}[name]()


MARKER = ((1, 2, 3), (4, 5, 6))


def _orientation(words):
    value = MARKER
    for name in reversed(words):
        value = _transform(name, value)
    return value


REPRESENTATIVES = {}
for _length in range(3):
    for _word in product(sorted(GEOMETRY), repeat=_length):
        REPRESENTATIVES.setdefault(_orientation(_word), _word)
assert len(REPRESENTATIVES) == 8


COLOR_OPS = {("invert",): (3, 2, 1)}
for _a in COLORS:
    COLOR_OPS[("solid", _a)] = (COLORS[_a],)*3
    for _b in COLORS:
        if _a != _b:
            COLOR_OPS[("recolor", _a, _b)] = tuple(COLORS[_b] if i == COLORS[_a] else i for i in (1, 2, 3))


def _color_representatives():
    # Small finite semigroup of positive-color maps. Minimize AST token count;
    # background 0 stays 0 under every supported operation.
    found, queue = {}, [(0, (), (1, 2, 3))]
    while queue:
        cost, word, mapping = heapq.heappop(queue)
        if mapping in found:
            continue
        found[mapping] = word
        for op, transform in COLOR_OPS.items():
            new_mapping = tuple(transform[c-1] for c in mapping)
            if new_mapping not in found:
                heapq.heappush(queue, (cost+len(op), (op,)+word, new_mapping))
    return found


COLOR_REPRESENTATIVES = _color_representatives()


def _color_op(p):
    if p.name == "invert":
        return ("invert",)
    if p.name in ("solid", "recolor") and all(c.name in COLORS and not c.arguments for c in p.arguments[1:]):
        return (p.name,) + tuple(c.name for c in p.arguments[1:])
    return None


def _canonical_pass(program: Program) -> Program:
    p = Program(program.name, tuple(canonical(c) for c in program.arguments))
    geometry, shape, mapping = [], [], (1, 2, 3)
    while p.name in COMMUTING or _color_op(p) is not None:
        if p.name in GEOMETRY:
            geometry.append(p.name)
        elif p.name in ("trim", "border"):
            shape.append(p.name)
        elif _color_op(p) is not None:
            op = _color_op(p)
            transform = COLOR_OPS.get(op, (1, 2, 3))  # recolor(c,c) is identity
            mapping = tuple(mapping[c-1] for c in transform)
        p = p.arguments[0]
    # Trim absorbs consecutive trim and all borders inside it. Geometric and
    # positive-color maps commute with both shape operations, so the extraction
    # above is sound, including on empty/all-background grids.
    shape_normal = []
    for name in shape:
        if shape_normal and shape_normal[-1] == "trim":
            continue
        shape_normal.append(name)
    for name in reversed(shape_normal):
        p = Program(name, (p,))
    for op in reversed(COLOR_REPRESENTATIVES[mapping]):
        p = Program(op[0], (p,)+tuple(Program(n) for n in op[1:]))
    for name in reversed(REPRESENTATIVES[_orientation(geometry)]):
        p = Program(name, (p,))
    return p


def canonical(program: Program) -> Program:
    while True:
        rewritten = _canonical_pass(program)
        if rewritten == program:
            return rewritten
        program = rewritten


def depth(p: Program) -> int:
    """Longest application path, excluding variables and nullary constants."""
    return 0 if not p.arguments else 1 + max(depth(c) for c in p.arguments)
