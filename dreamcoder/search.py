"""Uniform-cost typed hole expansion, with an admissible completion bound."""
from __future__ import annotations

import heapq
import itertools
import math
import time
from dataclasses import dataclass, field
from typing import Iterator

from .grammar import Grammar
from .language import Program, Type
from .tasks import Task


@dataclass(frozen=True)
class Hole:
    type: Type


@dataclass(frozen=True)
class Partial:
    name: str
    children: tuple[Partial | Hole, ...] = ()


@dataclass
class EnumerationStats:
    expanded_states: int = 0
    enumerated_nodes: int = 0
    budget_exhausted: bool = False


def enumerate_programs(grammar: Grammar, max_size: int = 7, max_states: int = 100000,
                       stats: EnumerationStats | None = None) -> Iterator[Program]:
    if max_size < 1 or max_states < 1:
        raise ValueError("Size and state budgets must be positive")
    stats = stats if stats is not None else EnumerationStats()
    language = grammar.language
    types = {language.input_type, language.output_type}
    for p in language.primitives.values():
        types.update(p.signature.arguments)
        types.add(p.signature.result)
    minimum = {t: (0.0 if t == language.input_type else math.inf) for t in types}
    for _ in range(len(types) + 1):
        for p in language.primitives.values():
            minimum[p.signature.result] = min(minimum[p.signature.result],
                -grammar.log_probabilities[p.name] + sum(minimum[t] for t in p.signature.arguments))

    def info(tree):
        if isinstance(tree, Hole):
            return minimum[tree.type], 1
        children = [info(c) for c in tree.children]
        return ((0 if tree.name == "$input" else -grammar.log_probabilities[tree.name]) +
                sum(x[0] for x in children), 1 + sum(x[1] for x in children))

    def replace(tree):
        if isinstance(tree, Hole):
            if tree.type == language.input_type:
                yield Partial("$input")
            for p in language.primitives.values():
                if p.signature.result == tree.type:
                    yield Partial(p.name, tuple(Hole(t) for t in p.signature.arguments))
            return
        for i, child in enumerate(tree.children):
            if contains_hole(child):
                for alternative in replace(child):
                    yield Partial(tree.name, tree.children[:i] + (alternative,) + tree.children[i+1:])
                return

    def contains_hole(tree):
        return isinstance(tree, Hole) or any(contains_hole(c) for c in tree.children)

    def complete(tree):
        return Program(tree.name, tuple(complete(c) for c in tree.children))

    counter = itertools.count()
    queue = [(minimum[language.output_type], next(counter), Hole(language.output_type))]
    while queue and stats.expanded_states < max_states:
        _, _, tree = heapq.heappop(queue)
        stats.expanded_states += 1
        if not contains_hole(tree):
            stats.enumerated_nodes += 1
            yield complete(tree)
        else:
            for new in replace(tree):
                cost, size = info(new)
                if size <= max_size and math.isfinite(cost):
                    heapq.heappush(queue, (cost, next(counter), new))
    stats.budget_exhausted = bool(queue)


@dataclass(frozen=True)
class Solution:
    program: Program
    log_prior: float
    log_likelihood: float = 0.0

    @property
    def log_posterior(self) -> float:
        return self.log_prior + self.log_likelihood


@dataclass
class Frontier:
    task: Task
    capacity: int
    solutions: list[Solution] = field(default_factory=list)

    def add(self, solution: Solution) -> None:
        if solution.program not in [s.program for s in self.solutions]:
            self.solutions.append(solution)
            self.solutions.sort(key=lambda s: (-s.log_posterior, str(s.program)))
            del self.solutions[self.capacity:]


@dataclass
class SearchResult:
    frontier: Frontier
    enumerated_nodes: int
    expanded_states: int
    seconds: float
    first_solution_nodes: int | None
    budget_exhausted: bool
    termination_reason: str = "unknown"


def search(task: Task, grammar: Grammar, top_k: int = 3, max_nodes: int = 3000,
           max_size: int = 7, max_states: int = 100000) -> SearchResult:
    if top_k < 1 or max_nodes < 1:
        raise ValueError("Budgets and top_k must be positive")
    started = time.perf_counter()
    frontier = Frontier(task, top_k)
    stats = EnumerationStats()
    first = None
    reason = "space_exhausted"
    for program in enumerate_programs(grammar, max_size, max_states, stats):
        if task.accepts(grammar.language, program):
            frontier.add(Solution(program, grammar.log_prior(program)))
            if first is None:
                first = stats.enumerated_nodes
            if len(frontier.solutions) == top_k:
                reason = "frontier_complete"
                break
        if stats.enumerated_nodes >= max_nodes:
            stats.budget_exhausted = True
            reason = "max_nodes"
            break
    if stats.budget_exhausted and reason == "space_exhausted":
        reason = "max_states"
    return SearchResult(frontier, stats.enumerated_nodes, stats.expanded_states,
                        time.perf_counter() - started, first, stats.budget_exhausted, reason)
