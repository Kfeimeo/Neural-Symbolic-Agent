"""Generic ML operators, instantiated at the domain's monomorphic types.

None of these know what an Object *is*; they receive the element type as a
parameter.  Bool / Int / Vec2 arithmetic is ML-level too.
"""
from __future__ import annotations

from fractions import Fraction

from ..ml.types import BOOL, INT, Arrow, Type
from .primitives import EvalError, Primitive, constant, function

# Fixed base weight of the ML logic / arithmetic combinators (add, sub, neg,
# eq_int, lt, not, and, or, vadd, vsub, vneg, vscale).  Part of the fixed
# Base_{ML+DSA} prior, identical in every condition; never tuned per task.
COMBINATOR_COST = 2


def bool_int_primitives() -> list[Primitive]:
    P: list[Primitive] = []
    for n in (0, 1, 2, 3):
        P.append(constant(f"i{n}", INT, n, description="integer constant"))
    c = COMBINATOR_COST
    P += [
        function("add", (INT, INT), INT, lambda a, b: a + b, cost=c),
        function("sub", (INT, INT), INT, lambda a, b: a - b, cost=c),
        function("neg", (INT,), INT, lambda a: -a, cost=c),
        function("eq_int", (INT, INT), BOOL, lambda a, b: a == b, cost=c),
        function("lt", (INT, INT), BOOL, lambda a, b: a < b, cost=c),
        function("not", (BOOL,), BOOL, lambda a: not a, cost=c),
        function("and", (BOOL, BOOL), BOOL, lambda a, b: a and b, cost=c),
        function("or", (BOOL, BOOL), BOOL, lambda a, b: a or b, cost=c),
    ]
    return P


def vec2_primitives(VEC2: Type) -> list[Primitive]:
    F = Fraction
    return [
        function("vec", (INT, INT), VEC2, lambda r, c: (F(r), F(c)), description="(row, col) vector"),
        constant("up", VEC2, (F(-1), F(0))),
        constant("down", VEC2, (F(1), F(0))),
        constant("left", VEC2, (F(0), F(-1))),
        constant("right", VEC2, (F(0), F(1))),
        function("vadd", (VEC2, VEC2), VEC2, lambda a, b: (a[0] + b[0], a[1] + b[1]), cost=COMBINATOR_COST),
        function("vsub", (VEC2, VEC2), VEC2, lambda a, b: (a[0] - b[0], a[1] - b[1]), cost=COMBINATOR_COST),
        function("vneg", (VEC2,), VEC2, lambda a: (-a[0], -a[1]), cost=COMBINATOR_COST),
        function("vscale", (INT, VEC2), VEC2, lambda k, a: (k * a[0], k * a[1]), cost=COMBINATOR_COST),
    ]


def collection_primitives(ELEM: Type, SET: Type, make_set) -> list[Primitive]:
    """map / filter / argmin / argmax / unique / count / insert / delete /
    replace / others / if for element type ELEM and multiset type SET."""
    f_elem = Arrow((ELEM,), ELEM)
    f_bool = Arrow((ELEM,), BOOL)
    f_int = Arrow((ELEM,), INT)

    def argmin(key, xs):
        if not xs:
            raise EvalError("argmin of empty set")
        best, best_key = None, None
        for x in xs:  # canonical order => deterministic tie-break (first)
            k = key(x)
            if best is None or k < best_key:
                best, best_key = x, k
        return best

    def argmax(key, xs):
        if not xs:
            raise EvalError("argmax of empty set")
        best, best_key = None, None
        for x in xs:
            k = key(x)
            if best is None or k > best_key:
                best, best_key = x, k
        return best

    def unique(pred, xs):
        hits = [x for x in xs if pred(x)]
        if len(hits) != 1:
            raise EvalError("unique: expected exactly one match")
        return hits[0]

    def delete(xs, x):
        out = [y for y in xs if y != x]
        if len(out) == len(xs):
            raise EvalError("delete: element not present")
        return make_set(out)

    def replace(xs, old, new):
        if old not in xs:
            raise EvalError("replace: element not present")
        return make_set([new if y == old else y for y in xs])

    def others(xs, x):
        return make_set([y for y in xs if y != x])

    return [
        function("map", (f_elem, SET), SET, lambda f, xs: make_set([f(x) for x in xs])),
        function("filter", (f_bool, SET), SET, lambda p, xs: make_set([x for x in xs if p(x)])),
        function("argmin", (f_int, SET), ELEM, argmin),
        function("argmax", (f_int, SET), ELEM, argmax),
        function("unique", (f_bool, SET), ELEM, unique),
        function("count", (SET,), INT, lambda xs: len(xs)),
        function("insert", (SET, ELEM), SET, lambda xs, x: make_set(list(xs) + [x])),
        function("delete", (SET, ELEM), SET, delete),
        function("replace", (SET, ELEM, ELEM), SET, replace),
        function("others", (SET, ELEM), SET, others),
        function("if_obj", (BOOL, ELEM, ELEM), ELEM, lambda c, a, b: a if c else b),
    ]
