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

## Results

See the *Preliminary results* section below (filled from
`results/arc_tsl/*/comparison.md`).
