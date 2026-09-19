from __future__ import annotations

import math
import random
from collections import Counter
from statistics import mean, median

from ..domains.grid.canonical import canonical, depth
from ..language import Language
from ..search import SearchResult
from .benchmark import bucket, fingerprint


def record(result: SearchResult, language: Language, probes, recognition_seconds: float = 0.0) -> dict:
    task = result.frontier.task
    gt = task.ground_truth
    expanded_gt = language.expand(gt)
    target = fingerprint(language, gt, probes)
    solutions = []
    for s in result.frontier.solutions:
        expanded = language.expand(s.program)
        solutions.append({"program": str(s.program), "expanded": str(expanded),
                          "canonical": str(canonical(expanded)), "log_prior": s.log_prior,
                          "expanded_depth": depth(expanded), "canonical_depth": depth(canonical(expanded)),
                          "expanded_ast_size": expanded.size,
                          "log_likelihood": s.log_likelihood,
                          "raw_exact": s.program == gt,
                          "expanded_exact": expanded == expanded_gt,
                          "canonical_recovery": canonical(expanded) == canonical(expanded_gt),
                          "behavioral_recovery": fingerprint(language, s.program, probes) == target,
                          "uses_library": any(language.primitives[n].definition is not None for n in s.program.symbols()),
                          "valid_training_io": task.accepts(language, s.program)})
    return {"task": task.name, "ground_truth": str(gt), "bucket": bucket(expanded_gt),
            "depth": depth(expanded_gt), "ast_size": expanded_gt.size,
            "solved": bool(solutions), "solutions": solutions,
            "exact_program_recovery": any(s["raw_exact"] for s in solutions),
            "expanded_ast_recovery": any(s["expanded_exact"] for s in solutions),
            "canonical_program_recovery": any(s["canonical_recovery"] for s in solutions),
            "behavioral_recovery": any(s["behavioral_recovery"] for s in solutions),
            "solved_using_library": any(s["uses_library"] and s["behavioral_recovery"] for s in solutions),
            "enumerated_nodes": result.enumerated_nodes, "expanded_states": result.expanded_states,
            "first_solution_nodes": result.first_solution_nodes,
            "search_seconds": result.seconds, "recognition_seconds": recognition_seconds,
            "total_seconds": result.seconds+recognition_seconds,
            "budget_exhausted": result.budget_exhausted, "termination_reason": result.termination_reason}


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {"task_count": 0}
    first = [r["first_solution_nodes"] for r in rows if r["first_solution_nodes"] is not None]
    result = {"task_count": n,
              "mean_enumerated_nodes": mean(r["enumerated_nodes"] for r in rows),
              "median_enumerated_nodes": median(r["enumerated_nodes"] for r in rows),
              "mean_expanded_states": mean(r["expanded_states"] for r in rows),
              "mean_first_solution_nodes": mean(first) if first else None,
              "first_solution_sample_count": len(first),
              "mean_censored_first_solution_nodes": mean(r["first_solution_nodes"] if r["first_solution_nodes"] is not None else r["enumerated_nodes"] for r in rows),
              "mean_search_time": mean(r["search_seconds"] for r in rows),
              "mean_recognition_time": mean(r["recognition_seconds"] for r in rows),
              "mean_total_time": mean(r["total_seconds"] for r in rows),
              "budget_exhaustion_rate": mean(r["budget_exhausted"] for r in rows),
              "unsolved_budget_exhaustion_rate": mean(r["budget_exhausted"] and not r["solved"] for r in rows),
              "frontier_complete_rate": mean(r["termination_reason"] == "frontier_complete" for r in rows),
              "termination_reasons": dict(Counter(r["termination_reason"] for r in rows)),
              "mean_frontier_size": mean(len(r["solutions"]) for r in rows)}
    for output, source in [("solve_rate", "solved"), ("exact_program_recovery_rate", "exact_program_recovery"),
                           ("expanded_ast_recovery_rate", "expanded_ast_recovery"),
                           ("canonical_program_recovery_rate", "canonical_program_recovery"),
                           ("behavioral_recovery_rate", "behavioral_recovery"),
                           ("library_solution_rate", "solved_using_library")]:
        result[output] = mean(r[source] for r in rows)
    return result


def paired_compare(correct: list[dict], other: list[dict], seed: int = 0) -> dict:
    """Paired node bootstrap and exact one-sided discordant-pair sign test.

    Node difference is budget-dependent and NOT a substitute for solve rate.
    """
    assert [r["task"] for r in correct] == [r["task"] for r in other]
    differences = [b["enumerated_nodes"]-a["enumerated_nodes"] for a, b in zip(correct, other)]
    wins = sum(a["solved"] and not b["solved"] for a, b in zip(correct, other))
    losses = sum(b["solved"] and not a["solved"] for a, b in zip(correct, other))
    discordant = wins+losses
    p = sum(math.comb(discordant, k) for k in range(wins, discordant+1)) / 2**discordant if discordant else 1.0
    rng = random.Random(seed)
    means = sorted(mean(rng.choices(differences, k=len(differences))) for _ in range(2000))
    return {"solve_wins": wins, "solve_losses": losses, "solve_sign_test_p_one_sided": p,
            "mean_node_saving": mean(differences), "node_saving_bootstrap_95_ci": [means[50], means[1949]],
            "note": "Paired task bootstrap; fixed trained model and benchmark, not multi-seed population inference"}


def derangement(size: int, rng: random.Random) -> list[int]:
    if size < 2:
        raise ValueError("Shuffle requires at least two tasks")
    values = list(range(size))
    # Uniformly sample permutations conditional on having no fixed points.
    while True:
        rng.shuffle(values)
        if all(i != j for i, j in enumerate(values)):
            return values
