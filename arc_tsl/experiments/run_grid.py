"""Minimal grid-DSL experiment: fit train, freeze program, then score test."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

from ..arc.grid import load_arc_task
from ..language import grid_library
from ..synthesis.enumerator import EnumerationConfig
from ..synthesis.evaluator import ERR, evaluate
from ..synthesis.grid_search import search_grids


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument("--task", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--max-cost", type=int, default=12)
    p.add_argument("--max-states", type=int, default=300000)
    p.add_argument("--time-limit", type=float, default=60)
    args = p.parse_args()
    task = load_arc_task(args.task)
    config = EnumerationConfig(max_cost=args.max_cost, max_expanded_states=args.max_states,
                               time_limit_seconds=args.time_limit)
    library = grid_library()
    source = Path(__file__).resolve().parents[1]
    hashes = {str(f.relative_to(source)): hashlib.sha256(f.read_bytes()).hexdigest()
              for f in sorted(source.rglob("*.py"))}
    cpu = time.process_time()
    result = search_grids(task["train"], library, config)
    cpu = time.process_time() - cpu
    best = result.frontier.best
    program = best.program if best else None
    frozen_hash = hashlib.sha256(str(program).encode()).hexdigest() if program else None
    scored = []
    score_started = time.perf_counter()
    for grid, target in task["test"]:
        prediction = evaluate(program, library, (grid,)) if program else ERR
        scored.append({"prediction": None if prediction is ERR else prediction,
                       "correct": prediction == target if target is not None else None})
    payload = {"language": "grid_shapes_v1", "config": asdict(config),
               "task_sha256": hashlib.sha256(args.task.read_bytes()).hexdigest(),
               "source_sha256": hashes, "fit": result.summary(), "fit_cpu_seconds": cpu,
               "program_sha256": frozen_hash, "test": scored,
               "scoring_seconds": time.perf_counter() - score_started}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"fit": result.summary(), "test": scored}, indent=2))


if __name__ == "__main__":
    main()
