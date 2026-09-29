"""Bottom-up, cost-ordered, typed enumeration with observational equivalence.

Terms are enumerated per (context, type, cost).  A context is the tuple of
de Bruijn variable types; v0.1 uses
    C0 = (ObjectSet,)                    the top-level scene
    C1 = (Object, ObjectSet)             inside one lambda
    C2 = (Object, Object, ObjectSet)     inside two nested lambdas
Every term is evaluated on all sample bindings of its context (the scenes of
the training pairs, and every object / pair of objects of those scenes for
C1 / C2).  Two terms with identical observation vectors are merged (the
first constructed, i.e. cheapest, survives).  Function-typed terms are
observed through their values on the sample objects of the binding's scene.

Statistics
  expanded_states     candidate terms constructed (before OE / dead pruning)
  retained_terms      terms kept after OE
  evaluated_programs  complete (C0, ObjectSet) programs checked against outputs
"""
from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from ..dsa.types import OBJECT, OBJECTS
from ..ml.ast import Abs, App, Prim, Term, Var
from ..ml.types import Arrow, Type
from .evaluator import ERR, Closure, _CAUGHT, compile_term
from .grammar import Library, TypeLike

Context = tuple[TypeLike, ...]


@dataclass
class EnumerationStats:
    expanded_states: int = 0
    retained_terms: int = 0
    evaluated_programs: int = 0
    dead_terms: int = 0
    equivalent_terms: int = 0
    cell_caps_hit: int = 0
    max_cost_reached: int = 0
    budget_exhausted: bool = False
    termination_reason: str = "running"
    seconds: float = 0.0


@dataclass
class EnumerationConfig:
    max_cost: int = 10
    max_expanded_states: int = 200_000
    time_limit_seconds: float = 60.0
    max_lambda_depth: int = 2
    max_terms_per_cell: int = 20000  # safety cap per (context, type, cost)
    max_context_bindings: int = 128  # deterministic subsample of sample bindings per lambda context


@dataclass
class Entry:
    term: Term
    cost: int
    values: list            # value per binding of the context
    obs: tuple              # hashable observation vector


class _Budget(Exception):
    pass


