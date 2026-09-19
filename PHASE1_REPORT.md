# Phase 1 Report: Learning Reusable Abstractions for Neural-Symbolic Program Synthesis

Status: methods and protocol fixed; result sections are filled from the measured
artefacts in `results/` after the runs complete (see the end of this file for the
exact commands and validation status).

## 1. Question and hypothesis

Given a task distribution generated from hidden latent abstractions
F = {F_1, …, F_n} that the learner never sees, can a synthesis system recover useful
abstractions F̂_i from (input, output) examples alone, and does that improve held-out
compositional generalisation? The hypothesis under test is the chain

    better abstraction discovery → shorter effective programs → easier synthesis → better generalisation.

Every link of the chain is measured separately: abstraction recovery (precision,
recall, F1, held-out-weighted recall under syntactic, type and behavioural
equivalence), effective program length ΔL of the held-out generator programs under
the learned library, search cost (first-solution rank, expanded states) and
held-out solve rate at fixed candidate budgets. The solver itself (Haskell symbolic
kernel, type system, program representation, enumeration, grammar semantics,
frontier objective, recognition objective, evaluator) is the frozen baseline from
`faithful/`; its source hashes are recorded in every benchmark manifest and verified
before and after every stage.

## 2. Benchmark (Phase 1.1): `benchmarks/latent_abstraction/`

Three independent benchmark instances (generator seeds 101, 202, 303) were
generated, calibrated with the uniform base grammar only, and frozen
(SHA-256 manifests) before any learned-library method was run. Each instance
contains four independent reuse cohorts of 56 training tasks (8 per depth 2–8) and
up to 32 held-out tasks (depths 3–8), six I/O examples per task.

Hidden library. Twelve latent abstractions per instance are generated
automatically: four `grid → grid`, four `grid → color → grid`, four
`grid → int → grid`, with internal operator depth 2 (three per kind) or 3 (one per
kind). Latents are canonical compositions of base operator stages with an optional
parameter slot, screened to be non-degenerate for at least two parameter values
(all values for grid latents): not identity or near-constant on 32 split probes,
not behaviourally equal to a shallower reference program (600 random single stages
plus the first 10000 programs of the uniform enumerator), not equal to any
single-stage deletion, and behaviourally distinct from every other accepted latent.

Reuse regimes. `zero`: independently generated base programs (no pool). `low`:
2 of 8 training tasks per depth use a latent from a 12-latent pool. `medium`: 4 of 8
from a 6-latent pool, nesting probability 0.3. `high`: 8 of 8 from a 4-latent pool,
nesting probability 0.4. Pools are nested and the least-used latent is chosen inside
a pool, so the reuse level is set by pool size and share rather than by sampling
noise. Incidental syntactic occurrences of latents in non-deliberate tasks are
detected and counted separately. For every latent and cohort the library records
id, definition (expression, typed λ-body), type, training/test occurrence counts
(deliberate and total), distinct tasks, distinct (outer, inner) contexts and the
list of contexts used.

Complexity. Requested operator-tree depth d ∈ {2,…,8} of the expanded base program;
AST size and depth, primitive leaf count, beta-normal size and the effective
complexity (leaf size after the exact best rewrite with the true active latents) are
stored per task.

Compositional generalisation. Held-out programs never coincide with training
programs (canonical expression, behaviour fingerprint and complete I/O set are
disjoint; validated per instance) but share latent sub-structure. Transfer types,
with the novelty condition verified on the contexts detected in the canonical
program: I g(F_i(·)) with an outer operator never applied to F_i in training;
II F_i(h(·)) with an inner operator never feeding F_i in training; III F_i(F_j(·))
with an ordered pair never nested in training (depth ≥ 5 so that one base stage
remains). The zero cohort receives matched-depth control tasks. Every held-out latent
is exposed in the same cohort's training tasks.

Generator development before freezing. Two structural adjustments were made while
developing the generator on a throw-away trial instance (seed 7), before any
learned-library run on any instance: (i) least-used latent selection inside pools
to balance reuse counts; (ii) transfer type III restricted to depth ≥ 5 after the
trial showed that bare two-latent compositions at depth 4 were almost always
behaviourally equal to a shallower program, and cells that cannot be populated
within 4000 attempts are recorded as unpopulated instead of aborting. No parameter
was changed after observing any result of methods B–E or the oracles.

