"""Frozen hidden-library benchmark; existing V1 learner, six budget prefixes."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from dataclasses import asdict
from pathlib import Path
from statistics import mean

import torch

from dreamcoder.abstraction import RepeatedSubprogramCompressor
from dreamcoder.audit.benchmark import BUCKETS, fingerprint, io_hash, program_record
from dreamcoder.audit.controlled import ControlledConfig, generate, private_record
from dreamcoder.audit.curves import search_curves
from dreamcoder.audit.distribution import (abstraction_metrics, decode, match_body, overlap,
                                          profile, rewrite_for_measurement, typed_search_growth, walk)
from dreamcoder.audit.metrics import derangement, record, summarize
from dreamcoder.domains.grid import make_language, sample_grid
from dreamcoder.domains.grid.canonical import canonical, depth
from dreamcoder.domains.grid.features import encode_task
from dreamcoder.dreaming import TrainingPair, dream, replay
from dreamcoder.grammar import Grammar
from dreamcoder.language import INPUT, Program
from dreamcoder.recognition import RecognitionModel
from dreamcoder.search import Frontier, SearchResult
from dreamcoder.tasks import Task

BUDGETS = (100, 300, 600, 1000, 3000, 10000)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def metrics(rows):
    result = summarize([{**r, "search_seconds": 0, "recognition_seconds": 0, "total_seconds": 0} for r in rows])
    for name in ("mean_search_time", "mean_recognition_time", "mean_total_time"):
        result[name] = None
    return result


def train_learner(tasks: list[Task], seed: int, exclude_dream, output: Path):
    """The learner only receives anonymous I/O. No hidden definitions or GT."""
    assert all(t.ground_truth is None for t in tasks)
    base = Grammar.uniform(make_language())
    initial = [curve[10000] for curve in search_curves(tasks, base, (10000,), max_size=33)]
    corpus = [r.frontier.solutions[0].program for r in initial if r.frontier.solutions]
    compressed = RepeatedSubprogramCompressor().compress(base, corpus)
    learned = compressed.grammar
    print(f"Training Wake: {len(corpus)}/{len(tasks)} solved; library={compressed.added}; MDL {compressed.description_length_before}->{compressed.description_length_after}", flush=True)
    real_pairs = replay([r.frontier for r in initial])
    def rewrite(p):
        for name in compressed.added:
            if p == learned.language.primitives[name].definition:
                return Program(name, (INPUT,))
        return Program(p.name, tuple(rewrite(c) for c in p.arguments))
    replay_pairs = [TrainingPair(p.task, rewrite(p.program)) for p in real_pairs]
    fantasies, rejected, attempted = [], 0, 0
    rng = random.Random(seed+100)
    while len(fantasies) < 600 and attempted < 10000:
        batch = dream(learned, sample_grid, rng, count=100)
        for pair in batch:
            attempted += 1
            if exclude_dream(learned.language.expand(pair.program)):
                rejected += 1
                continue
            # A distinct task id is only provenance; features never consume it.
            fantasies.append(TrainingPair(Task(f"fantasy_{len(fantasies)}", pair.task.examples), pair.program))
            if len(fantasies) == 600:
                break
    if len(fantasies) != 600:
        raise RuntimeError("Dream split exclusion exhausted")
    learned_pairs = fantasies + replay_pairs*5
    base_pairs = [TrainingPair(p.task, learned.language.expand(p.program)) for p in learned_pairs]
    models, histories = [], {}
    for label, grammar, pairs in (("C", base, base_pairs), ("D", learned, learned_pairs)):
        torch.manual_seed(seed)
        model = RecognitionModel(list(grammar.language.primitives), len(encode_task(tasks[0])[0]), encode_task)
        histories[label] = model.fit(pairs, seed, epochs=100)
        models.append(model)
        torch.save({"state_dict": model.state_dict(), "names": model.names,
                    "feature_count": len(encode_task(tasks[0])[0])}, output/f"model_{label}.pt")
    save(output/"learner_training.json", {
        "wake_solved": len(corpus), "wake_task_count": len(tasks),
        "frontiers": [{"task": r.frontier.task.name, "solutions": [program_record(s.program) for s in r.frontier.solutions],
                       "nodes": r.enumerated_nodes} for r in initial],
        "dream_attempted": attempted, "dream_rejected_reserved_test": rejected,
        "fantasies": [{"program": program_record(p.program),
                       "examples": [{"input": e.input, "output": e.output} for e in p.task.examples]} for p in fantasies],
        "replay_count": len(replay_pairs), "loss_histories": histories,
        "base_prior": base.log_probabilities, "learned_prior": learned.log_probabilities})
    return base, learned, models, compressed, corpus, real_pairs, fantasies


def curve_rows(curves, truth_tasks, language, benchmark):
    rows = {str(n): [] for n in BUDGETS}
    for curve, task in zip(curves, truth_tasks):
        for n, result in curve.items():
            with_truth = SearchResult(Frontier(task, result.frontier.capacity, result.frontier.solutions),
                                      result.enumerated_nodes, result.expanded_states, 0,
                                      result.first_solution_nodes, result.budget_exhausted, result.termination_reason)
            row = record(with_truth, language, benchmark.evaluation_probes)
            effective = depth(canonical(task.ground_truth))
            row.update({"raw_depth": row["depth"], "effective_depth": effective,
                        "effective_ast_size": canonical(task.ground_truth).size,
                        "bucket": BUCKETS[min((effective-1)//2, 3)],
                        "generation": benchmark.metadata.get(task.name, {}),
                        "search_seconds": None, "recognition_seconds": None, "total_seconds": None})
            rows[str(n)].append(row)
    return rows


def evaluate(tasks, truth_tasks, base, learned, models, corpus, benchmark, output):
    static = {"A": base, "B": learned, "base_fitted": base.fit(corpus), "library_uniform": Grammar.uniform(learned.language)}
    summary, contextual = {}, {}
    for key, grammar, model in (("C", base, models[0]), ("D", learned, models[1])):
        contextual[key] = [model.contextual_grammar(t, grammar) for t in tasks]
    permutation = derangement(len(tasks), random.Random(benchmark.config.seed+900))
    contextual["C_shuffle"] = [contextual["C"][i] for i in permutation]
    contextual["D_shuffle"] = [contextual["D"][i] for i in permutation]
    save(output/"shuffle.json", permutation)
    for label in (*static, *contextual):
        print(f"Calibration {label}: {len(tasks)} tasks, N={BUDGETS}", flush=True)
        start = time.perf_counter()
        if label in static:
            grammar = static[label]
            curves = search_curves(tasks, grammar, BUDGETS)
            rows = curve_rows(curves, truth_tasks, grammar.language, benchmark)
        else:
            rows = {str(n): [] for n in BUDGETS}
            for i, (task, grammar) in enumerate(zip(tasks, contextual[label])):
                curves = search_curves([task], grammar, BUDGETS)
                one = curve_rows(curves, [truth_tasks[i]], grammar.language, benchmark)
                for n in rows:
                    rows[n].extend(one[n])
                if (i+1) % 4 == 0:
                    print(f"  {label} {i+1}/{len(tasks)}", flush=True)
        summary[label] = {"budgets": {}, "wall_seconds_shared_trace_and_metrics": time.perf_counter()-start}
        for n, rs in rows.items():
            def grouped(field):
                groups = sorted({str(r["generation"].get(field)) for r in rs})
                return {g: metrics([r for r in rs if str(r["generation"].get(field)) == g]) for g in groups}
            summary[label]["budgets"][n] = {
                "overall": metrics(rs), "effective_depth_buckets": {b: metrics([r for r in rs if r["bucket"] == b]) for b in BUCKETS},
                "ast_size_buckets": {f"{lo}-{hi}": metrics([r for r in rs if lo <= r["effective_ast_size"] <= hi])
                                     for lo, hi in ((1,4),(5,8),(9,12),(13,100))},
                "difficulty": grouped("difficulty"), "reuse": grouped("reuse"), "transfer": grouped("recipe"),
                "latent": grouped("latent")}
        save(output/f"{label}_frontiers.json", rows)
        save(output/"curves.json", summary)
        print(label, [round(summary[label]["budgets"][str(n)]["overall"]["solve_rate"], 3) for n in BUDGETS], flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output", type=Path, default=Path("results/calibration"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    config = ControlledConfig(seed=args.seed)
    benchmark = generate(config)
    save(args.output/"benchmark_private.json", private_record(benchmark))
    frozen_hash = hashlib.sha256((args.output/"benchmark_private.json").read_bytes()).hexdigest()
    base_language = make_language()
    train_gt = [t.ground_truth for t in benchmark.training]
    test_gt = [t.ground_truth for t in benchmark.testing]
    split = overlap(train_gt, test_gt, base_language, benchmark.split_probes)
    split["complete_io_task_overlap"] = len({io_hash(t) for t in benchmark.training} & {io_hash(t) for t in benchmark.testing})
    split["input_overlap"] = len({e.input for t in benchmark.training for e in t.examples} & {e.input for t in benchmark.testing for e in t.examples})
    assert all(split[k] == 0 for k in ("full_program_overlap", "canonical_program_overlap", "behavioral_probe_overlap", "complete_io_task_overlap", "input_overlap"))
    assert split["shared_nontrivial_subtree_count"] > 0
    # Reserved-test collisions are censored from dreams, not used to choose test
    # tasks. This split guard runs outside the model and contains no Fi symbols.
    reserved_canonical = {canonical(p) for p in test_gt}
    reserved_behavior = {fingerprint(base_language, p, benchmark.split_probes) for p in test_gt}
    def exclude_dream(p):
        return canonical(p) in reserved_canonical or fingerprint(base_language, p, benchmark.split_probes) in reserved_behavior
    print(f"Frozen benchmark {frozen_hash}: {len(benchmark.training)} training / {len(benchmark.testing)} held out", flush=True)
    base, learned, models, compression, corpus, replay_pairs, fantasies = train_learner(
        benchmark.learner_training(), args.seed, exclude_dream, args.output)
    definitions = {n: learned.language.primitives[n].definition for n in compression.added}
    expanded_supervision = [learned.language.expand(p.program) for p in replay_pairs+fantasies]
    supervised_split = overlap(expanded_supervision, test_gt, base.language, benchmark.split_probes)
    assert all(supervised_split[k] == 0 for k in ("full_program_overlap", "canonical_program_overlap", "behavioral_probe_overlap"))
    assert len(base.language.primitives) == 24 and not any(n.startswith("F") for n in base.language.primitives)
    recovery = abstraction_metrics(definitions, benchmark.latents, base.language, benchmark.evaluation_probes)
    oracle = RepeatedSubprogramCompressor().compress(base, train_gt)
    oracle_defs = {n: oracle.grammar.language.primitives[n].definition for n in oracle.added}
    reductions = []
    for task in benchmark.testing:
        p = task.ground_truth
        methods = {}
        for label, can, param in (("native_exact_subtree", False, False), ("parameterized_capacity", False, True), ("canonical_capacity", True, True)):
            rewritten = rewrite_for_measurement(p, definitions, canonicalize=can, parameterized=param)
            original = canonical(p) if can else p
            assert all(learned.language.evaluate(rewritten, x) == base.language.evaluate(p, x) for x in benchmark.evaluation_probes)
            methods[label] = {"program": str(rewritten), "size_before": original.size, "size_after": rewritten.size,
                              "depth_before": depth(original), "depth_after": depth(rewritten),
                              "macro_calls": sum(n in definitions for n in rewritten.symbols())}
        reductions.append({"task": task.name, **methods})
    diagnostics = {"compression": {"mdl_before": compression.description_length_before, "mdl_after": compression.description_length_after,
                                   "learned": {n: str(p) for n, p in definitions.items()}, "library_size": len(learned.language.primitives)},
                   "latent_recovery": recovery,
                   "oracle_gt_diagnostic_not_used_for_learning": {"mdl_before": oracle.description_length_before, "mdl_after": oracle.description_length_after,
                                                                  "recovery": abstraction_metrics(oracle_defs, benchmark.latents, base.language, benchmark.evaluation_probes)},
                   "training_rewrite_size_reduction": sum(p.size for p in corpus)-sum(p.size for p in compression.programs),
                   "training_rewrite_mean_depth_before": mean(map(depth, corpus)) if corpus else None,
                   "training_rewrite_mean_depth_after": mean(map(depth, compression.programs)) if corpus else None,
                   "heldout_representational_capacity": reductions,
                   "split": split, "all_supervision_split": supervised_split,
                   "hidden_latents": {n: str(p) for n, p in benchmark.latents.items()},
                   "training_distribution": profile(train_gt, base.language),
                   "heldout_distribution": profile(test_gt, base.language),
                   "wake_map_distribution": profile(corpus, base.language),
                   "typed_search_growth": typed_search_growth(base.language),
                   "latent_reuse": {n: {"train_instantiations": sum(match_body(p, node) is not None for q in train_gt for node in walk(q)),
                                         "test_instantiations": sum(match_body(p, node) is not None for q in test_gt for node in walk(q))}
                                    for n, p in benchmark.latents.items()}}
    save(args.output/"diagnostics.json", diagnostics)
    curves = evaluate(benchmark.learner_testing(), benchmark.testing, base, learned, models, corpus, benchmark, args.output)
    assert frozen_hash == hashlib.sha256((args.output/"benchmark_private.json").read_bytes()).hexdigest()
    save(args.output/"summary.json", {"seed": args.seed, "benchmark_sha256": frozen_hash,
         "config": asdict(config), "budgets": BUDGETS, "max_states": 300000, "max_size": 33, "top_k": 3,
         "timing_note": "Exact per-task enumeration prefixes; common grammar streams reused. Per-task times intentionally null.",
         "diagnostics": diagnostics, "configurations": curves})
    print(f"Saved {args.output/'summary.json'}", flush=True)


if __name__ == "__main__":
    main()
