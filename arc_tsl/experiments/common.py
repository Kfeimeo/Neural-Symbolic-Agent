"""Shared CLI plumbing for the experiment scripts."""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path

from ..arc.grid import load_arc_task
from ..ontology.instance import ExtractionConfig
from ..synthesis.enumerator import EnumerationConfig
from ..tsl.pipeline import PipelineConfig, supported

DEFAULT_DATA = Path("data/arc/training")
DEFAULT_OUT = Path("results/arc_tsl")


def add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--data", type=Path, default=DEFAULT_DATA, help="directory of ARC task JSON files")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT / "latest", help="output directory")
    p.add_argument("--tasks", type=int, default=10, help="number of tasks to select deterministically")
    p.add_argument("--seed", type=int, default=0, help="seed for the deterministic task selection")
    p.add_argument("--task-ids", type=str, default=None, help="comma-separated explicit task ids (overrides --tasks)")
    p.add_argument("--in-scope-only", action="store_true",
                   help="fill the selection with tasks whose train outputs have the input shape")
    p.add_argument("--max-cost", type=int, default=10)
    p.add_argument("--max-states", type=int, default=300_000)
    p.add_argument("--time-limit", type=float, default=60.0)
    p.add_argument("--wake-max-cost", type=int, default=None, help="defaults to --max-cost")
    p.add_argument("--wake-max-states", type=int, default=None, help="defaults to --max-states")
    p.add_argument("--wake-time-limit", type=float, default=None, help="defaults to --time-limit")
    p.add_argument("--lambda-depth", type=int, default=2)
    p.add_argument("--max-context-bindings", type=int, default=128)
    p.add_argument("--connectivity", type=int, default=8, choices=[4, 8])
    p.add_argument("--background", type=str, default="color0", choices=["color0", "most_frequent"])
    p.add_argument("--same-color-only", action="store_true")
    p.add_argument("--wake-top-k", type=int, default=1)
    p.add_argument("--max-abstractions", type=int, default=3)
    p.add_argument("--max-arity", type=int, default=3)
    p.add_argument("--unused-cost", type=int, default=2)
    p.add_argument("--workers", type=int, default=1)


def pipeline_config(args) -> PipelineConfig:
    full = EnumerationConfig(args.max_cost, args.max_states, args.time_limit, args.lambda_depth,
                             max_context_bindings=args.max_context_bindings)
    wake = EnumerationConfig(args.wake_max_cost or args.max_cost, args.wake_max_states or args.max_states,
                             args.wake_time_limit or args.time_limit, args.lambda_depth,
                             max_context_bindings=args.max_context_bindings)
    return PipelineConfig(ExtractionConfig(args.connectivity, args.background, args.same_color_only),
                          wake, full, args.wake_top_k, args.max_abstractions, args.max_arity, args.unused_cost)


def select_tasks(data: Path, n: int, seed: int, in_scope_only: bool = False, task_ids: str | None = None) -> list[str]:
    """Deterministic selection: sorted ids, seeded shuffle, first n (optionally
    skipping tasks outside v0.1 expressivity by a structural shape test)."""
    if task_ids:
        return [t.strip() for t in task_ids.split(",") if t.strip()]
    ids = sorted(f[:-5] for f in os.listdir(data) if f.endswith(".json"))
    random.Random(seed).shuffle(ids)
    if not in_scope_only:
        return ids[:n]
    out = []
    for tid in ids:
        if supported(load_arc_task(data / f"{tid}.json")["train"])[0]:
            out.append(tid)
        if len(out) == n:
            break
    return out


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)


def read_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_parallel(fn, items, workers: int):
    if workers <= 1:
        return [fn(x) for x in items]
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fn, items))


def stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")
