"""Paired full-task and leave-one-training-pair-out evaluation in fresh processes.

Protocol and source hashes are frozen before dispatch. No fold reuses a library,
Wake frontier, or selected program from another fold. Validation is diagnostic,
not used to choose the full-task program. Test labels are scored only after fit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from dataclasses import replace

from ..arc.grid import load_arc_task
from ..ontology.instance import ExtractionConfig
from ..synthesis.enumerator import EnumerationConfig
from ..tsl.pipeline import PipelineConfig, run_baseline, run_tsl
from .common import add_common_args, pipeline_config, read_json, select_tasks, write_json
from .evaluation import evaluate_test
from .resources import peak_rss_bytes

ARMS = ("baseline", "parameters", "demand_single", "diverse")


def arm_config(config: PipelineConfig, arm: str) -> PipelineConfig:
    """Preregistered factorial controls: old Wake, demand Wake, then diversity."""
    if arm not in ARMS:
        raise ValueError(f"unknown arm: {arm}")
    diverse = arm == "diverse"
    return replace(config, wake_top_k=5 if diverse else 1, wake_diverse=diverse,
                   wake_demand_driven=arm in ("demand_single", "diverse"),
                   wake=replace(config.wake, oe_representatives=2 if diverse else 1),
                   full=replace(config.full, oe_representatives=1))


def split_pairs(train, heldout_index):
    if heldout_index is None:
        return list(train), []
    if len(train) < 2 or not 0 <= heldout_index < len(train):
        raise ValueError("leave-one-out requires at least two pairs and a valid index")
    return [p for i, p in enumerate(train) if i != heldout_index], [train[heldout_index]]


def decode_config(payload):
    payload = dict(payload)
    payload["extraction"] = ExtractionConfig(**payload["extraction"])
    payload["wake"] = EnumerationConfig(**payload["wake"])
    payload["full"] = EnumerationConfig(**payload["full"])
    return PipelineConfig(**payload)


def run_worker(job):
    started, cpu_started = time.perf_counter(), time.process_time()
    task = load_arc_task(job["data_path"])
    train, heldout = split_pairs(task["train"], job["heldout_index"])
    config = decode_config(job["config"])
    solve_started, solve_cpu = time.perf_counter(), time.process_time()
    if job["arm"] == "baseline":
        record = run_baseline(train, config)
    else:
        record = run_tsl(train, config, parameter_completion=True)
    solve_wall, solve_cpu = time.perf_counter() - solve_started, time.process_time() - solve_cpu
    # Freeze the selected program before reading validation/test labels for scoring.
    chosen = record.get("expanded_program") or record.get("program")
    frozen_hash = hashlib.sha256(chosen.encode("utf-8")).hexdigest() if chosen else None
    score_started = time.perf_counter()
    training_score = evaluate_test(record, train, config.extraction)
    evaluation_pairs = task["test"] if job["heldout_index"] is None else heldout
    score = evaluate_test(record, evaluation_pairs, config.extraction)
    stats = record.get("search") or record.get("rewake") or {}
    result = {"task_id": job["task_id"], "arm": job["arm"], "heldout_index": job["heldout_index"],
              "train_indices": [i for i in range(len(task["train"])) if i != job["heldout_index"]],
              "evaluation_kind": "task_test" if job["heldout_index"] is None else "leave_one_training_pair_out",
              "config": job["config"], "record": record, "training_evaluation": training_score,
              "evaluation": score, "frozen_program_sha256": frozen_hash,
              "total_expanded_states": record.get("total_expanded_states", stats.get("expanded_states", 0)),
              "resources": {"solve_wall_seconds": solve_wall, "solve_cpu_seconds": solve_cpu,
                            "scoring_wall_seconds": time.perf_counter() - score_started,
                            "worker_wall_seconds": time.perf_counter() - started,
                            "worker_cpu_seconds": time.process_time() - cpu_started,
                            "peak_rss_bytes": peak_rss_bytes(),
                            "memory_scope": "fresh worker lifetime OS peak; includes interpreter/imports; not parent memory"}}
    # The selection cannot be mutated by the scorer.
    assert chosen == (record.get("expanded_program") or record.get("program"))
    return result


def aggregate(rows):
    summary = {}
    for arm in dict.fromkeys(r["arm"] for r in rows):
        full = [r for r in rows if r["arm"] == arm and r["heldout_index"] is None]
        folds = [r for r in rows if r["arm"] == arm and r["heldout_index"] is not None]
        def block(items):
            scored = [r for r in items if r["evaluation"]["all_test_correct"] is not None]
            fitted = [r for r in scored if r["training_evaluation"]["all_test_correct"] is True]
            return {"runs": len(items), "scored_runs": len(scored),
                    "training_consistent": sum(r["training_evaluation"]["all_test_correct"] is True for r in items),
                    "correct": sum(r["evaluation"]["all_test_correct"] for r in scored),
                    "accuracy": sum(r["evaluation"]["all_test_correct"] for r in scored) / len(scored) if scored else None,
                    "generalization_given_fit": sum(r["evaluation"]["all_test_correct"] for r in fitted) / len(fitted) if fitted else None,
                    "generalization_given_fit_denominator": len(fitted),
                    "total_expanded_states": sum(r["total_expanded_states"] for r in items),
                    "solve_wall_seconds": sum(r["resources"]["solve_wall_seconds"] for r in items),
                    "solve_cpu_seconds": sum(r["resources"]["solve_cpu_seconds"] for r in items),
                    "job_wall_seconds": sum(r.get("job_wall_seconds", 0) for r in items),
                    "max_peak_rss_bytes": max((r["resources"]["peak_rss_bytes"] for r in items), default=None)}
        summary[arm] = {"full": block(full), "loo": block(folds)}
    return summary


def paired(rows, left="demand_single", right="diverse"):
    indexed = {(r["task_id"], r["heldout_index"], r["arm"]): r for r in rows}
    pairs = []
    for task, fold, arm in indexed:
        if arm != left or (task, fold, right) not in indexed:
            continue
        a, b = indexed[(task, fold, left)], indexed[(task, fold, right)]
        pairs.append({"task_id": task, "heldout_index": fold,
                      "left_correct": a["evaluation"]["all_test_correct"],
                      "right_correct": b["evaluation"]["all_test_correct"],
                      "states_delta_right_minus_left": b["total_expanded_states"] - a["total_expanded_states"],
                      "solve_wall_delta_right_minus_left": b["resources"]["solve_wall_seconds"] - a["resources"]["solve_wall_seconds"]})
    return {"left": left, "right": right, "pairs": pairs}


def write_report(out, rows, protocol):
    summary = aggregate(rows)
    write_json(out / "summary.json", {"arms": summary, "paired_diversity": paired(rows),
                                      "paired_wake_search": paired(rows, "parameters", "demand_single")})
    lines = ["# ARC-TSL generalization and total-cost diagnostic", "",
             "The known case is a development diagnostic. Its test answer was already inspected before this work; this is not an untouched benchmark claim.", "",
             "Each leave-one-out fold relearns Wake, compression and parameters from the remaining training pairs. Fold results do not select or modify the full-task program.", "",
             "| Arm / split | Train-consistent | Held-out correct | Total states | Solve wall (s) | Solve CPU (s) | Peak RSS (MiB) |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for arm, blocks in summary.items():
        for kind, b in blocks.items():
            if not b["runs"]:
                continue
            lines.append(f"| {arm} / {kind} | {b['training_consistent']}/{b['runs']} | {b['correct']}/{b['scored_runs']} | "
                         f"{b['total_expanded_states']} | {b['solve_wall_seconds']:.3f} | {b['solve_cpu_seconds']:.3f} | {b['max_peak_rss_bytes']/2**20:.1f} |")
    lines += ["", "`full` scores the task test; `loo` sums separate leave-one-training-pair-out runs. States and time are summed; memory is the maximum per fresh worker. Unsolved labeled runs count as incorrect. Missing labels are excluded, not scored as failures.", "",
              "## Full-task frontiers and selected programs", ""]
    for r in rows:
        if r["heldout_index"] is not None:
            continue
        rec = r["record"]
        lines += [f"### {r['task_id']} / {r['arm']}", "",
                  f"- Wake frontier sizes: {rec.get('wake', {}).get('frontier_sizes', [])}",
                  f"- Wake structure counts: {rec.get('wake', {}).get('frontier_structural_counts', [])}",
                  f"- Learned abstractions: {rec.get('sleep', {}).get('num_abstractions', 0)}",
                  f"- Test correct: {r['evaluation']['all_test_correct']}",
                  "", "```", rec.get("program") or "No training-consistent program returned.", "```", ""]
    lines += ["## Protocol and limits", "",
              "- All arms use the same per-run total state/time budget, DSL and extraction policy; all Wake cost is charged. The conditional prior is unchanged.",
              "- `parameters`: prior single-witness Wake; `demand_single`: demand-driven Wake with one solution; `diverse`: demand-driven Wake, K=5 distinct structures and at most 2 representatives per observational class. `baseline` is fixed-DSL full-task enumeration.",
              "- Diversity preserves operator/lambda/variable structure and ignores literal-only changes. These are syntactic alternatives, not proven semantic equivalence classes.",
              "- Parameter synthesis considers up to 64 cost-ordered witness assignments across pairs. Truncation, frontier sizes, additional OE representatives and cell caps are recorded.",
              "- Each arm/fold runs sequentially in a new process, with no cross-fold caches. OS peak RSS includes the interpreter and imports. Parent launch/transport time is recorded separately.",
              "- Search time limits are cooperative. `resources.solve_wall_seconds` includes the complete fit; scoring and job startup/transport are reported separately. Compression and witness validation are included in time, not enumeration-state counts.",
              "- Validation budgets are additional diagnostic expenditure, not free inference. Full-task and validation totals are reported separately above; sum both to obtain study cost.",
              "- No test/validation label or reference program enters synthesis or candidate selection. Fold scores are descriptive and correlated; one task does not establish a general accuracy gain.",
              "", "See `protocol.json` for frozen settings and source/data hashes and `runs/*/result.json` for programs, predictions, metrics and failures.", ""]
    (out / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--worker":
        job_path = Path(argv[1])
        write_json(job_path.with_name("result.json"), run_worker(read_json(job_path)))
        return
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    parser.set_defaults(task_ids="63613498", max_cost=24, max_states=300_000, time_limit=90,
                        wake_max_cost=10, wake_time_limit=20, total_budget=True,
                        out=Path("results/arc_tsl/frontier_generalization"))
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--loo", action="store_true")
    parser.add_argument("--loo-arms", default="parameters,demand_single,diverse")
    args = parser.parse_args(argv)
    arms, loo_arms = args.arms.split(","), args.loo_arms.split(",")
    if any(a not in ARMS for a in arms + loo_arms):
        raise SystemExit("unknown arm")
    ids = select_tasks(args.data, args.tasks, args.seed, args.in_scope_only, args.task_ids)
    base = pipeline_config(args)
    configs = {arm: arm_config(base, arm).to_dict() for arm in arms}
    sources = sorted(Path("arc_tsl").rglob("*.py"))
    protocol = {"task_ids": ids, "arms": arms, "loo": args.loo, "loo_arms": loo_arms,
                "configs": configs, "selection": "first training-consistent completion; no validation/test reranking",
                "known_test_exposure": ["63613498"],
                "source_sha256": {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                "data_sha256": {tid: hashlib.sha256((args.data / f"{tid}.json").read_bytes()).hexdigest() for tid in ids}}
    args.out.mkdir(parents=True, exist_ok=True)
    protocol_path = args.out / "protocol.json"
    if protocol_path.exists() and read_json(protocol_path) != protocol:
        raise SystemExit("Existing protocol/source differs; choose a new output directory.")
    write_json(protocol_path, protocol)
    rows = []
    for tid in ids:
        task = load_arc_task(args.data / f"{tid}.json")
        folds = [None] + (list(range(len(task["train"]))) if args.loo and len(task["train"]) > 1 else [])
        for fold in folds:
            for arm in arms:
                if fold is not None and arm not in loo_arms:
                    continue
                name = f"{tid}_{arm}_{'full' if fold is None else 'loo' + str(fold)}"
                folder = args.out / "runs" / name
                job_path = folder / "job.json"
                job = {"task_id": tid, "arm": arm, "heldout_index": fold,
                       "data_path": str((args.data / f"{tid}.json").resolve()), "config": configs[arm]}
                write_json(job_path, job)
                result_path = folder / "result.json"
                if not result_path.exists():
                    started = time.perf_counter()
                    proc = subprocess.run([sys.executable, "-m", "arc_tsl.experiments.generalization", "--worker", str(job_path)],
                                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                    elapsed = time.perf_counter() - started
                    if proc.returncode:
                        (folder / "failure.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
                        raise RuntimeError(f"Worker {name} failed; see {folder / 'failure.log'}")
                    row = read_json(result_path)
                    row["job_wall_seconds"] = elapsed
                    row["startup_transport_wall_seconds"] = max(0, elapsed - row["resources"]["worker_wall_seconds"])
                    write_json(result_path, row)
                row = read_json(result_path)
                rows.append(row)
                write_report(args.out, rows, protocol)
                print(f"{name}: train={row['training_evaluation']['all_test_correct']} heldout={row['evaluation']['all_test_correct']} "
                      f"states={row['total_expanded_states']} seconds={row['resources']['solve_wall_seconds']:.2f}", flush=True)
    write_json(args.out / "complete.json", {"runs": len(rows), "status": "complete"})


if __name__ == "__main__":
    main()
