"""Local wake: search each IO pair of one ARC task as a micro-task."""
from __future__ import annotations

import time
from dataclasses import dataclass, replace

from ..synthesis.enumerator import EnumerationConfig, EnumerationStats
from ..synthesis.frontier import Frontier
from ..synthesis.grammar import Library
from ..synthesis.search import Pair, SearchResult, search


@dataclass
class WakeResult:
    results: list[SearchResult]
    elapsed_seconds: float | None = None

    @property
    def frontiers(self):
        return [r.frontier.programs() for r in self.results]

    @property
    def solved_pairs(self) -> int:
        return sum(1 for r in self.results if r.solved)

    @property
    def total_expanded(self) -> int:
        return sum(r.stats.expanded_states for r in self.results)

    @property
    def total_seconds(self) -> float:
        return self.elapsed_seconds if self.elapsed_seconds is not None else sum(r.seconds for r in self.results)

    def to_dict(self) -> dict:
        return {"pairs": [r.summary() for r in self.results],
                "solved_pairs": self.solved_pairs, "num_pairs": len(self.results),
                "total_expanded_states": self.total_expanded, "total_seconds": self.total_seconds,
                "search_seconds_sum": sum(r.seconds for r in self.results),
                "frontier_sizes": [len(r.frontier.solutions) for r in self.results],
                "frontier_structural_counts": [r.structural_count for r in self.results]}


def local_wake(pairs: list[Pair], library: Library, config: EnumerationConfig, top_k: int,
               total_config: EnumerationConfig | None = None, diverse: bool = False,
               demand_driven: bool = False) -> WakeResult:
    started, results, states = time.perf_counter(), [], 0
    for pair in pairs:
        budget = config
        if total_config is not None:
            budget = replace(config,
                             max_expanded_states=min(config.max_expanded_states, max(0, total_config.max_expanded_states - states)),
                             time_limit_seconds=min(config.time_limit_seconds, max(0, total_config.time_limit_seconds - (time.perf_counter() - started))))
        if budget.max_expanded_states <= 0 or budget.time_limit_seconds <= 0:
            stats = EnumerationStats(budget_exhausted=True, termination_reason="total_budget_exhausted")
            result = SearchResult(Frontier(top_k), stats, None, None, None, 0, stats.termination_reason)
        else:
            result = search([pair], library, budget, top_k=top_k, diverse=diverse, demand_driven=demand_driven)
        results.append(result)
        states += result.stats.expanded_states
    return WakeResult(results, time.perf_counter() - started)
