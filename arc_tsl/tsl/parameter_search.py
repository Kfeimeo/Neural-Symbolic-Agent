"""Complete learned abstraction calls by synthesizing their varying arguments.

This bounded pilot supports an invented call at the program root, with ground
(non-function) parameter types. It considers bounded combinations of rewritten
Wake calls across training pairs, ordered by total cost. Identical arguments stay fixed; other
arguments are synthesized from their witnessed value vector over ALL pairs.
These sufficient constraints are deliberately conservative: other successful
parameter values or other Wake witnesses may be missed. No test data, reference
programs, new primitives, or task identifiers enter this module.
"""
from __future__ import annotations

import time
import heapq
from dataclasses import dataclass, field

from ..dsa.types import OBJECTS
from ..ml.ast import App, Prim, Term
from ..ml.types import Arrow
from ..synthesis.enumerator import EnumerationConfig, EnumerationStats, Enumerator
from ..synthesis.evaluator import ERR, evaluate
from ..synthesis.frontier import Frontier, Solution
from ..synthesis.grammar import Library
from ..synthesis.search import Pair, SearchResult, _accept
from .local_library import rewrite_with_library


def _ranked_assignments(options, library):
    """Lazy k-best Cartesian product, avoiding exponential materialization."""
    def score(indices):
        return sum(library.description_length(pool[i], False) for pool, i in zip(options, indices))
    first = (0,) * len(options)
    queue, seen = [(score(first), first)], {first}
    while queue:
        cost, indices = heapq.heappop(queue)
        yield cost, tuple(pool[i] for pool, i in zip(options, indices))
        for axis, pool in enumerate(options):
            if indices[axis] + 1 >= len(pool):
                continue
            next_indices = indices[:axis] + (indices[axis] + 1,) + indices[axis + 1:]
            if next_indices not in seen:
                seen.add(next_indices)
                heapq.heappush(queue, (score(next_indices), next_indices))


def _named_assignments(name, options, library):
    for cost, calls in _ranked_assignments(options, library):
        yield cost, name, calls


@dataclass
class _Template:
    name: str
    args: list[Term | None]
    targets: dict[int, tuple]
    types: dict
    limits: dict[int, int]
    rejected: bool = False
    found: dict[int, Term] = field(default_factory=dict)

    def program(self):
        args = tuple(self.found[i] if a is None else a for i, a in enumerate(self.args))
        return App(self.name, args) if args else Prim(self.name)


