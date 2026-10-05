"""Join baseline.json and tsl.json into the per-task metric table and the
summary statistics (mean / median / std; solved-only and all-task).

    python -m arc_tsl.experiments.compare --out results/arc_tsl/smoke
"""
from __future__ import annotations

import argparse
import math
import statistics
from pathlib import Path

from .common import read_json, write_json

METRIC_COLUMNS = [
    "task_id", "status", "solved", "num_train_pairs",
    "baseline_status", "baseline_expanded_states", "baseline_first_solution_nodes", "baseline_first_solution_states",
    "baseline_search_seconds", "baseline_program_length",
    "tsl_status", "tsl_expanded_states", "tsl_first_solution_nodes", "tsl_first_solution_states",
    "tsl_search_seconds", "tsl_program_length", "tsl_expanded_program_length",
    "local_wake_total_nodes", "local_wake_total_states", "local_wake_seconds", "local_wake_solved_pairs",
    "local_sleep_seconds", "tsl_num_abstractions", "tsl_num_abstractions_used", "tsl_description_length",
    "total_mdl", "sleep_mdl_before", "sleep_mdl_after", "abstraction_is_full_program",
    "states_ratio", "time_ratio", "first_states_ratio", "tsl_total_states_incl_wake", "total_states_ratio",
]


def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def row(b: dict, t: dict | None) -> dict:
    bs = b.get("search") or {}
    r = {
        "task_id": b["task_id"], "num_train_pairs": b["num_train_pairs"],
        "baseline_status": b["status"],
        "baseline_expanded_states": bs.get("expanded_states"),
        "baseline_first_solution_nodes": bs.get("first_solution_nodes"),
        "baseline_first_solution_states": bs.get("first_solution_states"),
        "baseline_search_seconds": bs.get("seconds"),
        "baseline_program_length": b.get("program_length"),
        "baseline_program": b.get("program"),
    }
    if t is None:
        r.update(tsl_status=None, status=b["status"], solved=b["status"] == "SOLVED")
        return r
    rw = t.get("rewake") or {}
    wk = t.get("wake") or {}
    sl = t.get("sleep") or {}
    abstractions = sl.get("abstractions") or []
    used = t.get("abstractions_used") or []
    full_program = False
    if t.get("program") and used:
        full_program = t["program"].startswith("(" + used[0] + " ") and t["program"].count("(") == 1
    r.update({
        "tsl_status": t["status"],
        "tsl_expanded_states": rw.get("expanded_states"),
        "tsl_first_solution_nodes": rw.get("first_solution_nodes"),
        "tsl_first_solution_states": rw.get("first_solution_states"),
        "tsl_search_seconds": rw.get("seconds"),
        "tsl_program_length": t.get("program_length"),
        "tsl_expanded_program_length": t.get("expanded_program_length"),
        "tsl_program": t.get("program"),
        "tsl_expanded_program": t.get("expanded_program"),
        "local_wake_total_nodes": sum((p.get("evaluated_programs") or 0) for p in wk.get("pairs", [])) or None,
        "local_wake_total_states": wk.get("total_expanded_states"),
        "local_wake_seconds": wk.get("total_seconds"),
        "local_wake_solved_pairs": wk.get("solved_pairs"),
        "local_sleep_seconds": sl.get("seconds"),
        "tsl_num_abstractions": sl.get("num_abstractions"),
        "tsl_num_abstractions_used": len(used),
        "tsl_abstractions": abstractions,
        "tsl_description_length": sl.get("library_description_length"),
        "total_mdl": t.get("total_mdl"),
        "sleep_mdl_before": sl.get("mdl_before"),
        "sleep_mdl_after": sl.get("mdl_after"),
        "abstraction_is_full_program": full_program,
    })
    r["solved"] = b["status"] == "SOLVED" or t["status"] == "SOLVED"
    r["status"] = "SOLVED" if r["solved"] else (t["status"] if t["status"] != "SEARCH_TIMEOUT" else b["status"])
    r["states_ratio"] = _ratio(r["baseline_expanded_states"], r["tsl_expanded_states"])
    r["time_ratio"] = _ratio(r["baseline_search_seconds"], r["tsl_search_seconds"])
    r["first_states_ratio"] = _ratio(r["baseline_first_solution_states"], r["tsl_first_solution_states"])
    if r["tsl_expanded_states"] is not None and r["local_wake_total_states"] is not None:
        r["tsl_total_states_incl_wake"] = r["tsl_expanded_states"] + r["local_wake_total_states"]
        r["total_states_ratio"] = _ratio(r["baseline_expanded_states"], r["tsl_total_states_incl_wake"])
    else:
        r["tsl_total_states_incl_wake"] = r["total_states_ratio"] = None
    return r


