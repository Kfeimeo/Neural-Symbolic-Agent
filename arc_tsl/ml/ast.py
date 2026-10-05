"""Typed lambda-calculus AST with de Bruijn indices.

Nodes
-----
Var(index)            bound variable ($0 innermost)
Prim(name)            nullary primitive / constant
App(name, args)       fully applied primitive or invented abstraction
Abs(param_type, body) typed lambda abstraction
Hole(index)           pattern hole (only inside compression patterns)

v0.1 restriction: application heads are always named productions (primitives
or invented abstractions), and function-typed positions are always filled by
Abs nodes.  Bound variables therefore never have function type.  This keeps
enumeration and anti-unification simple while still giving typed lambda
abstraction / application, composition, map/filter/argmin, and library
abstractions with typed parameters.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Union

from .types import Arrow, Type


class Term:
    __slots__ = ()

    def __str__(self) -> str:
        return pretty(self)

    __repr__ = __str__


@dataclass(frozen=True, slots=True)
class Var(Term):
    index: int


@dataclass(frozen=True, slots=True)
class Prim(Term):
    name: str


@dataclass(frozen=True, slots=True)
class App(Term):
    name: str
    args: tuple[Term, ...]


@dataclass(frozen=True, slots=True)
class Abs(Term):
    param_type: Union[Type, Arrow]
    body: Term


@dataclass(frozen=True, slots=True)
class Hole(Term):
    index: int


def pretty(t: Term) -> str:
    if isinstance(t, Var):
        return f"${t.index}"
    if isinstance(t, Prim):
        return t.name
    if isinstance(t, Hole):
        return f"?{t.index}"
    if isinstance(t, App):
        return "(" + " ".join([t.name] + [pretty(a) for a in t.args]) + ")"
    if isinstance(t, Abs):
        return f"(λ{t.param_type}. {pretty(t.body)})"
    raise TypeError(t)


def subterms(t: Term) -> Iterator[Term]:
    """Pre-order traversal, including ``t`` itself."""
    yield t
    if isinstance(t, App):
        for a in t.args:
            yield from subterms(a)
    elif isinstance(t, Abs):
        yield from subterms(t.body)


def children(t: Term) -> tuple[Term, ...]:
    if isinstance(t, App):
        return t.args
    if isinstance(t, Abs):
        return (t.body,)
    return ()


def size(t: Term) -> int:
    """Node count (every node counts 1)."""
    return 1 + sum(size(c) for c in children(t))


def leaves(t: Term) -> Iterator[Term]:
    if isinstance(t, (Var, Prim, Hole)):
        yield t
    elif isinstance(t, App):
        # the head symbol is a leaf-like production
        yield Prim(t.name)
        for a in t.args:
            yield from leaves(a)
    else:
        yield from leaves(t.body)


def free_variables(t: Term, depth: int = 0) -> set[int]:
    """Free de Bruijn indices, expressed relative to the root of ``t``."""
    if isinstance(t, Var):
        return {t.index - depth} if t.index >= depth else set()
    if isinstance(t, App):
        out: set[int] = set()
        for a in t.args:
            out |= free_variables(a, depth)
        return out
    if isinstance(t, Abs):
        return free_variables(t.body, depth + 1)
    return set()


def shift(t: Term, amount: int, cutoff: int = 0) -> Term:
    """Shift free variables (index >= cutoff) by ``amount``."""
    if isinstance(t, Var):
        if t.index >= cutoff:
            new = t.index + amount
            if new < 0:
                raise ValueError("Negative de Bruijn index after shift")
            return Var(new)
        return t
    if isinstance(t, App):
        return App(t.name, tuple(shift(a, amount, cutoff) for a in t.args))
    if isinstance(t, Abs):
        return Abs(t.param_type, shift(t.body, amount, cutoff + 1))
    return t


def substitute(t: Term, index: int, replacement: Term) -> Term:
    """Replace free ``Var(index)`` in ``t`` by ``replacement`` (capture-avoiding
    via shifting), and decrement free variables above ``index``."""
    if isinstance(t, Var):
        if t.index == index:
            return replacement
        if t.index > index:
            return Var(t.index - 1)
        return t
    if isinstance(t, App):
        return App(t.name, tuple(substitute(a, index, replacement) for a in t.args))
    if isinstance(t, Abs):
        return Abs(t.param_type, substitute(t.body, index + 1, shift(replacement, 1)))
    return t


def has_holes(t: Term) -> bool:
    return any(isinstance(s, Hole) for s in subterms(t))


def count_symbols(t: Term) -> dict[str, int]:
    out: dict[str, int] = {}
    for s in subterms(t):
        if isinstance(s, (Prim, App)):
            out[s.name] = out.get(s.name, 0) + 1
    return out
