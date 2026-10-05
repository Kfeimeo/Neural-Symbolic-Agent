"""TSL_tau = (Base_{ML+DSA}, A_tau, theta_tau).

A TSL is an ordinary ``Library`` whose ``abstractions`` are the task-local
A_tau and whose ``costs`` are the optional task-local production weights
theta_tau.  This module provides expansion / contraction helpers and the
theta_tau estimator used by the reweighting ablation.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ..ml.ast import Abs, App, Hole, Prim, Term, Var, subterms
from ..synthesis.grammar import Abstraction, Library
from .compression import Candidate, frontier_mdl, rewrite, total_mdl


def abstraction_to_candidate(a: Abstraction) -> Candidate:
    k = a.arity

    def go(t: Term, depth: int) -> Term:
        if isinstance(t, Var):
            if t.index >= depth:
                return Hole(k - 1 - (t.index - depth))
            return t
        if isinstance(t, App):
            return App(t.name, tuple(go(x, depth) for x in t.args))
        if isinstance(t, Abs):
            return Abs(t.param_type, go(t.body, depth + 1))
        return t

    return Candidate(go(a.body, 0), a.param_types, a.result)


def rewrite_with_library(library: Library, t: Term) -> Term:
    """Rewrite a base-language term with every abstraction of ``library`` in
    the order they were invented (earlier ones may be used by later bodies)."""
    for name, a in library.abstractions.items():
        t = rewrite(t, abstraction_to_candidate(a), name)
    return t


def used_productions(t: Term) -> set[str]:
    return {s.name for s in subterms(t) if isinstance(s, (Prim, App))}


def best_programs(library: Library, frontiers: list[list[Term]]) -> list[Term]:
    return [min(F, key=lambda p: (library.description_length(p), str(p))) for F in frontiers if F]


def prune_unused(library: Library, frontiers: list[list[Term]]) -> tuple[Library, list[str]]:
    """Contraction rule 1: drop abstractions not used by any frontier's best
    program (transitively through other abstraction bodies)."""
    removed: list[str] = []
    while True:
        used: set[str] = set()
        for p in best_programs(library, frontiers):
            used |= used_productions(p)
        # closure through bodies
        changed = True
        while changed:
            changed = False
            for name in list(used):
                if name in library.abstractions:
                    more = used_productions(library.abstractions[name].body) - used
                    if more:
                        used |= more
                        changed = True
        unused = [n for n in library.abstractions if n not in used]
        if not unused:
            return library, removed
        for n in unused:
            library = library.without_abstraction(n)
            removed.append(n)
        # the frontiers may still mention removed names; expand those programs
        frontiers = [[_expand_names(library, p, removed) for p in F] for F in frontiers]


def _expand_names(library: Library, t: Term, names: list[str]) -> Term:
    if not any(n in used_productions(t) for n in names):
        return t
    # fall back: fully expand then re-rewrite with what is left
    base = Library(library.primitives)
    return rewrite_with_library(library, _full_expand(library, t))


def _full_expand(library: Library, t: Term) -> Term:
    return library.expand(t)


def contract(library: Library, expanded_frontiers: list[list[Term]]) -> tuple[Library, list[str]]:
    """Contraction rule 2: drop any abstraction whose removal does not increase
    total MDL (recomputed by re-rewriting the expanded frontiers)."""
    removed: list[str] = []
    current = total_mdl(library, [[rewrite_with_library(library, p) for p in F] for F in expanded_frontiers])
    for name in list(library.abstractions):
        trial = library.without_abstraction(name)
        # abstractions whose bodies mention `name` cannot survive its removal
        dependents = [n for n, a in trial.abstractions.items() if name in used_productions(a.body)]
        for d in dependents:
            trial = trial.without_abstraction(d)
        mdl = total_mdl(trial, [[rewrite_with_library(trial, p) for p in F] for F in expanded_frontiers])
        if mdl <= current:
            library, current = trial, mdl
            removed.append(name)
            removed.extend(dependents)
    return library, removed


@dataclass
class ThetaConfig:
    unused_cost: int = 2


def fit_costs(library: Library, programs: list[Term], config: ThetaConfig = ThetaConfig()) -> dict[str, int]:
    """theta_tau: quantised task-local production prior.  Productions that
    occur in at least one wake-frontier program keep cost 1; the others get
    ``unused_cost``.  Invented abstractions always cost 1."""
    counts: Counter[str] = Counter()
    for p in programs:
        for s in subterms(p):
            if isinstance(s, (Prim, App)):
                counts[s.name] += 1
    costs: dict[str, int] = {}
    for name in library.production_names:
        if library.is_invented(name):
            costs[name] = 1
        else:
            costs[name] = 1 if counts[name] > 0 else config.unused_cost
    return costs
