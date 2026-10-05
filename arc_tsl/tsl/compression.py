"""Task-local library induction (DreamCoder-style sleep phase, v0.1).

Input:  frontiers F_1..F_n of programs solving the local micro-tasks
        (x_i, y_i) of ONE ARC task, in the current library.
Output: abstractions A_tau minimising

        L(A_tau) + sum_i  min_{p in F_i} L(p | Base + A_tau)

Proposal step (typed anti-unification):
  every subterm of every frontier program is *closed* (free de Bruijn
  variables become typed parameters) and taken as a candidate; every pair of
  closed subterms with the same type and head symbol is anti-unified (least
  general generalisation) to propose parameterised fragments.  Holes are
  never created inside a lambda when the abstracted subterms would capture
  the lambda-bound variable; the enclosing lambda becomes the hole instead.

Selection step (MDL gate):
  each candidate is scored by rewriting all frontier programs with a greedy
  top-down semantics-preserving rewrite and recomputing the objective; the
  best strictly improving candidate is accepted, and the loop repeats on the
  rewritten frontiers (so later abstractions can use earlier ones).

Differences from the original DreamCoder compressor are listed in README.md:
no version-space/e-graph enumeration of refactorings, no inside-outside
grammar fitting inside the objective, unit production costs instead of
-log p, and greedy (not beam) acceptance.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from ..ml.ast import Abs, App, Hole, Prim, Term, Var, free_variables, shift, subterms
from ..ml.types import Arrow
from ..synthesis.grammar import Abstraction, Library, TypeLike


# ----------------------------------------------------------------------------
# candidate patterns
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Candidate:
    pattern: Term                        # contains Hole(0..k-1)
    param_types: tuple[TypeLike, ...]
    result: TypeLike

    @property
    def arity(self) -> int:
        return len(self.param_types)

    def to_abstraction(self, name: str) -> Abstraction:
        k = self.arity

        def convert(t: Term, depth: int) -> Term:
            if isinstance(t, Hole):
                return Var(depth + (k - 1 - t.index))
            if isinstance(t, Var):
                # variables inside a closed pattern are bound within it
                return t
            if isinstance(t, App):
                return App(t.name, tuple(convert(a, depth) for a in t.args))
            if isinstance(t, Abs):
                return Abs(t.param_type, convert(t.body, depth + 1))
            return t

        return Abstraction(name, self.param_types, self.result, convert(self.pattern, 0))


class _Capture(Exception):
    pass


def _primitive_leaf_count(t: Term) -> int:
    n = 0
    for s in subterms(t):
        if isinstance(s, (Prim, App)):
            n += 1
    return n


def _hole_indices(t: Term) -> list[int]:
    return [s.index for s in subterms(t) if isinstance(s, Hole)]


def nontrivial(c: Candidate) -> bool:
    leaves = _primitive_leaf_count(c.pattern)
    holes = _hole_indices(c.pattern)
    if leaves > 1:
        return True
    return leaves == 1 and len(holes) > len(set(holes))


class _Builder:
    """Accumulates holes keyed by the (sub)terms they abstract."""

    def __init__(self):
        self.keys: dict = {}
        self.types: list[TypeLike] = []

    def hole(self, key, typ: TypeLike) -> Hole:
        if key not in self.keys:
            self.keys[key] = len(self.types)
            self.types.append(typ)
        return Hole(self.keys[key])


def _typed_children(library: Library, t: Term, typ: TypeLike):
    """Yield (child, child_type, under_lambda) for the children of t."""
    if isinstance(t, App):
        args, _ = library.signature(t.name)
        for a, at in zip(t.args, args):
            yield a, at
    elif isinstance(t, Abs):
        assert isinstance(typ, Arrow)
        yield t.body, typ.result


def close_subterm(library: Library, t: Term, typ: TypeLike, ctx: tuple[TypeLike, ...]) -> Candidate | None:
    """Turn a subterm (with free variables typed by ctx) into a closed pattern."""
    b = _Builder()

    def go(s: Term, st: TypeLike, depth: int) -> Term:
        if isinstance(s, Var):
            if s.index >= depth:
                return b.hole(("var", s.index - depth), ctx[s.index - depth])
            return s
        if isinstance(s, App):
            args, _ = library.signature(s.name)
            return App(s.name, tuple(go(a, at, depth) for a, at in zip(s.args, args)))
        if isinstance(s, Abs):
            return Abs(s.param_type, go(s.body, st.result, depth + 1))
        return s

    pattern = go(t, typ, 0)
    return Candidate(pattern, tuple(b.types), typ)


def anti_unify(library: Library, t1: Term, t2: Term, typ: TypeLike) -> Candidate | None:
    """Least general generalisation of two closed patterns of type ``typ``.
    Existing holes are treated as distinct atoms keyed by their identity."""
    b = _Builder()

    def go(a: Term, c: Term, st: TypeLike, depth: int) -> Term:
        if isinstance(a, App) and isinstance(c, App) and a.name == c.name and len(a.args) == len(c.args):
            args, _ = library.signature(a.name)
            return App(a.name, tuple(go(x, y, at, depth) for x, y, at in zip(a.args, c.args, args)))
        if isinstance(a, Abs) and isinstance(c, Abs) and a.param_type == c.param_type:
            try:
                return Abs(a.param_type, go(a.body, c.body, st.result, depth + 1))
            except _Capture:
                if depth == 0:
                    return b.hole(("pair", a, c), st)
                raise
        if a == c and not isinstance(a, Hole):
            return a
        # mismatch (or hole vs anything): becomes a parameter
        if depth > 0 and (_captures(a, depth) or _captures(c, depth)):
            raise _Capture()
        return b.hole(("pair", a, c), st)

    try:
        pattern = go(t1, t2, typ, 0)
    except _Capture:
        return None
    if isinstance(pattern, Hole):
        return None
    return Candidate(pattern, tuple(b.types), typ)


def _captures(t: Term, depth: int) -> bool:
    """Does t reference a variable bound within the last ``depth`` lambdas of
    the pattern (i.e. a free index < depth)?"""
    return any(i < 0 for i in free_variables(t, depth))


def _renumber(c: Candidate) -> Candidate:
    """Renumber holes by first occurrence (canonical form)."""
    order: dict[int, int] = {}
    for i in _hole_indices(c.pattern):
        if i not in order:
            order[i] = len(order)

    def go(t: Term) -> Term:
        if isinstance(t, Hole):
            return Hole(order[t.index])
        if isinstance(t, App):
            return App(t.name, tuple(go(a) for a in t.args))
        if isinstance(t, Abs):
            return Abs(t.param_type, go(t.body))
        return t

    types = tuple(c.param_types[old] for old, _ in sorted(order.items(), key=lambda kv: kv[1]))
    return Candidate(go(c.pattern), types, c.result)


def typed_subterms(library: Library, t: Term, typ: TypeLike, ctx: tuple[TypeLike, ...]):
    """Yield (subterm, type, context) for every subterm of ``t``."""
    yield t, typ, ctx
    if isinstance(t, App):
        args, _ = library.signature(t.name)
        for a, at in zip(t.args, args):
            yield from typed_subterms(library, a, at, ctx)
    elif isinstance(t, Abs):
        yield from typed_subterms(library, t.body, typ.result, (t.param_type,) + ctx)


def propose(library: Library, programs: list[Term], root_ctx: tuple[TypeLike, ...], root_type: TypeLike,
            max_arity: int = 3) -> list[Candidate]:
    closed: list[Candidate] = []
    seen: set[tuple] = set()
    for p in programs:
        for s, st, ctx in typed_subterms(library, p, root_type, root_ctx):
            if isinstance(s, (Var, Prim, Hole)):
                continue
            c = close_subterm(library, s, st, ctx)
            if c is None:
                continue
            c = _renumber(c)
            key = (c.pattern, c.param_types)
            if key not in seen:
                seen.add(key)
                closed.append(c)
    candidates: list[Candidate] = []
    cand_seen: set[tuple] = set()

    def consider(c: Candidate | None):
        if c is None:
            return
        c = _renumber(c)
        if c.arity > max_arity or not nontrivial(c):
            return
        key = (c.pattern, c.param_types)
        if key in cand_seen:
            return
        cand_seen.add(key)
        candidates.append(c)

    for c in closed:
        consider(c)
    by_type: dict = {}
    for c in closed:
        by_type.setdefault(c.result, []).append(c)
    for group in by_type.values():
        for a, b in itertools.combinations(group, 2):
            if _head(a.pattern) != _head(b.pattern):
                continue
            consider(anti_unify(library, a.pattern, b.pattern, a.result))
    return candidates


def _head(t: Term):
    if isinstance(t, App):
        return ("app", t.name)
    if isinstance(t, Abs):
        return ("abs", t.param_type)
    return ("atom", t)


# ----------------------------------------------------------------------------
# matching / rewriting
# ----------------------------------------------------------------------------
def match(pattern: Term, t: Term, bindings: dict[int, Term], d: int = 0) -> bool:
    """Match ``pattern`` against ``t`` where ``t`` sits ``d`` lambdas below the
    match root.  Hole arguments are shifted out of those lambdas."""
    if isinstance(pattern, Hole):
        if d > 0 and _captures(t, d):
            return False
        arg = shift(t, -d, d) if d > 0 else t
        if pattern.index in bindings:
            return bindings[pattern.index] == arg
        bindings[pattern.index] = arg
        return True
    if isinstance(pattern, App):
        if not isinstance(t, App) or t.name != pattern.name or len(t.args) != len(pattern.args):
            return False
        return all(match(pa, ta, bindings, d) for pa, ta in zip(pattern.args, t.args))
    if isinstance(pattern, Abs):
        if not isinstance(t, Abs) or t.param_type != pattern.param_type:
            return False
        return match(pattern.body, t.body, bindings, d + 1)
    return pattern == t


def rewrite(t: Term, candidate: Candidate, name: str) -> Term:
    """Greedy top-down rewrite of every match of ``candidate`` into ``name``."""
    bindings: dict[int, Term] = {}
    if match(candidate.pattern, t, bindings):
        args = tuple(rewrite(bindings[i], candidate, name) for i in range(candidate.arity))
        return App(name, args) if args else Prim(name)
    if isinstance(t, App):
        return App(t.name, tuple(rewrite(a, candidate, name) for a in t.args))
    if isinstance(t, Abs):
        return Abs(t.param_type, rewrite(t.body, candidate, name))
    return t


# ----------------------------------------------------------------------------
# MDL objective and greedy compression loop
# ----------------------------------------------------------------------------
def frontier_mdl(library: Library, frontiers: list[list[Term]]) -> int:
    return sum(min(library.description_length(p) for p in F) for F in frontiers if F)


def total_mdl(library: Library, frontiers: list[list[Term]]) -> int:
    return library.library_description_length() + frontier_mdl(library, frontiers)


@dataclass
class CompressionStep:
    abstraction: Abstraction
    mdl_before: int
    mdl_after: int
    candidates_scored: int

    def to_dict(self) -> dict:
        return {"abstraction": str(self.abstraction), "name": self.abstraction.name,
                "arity": self.abstraction.arity, "body_length": None,
                "mdl_before": self.mdl_before, "mdl_after": self.mdl_after,
                "candidates_scored": self.candidates_scored}


@dataclass
class CompressionResult:
    library: Library
    frontiers: list[list[Term]]          # rewritten
    steps: list[CompressionStep] = field(default_factory=list)
    mdl_before: int = 0
    mdl_after: int = 0

    @property
    def added(self) -> list[str]:
        return [s.abstraction.name for s in self.steps]


def compress(library: Library, frontiers: list[list[Term]], root_ctx: tuple[TypeLike, ...],
             root_type: TypeLike, max_abstractions: int = 3, max_arity: int = 3,
             name_prefix: str = "#f") -> CompressionResult:
    current = [list(F) for F in frontiers]
    lib = library
    result = CompressionResult(lib, current, mdl_before=total_mdl(lib, current))
    for _ in range(max_abstractions):
        programs = [p for F in current for p in F]
        candidates = propose(lib, programs, root_ctx, root_type, max_arity)
        before = total_mdl(lib, current)
        best = None
        index = len(lib.abstractions)
        name = f"{name_prefix}{index}"
        for c in candidates:
            abstraction = c.to_abstraction(name)
            trial_lib = lib.with_abstraction(abstraction)
            rewritten = [[rewrite(p, c, name) for p in F] for F in current]
            after = total_mdl(trial_lib, rewritten)
            key = (after, c.arity, str(c.pattern))
            if after < before and (best is None or key < best[0]):
                best = (key, abstraction, trial_lib, rewritten)
        if best is None:
            break
        _, abstraction, lib, current = best
        result.steps.append(CompressionStep(abstraction, before, total_mdl(lib, current), len(candidates)))
    result.library, result.frontiers = lib, current
    result.mdl_after = total_mdl(lib, current)
    return result
