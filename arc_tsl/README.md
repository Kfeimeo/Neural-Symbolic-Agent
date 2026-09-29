# ARC-TSL v0.1 — task-specific language induction for ARC-AGI-1 program synthesis

A runnable, testable, controlled prototype for one research question:

> **On fixed domain axioms, does inducing a task-specific language `TSL_τ` from
> the IO pairs of a single ARC task (DreamCoder-style wake / compression /
> re-wake *inside* the task) reduce the complexity of searching for the task
> program, compared with searching the fixed full DSL?**

```
ML  ──►  DSA  ──►  TSL_τ  ──►  Program_τ
```

* **ML** (`arc_tsl/ml/`): fixed, domain-independent typed λ-calculus with
  Bool / Int / Vec2, `map` / `filter` / `argmin` / `argmax` / `unique`,
  collection edits, conditionals.
* **DSA** (`arc_tsl/dsa/`, `arc_tsl/ontology/`, `arc_tsl/arc/`): fixed,
  task-independent ARC ontology (Grid → Instance → ObjectToken / ObjectClass) and
  transformation semantics (`Object × Param → Object`), observers, relations,
  object-local `RegionExpr`.
* **TSL_τ** (`arc_tsl/tsl/`): `(Base_{ML+DSA}, A_τ, θ_τ)` induced per task by
  *local wake → local compression → local re-wake*.  No cross-task library
  learning, no hand-written task rules.

The design note with every modelling decision is in
[`docs/ARC_TSL_DESIGN.md`](../docs/ARC_TSL_DESIGN.md).

## Quick start

```bash
pip install pytest                      # the prototype itself is pure Python 3.11+, no torch needed
python -m pytest tests/arctsl -q        # unit + property tests (46)

# 1. fixed-DSL baseline  (Baseline A)
python -m arc_tsl.experiments.run_baseline --tasks 10 --seed 0 --in-scope-only --out results/arc_tsl/smoke --workers 4
# 2. task-specific TSL   (Method B, plus ablations C = reweight only, D = tsl+reweight)
python -m arc_tsl.experiments.run_tsl      --tasks 10 --seed 0 --in-scope-only --out results/arc_tsl/smoke --workers 4
# 3. comparison summary (mean / median / std, solved-only and all-task, ratios)
python -m arc_tsl.experiments.compare --out results/arc_tsl/smoke
# (1+2+3 in one go)
python -m arc_tsl.experiments.run_all --tasks 10 --seed 0 --in-scope-only --out results/arc_tsl/smoke --workers 4

# end-to-end trace of one real task from a finished run
python -m arc_tsl.experiments.trace --out results/arc_tsl/smoke --task 25ff71a9
# synthetic example: pairwise programs -> learned local abstraction -> reduced search
python -m arc_tsl.experiments.synthetic_demo
```

The ARC-AGI-1 training set (400 tasks, Apache-2.0, from
`github.com/fchollet/ARC-AGI`) is vendored in `data/arc/training/`.
Task selection is deterministic: sorted ids, `random.Random(seed).shuffle`,
first *n* (`--in-scope-only` skips tasks whose train outputs do not have the
input shape, a structural test that never looks at solutions).  Budgets are
CLI flags (`--max-cost`, `--max-states`, `--time-limit`, `--lambda-depth`, …)
and are recorded in every result file.

## What one task run does

```
Grid ──parse──► ObjectSet ──p──► ObjectSet ──render──► Grid        render(parse(g)) == g

baseline : search p_τ with ∀i p_τ(x_i)=y_i in Base_{ML+DSA}
tsl      : wake   : for each pair i search F_i = {p : p(x_i)=y_i} in Base           (local micro-tasks)
           sleep  : A_τ = argmin_A  L(A) + Σ_i min_{p∈F_i} L(p | Base + A)         (typed anti-unification
                    + expansion when ΔMDL > 0, contraction of unused / MDL-neutral abstractions)
           re-wake: search p_τ with ∀i p_τ(x_i)=y_i in Base + A_τ  (+ θ_τ)
```

Statuses: `SOLVED`, `UNSUPPORTED` (output shape ≠ input shape),
`SEARCH_TIMEOUT` (baseline budget exhausted), `NO_PAIRWISE_SOLUTION`
(some pair unsolved in wake and re-wake failed), `NO_SHARED_PROGRAM` (all
pairs solved locally but no single program found in budget).

