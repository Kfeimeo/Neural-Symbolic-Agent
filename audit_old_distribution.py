"""Reanalyse frozen V1 data; no task selection or training on audit ground truth."""
import argparse
import ast
import json
import time
from pathlib import Path

import torch

from dreamcoder.audit.curves import search_curves
from dreamcoder.audit.distribution import decode, overlap, profile, typed_search_growth
from dreamcoder.audit.metrics import record
from dreamcoder.audit.controlled import substitute
from dreamcoder.domains.grid import make_language
from dreamcoder.domains.grid.canonical import canonical, depth
from dreamcoder.domains.grid.features import encode_task
from dreamcoder.grammar import Grammar
from dreamcoder.language import INPUT, FunctionType, Primitive, Program
from dreamcoder.recognition import RecognitionModel
from dreamcoder.search import Frontier, SearchResult
from dreamcoder.tasks import Example, Task
from run_calibration import BUDGETS, metrics, save


def parse(text):
    def convert(node):
        if isinstance(node, ast.Name):
            return INPUT if node.id == "__input__" else Program(node.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            return Program(node.func.id, tuple(convert(x) for x in node.args))
        raise ValueError("Not a DSL expression")
    return convert(ast.parse(text.replace("$input", "__input__"), mode="eval").body)


def task_from_record(value):
    grid = lambda x: tuple(tuple(r) for r in x)
    return Task(value["name"], tuple(Example(grid(e["input"]), grid(e["output"])) for e in value["examples"]),
                decode(value["ground_truth"]))


def analyze_old(root=Path("results/audit")):
    data = json.loads((root/"training_data.json").read_text(encoding="utf-8"))
    manifest = json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    benchmark = json.loads((root/"benchmark.json").read_text(encoding="utf-8"))
    base = make_language()
    definitions = {n: parse(p) for n, p in manifest["training"]["learned_primitives"].items()}
    learned = make_language()
    for name, definition in definitions.items():
        learned.primitives[name] = Primitive(name, FunctionType((base.input_type,), base.output_type),
                                             lambda x, p=definition: base.evaluate(p, x), definition)
    training = [decode(t["ground_truth"]) for t in data["tasks"]]
    dreams = [decode(t["program"]) for t in data["fantasies"]]
    replay = [decode(t["program"]) for t in data["replay"]]
    probes = [tuple(tuple(r) for r in x) for x in benchmark["selection_probes"]]
    profiles = {"wake_ground_truth": profile(training, base),
                "dream_expanded": profile([learned.expand(p) for p in dreams], base),
                "replay": profile(replay, base), "typed_search_growth": typed_search_growth(base)}
    profiles["dream_identity_fraction"] = sum(learned.expand(p) == INPUT for p in dreams)/len(dreams)
    for key in ("original", "stress", "transfer"):
        ps = [decode(t["ground_truth"]) for t in benchmark[key]]
        profiles[key] = profile(ps, base)
        profiles[key+"_vs_wake_overlap"] = overlap(training, ps, base, probes)
        profiles[key+"_vs_all_supervision_overlap"] = overlap(training+replay+[learned.expand(p) for p in dreams], ps, base, probes)
    return profiles, benchmark, learned, manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results/calibration"))
    args = parser.parse_args()
    torch.set_num_threads(1)
    profiles, old, learned, manifest = analyze_old()
    save(args.output/"old_distribution.json", profiles)
    base = Grammar.uniform(make_language())
    probes = [tuple(tuple(r) for r in x) for x in old["evaluation_probes"]]
    tasks = [task_from_record(t) for t in old["stress"]]
    public = [Task(t.name, t.examples) for t in tasks]
    curves = search_curves(public, base, BUDGETS)
    report = {"A": {}, "D_old_high_depth": {}}
    def rows_of(curve, task, language):
        rows = {}
        for n, r in curve.items():
            t = SearchResult(Frontier(task, 3, r.frontier.solutions), r.enumerated_nodes, r.expanded_states,
                             0, r.first_solution_nodes, r.budget_exhausted, r.termination_reason)
            rows[str(n)] = record(t, language, probes)
        return rows
    rows = [rows_of(c, t, base.language) for c, t in zip(curves, tasks)]
    for n in BUDGETS:
        at = [r[str(n)] for r in rows]
        report["A"][str(n)] = {"overall": metrics(at), "high_depth": metrics([r for r in at if r["depth"] >= 5]),
                               "rows": at}
    print("Old A high-depth SolveRate:", [report["A"][str(n)]["high_depth"]["solve_rate"] for n in BUDGETS], flush=True)
    checkpoint = torch.load("results/audit/model_D.pt", weights_only=True)
    model = RecognitionModel(checkpoint["names"], checkpoint["feature_count"], encode_task)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    grammar = Grammar(learned, manifest["training"]["learned_prior"])
    high = [t for t in tasks if depth(canonical(t.ground_truth)) >= 5]
    collected = []
    for i, task in enumerate(high):
        anon = Task(task.name, task.examples)
        context = model.contextual_grammar(anon, grammar)
        curve = search_curves([anon], context, BUDGETS)[0]
        collected.append(rows_of(curve, task, learned))
        if (i+1) % 4 == 0:
            print(f"Old D high-depth {i+1}/{len(high)}", flush=True)
    for n in BUDGETS:
        at = [r[str(n)] for r in collected]
        report["D_old_high_depth"][str(n)] = {"overall": metrics(at), "rows": at}
    save(args.output/"old_budget_curves.json", report)
    print("Old D high-depth SolveRate:", [report["D_old_high_depth"][str(n)]["overall"]["solve_rate"] for n in BUDGETS], flush=True)


if __name__ == "__main__":
    main()