def _ratio(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def _stats(values):
    vals = [v for v in values if _num(v) is not None]
    if not vals:
        return {"n": 0, "mean": None, "median": None, "std": None}
    return {"n": len(vals), "mean": statistics.fmean(vals), "median": statistics.median(vals),
            "std": statistics.pstdev(vals) if len(vals) > 1 else 0.0}


def _geomean(values):
    vals = [v for v in values if _num(v) is not None and v > 0]
    return math.exp(sum(math.log(v) for v in vals) / len(vals)) if vals else None


SUMMARY_METRICS = ["baseline_expanded_states", "tsl_expanded_states", "baseline_first_solution_states",
                   "tsl_first_solution_states", "baseline_first_solution_nodes", "tsl_first_solution_nodes",
                   "baseline_search_seconds", "tsl_search_seconds", "baseline_program_length",
                   "tsl_program_length", "tsl_expanded_program_length", "tsl_description_length", "total_mdl",
                   "tsl_num_abstractions", "local_wake_total_states", "local_wake_seconds", "local_sleep_seconds",
                   "states_ratio", "time_ratio", "first_states_ratio", "total_states_ratio"]


def summarize(rows: list[dict], condition: str) -> dict:
    def block(subset):
        out = {m: _stats([r.get(m) for r in subset]) for m in SUMMARY_METRICS}
        out["states_ratio_geomean"] = _geomean([r.get("states_ratio") for r in subset])
        out["time_ratio_geomean"] = _geomean([r.get("time_ratio") for r in subset])
        out["first_states_ratio_geomean"] = _geomean([r.get("first_states_ratio") for r in subset])
        out["total_states_ratio_geomean"] = _geomean([r.get("total_states_ratio") for r in subset])
        out["n"] = len(subset)
        return out

    in_scope = [r for r in rows if r["baseline_status"] != "UNSUPPORTED"]
    both = [r for r in rows if r["baseline_status"] == "SOLVED" and r.get("tsl_status") == "SOLVED"]
    statuses = {}
    for r in rows:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
    return {
        "condition": condition,
        "num_tasks": len(rows),
        "num_in_scope": len(in_scope),
        "solve_rate_baseline": sum(r["baseline_status"] == "SOLVED" for r in rows) / max(1, len(rows)),
        "solve_rate_tsl": sum(r.get("tsl_status") == "SOLVED" for r in rows) / max(1, len(rows)),
        "solve_rate_baseline_in_scope": sum(r["baseline_status"] == "SOLVED" for r in in_scope) / max(1, len(in_scope)),
        "solve_rate_tsl_in_scope": sum(r.get("tsl_status") == "SOLVED" for r in in_scope) / max(1, len(in_scope)),
        "solved_by_baseline_only": [r["task_id"] for r in rows if r["baseline_status"] == "SOLVED" and r.get("tsl_status") != "SOLVED"],
        "solved_by_tsl_only": [r["task_id"] for r in rows if r["baseline_status"] != "SOLVED" and r.get("tsl_status") == "SOLVED"],
        "num_tasks_with_abstractions": sum(1 for r in rows if (r.get("tsl_num_abstractions") or 0) > 0),
        "num_solved_using_abstraction": sum(1 for r in both if (r.get("tsl_num_abstractions_used") or 0) > 0),
        "num_full_program_abstractions": sum(1 for r in both if r.get("abstraction_is_full_program")),
        "status_counts": statuses,
        "all_tasks": block(in_scope),
        "solved_only": block(both),
        "solved_only_nontrivial_abstraction": block([r for r in both if (r.get("tsl_num_abstractions_used") or 0) > 0
                                                     and not r.get("abstraction_is_full_program")]),
    }


def markdown(summaries: dict, tables: dict) -> str:
    lines = ["# Fixed-DSL baseline vs task-specific TSL", ""]
    for cond, s in summaries.items():
        lines += [f"## Condition: {cond}", "",
                  f"- tasks: {s['num_tasks']} (in scope: {s['num_in_scope']}); status counts: {s['status_counts']}",
                  f"- solve rate (all): baseline {s['solve_rate_baseline']:.3f} vs {cond} {s['solve_rate_tsl']:.3f}",
                  f"- solve rate (in scope): baseline {s['solve_rate_baseline_in_scope']:.3f} vs {cond} {s['solve_rate_tsl_in_scope']:.3f}",
                  f"- solved by baseline only: {s['solved_by_baseline_only']}; by {cond} only: {s['solved_by_tsl_only']}",
                  f"- tasks with >=1 abstraction: {s['num_tasks_with_abstractions']}; solved using an abstraction: "
                  f"{s['num_solved_using_abstraction']} (of which whole-program abstractions: {s['num_full_program_abstractions']})",
                  ""]
        for name in ("solved_only", "solved_only_nontrivial_abstraction", "all_tasks"):
            b = s[name]
            lines += [f"### {name} (n={b['n']})", "", "| metric | mean | median | std | n |", "|---|---:|---:|---:|---:|"]
            for m in SUMMARY_METRICS:
                st = b[m]
                if st["n"] == 0:
                    continue
                lines.append(f"| {m} | {st['mean']:.4g} | {st['median']:.4g} | {st['std']:.4g} | {st['n']} |")
            lines += [f"| states_ratio (geomean) | {_fmt(b['states_ratio_geomean'])} | | | |",
                      f"| first_states_ratio (geomean) | {_fmt(b['first_states_ratio_geomean'])} | | | |",
                      f"| time_ratio (geomean) | {_fmt(b['time_ratio_geomean'])} | | | |",
                      f"| total_states_ratio incl. wake (geomean) | {_fmt(b['total_states_ratio_geomean'])} | | | |", ""]
        lines += ["### Per-task table", "",
                  "| task | status | pairs | base states | base first | base L | tsl states | tsl first | tsl L | L(expanded) | wake states | #A | used | L(A) | MDL | states ratio | time ratio |",
                  "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for r in tables[cond]:
            lines.append("| " + " | ".join(str(x) if x is not None else "" for x in [
                r["task_id"], r["status"], r["num_train_pairs"], r["baseline_expanded_states"],
                r["baseline_first_solution_states"], r["baseline_program_length"], r.get("tsl_expanded_states"),
                r.get("tsl_first_solution_states"), r.get("tsl_program_length"), r.get("tsl_expanded_program_length"),
                r.get("local_wake_total_states"), r.get("tsl_num_abstractions"), r.get("tsl_num_abstractions_used"),
                r.get("tsl_description_length"), r.get("total_mdl"),
                _fmt(r.get("states_ratio")), _fmt(r.get("time_ratio"))]) + " |")
        lines.append("")
    return "\n".join(lines)


def _fmt(x):
    return "" if x is None else f"{x:.3g}"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=Path("results/arc_tsl/latest"))
    p.add_argument("--baseline", type=Path, default=None)
    p.add_argument("--tsl", type=Path, default=None)
    args = p.parse_args(argv)
    baseline = read_json(args.baseline or args.out / "baseline.json")
    tsl = read_json(args.tsl or args.out / "tsl.json")
    by_id = {r["task_id"]: r for r in tsl["records"]}
    summaries, tables = {}, {}
    for cond in tsl["conditions"]:
        rows = [row(b, by_id.get(b["task_id"], {}).get("conditions", {}).get(cond)) for b in baseline["records"]]
        tables[cond] = rows
        summaries[cond] = summarize(rows, cond)
    write_json(args.out / "comparison.json", {"summaries": summaries, "tables": tables,
                                              "baseline_config": baseline["config"], "tsl_config": tsl["config"]})
    md = markdown(summaries, tables)
    with open(args.out / "comparison.md", "w", encoding="utf-8") as f:
        f.write(md)
    print(md)


if __name__ == "__main__":
    main()
