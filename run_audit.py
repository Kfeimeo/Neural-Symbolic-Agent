"""Reproduce V1, freeze training, then test previously unseen compositions.

All test selection is independent of search outcomes. No hyperparameter tuning,
fallback seed selection, or assertion that an ablation must win is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import time
from collections import Counter
from pathlib import Path

import torch

from dreamcoder.abstraction import RepeatedSubprogramCompressor
from dreamcoder.audit.benchmark import (BUCKETS, ProgramSplit, diverse_grid, fingerprint,
                                       io_hash, program_record, stress_tasks, transfer_tasks)
from dreamcoder.audit.metrics import derangement, paired_compare, record, summarize
from dreamcoder.audit.reporting import write_summary
from dreamcoder.domains.grid import make_language, sample_grid, synthetic_tasks
from dreamcoder.domains.grid.canonical import canonical
from dreamcoder.domains.grid.features import encode_task
from dreamcoder.dreaming import TrainingPair, dream, replay
from dreamcoder.ec import wake
from dreamcoder.grammar import Grammar
from dreamcoder.language import INPUT, Program
from dreamcoder.recognition import RecognitionModel
from dreamcoder.search import search
from dreamcoder.tasks import Task


def no_metadata(task: Task) -> Task:
    return Task("anonymous", task.examples)


def save_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def task_record(task: Task) -> dict:
    return {"name": task.name, "ground_truth": program_record(task.ground_truth) if task.ground_truth else None,
            "examples": [{"input": e.input, "output": e.output} for e in task.examples], "io_hash": io_hash(task)}


def train_v1(seed: int, dreams: int, epochs: int, output: Path):
    base = Grammar.uniform(make_language())
    snapshot = dict(base.log_probabilities)
    train = synthetic_tasks(base.language, random.Random(seed), 36, "train")
    print("[train] Original 36-task Wake; fixed V1 settings", flush=True)
    initial = wake(train, base, top_k=3, max_nodes=1500, max_size=7)
    corpus = [r.frontier.solutions[0].program for r in initial if r.frontier.solutions]
    compressed = RepeatedSubprogramCompressor().compress(base, corpus)
    learned = compressed.grammar
    fantasies = dream(learned, sample_grid, random.Random(seed+100), count=dreams)
    real = replay([r.frontier for r in initial])
    def rewrite(p):
        for name in compressed.added:
            if learned.language.expand(p) == learned.language.expand(learned.language.primitives[name].definition):
                return Program(name, (INPUT,))
        return Program(p.name, tuple(rewrite(c) for c in p.arguments))
    replay_learned = [TrainingPair(no_metadata(p.task), rewrite(p.program)) for p in real]
    learned_pairs = fantasies + replay_learned*5
    base_pairs = [TrainingPair(no_metadata(p.task), learned.language.expand(p.program)) for p in learned_pairs]
    models, training_history = [], []
    for tag, grammar, pairs in (("C", base, base_pairs), ("D", learned, learned_pairs)):
        print(f"[train] Recognition {tag}, {len(pairs)} pairs, {epochs} fixed epochs", flush=True)
        torch.manual_seed(seed)
        model = RecognitionModel(list(grammar.language.primitives), len(encode_task(train[0])[0]), encode_task)
        history = model.fit(pairs, seed=seed, epochs=epochs)
        models.append(model)
        training_history.append(history)
        torch.save({"state_dict": model.state_dict(), "names": model.names,
                    "feature_count": len(encode_task(train[0])[0])}, output/f"model_{tag}.pt")
    assert base.log_probabilities == snapshot
    assert len(base.language.primitives) == 24
    assert all(abs(v+math.log(24)) < 1e-12 for v in snapshot.values())
    assert all(p.definition is None for p in base.language.primitives.values())
    assert all(p.task.accepts(learned.language, p.program) for p in fantasies+replay_learned)
    assert all(r.frontier.task.accepts(base.language, s.program) for r in initial for s in r.frontier.solutions)
    metadata = {"base_uniform_and_unchanged": True, "base_prior_snapshot": snapshot,
                "learned_prior": learned.log_probabilities,
                "learned_primitives": {n: str(learned.language.primitives[n].definition) for n in compressed.added},
                "base_library_size": len(base.language.primitives), "learned_library_size": len(learned.language.primitives),
                "mdl_before": compressed.description_length_before, "mdl_after": compressed.description_length_after,
                "mdl_corpus_before": sum(p.size for p in corpus),
                "mdl_corpus_after": sum(p.size for p in compressed.programs),
                "mdl_definition_cost": sum(learned.language.primitives[n].definition.size+1 for n in compressed.added),
                "map_program_counts": dict(Counter(map(str, corpus))),
                "dream_count": len(fantasies), "replay_count": len(real),
                "dreams_valid": True, "replay_valid": True,
                "training_losses": training_history,
                "training_frontiers": [{"task": r.frontier.task.name, "solutions": [str(s.program) for s in r.frontier.solutions],
                                        "enumerated_nodes": r.enumerated_nodes} for r in initial]}
    save_json(output/"training_data.json", {"tasks": [task_record(t) for t in train],
             "fantasies": [{"task": task_record(p.task), "program": program_record(p.program)} for p in fantasies],
             "replay": [{"task": p.task.name, "program": program_record(p.program)} for p in real]})
    # Unique supervised programs, including all frontier alternatives, not just MAP.
    all_programs = list(set([t.ground_truth for t in train] + [p.program for p in learned_pairs]))
    all_inputs = {e.input for t in train for e in t.examples} | {e.input for p in fantasies for e in p.task.examples}
    return base, learned, models, train, corpus, all_programs, all_inputs, metadata


def separate_inputs(tasks, forbidden, language, seed):
    from dreamcoder.audit.benchmark import make_task
    rng = random.Random(seed)
    result = []
    for t in tasks:
        for _ in range(1000):
            if not any(e.input in forbidden for e in t.examples):
                break
            t = make_task(language, t.ground_truth, rng, t.name)
        else:
            raise RuntimeError("Cannot obtain input-disjoint task")
        result.append(t)
    return result


def evaluate_suite(name, tasks, base, learned, models, corpus, probes, options, seed, output, shuffle_repeats):
    print(f"[{name}] {len(tasks)} tasks; budget {options}", flush=True)
    grammars, inference = {}, {}
    for label, grammar, model in (("C", base, models[0]), ("D", learned, models[1])):
        grammars[label], inference[label] = [], []
        for task in tasks:
            start = time.perf_counter()
            grammars[label].append(model.contextual_grammar(no_metadata(task), grammar))
            inference[label].append(time.perf_counter()-start)
    # Isolate the original B-vs-A confound using two extra static controls.
    configs = {"A": [base]*len(tasks), "B": [learned]*len(tasks), **grammars,
               "base_fitted": [base.fit(corpus)]*len(tasks),
               "library_uniform": [Grammar.uniform(learned.language)]*len(tasks)}
    permutations = {}
    for repeat in range(shuffle_repeats):
        perm = derangement(len(tasks), random.Random(seed+repeat))
        permutations[str(repeat)] = perm
        for target in ("C", "D"):
            label = f"{target}_shuffle_{repeat}"
            configs[label] = [grammars[target][j] for j in perm]
            inference[label] = [inference[target][j] for j in perm]
    report = {"budget": options, "shuffle_permutations": permutations,
              "configurations": {}, "buckets": {}, "frontiers": {}, "comparisons": {}}
    for label, contexts in configs.items():
        rows = []
        for i, (task, grammar) in enumerate(zip(tasks, contexts)):
            result = search(task, grammar, **options)
            row = record(result, grammar.language, probes, inference.get(label, [0.0]*len(tasks))[i])
            assert all(s["valid_training_io"] for s in row["solutions"])
            assert row["enumerated_nodes"] <= options["max_nodes"]
            assert row["expanded_states"] <= options["max_states"]
            rows.append(row)
            if (i+1) % 12 == 0:
                print(f"  {label}: {i+1}/{len(tasks)}", flush=True)
        report["frontiers"][label] = rows
        report["configurations"][label] = summarize(rows)
        report["buckets"][label] = {b: summarize([r for r in rows if r["bucket"] == b]) for b in BUCKETS}
        m = report["configurations"][label]
        print(f"  {label:18s} solve={m['solve_rate']:.1%}, nodes={m['mean_enumerated_nodes']:.1f}, exhausted={m['budget_exhaustion_rate']:.1%}", flush=True)
        save_json(output/f"{name}.json", report)
    for repeat in range(shuffle_repeats):
        for target in ("C", "D"):
            other = f"{target}_shuffle_{repeat}"
            report["comparisons"][f"{target}_vs_{other}"] = paired_compare(report["frontiers"][target], report["frontiers"][other], seed)
    for a, b in (("D", "A"), ("D", "B"), ("D", "C"), ("library_uniform", "A"), ("B", "base_fitted")):
        report["comparisons"][f"{a}_vs_{b}"] = paired_compare(report["frontiers"][a], report["frontiers"][b], seed)
    save_json(output/f"{name}.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--dreams", type=int, default=600)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--per-bucket", type=int, default=12)
    parser.add_argument("--transfer-per-direction", type=int, default=6)
    parser.add_argument("--max-nodes", type=int, default=600)
    parser.add_argument("--max-states", type=int, default=6000)
    parser.add_argument("--shuffle-repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("results/audit"))
    args = parser.parse_args()
    if min(args.dreams, args.epochs, args.per_bucket, args.transfer_per_direction,
           args.max_nodes, args.max_states, args.shuffle_repeats) < 1:
        parser.error("Counts and budgets must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    torch.manual_seed(args.seed)
    torch.use_deterministic_algorithms(True)
    base, learned, models, train, corpus, training_programs, training_inputs, training = train_v1(
        args.seed, args.dreams, args.epochs, args.output)
    selection_probes = [diverse_grid(random.Random(args.seed+2000+i)) for i in range(32)]
    evaluation_probes = [diverse_grid(random.Random(args.seed+4000+i)) for i in range(64)]
    split = ProgramSplit(learned.language, training_programs, selection_probes)
    print("[benchmark] Build program-disjoint compositions AFTER freezing models", flush=True)
    # Transfer cases are reserved first, so stress examples cannot consume them.
    transfer, directions = transfer_tasks(split, next(iter(training["learned_primitives"])),
                                         args.seed+500, args.transfer_per_direction)
    stress = stress_tasks(split, args.seed+600, args.per_bucket)
    transfer = separate_inputs(transfer, training_inputs, learned.language, args.seed+700)
    stress = separate_inputs(stress, training_inputs, learned.language, args.seed+800)
    original = synthetic_tasks(base.language, random.Random(args.seed+1), 24, "original")
    frozen = {"stress": [task_record(t) for t in stress], "transfer": [task_record(t) for t in transfer],
              "transfer_directions": dict(zip([t.name for t in transfer], directions)),
              "original": [task_record(t) for t in original],
              "selection_probes": selection_probes, "evaluation_probes": evaluation_probes}
    save_json(args.output/"benchmark.json", frozen)
    benchmark_hash = hashlib.sha256((args.output/"benchmark.json").read_bytes()).hexdigest()
    separation = {}
    for label, tasks in (("original", original), ("stress", stress), ("transfer", transfer)):
        separation[label] = {
            "task_count": len(tasks),
            "raw_ast_overlap_with_wake_train": sum(t.ground_truth in [x.ground_truth for x in train] for t in tasks),
            "canonical_overlap_with_all_training": sum(canonical(t.ground_truth) in split.training_canonical for t in tasks),
            "behavior_overlap_with_all_training_32_probes": sum(fingerprint(learned.language, t.ground_truth, selection_probes) in split.training_behavior for t in tasks),
            "input_overlap_with_all_training": sum(e.input in training_inputs for t in tasks for e in t.examples),
            "io_task_overlap_with_wake_train": sum(io_hash(t) in {io_hash(x) for x in train} for t in tasks)}
        if label != "original":
            assert all(v == 0 for k, v in separation[label].items() if "overlap" in k)
    options = dict(top_k=3, max_nodes=args.max_nodes, max_states=args.max_states, max_size=33)
    assert all(t.ground_truth.size <= options["max_size"] for t in stress+transfer)
    manifest = {"seed": args.seed, "torch_version": torch.__version__, "training": training,
                "args": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
                "benchmark_sha256": benchmark_hash, "separation": separation,
                "selection_rejections": split.rejections,
                "evaluation_note": "No test-outcome-based selection or tuning; fixed original V1 training; novel-composition stress is out of distribution"}
    save_json(args.output/"manifest.json", manifest)
    for name, tasks in (("original", original), ("transfer", transfer), ("stress", stress)):
        budgets = dict(top_k=3, max_nodes=1500, max_states=100000, max_size=7) if name == "original" else options
        evaluate_suite(name, tasks, base, learned, models, corpus, evaluation_probes, budgets,
                       args.seed+900, args.output, args.shuffle_repeats)
    assert all(abs(v+math.log(24)) < 1e-12 for v in base.log_probabilities.values())
    write_summary(args.output)
    print(f"Audit complete: {args.output.resolve()}", flush=True)


if __name__ == "__main__":
    main()
