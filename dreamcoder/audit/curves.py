"""Budget snapshots of the existing enumerator; no change to search policy.

Tasks sharing exactly the same grammar reuse its deterministic stream. Each task
sees exactly the prefix it would see in an independent search. Time is amortized
instrumentation, not a claim of independent per-task wall-clock speed.
"""
from ..grammar import Grammar
from ..search import EnumerationStats, Frontier, SearchResult, Solution, enumerate_programs
from ..tasks import Task


def search_curves(tasks: list[Task], grammar: Grammar, budgets: tuple[int, ...], *,
                  top_k: int = 3, max_size: int = 33, max_states: int = 300000) -> list[dict[int, SearchResult]]:
    if not budgets or tuple(sorted(set(budgets))) != budgets or budgets[0] < 1 or top_k < 1:
        raise ValueError("Budgets must be sorted, unique and positive")
    frontiers = [Frontier(t, top_k) for t in tasks]
    first = [None]*len(tasks)
    results = [{} for _ in tasks]
    active = set(range(len(tasks)))
    stats = EnumerationStats()
    def snapshot(i, reason):
        return SearchResult(Frontier(tasks[i], top_k, list(frontiers[i].solutions)),
                            stats.enumerated_nodes, stats.expanded_states, 0.0, first[i],
                            reason in ("max_nodes", "max_states"), reason)
    for program in enumerate_programs(grammar, max_size=max_size, max_states=max_states, stats=stats):
        for i in sorted(active):
            if tasks[i].accepts(grammar.language, program):
                frontiers[i].add(Solution(program, grammar.log_prior(program)))
                if first[i] is None:
                    first[i] = stats.enumerated_nodes
                if len(frontiers[i].solutions) == top_k:
                    done = snapshot(i, "frontier_complete")
                    for budget in budgets:
                        results[i].setdefault(budget, done)
                    active.remove(i)
            if i in active and stats.enumerated_nodes in budgets:
                results[i][stats.enumerated_nodes] = snapshot(i, "max_nodes")
        if not active or stats.enumerated_nodes >= budgets[-1]:
            break
    for i in active:
        reason = "max_states" if stats.budget_exhausted else "space_exhausted"
        done = snapshot(i, reason)
        for budget in budgets:
            results[i].setdefault(budget, done)
    return results
