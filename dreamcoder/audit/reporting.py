"""Consolidate audit results without treating shuffle replicates as new tasks."""
import json
from collections import Counter
from pathlib import Path

from .benchmark import BUCKETS
from .metrics import summarize


def write_summary(root: Path) -> dict:
    summary = {}
    benchmark = json.loads((root/"benchmark.json").read_text(encoding="utf-8"))
    for name in ("original", "transfer", "stress"):
        data = json.loads((root/f"{name}.json").read_text(encoding="utf-8"))
        configs = {k: v for k, v in data["configurations"].items() if "_shuffle_" not in k}
        buckets = {k: v for k, v in data["buckets"].items() if "_shuffle_" not in k}
        for key in ("C", "D"):
            labels = [label for label in data["frontiers"] if label.startswith(key+"_shuffle_")]
            rows = [r for label in labels for r in data["frontiers"][label]]
            configs[key+"_shuffle"] = {**summarize(rows), "shuffle_repeats": len(labels),
                                       "unique_task_count": len(data["frontiers"][key]),
                                       "note": "Pooled descriptive statistics; repeats are NOT independent tasks"}
            buckets[key+"_shuffle"] = {b: summarize([r for r in rows if r["bucket"] == b]) for b in BUCKETS}
        summary[name] = {"configurations": configs, "buckets": buckets, "comparisons": data["comparisons"],
                         "depth_histogram": dict(Counter(r["depth"] for r in data["frontiers"]["A"])),
                         "ast_size_histogram": dict(Counter(r["ast_size"] for r in data["frontiers"]["A"]))}
        if name == "transfer":
            summary[name]["directions"] = {
                label: {direction: summarize([r for r in rows if benchmark["transfer_directions"][r["task"]] == direction])
                        for direction in ("g(f(x))", "f(h(x))")}
                for label, rows in data["frontiers"].items()}
        print(f"Summary {name}: " + "; ".join(
            f"{key} {configs[key]['solve_rate']:.1%} solved / {configs[key]['mean_enumerated_nodes']:.1f} nodes"
            for key in ("A", "B", "C", "D", "C_shuffle", "D_shuffle")), flush=True)
    (root/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
