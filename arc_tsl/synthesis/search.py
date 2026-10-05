"""Task-level search: enumerate programs and accept those whose rendered
output equals every target grid."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

from ..arc.grid import Grid
from ..arc.parse import Scene
from ..arc.render import render
from ..ml.ast import Term
from .enumerator import EnumerationConfig, EnumerationStats, Enumerator
from .evaluator import ERR
from .frontier import Frontier, Solution
from .grammar import Library


@dataclass(frozen=True)
class Pair:
    scene: Scene
    output: Grid


@dataclass
class SearchResult:
    frontier: Frontier
    stats: EnumerationStats
    first_solution_nodes: int | None      # evaluated programs up to first solution
    first_solution_states: int | None     # expanded states up to first solution
    first_solution_seconds: float | None
    seconds: float
    termination_reason: str

    @property
    def solved(self) -> bool:
        return bool(self.frontier.solutions)

    def summary(self) -> dict:
        best = self.frontier.best
        return {
            "solved": self.solved,
            "expanded_states": self.stats.expanded_states,
            "retained_terms": self.stats.retained_terms,
            "evaluated_programs": self.stats.evaluated_programs,
            "equivalent_terms": self.stats.equivalent_terms,
            "dead_terms": self.stats.dead_terms,
            "first_solution_nodes": self.first_solution_nodes,
            "first_solution_states": self.first_solution_states,
            "first_solution_seconds": self.first_solution_seconds,
            "seconds": self.seconds,
            "termination_reason": self.termination_reason,
            "max_cost_reached": self.stats.max_cost_reached,
            "best_program": str(best.program) if best else None,
            "best_program_length": best.description_length if best else None,
            "frontier": [str(s.program) for s in self.frontier.solutions],
        }


def _accept(values, pairs, targets) -> bool:
    for value, pair, target in zip(values, pairs, targets):
        if value is ERR:
            return False
        if render(value, pair.scene.grid_shape, pair.scene.background) != target:
            return False
    return True


def search(pairs: list[Pair], library: Library, config: EnumerationConfig = EnumerationConfig(),
           top_k: int = 1) -> SearchResult:
    started = time.perf_counter()
    scenes = [p.scene.objects for p in pairs]
    targets = [p.output for p in pairs]
    def is_solution(values) -> bool:
        return _accept(values, pairs, targets)

    enumerator = Enumerator(library, scenes, config, is_solution=is_solution if top_k > 1 else None)
    frontier = Frontier(top_k)
    first_nodes = first_states = first_seconds = None
    reason = None
    for entry in enumerator.programs():
        if _accept(entry.values, pairs, targets):
            stats = enumerator.stats
            sol = Solution(entry.term, entry.cost, library.description_length(entry.term),
                           stats.evaluated_programs, stats.expanded_states)
            if frontier.add(sol) and first_nodes is None:
                first_nodes, first_states = stats.evaluated_programs, stats.expanded_states
                first_seconds = time.perf_counter() - started
            if frontier.full:
                reason = "frontier_complete"
                break
    stats = enumerator.stats
    if reason is None:
        reason = stats.termination_reason
    return SearchResult(frontier, stats, first_nodes, first_states, first_seconds,
                        time.perf_counter() - started, reason)