Per-task metrics written by `compare.py` (`comparison.json` / `comparison.md`):
`task_id, solved, num_train_pairs, baseline_expanded_states,
baseline_first_solution_nodes/states, baseline_search_seconds,
baseline_program_length, tsl_expanded_states, tsl_first_solution_nodes/states,
tsl_search_seconds, tsl_program_length (+ expanded length),
local_wake_total_nodes/states, local_sleep_seconds, tsl_num_abstractions,
tsl_num_abstractions_used, tsl_description_length, total_mdl`, and the ratios
`baseline_expanded_states / tsl_expanded_states`,
`baseline_search_seconds / tsl_search_seconds`, plus the same ratio counting
the wake cost.  Summaries give mean / median / std and geometric means for
*all in-scope tasks*, *solved-by-both tasks*, and *solved with a non-trivial
(not whole-program) abstraction*.

## Search engine and cost convention

Bottom-up, cost-ordered, typed enumeration with observational-equivalence
pruning over de Bruijn contexts (`synthesis/enumerator.py`); statistics
`expanded_states`, `evaluated_programs`, `first_solution_*`, wall time.  Costs
are unit production weights (application 0, λ 1); `L(A_τ) = Σ (L(body)+1)`;
program lengths are always reported in unit weights even when `θ_τ` reweights
the search.  The same enumerator and the same budget are used by every
condition; the only difference is the library.

## Honest notes and limitations

* **Compressor vs. DreamCoder.**  Proposal = typed anti-unification of closed
  subterms (holes never capture λ-bound variables); selection = greedy MDL gate
  on `L(A) + Σ_i min_p L(p|A)` with semantics-preserving rewriting (checked by
  expansion equality).  It is *not* the DreamCoder version-space compressor:
  no refactoring enumeration, no inside-outside fitting, MAP instead of marginal
  over frontier entries, unit costs instead of `-log p`.  The repository's
  Haskell kernel / Stitch bridge (`faithful/`) need GHC and `stitch_core`, which
  are unavailable here, and the Python `dreamcoder/` core is first-order, so a
  new typed λ-core was written (mirroring its search / frontier / compression
  interfaces).
* **Frontiers under observational equivalence are tiny.**  For one pair, every
  correct program has the same observation, so the wake frontier is effectively
  one canonical program per pair.  Abstractions therefore come from
  anti-unifying the *different* pairs' programs, not from within-pair diversity.
* **Whole-program abstractions.**  When every pair's local program is identical,
  compression yields a single 0-parameter-body abstraction of the whole program
  and the re-wake is trivially cheap.  This is legitimate MDL behaviour but not
  evidence of *compositional* reuse; the summaries report these cases
  separately (`abstraction_is_full_program`).
* **Same-shape tasks only**; no whole-grid rotations/flips (transforms are
  object-centric), no cardinality-changing primitives beyond generic
  `insert`/`delete`/`replace`, no absolute coordinates at all.
* The search is exhaustive by cost level, so budgets determine what is
  solvable.  Unsolved tasks are recorded with their termination reason; no
  task-specific primitive was added anywhere.

## Preliminary results (v0.1)

All numbers below are produced by the commands above and stored under
`results/arc_tsl/` (`main/` = deterministic 130-task run, `deep/` = hand-picked
diagnostic run, `synthetic_demo.md`, `main/trace_*.md`).  Machine: 4 CPU
cores, pure Python.

### Main deterministic run (`results/arc_tsl/main`, 130 in-scope tasks, seed 0)

Budget per search: `max_cost 10`, `300k expanded states`, `30 s` (wake: 20 s
per pair), lambda depth 2, 8-connectivity, background = color 0.

| condition | solve rate (130 in-scope tasks) | statuses |
|---|---:|---|
| baseline (fixed Base_{ML+DSA}) | 2 / 130 | 128 SEARCH_TIMEOUT |
| tsl (A_τ, uniform θ) | 2 / 130 | 127 NO_PAIRWISE_SOLUTION, 1 NO_SHARED_PROGRAM |
| reweight (θ_τ only) | 2 / 130 | same |
| tsl_reweight (A_τ + θ_τ) | 2 / 130 | same |

The two solved tasks (`3c9b0459`: rotate every object by 180°, `3aa6fb7a`: fill
each object's bbox) are solved by every condition; on them (n = 2, geometric
means, from `main/comparison.md`):