def parameter_search(pairs: list[Pair], library: Library, frontiers: list[list[Term]],
                     config: EnumerationConfig, max_templates: int = 64) -> tuple[SearchResult, dict]:
    """Search only argument expressions, with a shared state/time budget.

    ``max_cost`` bounds the completed call, including the fixed skeleton.
    Frontiers must retain their original pair positions (including empties).
    Unsupported templates return a diagnostic rather than silently falling
    back to a full search with a fresh budget.
    """
    started = time.perf_counter()
    if max_templates < 1:
        raise ValueError("max_templates must be positive")
    stats, frontier = EnumerationStats(), Frontier(1)
    diagnostics = {"strategy": "witness_constrained_parameters", "templates": [],
                   "parameter_expressions": 0, "complete_program_checks": 0,
                   "witness_program_checks": 0, "cell_caps_hit": 0,
                   "witness_assignments_considered": 0, "templates_truncated": False,
                   "max_templates": max_templates}
    templates = []
    reason = "no_applicable_template"
    enum = None
    stream = None

    def expired():
        return time.perf_counter() - started >= config.time_limit_seconds

    def verifies(program):
        values = [evaluate(program, library, (p.scene.objects,)) for p in pairs]
        return _accept(values, pairs, [p.output for p in pairs])

    def finish():
        nonlocal stats
        if stream is not None:
            stream.close()
        if enum is not None:
            stats = enum.stats
        for template, detail in zip(templates, diagnostics["templates"]):
            detail["matched_parameters"] = {str(i): str(p) for i, p in template.found.items()}
        diagnostics["cell_caps_hit"] = stats.cell_caps_hit
        stats.evaluated_programs = diagnostics["complete_program_checks"]
        stats.seconds = time.perf_counter() - started
        stats.termination_reason = reason
        stats.budget_exhausted = reason in ("time_limit", "max_expanded_states")
        first = frontier.best
        return SearchResult(frontier, stats, first.order if first else None,
                            first.expanded_states if first else None,
                            stats.seconds if first else None, stats.seconds, reason), diagnostics

    def check_ready(template):
        if template.rejected or len(template.found) != len(template.targets):
            return False
        program = template.program()
        cost = library.description_length(program, uniform=False)
        if cost > config.max_cost:
            template.rejected = True
            return False
        diagnostics["complete_program_checks"] += 1
        if library.infer(program, (OBJECTS,)) == OBJECTS and verifies(program):
            frontier.add(Solution(program, cost, library.description_length(program),
                                  diagnostics["complete_program_checks"],
                                  enum.stats.expanded_states if enum else 0))
            return True
        template.rejected = True
        return False

    if config.time_limit_seconds <= 0:
        reason = "time_limit"
        return finish()
    if config.max_expanded_states <= 0:
        reason = "max_expanded_states"
        return finish()
    if not pairs or len(frontiers) != len(pairs) or any(not f for f in frontiers):
        diagnostics["inapplicable_reason"] = "requires a nonempty Wake frontier for every pair"
        return finish()
    rewritten = [[rewrite_with_library(library, p) for p in f] for f in frontiers]
    assignment_streams = []
    for name, abstraction in library.abstractions.items():
        if expired():
            reason = "time_limit"
            return finish()
        if abstraction.result != OBJECTS:
            continue
        options = []
        for pair, f in zip(pairs, rewritten):
            matches = [p for p in f if isinstance(p, (App, Prim)) and p.name == name]
            valid_calls = []
            for call in matches:
                diagnostics["witness_program_checks"] += 1
                value = evaluate(call, library, (pair.scene.objects,))
                if _accept([value], [pair], [pair.output]):
                    valid_calls.append(call)
            matches = valid_calls
            if not matches:
                break
            options.append(sorted(set(matches), key=lambda p: (library.description_length(p, False), str(p))))
        if len(options) == len(pairs):
            assignment_streams.append(_named_assignments(name, options, library))
    seen_templates = set()
    for _, name, calls in heapq.merge(*assignment_streams, key=lambda item: (item[0], item[1])):
        if diagnostics["witness_assignments_considered"] >= max_templates:
            diagnostics["templates_truncated"] = True
            break
        diagnostics["witness_assignments_considered"] += 1
        if expired():
            reason = "time_limit"
            return finish()
        abstraction = library.abstractions[name]
        valid = True
        if not calls:
            continue
        args, targets, types = [], {}, {}
        for i, typ in enumerate(abstraction.param_types):
            expressions = [p.args[i] for p in calls]
            if all(e == expressions[0] for e in expressions):
                args.append(expressions[0])
                continue
            if isinstance(typ, Arrow):
                valid = False
                break
            values = tuple(evaluate(e, library, (p.scene.objects,)) for e, p in zip(expressions, pairs))
            if any(v is ERR for v in values):
                valid = False
                break
            args.append(None)
            targets[i], types[i] = values, typ
        if not valid:
            continue
        template_key = (name, tuple(args), tuple(targets.items()))
        if template_key in seen_templates:
            continue
        seen_templates.add(template_key)
        fixed_cost = library.cost(name) + sum(library.description_length(a, False) for a in args if a is not None)
        limits = {i: config.max_cost - fixed_cost - (len(targets) - 1) for i in targets}
        template = _Template(name, args, targets, types, limits)
        templates.append(template)
        diagnostics["templates"].append({"abstraction": name, "witness_calls": [str(p) for p in calls],
                                         "varying_parameters": list(targets), "fixed_cost": fixed_cost,
                                         "parameter_types": {str(i): str(t) for i, t in types.items()},
                                         "parameter_cost_limits": limits})
        if check_ready(template):
            reason = "frontier_complete"
            return finish()
    if not templates:
        return finish()
    goals = {}
    for t in templates:
        for i, typ in t.types.items():
            goals[typ] = max(goals.get(typ, 0), t.limits[i])
    if not goals or max(goals.values()) < 1:
        reason = "max_cost"
        return finish()
    if expired():
        reason = "time_limit"
        return finish()
    from dataclasses import replace
    remaining = replace(config, time_limit_seconds=max(0, config.time_limit_seconds - (time.perf_counter() - started)))
    enum = Enumerator(library, [p.scene.objects for p in pairs], remaining)
    stream = enum.expressions(goals, demand_driven=True)
    for typ, entry in stream:
        diagnostics["parameter_expressions"] += 1
        if expired():
            reason = "time_limit"
            return finish()
        values = tuple(entry.values)
        for template in templates:
            if template.rejected:
                continue
            for i, target in template.targets.items():
                if i not in template.found and template.types[i] == typ and entry.cost <= template.limits[i] and values == target:
                    template.found[i] = entry.term
            if check_ready(template):
                reason = "frontier_complete"
                diagnostics["parameter_programs"] = {str(i): str(p) for i, p in template.found.items()}
                return finish()
    reason = enum.stats.termination_reason
    return finish()