def _subsample(items: list, k: int) -> list:
    """Deterministic, evenly spaced subsample (keeps order).  Sample bindings
    of lambda contexts are only used for observational-equivalence keys; the
    top-level scenes are never subsampled, so accepted programs are always
    verified on every training pair."""
    n = len(items)
    if k <= 0 or n <= k:
        return items
    return [items[(i * n) // k] for i in range(k)]


class Enumerator:
    def __init__(self, library: Library, scenes: list[tuple], config: EnumerationConfig = EnumerationConfig(),
                 is_solution=None):
        """``is_solution(values) -> bool`` lets observationally duplicate *solutions*
        of the top cell be reported (not retained), so top-K frontiers of
        syntactically distinct programs can be collected."""
        self.library = library
        self.is_solution = is_solution
        self.config = config
        self.scenes = scenes
        self.stats = EnumerationStats()
        self.contexts: list[Context] = []
        self.envs: dict[Context, list[tuple]] = {}
        self.scene_objects: dict[Context, list[tuple]] = {}
        self._build_contexts()
        self.types = list(library.all_types())
        self.terms: dict[tuple[Context, TypeLike], dict[int, list[Entry]]] = {}
        self.seen: dict[tuple[Context, TypeLike], set] = {}
        for ctx in self.contexts:
            for t in self.types:
                self.terms[(ctx, t)] = {}
                self.seen[(ctx, t)] = set()
        self._closures: dict[Term, Callable] = {}
        self._impl = {n: p.implementation for n, p in library.primitives.items()}
        self._started = 0.0

    # ------------------------------------------------------------------
    def _build_contexts(self):
        ctx: Context = (OBJECTS,)
        envs = [(scene,) for scene in self.scenes]
        self.contexts.append(ctx)
        self.envs[ctx] = envs
        for _ in range(self.config.max_lambda_depth):
            inner: Context = (OBJECT,) + ctx
            inner_envs = [(o,) + env for env in envs for o in env[-1]]
            inner_envs = _subsample(inner_envs, self.config.max_context_bindings)
            self.contexts.append(inner)
            self.envs[inner] = inner_envs
            ctx, envs = inner, inner_envs
        # inner contexts first, so lambda bodies exist before lambdas
        self.contexts.reverse()

    def _inner(self, ctx: Context) -> Context | None:
        inner = (OBJECT,) + ctx
        return inner if inner in self.envs else None

    # ------------------------------------------------------------------
    def _observe(self, value: Any, typ: TypeLike, env: tuple):
        if value is ERR:
            return ERR
        if isinstance(typ, Arrow):
            out = []
            for o in env[-1]:
                try:
                    v = value(o)
                except _CAUGHT:
                    v = ERR
                out.append(self._observe(v, typ.result, env))
            return ("λ",) + tuple(out)
        return value

    def _values_app(self, name: str, arg_entries: list[Entry], n: int) -> list:
        lib = self.library
        if lib.is_invented(name):
            body_fn = self._closures.get(name)
            if body_fn is None:
                body_fn = self._closures[name] = compile_term(lib.abstractions[name].body, lib)
            def call(args):
                args = list(args)
                args.reverse()
                return body_fn(tuple(args))
        else:
            impl = self._impl[name]
            def call(args):
                return impl(*args)
        out = []
        cols = [e.values for e in arg_entries]
        for j in range(n):
            args = [c[j] for c in cols]
            if any(a is ERR for a in args):
                out.append(ERR)
                continue
            try:
                out.append(call(args))
            except _CAUGHT:
                out.append(ERR)
        return out

    def _values_abs(self, body: Term, ctx: Context) -> list:
        body_fn = compile_term(body, self.library)
        term = Abs(OBJECT, body)
        return [Closure(lambda x, env=env, f=body_fn: f((x,) + env), term, env) for env in self.envs[ctx]]

    # ------------------------------------------------------------------
    def _add(self, ctx: Context, typ: TypeLike, cost: int, term: Term, values: list) -> Entry | None:
        self.stats.expanded_states += 1
        if self.stats.expanded_states >= self.config.max_expanded_states:
            self.stats.termination_reason = "max_expanded_states"
            raise _Budget()
        if self.stats.expanded_states % 512 == 0 and time.perf_counter() - self._started > self.config.time_limit_seconds:
            self.stats.termination_reason = "time_limit"
            raise _Budget()
        envs = self.envs[ctx]
        obs = tuple(self._observe(v, typ, env) for v, env in zip(values, envs))
        if all(o is ERR for o in obs):
            self.stats.dead_terms += 1
            return None
        seen = self.seen[(ctx, typ)]
        if obs in seen:
            self.stats.equivalent_terms += 1
            if (self.is_solution is not None and ctx == self.contexts[-1] and typ == OBJECTS
                    and self.is_solution(values)):
                return Entry(term, cost, values, obs)   # reported, not retained
            return None
        seen.add(obs)
        entry = Entry(term, cost, values, obs)
        cell = self.terms[(ctx, typ)].setdefault(cost, [])
        cell.append(entry)
        self.stats.retained_terms += 1
        return entry

    def _entries(self, ctx: Context, typ: TypeLike, cost: int) -> list[Entry]:
        return self.terms.get((ctx, typ), {}).get(cost, [])

    def _min_cost(self, ctx: Context, typ: TypeLike) -> int:
        cells = self.terms.get((ctx, typ), {})
        return min(cells) if cells else 10**9

    # ------------------------------------------------------------------
    def _gen_leaves(self, ctx: Context, typ: TypeLike, cost: int) -> Iterator[Entry]:
        lib = self.library
        n = len(self.envs[ctx])
        if cost == lib.var_cost:
            for i, vt in enumerate(ctx):
                if vt == typ:
                    e = self._add(ctx, typ, cost, Var(i), [env[i] for env in self.envs[ctx]])
                    if e:
                        yield e
        for name in lib.production_names:
            args, res = lib.signature(name)
            if args or res != typ or lib.cost(name) != cost:
                continue
            if lib.is_invented(name):
                values = self._values_app(name, [], n)
            else:
                v = lib.primitives[name].implementation()
                values = [v] * n
            e = self._add(ctx, typ, cost, Prim(name), values)
            if e:
                yield e

    def _gen_apps(self, ctx: Context, typ: TypeLike, cost: int) -> Iterator[Entry]:
        lib = self.library
        n = len(self.envs[ctx])
        for name in lib.production_names:
            args, res = lib.signature(name)
            if not args or res != typ:
                continue
            remaining = cost - lib.cost(name)
            if remaining < len(args):
                continue
            mins = [self._min_cost(ctx, a) for a in args]
            if sum(mins) > remaining:
                continue
            for combo in self._arg_combos(ctx, args, mins, remaining):
                term = App(name, tuple(e.term for e in combo))
                values = self._values_app(name, list(combo), n)
                e = self._add(ctx, typ, cost, term, values)
                if e:
                    yield e

    def _arg_combos(self, ctx: Context, args, mins, remaining) -> Iterator[tuple[Entry, ...]]:
        k = len(args)
        def rec(i: int, budget: int):
            if i == k - 1:
                for e in self._entries(ctx, args[i], budget):
                    yield (e,)
                return
            rest_min = sum(mins[i + 1:])
            for c in range(mins[i], budget - rest_min + 1):
                entries = self._entries(ctx, args[i], c)
                if not entries:
                    continue
                for tail in rec(i + 1, budget - c):
                    for e in entries:
                        yield (e,) + tail
        yield from rec(0, remaining)

    def _gen_lambdas(self, ctx: Context, typ: TypeLike, cost: int) -> Iterator[Entry]:
        if not isinstance(typ, Arrow) or typ.arguments != (OBJECT,):
            return
        inner = self._inner(ctx)
        if inner is None:
            return
        body_cost = cost - self.library.lam_cost
        for be in self._entries(inner, typ.result, body_cost):
            term = Abs(OBJECT, be.term)
            values = self._values_abs(be.term, ctx)
            e = self._add(ctx, typ, cost, term, values)
            if e:
                yield e

    # ------------------------------------------------------------------
    def programs(self) -> Iterator[Entry]:
        """Yield complete programs (C0 terms of type ObjectSet) in enumeration
        order.  Values are the output ObjectSets per scene."""
        self._started = time.perf_counter()
        top = self.contexts[-1]
        try:
            cells = [(ctx, typ) for ctx in self.contexts for typ in self.types]
            # the top cell only depends on strictly cheaper terms, so expanding it
            # first at every level reports solutions before the level's other cells
            cells.remove((top, OBJECTS))
            cells.insert(0, (top, OBJECTS))
            for cost in range(1, self.config.max_cost + 1):
                self.stats.max_cost_reached = cost
                for ctx, typ in cells:
                    if True:
                        gens = itertools.chain(self._gen_leaves(ctx, typ, cost),
                                               self._gen_apps(ctx, typ, cost),
                                               self._gen_lambdas(ctx, typ, cost))
                        cell_count = 0
                        for e in gens:
                            cell_count += 1
                            if ctx == top and typ == OBJECTS:
                                self.stats.evaluated_programs += 1
                                yield e
                            if cell_count >= self.config.max_terms_per_cell:
                                self.stats.cell_caps_hit += 1
                                break
            self.stats.termination_reason = "max_cost"
        except _Budget:
            self.stats.budget_exhausted = True
        finally:
            self.stats.seconds = time.perf_counter() - self._started
