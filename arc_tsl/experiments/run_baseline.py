"""Baseline A: fixed Base_{ML+DSA} search of one program for all IO pairs.

    python -m arc_tsl.experiments.run_baseline --tasks 10 --out results/arc_tsl/smoke
"""
from __future__ import annotations

import argparse
import sys
import time

from ..arc.grid import load_arc_task
from ..tsl.pipeline import run_baseline
from .common import add_common_args, pipeline_config, run_parallel, select_tasks, stamp, write_json


def _one(job):
    tid, path, args = job
    cfg = pipeline_config(args)
    task = load_arc_task(path)
    t0 = time.perf_counter()
    rec = run_baseline(task["train"], cfg)
    rec.update(task_id=tid, wall_seconds=time.perf_counter() - t0)
    print(f"[baseline] {tid} {rec['status']} states={(rec.get('search') or {}).get('expanded_states')} "
          f"program={rec.get('program')}", file=sys.stderr, flush=True)
    return rec


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    add_common_args(p)
    args = p.parse_args(argv)
    ids = select_tasks(args.data, args.tasks, args.seed, args.in_scope_only, args.task_ids)
    jobs = [(tid, args.data / f"{tid}.json", args) for tid in ids]
    records = run_parallel(_one, jobs, args.workers)
    payload = {"condition": "baseline", "created": stamp(), "config": pipeline_config(args).to_dict(),
               "seed": args.seed, "task_ids": ids, "records": records}
    write_json(args.out / "baseline.json", payload)
    solved = sum(r["status"] == "SOLVED" for r in records)
    print(f"baseline: {solved}/{len(records)} solved -> {args.out / 'baseline.json'}")


if __name__ == "__main__":
    main()
