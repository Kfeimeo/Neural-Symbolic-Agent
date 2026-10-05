"""Failure diagnosis: does a hand-written reference program (written by a
human for analysis only; NEVER used by the search) solve an ARC task in the
fixed language, and what would it cost?  Compares that cost with the cost
level the budgeted search actually reached, to classify a failure as
"expressible but beyond the reached cost level" versus "not expressible /
reference wrong".

    python -m arc_tsl.experiments.diagnose --task 25ff71a9 \
        --program "(map (λObject. (translate $0 down)) $0)" [--out results/arc_tsl/main]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from ..arc.grid import load_arc_task
from ..arc.render import render
from ..dsa.types import OBJECTS
from ..language import base_library
from ..ml.parser import parse_term
from ..synthesis.evaluator import ERR, evaluate
from ..tsl.pipeline import make_pairs, supported
from ..ontology.instance import ExtractionConfig
from .common import read_json


def diagnose(task_id: str, program_text: str, data: Path, out: Path | None, extraction: ExtractionConfig) -> dict:
    task = load_arc_task(data / f"{task_id}.json")
    lib = base_library()
    term = parse_term(program_text)
    info = {"task_id": task_id, "program": str(term)}
    ok, why = supported(task["train"])
    if not ok:
        info.update(status="UNSUPPORTED", reason=why)
        return info
    try:
        typ = lib.infer(term, (OBJECTS,))
    except (TypeError, KeyError) as e:
        info.update(status="ILL_TYPED", reason=str(e))
        return info
    if typ != OBJECTS:
        info.update(status="ILL_TYPED", reason=f"program has type {typ}, expected ObjectSet")
        return info
    pairs = make_pairs(task["train"], extraction)
    mismatches = []
    for i, p in enumerate(pairs):
        value = evaluate(term, lib, (p.scene.objects,))
        if value is ERR or render(value, p.scene.grid_shape, p.scene.background) != p.output:
            mismatches.append(i)
    info["cost"] = lib.description_length(term)
    info["mismatching_pairs"] = mismatches
    info["status"] = "REFERENCE_SOLVES" if not mismatches else "REFERENCE_DOES_NOT_SOLVE"
    if out is not None and (out / "baseline.json").exists():
        rec = {r["task_id"]: r for r in read_json(out / "baseline.json")["records"]}.get(task_id)
        if rec and rec.get("search"):
            s = rec["search"]
            info["search"] = {k: s.get(k) for k in ("solved", "expanded_states", "max_cost_reached", "termination_reason",
                                                    "seconds", "best_program")}
            if not mismatches and not s.get("solved"):
                info["classification"] = ("expressible, beyond reached cost level"
                                          if info["cost"] > s.get("max_cost_reached", 0)
                                          else "expressible at a reached cost level but not found "
                                               "(level incomplete: budget exhausted inside it, or OE merge)")
    return info


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", default=None)
    p.add_argument("--program", default=None)
    p.add_argument("--all", action="store_true", help="diagnose every entry of reference_programs.json")
    p.add_argument("--data", type=Path, default=Path("data/arc/training"))
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--connectivity", type=int, default=8)
    p.add_argument("--background", default="color0")
    p.add_argument("--same-color-only", action="store_true")
    args = p.parse_args(argv)
    if args.all:
        import json
        refs = json.loads((Path(__file__).parent / "reference_programs.json").read_text(encoding="utf-8"))["programs"]
        rows = []
        for tid, spec in refs.items():
            info = diagnose(tid, spec["program"], args.data, args.out,
                            ExtractionConfig(spec.get("connectivity", 8), spec.get("background", "color0"),
                                             spec.get("same_color_only", False)))
            rows.append(info)
            s = info.get("search") or {}
            print(f"{tid}: {info['status']} cost={info.get('cost')} mismatches={info.get('mismatching_pairs')} "
                  f"reached_cost={s.get('max_cost_reached')} states={s.get('expanded_states')} "
                  f"{info.get('classification', '')}")
        if args.out is not None:
            from .common import write_json
            write_json(args.out / "diagnosis.json", rows)
        return
    if not args.task or not args.program:
        raise SystemExit("--task and --program are required (or --all)")
    info = diagnose(args.task, args.program, args.data, args.out,
                    ExtractionConfig(args.connectivity, args.background, args.same_color_only))
    for k, v in info.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
