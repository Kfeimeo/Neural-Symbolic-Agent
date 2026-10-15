"""Train faithful DreamCoder on real ARC with the Grid DSL and parallel Wake."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from arc_tsl.arc.grid import load_arc_task
from faithful.lib import (Kernel, KernelPool, ExploreCompress, ECConfig, SearchConfig,
                          DreamConfig, RecognitionConfig, OriginalCompressor,
                          StitchCompressor, NoCompression, ast)
from faithful.lib.domains.arc_shapes import ARCShapesDomain


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument("--data", type=Path, default=Path("data/arc/training"))
    p.add_argument("--task-ids", required=True, help="comma-separated tasks for EC learning")
    p.add_argument("--heldout-task-ids", default="", help="unseen tasks; demonstrations used only at final solve")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--workers", type=int, default=1, help="task-parallel Wake processes (one persistent pool)")
    p.add_argument("--kernel-threads", type=int, default=1,
                   help="kernel processes in the parent for rescoring, recognition summaries and MDL accounting")
    p.add_argument("--rounds", type=int, default=2)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--limit", type=int, default=3000, help="candidate limit per task per Wake")
    p.add_argument("--max-states", type=int, default=100000)
    p.add_argument("--max-size", type=int, default=33)
    p.add_argument("--maximum-depth", type=int, default=14)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--dreams", type=int, default=20)
    p.add_argument("--dream-seeding", choices=["sequential", "independent"], default="sequential",
                   help="independent: one child seed per draw, so --workers / --kernel-threads parallelize dreams")
    p.add_argument("--recognition-steps", type=int, default=30)
    p.add_argument("--compressor", choices=["original", "stitch", "none"], default="original")
    p.add_argument("--kernel-timeout", type=float, default=120, help="seconds per kernel call; timeout fails the run")
    args = p.parse_args()
    if args.rounds < 1 or args.workers < 1 or args.kernel_threads < 1 or args.kernel_timeout <= 0:
        p.error("rounds, workers, kernel-threads and kernel-timeout must be positive")
    ids = [x.strip() for x in args.task_ids.split(",") if x.strip()]
    heldout = [x.strip() for x in args.heldout_task_ids.split(",") if x.strip()]
    if not ids or len(set(ids + heldout)) != len(ids + heldout):
        p.error("task lists must be nonempty (training), unique and disjoint")
    if args.out.exists() and any(args.out.iterdir()):
        p.error("output directory must be empty; use a new directory for each run")
    domain = ARCShapesDomain()
    raw = {tid: load_arc_task(args.data / f"{tid}.json") for tid in ids + heldout}
    tasks = {tid: domain.unary_task(tid, raw[tid]["train"]) for tid in raw}
    config = ECConfig(rounds=args.rounds, seed=args.seed, workers=args.workers, output=args.out,
                      search=SearchConfig(limit=args.limit, max_states=args.max_states,
                                          max_size=args.max_size, maximum_depth=args.maximum_depth,
                                          top_k=args.top_k),
                      dream=DreamConfig(enabled=args.dreams > 0, draws=args.dreams, seeding=args.dream_seeding),
                      recognition=RecognitionConfig(enabled=args.recognition_steps > 0,
                                                    steps=args.recognition_steps))
    compressors = {"original": OriginalCompressor, "stitch": StitchCompressor, "none": NoCompression}
    repo = Path(__file__).resolve().parents[2]
    hashes = {str(f.relative_to(repo)): hashlib.sha256(f.read_bytes()).hexdigest()
              for root in (repo / "arc_tsl", repo / "faithful/lib", repo / "faithful/haskell",
                           repo / "faithful/python", repo / "faithful/compression", repo / "faithful/versionspace")
              for f in root.rglob("*") if f.suffix in (".py", ".hs")}
    args.out.mkdir(parents=True, exist_ok=True)
    def save(name, value):
        (args.out / name).write_text(json.dumps(value, indent=2), encoding="utf-8")
    save("protocol.json", {"config": config.to_dict(), "compressor": args.compressor,
                          "training_task_ids": ids, "heldout_task_ids": heldout,
                          "source_sha256": hashes,
                          "task_sha256": {tid: hashlib.sha256((args.data / f"{tid}.json").read_bytes()).hexdigest()
                                          for tid in raw}})
    started = time.perf_counter()
    kernel = (KernelPool(args.kernel_threads, timeout=args.kernel_timeout) if args.kernel_threads > 1
              else Kernel(timeout=args.kernel_timeout))
    with kernel, ExploreCompress(domain, kernel, compressors[args.compressor](), config) as ec:
        save("kernel.json", {"path": str(kernel.executable), "kernel_threads": args.kernel_threads,
                              "sha256": hashlib.sha256(kernel.executable.read_bytes()).hexdigest()})
        history = ec.run([tasks[tid] for tid in ids])
        # Selection sees demonstration pairs only, including for unseen tasks.
        solved = ec.solve(list(tasks.values()))
        frozen = {tid: (frontier["entries"][0]["program"] if frontier["entries"] else None)
                  for tid, (frontier, _) in zip(tasks, solved)}
        save("selected_programs.json", frozen)
        from dataclasses import asdict
        fit_wall = time.perf_counter() - started
        score_started = time.perf_counter()
        rows = []
        for tid, (_, trace) in zip(tasks, solved):
            program = frozen[tid]
            predictions = domain.evaluate_batch(program, [[x] for x, _ in raw[tid]["test"]]) if program else [None] * len(raw[tid]["test"])
            rows.append({"task_id": tid, "split": "heldout" if tid in heldout else "training",
                         "program": program, "program_text": ast.show_program(program) if program else None,
                         "program_sha256": hashlib.sha256(json.dumps(program, sort_keys=True).encode()).hexdigest() if program else None,
                         "fit": asdict(trace),
                         "test": [{"prediction": pred, "correct": pred == target if target is not None else None}
                                  for pred, (_, target) in zip(predictions, raw[tid]["test"])]})
        total_states = sum(t.expanded_states for r in history for t in r.traces) + sum(t.expanded_states for _, t in solved)
        report = {"tasks": rows, "rounds": len(history), "total_wake_states": total_states,
                  "fit_wall_seconds": fit_wall, "scoring_seconds": time.perf_counter() - score_started,
                  "total_wall_seconds": time.perf_counter() - started,
                  "cost_scope": "wall includes startup, Wake, compression, dream and recognition; states count Wake only"}
        save("report.json", report)
        print(json.dumps({"report": str(args.out / "report.json"), "total_wake_states": total_states,
                          "fit_wall_seconds": fit_wall,
                          "tasks": [{"id": r["task_id"], "train_solved": r["program"] is not None,
                                     "test_correct": [x["correct"] for x in r["test"]]} for r in rows]}, indent=2))


if __name__ == "__main__":
    main()
