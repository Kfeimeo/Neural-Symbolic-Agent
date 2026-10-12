"""Opt-in Grid -> Grid search; all parsing choices share one search budget."""
import time
from dataclasses import replace

from ..dsa.shapes import sample_objects
from ..dsa.types import GRID
from ..language import grid_library
from .diversity import structure_key
from .enumerator import EnumerationConfig, Enumerator
from .frontier import Frontier, Solution
from .search import SearchResult


def search_grids(train, library=None, config=None, top_k=1, diverse=False):
    started = time.perf_counter()
    library = grid_library() if library is None else library
    config = EnumerationConfig() if config is None else config
    if not train:
        raise ValueError("at least one training pair is required")
    scenes, targets = zip(*train)
    accept = lambda values: tuple(values) == targets
    enum = Enumerator(library, scenes, config, is_solution=accept if top_k > 1 else None,
                      root_type=GRID, object_samples=sample_objects)
    # Object extraction / lambda binding preparation uses the same wall budget.
    enum.config = replace(config, time_limit_seconds=max(
        0.0, config.time_limit_seconds - (time.perf_counter() - started)))
    frontier = Frontier(top_k, structure=(lambda p: structure_key(p, library)) if diverse else None)
    first_nodes = first_states = first_seconds = None
    reason = None
    stream = enum.expressions({GRID: config.max_cost}, demand_driven=True)
    try:
        for _, entry in stream:
            if accept(entry.values):
                stats = enum.stats
                solution = Solution(entry.term, entry.cost, library.description_length(entry.term),
                                    stats.evaluated_programs, stats.expanded_states)
                if frontier.add(solution) and first_nodes is None:
                    first_nodes, first_states = stats.evaluated_programs, stats.expanded_states
                    first_seconds = time.perf_counter() - started
                if frontier.full:
                    reason = "frontier_complete"
                    break
    finally:
        stream.close()
    return SearchResult(frontier, enum.stats, first_nodes, first_states, first_seconds,
                        time.perf_counter() - started, reason or enum.stats.termination_reason,
                        len({structure_key(s.program, library) for s in frontier.solutions}))
