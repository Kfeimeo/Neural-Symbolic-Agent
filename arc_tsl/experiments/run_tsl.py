"""Method B (and ablations): local wake -> local compression -> TSL_tau -> re-wake.

    python -m arc_tsl.experiments.run_tsl --tasks 10 --out results/arc_tsl/smoke
    python -m arc_tsl.experiments.run_tsl --conditions tsl,reweight,tsl_reweight ...

All conditions of one task share the same local wake (deterministic).
"""
from __future__ import annotations

import argparse
import sys
import time

from ..arc.grid import load_arc_task
from ..language import base_library
from ..tsl.local_wake import local_wake
from ..tsl.pipeline import make_pairs, run_tsl, supported
from .common import add_common_args, pipeline_config, run_parallel, select_tasks, stamp, write_json

CONDITIONS = {"tsl": (True, False), "reweight": (False, True), "tsl_reweight": (True, True)}


def _one(job):
    tid, path, args, conditions = job
    cfg = pipeline_config(args)
    task = load_arc_task(path)
    base = base_library()
    out = {"task_id": tid, "num_train_pairs": len(task["train"]), "conditions": {}}
    ok, why = supported(task["train"])
    if not ok:
        for c in conditions:
            out["conditions"][c] = {"status": "UNSUPPORTED", "reason": why, "condition": c,
                                    "num_train_pairs": len(task["train"])}
        print(f"[tsl] {tid} UNSUPPORTED ({why})", file=sys.stderr, flush=True)
        return out
    t0 = time.perf_counter()
    wake = local_wake(make_pairs(task["train"], cfg.extraction), base, cfg.wake, cfg.wake_top_k)
    out["wake_seconds"] = time.perf_counter() - t0
    cache: dict = {}
    for c in conditions:
        abstractions, reweight = CONDITIONS[c]
        t1 = time.perf_counter()
        rec = run_tsl(task["train"], cfg, abstractions, reweight, base, wake, cache)
        rec["wall_seconds"] = time.perf_counter() - t1 + out["wake_seconds"]
        out["conditions"][c] = rec
        print(f"[{c}] {tid} {rec['status']} wake={wake.solved_pairs}/{len(task['train'])} "
              f"A={rec.get('sleep', {}).get('num_abstractions')} states={rec.get('rewake', {}).get('expanded_states')} "
              f"program={rec.get('program')}", file=sys.stderr, flush=True)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    add_common_args(p)
    p.add_argument("--conditions", type=str, default="tsl,reweight,tsl_reweight")
    args = p.parse_args(argv)
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    for c in conditions:
        if c not in CONDITIONS:
            raise SystemExit(f"unknown condition {c}")
    ids = select_tasks(args.data, args.tasks, args.seed, args.in_scope_only, args.task_ids)
    jobs = [(tid, args.data / f"{tid}.json", args, conditions) for tid in ids]
    records = run_parallel(_one, jobs, args.workers)
    payload = {"conditions": conditions, "created": stamp(), "config": pipeline_config(args).to_dict(),
               "seed": args.seed, "task_ids": ids, "records": records}
    write_json(args.out / "tsl.json", payload)
    for c in conditions:
        solved = sum(r["conditions"][c]["status"] == "SOLVED" for r in records)
        print(f"{c}: {solved}/{len(records)} solved")
    print(f"-> {args.out / 'tsl.json'}")


if __name__ == "__main__":
    main()
