"""Local wake: search each IO pair of one ARC task as a micro-task."""
from __future__ import annotations

from dataclasses import dataclass

from ..synthesis.enumerator import EnumerationConfig
from ..synthesis.grammar import Library
from ..synthesis.search import Pair, SearchResult, search


@dataclass
class WakeResult:
    results: list[SearchResult]

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
        return sum(r.seconds for r in self.results)

    def to_dict(self) -> dict:
        return {"pairs": [r.summary() for r in self.results],
                "solved_pairs": self.solved_pairs, "num_pairs": len(self.results),
                "total_expanded_states": self.total_expanded, "total_seconds": self.total_seconds}


def local_wake(pairs: list[Pair], library: Library, config: EnumerationConfig, top_k: int) -> WakeResult:
    return WakeResult([search([p], library, config, top_k=top_k) for p in pairs])