## 3. Methods (Phase 1.4): `experiments/abstraction_learning/`

All arms run the same learner (`learner.py`): a multi-round Explore–Compress loop on
the frozen core — bounded typed enumeration (Wake, 3000 complete candidates,
top-3 persistent frontiers rescored under the current grammar), a compressor
(Sleep), and the frozen inside-outside prior fit. The neural recognition model is
switched off in every arm so that the only difference between arms is the
compressor; every stage is then deterministic and replication is spent on
independent benchmark instances (cross-dataset robustness) rather than on training
seeds.

Compressor interface: `Frontiers + Grammar (+ task ids) → Compressor → new library +
updated grammar`, with identical inputs, identical frozen rewriting
(`compression_trial`: typed inverse-β rewrite, inside-outside fit, DreamCoder
objective) and identical budgets (up to 3 accepted inventions per round).

| Arm | Proposals | Selection objective |
|---|---|---|
| A | none | prior fit only |
| B (DreamCoder) | inverse-β fragments with ≥2-task support (frozen Haskell `compress`) | DreamCoder Bayesian MDL |
| C (Stitch) | Stitch (`stitch-core 0.1.29`, 9 configurations: max arity 1–3 × structure penalty 0.5/1/2, 4 iterations each) | Stitch leaf-cost utility (savings − body cost) |
| D (hybrid) | Stitch, as C | DreamCoder Bayesian MDL |
| E | DreamCoder candidates, as B | Stitch leaf-cost utility |

C, D and E share one greedy loop (propose, score every admissible candidate with
the frozen typed rewrite, accept the best strictly improving candidate, repeat) so
that proposal source and objective are the only factors; the loop reproduces the
frozen B compressor exactly when fed DreamCoder proposals with the MDL objective
(regression test). Admissibility applies DreamCoder's own triviality filter
(Stitch otherwise proposes η-wrappers such as `λx. #f x`) and rejects β-duplicates
of existing productions.

Oracles (Phase 1.5). `O`: the true active latents are added to the base grammar
and the same loop runs with prior fitting but no compression. `O_uniform`: the same
library with uniform weights and no learning. `PW_*` (perfect Wake): each
compressor is applied once (up to 12 inventions) to the ground-truth programs of
all 56 training tasks, isolating abstraction discovery from search exposure.

Search exposure. `B_wake10000` and `D_wake10000` repeat B and D with a
10000-candidate Wake (a 30000-candidate Wake needs about 1M agenda states and
10 GB of kernel memory per process on the available machine and was dropped
before any run).

Evaluation (Phases 1.2–1.3). After every round the grammar is evaluated on the
cohort's held-out tasks by a single uniform-cost enumeration (3M expanded-state
cap, leaf size ≤ 33, depth ≤ 14): 10000 complete candidates after rounds 1–5,
20000 after the final round and for the static and perfect-Wake grammars; the
first-solution rank gives the exact solve outcome at every smaller budget (100,
300, 1000, 3000, 10000). A solution is probe-consistent when a top-3 solution reproduces the
generator program on 40 independent probes. Effective complexity ΔL = L_base − L_L
is the exact minimum leaf size of the held-out generator program in the β-normal
subtree/slot rewrite space under the learned library. Recovery compares every
invention with every active latent under syntactic, canonical, β, type (strict and
up to argument permutation) and behavioural equivalence (type-compatible and equal
outputs on the 40 probes for every valid parameter value); an invention with more
parameters than a latent is not credited.

Protocol: `results/abstraction_learning/protocol.json` was written before the first
arm ran; benchmark hashes are verified before and after every stage. Statistics are
means and standard deviations over the three instances; contrasts use the two-way
paired bootstrap (instances and task positions resampled together, 2000 draws).

## 4. Results

(filled from `results/solve_curves.json`, `results/abstraction_recovery.json`,
`results/compression_results.json` and `results/abstraction_learning/tables.md`)

## 5. Answers to the five questions

(filled after the results)

## 6. Limitations

(filled after the results)

## 7. Reproduction and validation

(filled after the results)