| condition | expanded states baseline / method | first-solution states ratio | search-time ratio | program length (method / expanded) | total ratio incl. wake cost |
|---|---:|---:|---:|---:|---:|
| tsl | **127×** (24 410 → 134) | 127× | 115× | 2.5 / 6.5 | 0.41× |
| reweight | 22.9× (24 410 → 1 004) | 22.9× | 9.8× | 6.5 / 6.5 | 0.40× |
| tsl_reweight | **595×** (24 410 → 59.5) | 595× | 94× | 2.5 / 6.5 | 0.41× |

Reading: once `TSL_τ` exists, the full-task re-wake is two to three orders of
magnitude cheaper, and the task-local prior θ_τ alone already gives ~20×.
But the local wake that induces `TSL_τ` costs more than the baseline search
saved (total-cost ratio ≈ 0.4), and on these two tasks both abstractions are
(near-)whole-program abstractions (`#f0 = map (λo. rotate o r180) $0`,
`#f0 = λo. add_region o rg_bbox c1`), because every pair's local program was
identical.  So the main run does **not** yet show a compositional benefit; it
shows that the closed loop works end to end and that re-wake cost collapses
when the per-pair programs already agree.

**Solve rate is the real bottleneck.**  The failure diagnosis
(`python -m arc_tsl.experiments.diagnose --all --out results/arc_tsl/main`,
human reference programs in `experiments/reference_programs.json`, never used
by the search) shows that the bottom-up OE search reaches cost level 7–8 within
the budget (histogram of `max_cost_reached`: 5:1, 6:23, 7:48, 8:51, 9:6, 10:1)
while object-centric ARC programs typically cost 11–24 in this language, e.g.

| task | reference program (cost) | reached | classification |
|---|---|---:|---|
| 67385a82 | `map (λo. if_obj (lt i2 (size o)) (recolor o c8) o)` (13) | 8 | expressible, beyond reached level |
| bb43febb | `map (λo. add_region (recolor (remove_region o rg_boundary) c2) rg_neighbors8 c5)` (11) | 8 | expressible, beyond reached level |
| 5521c0d9 | `map (λo. translate o (vec (neg (height o)) i0))` (11) | 7 | expressible, beyond reached level |
| b27ca6d3 | size-2 objects get an 8-neighbour outline (14) | 7 | expressible, beyond reached level |
| d2abd087 / 6e82a1ae / aabf363d | conditional recolor by size / by the smallest object's color (18 / 24 / 17) | 7 | expressible, beyond reached level |
| d364b489, 913fb3ed | per-direction / per-color outlines | – | not expressible in v0.1 (no direction- or color-indexed regions) |

The per-pair wake reaches one cost level *deeper* than the full search on
53 % of the tasks (fewer OE classes per single pair), which is exactly the lever
the hypothesis needs, but one level is not enough to bridge 8 → 11–18.

### The most informative failure: `63613498` (`main/trace_63613498.md`)

All three pairs are solved locally with programs that differ only in one
color constant (`map (λo. replace_color o c6 c5) $0`, `… c9 …`, `… c1 …`).
Compression invents `#f0 = λ(x0:Color, x1:ObjectSet). map (λo. replace_color o x0 c5) x1`
(MDL 21 → 17) and rewrites the frontiers to `(#f0 c6 $0)`, `(#f0 c9 $0)`,
`(#f0 c1 $0)`.  The task-level program is `(#f0 ⟨relational Color expression⟩ $0)`:
the abstraction has isolated exactly the part of the program that must
generalise across pairs.  The re-wake still fails within 30 s because the
relational color expression (the color of the object whose shape matches the
template object) costs more than the reachable level.  This is the intended
mechanism working up to the search budget, and the clearest evidence that the
comparison has to be run at larger budgets (see *deep* run below).

### Synthetic example (`results/arc_tsl/synthetic_demo.md`)

Three pairs generated by `map (λo. recolor (translate o v) c2) $0` with
`v ∈ {down, up, left}`; the task-level target uses `v = right` (unseen).
Wake finds the three concrete programs, compression invents
`#f0 = λ(v, s). map (λo. translate (recolor o c2) v) s` (MDL 24 → 18), and the
full-task search needs **148** expanded states in `TSL_τ` versus **93 456** in
the fixed DSL (631×; wake cost 188 448 states), with program length 3 vs 8.

### Deep-budget diagnostic run (`results/arc_tsl/deep`)

DEEP_RESULTS_PLACEHOLDER
