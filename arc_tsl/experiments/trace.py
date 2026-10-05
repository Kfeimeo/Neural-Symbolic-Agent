"""Write a human-readable end-to-end execution trace for one task from a
finished run (baseline.json + tsl.json).

    python -m arc_tsl.experiments.trace --out results/arc_tsl/smoke --task 25ff71a9
"""
from __future__ import annotations

import argparse
from pathlib import Path

from ..arc.grid import grid_to_text, load_arc_task
from .common import read_json


def trace_markdown(task_id: str, task: dict, baseline: dict, tsl_record: dict, condition: str = "tsl") -> str:
    L = [f"# Execution trace: ARC task `{task_id}`", ""]
    L += ["## Training pairs (input → output)", ""]
    for i, (x, y) in enumerate(task["train"]):
        L += [f"### pair {i}", "", "```", grid_to_text(x), "", "→", "", grid_to_text(y), "```", ""]
    L += ["## Baseline A: fixed ML+DSA search over all pairs", ""]
    L += ["```", _dump(baseline.get("search") or {}), "```", ""]
    rec = tsl_record["conditions"][condition]
    L += [f"## Method B ({condition}): local wake → local compression → TSL_τ → re-wake", ""]
    L += ["### Local wake (one micro-task per pair)", ""]
    for i, pr in enumerate((rec.get("wake") or {}).get("pairs", [])):
        L += [f"- pair {i}: solved={pr['solved']} expanded_states={pr['expanded_states']} "
              f"first_solution_states={pr['first_solution_states']} seconds={pr['seconds']:.2f}",
              f"  - frontier: {pr['frontier']}"]
    L += ["", "### Local sleep (compression)", ""]
    sl = rec.get("sleep") or {}
    L += [f"- MDL before: {sl.get('mdl_before')}  after: {sl.get('mdl_after')}  L(A_τ) = {sl.get('library_description_length')}",
          f"- sleep seconds: {sl.get('seconds')}", f"- pruned: {sl.get('pruned')}"]
    for st in sl.get("steps", []):
        L.append(f"- accepted `{st['abstraction']}` (MDL {st['mdl_before']} → {st['mdl_after']}, "
                 f"{st['candidates_scored']} candidates scored)")
    L += ["- rewritten frontiers:"]
    for i, F in enumerate(sl.get("rewritten_frontiers", [])):
        L.append(f"  - pair {i}: {F}")
    L += ["- final TSL_τ abstractions:"]
    for a in sl.get("abstractions", []):
        L.append(f"  - `{a}`")
    if sl.get("costs"):
        L.append(f"- θ_τ (non-unit costs): {sl['costs']}")
    L += ["", "### Local re-wake (one program for all pairs in TSL_τ)", ""]
    L += ["```", _dump(rec.get("rewake") or {}), "```", ""]
    L += [f"- status: **{rec['status']}**", f"- program: `{rec.get('program')}`",
          f"- expanded program: `{rec.get('expanded_program')}`",
          f"- L(p_τ | TSL_τ) = {rec.get('program_length')}, L(expanded) = {rec.get('expanded_program_length')}, "
          f"total MDL = L(TSL_τ) + L(p_τ|TSL_τ) = {rec.get('total_mdl')}",
          f"- abstractions used: {rec.get('abstractions_used')}", ""]
    bs = baseline.get("search") or {}
    rw = rec.get("rewake") or {}
    if bs.get("expanded_states") and rw.get("expanded_states"):
        L += ["## Comparison", "",
              f"- expanded states: baseline {bs['expanded_states']} vs TSL {rw['expanded_states']} "
              f"(ratio {bs['expanded_states'] / rw['expanded_states']:.2f})",
              f"- first-solution states: baseline {bs.get('first_solution_states')} vs TSL {rw.get('first_solution_states')}",
              f"- search seconds: baseline {bs['seconds']:.2f} vs TSL {rw['seconds']:.2f}",
              f"- program length: baseline {baseline.get('program_length')} vs TSL {rec.get('program_length')} "
              f"(expanded {rec.get('expanded_program_length')})",
              f"- TSL total search incl. wake: {rw['expanded_states'] + (rec.get('wake') or {}).get('total_expanded_states', 0)} states",
              ""]
    return "\n".join(L)


def _dump(d: dict) -> str:
    keys = ["solved", "expanded_states", "retained_terms", "evaluated_programs", "equivalent_terms", "dead_terms",
            "first_solution_nodes", "first_solution_states", "first_solution_seconds", "seconds",
            "termination_reason", "max_cost_reached", "best_program", "best_program_length"]
    return "\n".join(f"{k}: {d.get(k)}" for k in keys if k in d)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=Path("results/arc_tsl/latest"))
    p.add_argument("--data", type=Path, default=Path("data/arc/training"))
    p.add_argument("--task", type=str, required=True)
    p.add_argument("--condition", type=str, default="tsl")
    args = p.parse_args(argv)
    baseline = {r["task_id"]: r for r in read_json(args.out / "baseline.json")["records"]}[args.task]
    tsl = {r["task_id"]: r for r in read_json(args.out / "tsl.json")["records"]}[args.task]
    task = load_arc_task(args.data / f"{args.task}.json")
    md = trace_markdown(args.task, task, baseline, tsl, args.condition)
    path = args.out / f"trace_{args.task}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    print(f"-> {path}")


if __name__ == "__main__":
    main()
