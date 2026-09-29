"""Synthetic end-to-end example:

    pairwise programs -> learned local abstraction -> reduced search

Three IO pairs are generated from three *different* concrete programs that
share the fragment  map (λo. recolor (translate o ■) c2)  with a different
translation vector ■ per pair (a constant per pair, but relational across
pairs: each object moves onto the position of the nearest other object's
column... simplified here to: down / up / left).  The task-level program
that explains all pairs at once is the shared fragment with a relational
vector, which the fixed-DSL search has to discover from scratch while the
TSL search only has to fill the abstraction's hole.

    python -m arc_tsl.experiments.synthetic_demo
"""
from __future__ import annotations

import argparse
from pathlib import Path

from ..arc.grid import grid_to_text, to_grid
from ..arc.parse import parse
from ..arc.render import render
from ..dsa.types import OBJECT, OBJECTS
from ..language import base_library
from ..ml.ast import Abs, App, Prim, Var
from ..synthesis.enumerator import EnumerationConfig
from ..synthesis.evaluator import evaluate
from ..synthesis.search import Pair, search
from ..tsl.compression import compress
from ..tsl.local_library import contract, prune_unused
from ..tsl.local_wake import local_wake


def prog(v):
    return App("map", (Abs(OBJECT, App("recolor", (App("translate", (Var(0), v)), Prim("c2")))), Var(0)))


def run(max_cost: int = 9, max_states: int = 400_000) -> str:
    L = base_library()
    lines = []
    # --- three micro-tasks whose ground-truth programs differ by a Vec2 constant
    grids = [to_grid([[0, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]),
             to_grid([[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 3, 0], [0, 0, 0, 0]]),
             to_grid([[0, 4, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]])]
    truths = [prog(Prim("down")), prog(Prim("up")), prog(Prim("left"))]
    pairs = []
    for g, t in zip(grids, truths):
        s = parse(g)
        pairs.append(Pair(s, render(evaluate(t, L, (s.objects,)), s.grid_shape, s.background)))
    cfg = EnumerationConfig(max_cost=max_cost, max_expanded_states=max_states, time_limit_seconds=300)
    lines.append("# Synthetic demo: pairwise programs -> local abstraction -> reduced search\n")
    for i, (p, t) in enumerate(zip(pairs, truths)):
        lines.append(f"pair {i}: ground truth {t}\n```\n{grid_to_text(grids[i])}\n->\n{grid_to_text(p.output)}\n```")
    # --- local wake
    wake = local_wake(pairs, L, cfg, top_k=1)
    lines.append("\n## Local wake (each pair searched alone)")
    for i, r in enumerate(wake.results):
        lines.append(f"- pair {i}: {r.frontier.best.program if r.solved else None}  "
                     f"(expanded_states={r.stats.expanded_states}, first_solution_states={r.first_solution_states})")
    # --- local sleep
    comp = compress(L, [F for F in wake.frontiers if F], (OBJECTS,), OBJECTS, max_abstractions=3, max_arity=3)
    tsl, pruned = prune_unused(comp.library, comp.frontiers)
    tsl, pruned2 = contract(tsl, [[comp.library.expand(p) for p in F] for F in comp.frontiers])
    lines.append("\n## Local sleep (compression)")
    lines.append(f"- MDL {comp.mdl_before} -> {comp.mdl_after}; pruned {pruned + pruned2}")
    for st in comp.steps:
        lines.append(f"- accepted `{st.abstraction}`  ({st.candidates_scored} candidates scored)")
    for F in comp.frontiers:
        lines.append(f"  - rewritten: {[str(p) for p in F]}")
    # --- the *task-level* target: a new instance of the shared fragment.
    # Every object moves by the vector 'right' (not seen in any pair), so the
    # re-wake must fill the abstraction's Vec2 hole with a new expression.
    target = prog(Prim("right"))
    task_pairs = []
    for g in grids:
        s = parse(g)
        task_pairs.append(Pair(s, render(evaluate(target, L, (s.objects,)), s.grid_shape, s.background)))
    base_r = search(task_pairs, L, cfg)
    tsl_r = search(task_pairs, tsl, cfg)
    lines.append("\n## Full-task search (all pairs), fixed DSL vs TSL_τ")
    lines.append(f"- target program: {target}")
    lines.append(f"- fixed DSL : solved={base_r.solved} program={base_r.frontier.best.program if base_r.solved else None} "
                 f"expanded_states={base_r.stats.expanded_states} first_solution_states={base_r.first_solution_states} "
                 f"seconds={base_r.seconds:.2f} L={base_r.frontier.best.description_length if base_r.solved else None}")
    lines.append(f"- TSL_τ     : solved={tsl_r.solved} program={tsl_r.frontier.best.program if tsl_r.solved else None} "
                 f"expanded_states={tsl_r.stats.expanded_states} first_solution_states={tsl_r.first_solution_states} "
                 f"seconds={tsl_r.seconds:.2f} L={tsl_r.frontier.best.description_length if tsl_r.solved else None} "
                 f"L(A_τ)={tsl.library_description_length()}")
    if base_r.solved and tsl_r.solved:
        lines.append(f"- expanded-state ratio (fixed / TSL): {base_r.stats.expanded_states / tsl_r.stats.expanded_states:.2f}; "
                     f"first-solution ratio: {base_r.first_solution_states / tsl_r.first_solution_states:.2f}; "
                     f"wake cost: {wake.total_expanded} states")
        lines.append(f"- expanded TSL program: {tsl.expand(tsl_r.frontier.best.program)}")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--max-cost", type=int, default=9)
    p.add_argument("--max-states", type=int, default=400_000)
    args = p.parse_args(argv)
    text = run(args.max_cost, args.max_states)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
