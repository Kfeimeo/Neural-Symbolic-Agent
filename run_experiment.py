import argparse
import json
import random
from pathlib import Path

import torch

from dreamcoder.domains.grid import make_language, sample_grid, synthetic_tasks
from dreamcoder.domains.grid.features import encode_task
from dreamcoder.ec import run_iteration
from dreamcoder.grammar import Grammar


def main():
    parser = argparse.ArgumentParser(description="Run a complete minimal DreamCoder EC iteration")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--train-tasks", type=int, default=36)
    parser.add_argument("--heldout-tasks", type=int, default=24)
    parser.add_argument("--dreams", type=int, default=600)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--max-nodes", type=int, default=1500)
    parser.add_argument("--max-size", type=int, default=7)
    parser.add_argument("--output", type=Path, default=Path("results/experiment.json"))
    args = parser.parse_args()
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    language = make_language()
    report = run_iteration(Grammar.uniform(language),
                           synthetic_tasks(language, random.Random(args.seed), args.train_tasks, "train"),
                           synthetic_tasks(language, random.Random(args.seed+1), args.heldout_tasks, "heldout"),
                           sample_grid, encode_task, args.seed, args.dreams, args.epochs,
                           top_k=args.top_k, max_nodes=args.max_nodes, max_size=args.max_size)
    report["runtime"] = {"torch": torch.__version__, "epochs": args.epochs}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved {args.output.resolve()}")
    if not report["recognition_improves_nodes"]:
        raise SystemExit("Recognition did not improve nodes in this run; inspect the report.")


if __name__ == "__main__":
    main()
