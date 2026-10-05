"""Monomorphic type language for the Meta Language (ML).

ML knows nothing about grids or objects: base types are opaque names.  The
DSA registers its own base types (Object, Color, ...) through the same
constructors.  v0.1 deliberately instantiates every polymorphic ML operator
(map, filter, argmin, ...) at a finite set of monomorphic types instead of
implementing Hindley-Milner unification; see docs/DESIGN.md.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Type:
    """Base type (nominal)."""
    name: str

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Arrow:
    """Function type ``arguments -> result`` (uncurried, n-ary)."""
    arguments: tuple[Type | "Arrow", ...]
    result: Type

    def __str__(self) -> str:
        args = ", ".join(str(a) for a in self.arguments)
        return f"({args}) -> {self.result}"

    __repr__ = __str__


# Generic ML base types.  Domain types are declared by the DSA.
BOOL = Type("Bool")
INT = Type("Int")


def arrow(*args: Type | Arrow, result: Type) -> Arrow:
    return Arrow(tuple(args), result)


def is_function(t: Type | Arrow) -> bool:
    return isinstance(t, Arrow)
