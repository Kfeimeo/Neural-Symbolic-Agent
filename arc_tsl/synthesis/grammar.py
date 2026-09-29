"""Library = fixed base productions (ML + DSA) + task-local abstractions +
production costs.

Cost convention (shared by every experimental condition):
  * each production occurrence (primitive, invented abstraction, variable)
    costs an integer weight, 1 under the uniform grammar;
  * application nodes cost 0, lambda nodes cost ``lam_cost`` (1);
  * L(A) = sum over abstractions of L(body) + 1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Union

from ..ml.ast import Abs, App, Hole, Prim, Term, Var, shift, substitute
from ..ml.primitives import Primitive
from ..ml.types import Arrow, Type

TypeLike = Union[Type, Arrow]


@dataclass(frozen=True)
class Abstraction:
    """Invented production ``name : param_types -> result`` with a closed body
    in which parameter i (0-based) is de Bruijn index ``arity-1-i`` at depth 0."""
    name: str
    param_types: tuple[TypeLike, ...]
    result: TypeLike
    body: Term

    @property
    def arity(self) -> int:
        return len(self.param_types)

    def instantiate(self, args: tuple[Term, ...]) -> Term:
        """Beta-reduce ``name args`` (args are terms in the caller's context)."""
        if len(args) != self.arity:
            raise ValueError("arity mismatch")
        body = self.body
        # parameters are indices arity-1 ... 0 ; substitute the outermost first
        for i, arg in enumerate(args):
            idx = self.arity - 1 - i
            # body currently has (arity - i) free parameter slots; shift arg past them
            body = substitute(body, idx, shift(arg, idx))
        return body

    def __str__(self) -> str:
        params = " ".join(f"x{i}:{t}" for i, t in enumerate(self.param_types))
        return f"{self.name} = λ{params}. {self.body}"


@dataclass
class Library:
    primitives: dict[str, Primitive]
    abstractions: dict[str, Abstraction] = field(default_factory=dict)
    costs: dict[str, int] = field(default_factory=dict)
    var_cost: int = 1
    lam_cost: int = 1

    # --- construction ---------------------------------------------------
    @classmethod
    def from_primitives(cls, prims: Iterable[Primitive]) -> "Library":
        prims = list(prims)
        names = [p.name for p in prims]
        if len(set(names)) != len(names):
            raise ValueError("duplicate primitive names")
        return cls({p.name: p for p in prims})

    def with_abstraction(self, a: Abstraction, cost: int = 1) -> "Library":
        if a.name in self.primitives or a.name in self.abstractions:
            raise ValueError(f"name clash: {a.name}")
        return Library(self.primitives, {**self.abstractions, a.name: a}, {**self.costs, a.name: cost},
                       self.var_cost, self.lam_cost)

    def without_abstraction(self, name: str) -> "Library":
        abstractions = {k: v for k, v in self.abstractions.items() if k != name}
        costs = {k: v for k, v in self.costs.items() if k != name}
        return Library(self.primitives, abstractions, costs, self.var_cost, self.lam_cost)

    def with_costs(self, costs: dict[str, int]) -> "Library":
        return Library(self.primitives, dict(self.abstractions), {**self.costs, **costs}, self.var_cost, self.lam_cost)

    def uniform(self) -> "Library":
        return Library(self.primitives, dict(self.abstractions), {}, 1, 1)

    # --- queries --------------------------------------------------------
    @property
    def production_names(self) -> list[str]:
        return list(self.primitives) + list(self.abstractions)

    def cost(self, name: str) -> int:
        return self.costs.get(name, 1)

    def signature(self, name: str) -> tuple[tuple[TypeLike, ...], TypeLike]:
        if name in self.primitives:
            p = self.primitives[name]
            return p.arguments, p.result
        a = self.abstractions[name]
        return a.param_types, a.result

    def is_invented(self, name: str) -> bool:
        return name in self.abstractions

    def all_types(self) -> list[TypeLike]:
        seen: list[TypeLike] = []
        def add(t):
            if t not in seen:
                seen.append(t)
        for name in self.production_names:
            args, res = self.signature(name)
            add(res)
            for t in args:
                add(t)
                if isinstance(t, Arrow):
                    add(t.result)
        return seen

    # --- typing ---------------------------------------------------------
    def infer(self, t: Term, ctx: tuple[TypeLike, ...] = ()) -> TypeLike:
        """Type of ``t`` in context ``ctx`` (ctx[0] is $0).  Raises TypeError."""
        if isinstance(t, Var):
            if t.index >= len(ctx):
                raise TypeError(f"unbound variable ${t.index} in context {ctx}")
            return ctx[t.index]
        if isinstance(t, Prim):
            args, res = self.signature(t.name)
            if args:
                raise TypeError(f"{t.name} used as constant but has arity {len(args)}")
            return res
        if isinstance(t, App):
            args, res = self.signature(t.name)
            if len(args) != len(t.args):
                raise TypeError(f"{t.name}: expected {len(args)} args, got {len(t.args)}")
            for expected, actual in zip(args, t.args):
                got = self.infer(actual, ctx)
                if got != expected:
                    raise TypeError(f"{t.name}: expected {expected}, got {got} for {actual}")
            return res
        if isinstance(t, Abs):
            body = self.infer(t.body, (t.param_type,) + ctx)
            return Arrow((t.param_type,), body)
        if isinstance(t, Hole):
            raise TypeError("cannot type a hole")
        raise TypeError(t)

    # --- description length ----------------------------------------------
    def description_length(self, t: Term, uniform: bool = True) -> int:
        """L(t | this library).  ``uniform`` ignores learned costs."""
        if isinstance(t, Var):
            return 1 if uniform else self.var_cost
        if isinstance(t, Hole):
            return 1
        if isinstance(t, Prim):
            self._check(t.name)
            return 1 if uniform else self.cost(t.name)
        if isinstance(t, App):
            self._check(t.name)
            head = 1 if uniform else self.cost(t.name)
            return head + sum(self.description_length(a, uniform) for a in t.args)
        if isinstance(t, Abs):
            return (1 if uniform else self.lam_cost) + self.description_length(t.body, uniform)
        raise TypeError(t)

    def library_description_length(self) -> int:
        return sum(self.description_length(a.body) + 1 for a in self.abstractions.values())

    def _check(self, name: str) -> None:
        if name not in self.primitives and name not in self.abstractions:
            raise KeyError(f"unknown production {name!r}")

    def __repr__(self) -> str:
        return (f"Library({len(self.primitives)} primitives, abstractions={list(self.abstractions)}, "
                f"costs={ {k: v for k, v in self.costs.items() if v != 1} })")

    # --- expansion ------------------------------------------------------
    def expand(self, t: Term) -> Term:
        """Inline every invented abstraction (repeatedly) to a base-language term."""
        if isinstance(t, App):
            args = tuple(self.expand(a) for a in t.args)
            if t.name in self.abstractions:
                return self.expand(self.abstractions[t.name].instantiate(args))
            return App(t.name, args)
        if isinstance(t, Abs):
            return Abs(t.param_type, self.expand(t.body))
        if isinstance(t, Prim) and t.name in self.abstractions:
            return self.expand(self.abstractions[t.name].body)
        return t
