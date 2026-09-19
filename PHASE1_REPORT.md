# Phase 1 Report: Learning Reusable Abstractions for Neural-Symbolic Program Synthesis

All numbers in this report are read from `results/solve_curves.json`,
`results/abstraction_recovery.json`, `results/compression_results.json` and the
generated `results/abstraction_learning/tables.md`; figures are in
`results/abstraction_learning/figures/`. The solver (Haskell symbolic kernel, type
system, program representation, enumeration, grammar semantics, frontier objective,
recognition objective, evaluator) is the frozen `faithful/` baseline; its source
hashes are recorded in every benchmark manifest and were verified before and after
every stage.

## 1. Question and hypothesis

Given a task distribution generated from hidden latent abstractions F = {F_1, …, F_n}
that the learner never sees, can a synthesis system recover useful abstractions F̂_i
from (input, output) examples alone, and does that improve held-out compositional
generalisation? The hypothesis under test is the chain

    better abstraction discovery → shorter effective programs → easier synthesis → better generalisation.

Every link is measured separately: abstraction recovery (precision, recall, F1,
held-out-weighted recall under syntactic, type and behavioural equivalence),
effective program length ΔL of the held-out generator programs under the learned
library, search cost (first-solution rank) and held-out solve rate at fixed
candidate budgets.

## 2. Benchmark (Phase 1.1): `benchmarks/latent_abstraction/`

Three independent benchmark instances (generator seeds 101, 202, 303) were
generated, calibrated with the uniform base grammar only, and frozen (SHA-256
manifests) before any learned-library method was run. Each instance has four
independent reuse cohorts of 56 training tasks (8 per operator depth 2–8) and
23–32 held-out tasks (depths 3–8), six I/O examples per task.

Hidden library. Twelve latent abstractions per instance are generated
automatically: four `grid → grid`, four `grid → color → grid`, four
`grid → int → grid`, with internal operator depth 2 (three per kind) or 3 (one per
kind). Latents are canonical compositions of base operator stages with an optional
parameter slot, screened to be non-degenerate for at least two parameter values
(all values for grid latents): not identity or near-constant on 32 split probes, not
behaviourally equal to a shallower reference program (600 random single stages plus
the first 10000 programs of the uniform enumerator), not equal to any single-stage
deletion, and behaviourally distinct from every other accepted latent. Examples
(instance 101, high-reuse pool): `rotate90(translate(x, 1, 1))`,
`trim(recolor(x, red, blue))`, `solid(flipV(x), p)`, `translate(rotate90(x), 0, p)`.

Reuse regimes. `zero`: independently generated base programs (no pool).
`low`: 2 of 8 training tasks per depth use a latent from a 12-latent pool
(1.2 deliberate training uses per latent). `medium`: 4 of 8 from a 6-latent pool
(4.8–5.7 uses per latent, nesting probability 0.3). `high`: 8 of 8 from a 4-latent
pool (15–18 uses per latent, nesting probability 0.4). Pools are nested and the
least-used latent is chosen inside a pool, so the reuse level is set by pool size
and share rather than sampling noise. Incidental syntactic occurrences of latents in
non-deliberate tasks are detected and counted separately (4–22 per cohort). For every
latent and cohort the library records id, definition (expression and typed λ-body),
type, training/test occurrence counts (deliberate and total), distinct tasks,
distinct (outer, inner) contexts and the list of contexts used.

Complexity. Requested operator-tree depth d ∈ {2,…,8} of the expanded base program;
AST size and depth, primitive leaf count, β-normal size and the effective complexity
(leaf size after the exact best rewrite with the true active latents; mean ΔL 2.5–3.2
leaves in the reuse cohorts) are stored per task.

Compositional generalisation. Held-out programs never coincide with training
programs (canonical expression, behaviour fingerprint and complete I/O set are
disjoint; validated per instance) but share latent sub-structure. Transfer types,
with the novelty condition verified on the contexts detected in the canonical program:
I g(F_i(·)) with an outer operator never applied to F_i in training; II F_i(h(·))
with an inner operator never feeding F_i in training; III F_i(F_j(·)) with an
ordered pair never nested in training (depth ≥ 5 so that one base stage remains).
The zero cohort receives matched-depth control tasks. Every held-out latent is exposed
in the same cohort's training tasks. Cells that could not be populated within 4000
attempts (1–13 per instance, mostly nested cells of the small high-reuse pool) are
recorded, which is why cohort sizes differ.

A0 calibration (uniform base grammar, before freezing; held-out solve rate at 10000
candidates): depth 3 tasks 0.33–0.75, depth 4 tasks 0–0.25, depth ≥ 5 essentially
unsolved. The distribution is deliberately hard at depth ≥ 4 so that abstraction is
needed, and shallow enough at depths 2–3 for Wake to expose latents.

Generator development before freezing. Two structural adjustments were made while
developing the generator on a throw-away trial instance (seed 7), before any
learned-library run on any instance: (i) least-used latent selection inside pools to
balance reuse counts; (ii) transfer type III restricted to depth ≥ 5 after the trial
showed that bare two-latent compositions at depth 4 were almost always behaviourally
equal to a shallower program, with unpopulated cells recorded instead of aborting.
No parameter was changed after observing any result of methods B–E or the oracles.

## 3. Methods (Phase 1.4): `experiments/abstraction_learning/`

All arms run the same learner (`learner.py`): a multi-round Explore–Compress loop on
the frozen core — bounded typed enumeration (Wake, 3000 complete candidates, top-3
persistent frontiers rescored under the current grammar), a compressor (Sleep), and
the frozen inside-outside prior fit. The neural recognition model is switched off in
every arm so that the only difference between arms is the compressor; every stage is
then deterministic and replication is spent on independent benchmark instances
(cross-dataset robustness) rather than on training seeds.

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

C, D and E share one greedy loop (propose, score every admissible candidate with the
frozen typed rewrite, accept the best strictly improving candidate, repeat) so that
proposal source and objective are the only factors; the loop reproduces the frozen B
compressor exactly when fed DreamCoder proposals with the MDL objective (regression
test). Admissibility applies DreamCoder's own triviality filter (Stitch otherwise
proposes η-wrappers such as `λx. #f x`) and rejects β-duplicates of existing
productions.

Oracles (Phase 1.5). `O`: the true active latents are added to the base grammar and
the same loop runs with prior fitting but no compression. `O_uniform`: the same
library with uniform weights and no learning. `PW_*` / `PWS_*` (perfect Wake): each
compressor is applied once (up to 12 inventions) to the ground-truth programs of all
56 training tasks (`PW`) or of the training tasks with depth ≤ 4 (`PWS`), isolating
abstraction discovery from search exposure; each call has a wall-clock limit
(1200 s, lowered to 120 s on the full corpus after the first two cohorts because the
DreamCoder-proposal compressors did not finish in 1200 s).

Search exposure. `B_wake10000` and `D_wake10000` repeat B and D with a
10000-candidate Wake (a 30000-candidate Wake needs about 1M agenda states and 10 GB
of kernel memory per process on the available machine and was dropped before any run).

Evaluation (Phases 1.2–1.3). After every round the grammar is evaluated on the
cohort's held-out tasks by a single uniform-cost enumeration of 10000 complete
candidates (3M expanded-state cap, leaf size ≤ 33, depth ≤ 14); the first-solution
rank gives the exact solve outcome at every smaller budget (100, 300, 1000, 3000).
The budget was capped at 10000 because the uniform oracle grammar of the low-reuse
cohort (36 productions) already needs ~580k agenda states and ~9 GB of memory at
10000 candidates, and 20000-candidate searches were killed by the memory cgroup; the
cap matches the earlier controlled study. A solution is probe-consistent when a
top-3 solution reproduces the generator program on 40 independent probes. Effective
complexity ΔL = L_base − L_L is the exact minimum leaf size of the held-out generator
program in the β-normal subtree/slot rewrite space under the learned library.
Recovery compares every invention with every active latent under syntactic,
canonical, β, type (strict and up to argument permutation) and behavioural
equivalence (type-compatible and equal outputs on the 40 probes for every valid
parameter value); an invention with more parameters than a latent is not credited.

Protocol: `results/abstraction_learning/protocol.json` was written before the first
arm ran; benchmark hashes are verified before and after every stage. Statistics are
means ± sample standard deviations over the three instances; contrasts use a two-way
paired bootstrap (instances and, within each instance, their held-out tasks are
resampled together, 2000 draws). With three instances the intervals are wide and are
conditional on the generated instances.

## 4. Results

### 4.1 Experiment 1: effect of reuse

Held-out solve rate at 10000 candidates, final EC iteration (mean ± SD over
instances; `A0` and `O_uniform` are static):

| Reuse | A0 | A | B | C | D | E | O | O_uniform |
|---|---|---|---|---|---|---|---|---|
| zero | 0.104 ± 0.048 | 0.135 ± 0.036 | 0.208 ± 0.048 | 0.219 ± 0.094 | 0.156 ± 0.054 | 0.177 ± 0.079 | 0.135 ± 0.036 | 0.104 ± 0.048 |
| low | 0.065 ± 0.003 | 0.110 ± 0.056 | 0.121 ± 0.054 | 0.121 ± 0.045 | 0.132 ± 0.039 | 0.121 ± 0.045 | 0.402 ± 0.014 | 0.401 ± 0.032 |
| medium | 0.046 ± 0.040 | 0.194 ± 0.055 | 0.274 ± 0.072 | 0.239 ± 0.093 | 0.250 ± 0.122 | 0.193 ± 0.052 | 0.456 ± 0.127 | 0.387 ± 0.142 |
| high | 0.068 ± 0.031 | 0.241 ± 0.061 | 0.459 ± 0.091 | 0.389 ± 0.078 | 0.393 ± 0.112 | 0.389 ± 0.078 | 0.402 ± 0.042 | 0.334 ± 0.037 |

Probe-consistent rates are identical or within one task of these rates for every
arm: solutions that fit six examples almost always reproduce the generator program.

Paired contrasts (mean difference, 95% bootstrap interval), final iteration:

| Reuse | B−A | C−A | D−A | E−A | A−A0 | D−B | C−B | E−B |
|---|---|---|---|---|---|---|---|---|
| zero | +0.073 [0.010, 0.146] | +0.083 [0.000, 0.177] | +0.021 [−0.073, 0.115] | +0.042 [−0.042, 0.125] | +0.031 [−0.010, 0.083] | −0.052 [−0.146, 0.042] | +0.010 [−0.062, 0.104] | −0.031 [−0.104, 0.042] |
| low | +0.010 [−0.056, 0.075] | +0.011 [−0.046, 0.065] | +0.022 [−0.046, 0.098] | +0.011 [−0.046, 0.065] | +0.045 [−0.022, 0.115] | +0.011 [−0.042, 0.086] | 0.000 [−0.053, 0.065] | 0.000 [−0.053, 0.065] |
| medium | +0.080 [−0.035, 0.183] | +0.046 [−0.069, 0.161] | +0.056 [−0.114, 0.207] | −0.001 [−0.126, 0.122] | +0.148 [0.069, 0.228] | −0.023 [−0.149, 0.092] | −0.034 [−0.124, 0.046] | −0.080 [−0.184, 0.021] |
| high | +0.218 [0.077, 0.374] | +0.148 [0.011, 0.308] | +0.151 [0.003, 0.339] | +0.148 [0.014, 0.332] | +0.174 [0.072, 0.282] | −0.066 [−0.181, 0.029] | −0.070 [−0.182, 0.032] | −0.070 [−0.185, 0.029] |

Findings. (i) Library learning helps most where reuse is high: B adds 21.8 points over
prior fitting alone (interval excludes zero) and every compressor adds 15–22 points.
(ii) At low reuse (1.2 uses per latent) no compressor adds anything measurable (≤ 2
points) although the oracle library would add 29 points: the abstractions exist and
would help, but they are not discoverable from a corpus in which each occurs once or
twice. (iii) At zero reuse, B and C still add 7–8 points: the base DSL produces
incidental reusable fragments (border/flip chains, translate patterns) and compressing
them helps search even without deliberate latents, replicating the earlier controlled
study's "no clean zero" result. (iv) Prior fitting alone (A − A0) is a large effect
at medium and high reuse (+15, +17 points): a substantial part of the total gain of
any learned-library arm over the untrained baseline comes from re-weighting the base
grammar on solved tasks, not from inventions. (v) The four compressors are
statistically indistinguishable in every cohort; B is nominally best at medium and
high reuse and D/C/E are 6–8 points below it at high reuse with intervals that
include zero.

### 4.2 Experiment 2: effect of complexity and transfer type

Solve rate at 10000 candidates by requested depth (final iteration), high reuse:

| Arm | d=3 | d=4 | d=5 | d=6 | d=7 | d=8 |
|---|---|---|---|---|---|---|
| A0 | 0.56 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| A | 0.89 | 0.50 | 0.17 | 0.08 | 0.00 | 0.07 |
| B | 1.00 | 0.83 | 0.25 | 0.39 | 0.22 | 0.28 |
| C | 1.00 | 0.75 | 0.17 | 0.39 | 0.22 | 0.06 |
| D | 1.00 | 0.83 | 0.25 | 0.33 | 0.22 | 0.00 |
| E | 0.89 | 0.75 | 0.25 | 0.31 | 0.22 | 0.17 |
| O | 1.00 | 0.83 | 0.25 | 0.31 | 0.22 | 0.07 |
| O_uniform | 1.00 | 0.83 | 0.11 | 0.22 | 0.06 | 0.07 |

The untrained grammar solves nothing beyond depth 3; the learned libraries solve most
depth-4 tasks and a quarter to a third of depth 5–8 tasks in the high-reuse cohorts
(`figures/solve_rate_by_depth.png`). At low reuse the learned arms stay at
0.50/0.17–0.33/≤0.11 for depths 3/4/5 and zero beyond, while the oracle library
reaches 1.00/0.75/0.56/0.12/0.22/0.00: the depth profile of the oracle shows what the
true abstractions can buy and how quickly the uniform-cost search saturates even
with them (depth 8 is out of reach for every arm at 10000 candidates).

By transfer type (final iteration): in the high-reuse cohorts B solves 0.53 / 0.36 /
0.69 of type I / II / III tasks (A: 0.33 / 0.18 / 0.06), i.e. the learned library
transfers to new outer contexts, new inner contexts and never-seen latent nestings;
type III is the least stable stratum (few tasks, SD 0.44). At medium reuse the
learned arms reach 0.25–0.36 on I/II and 0.07–0.13 on III versus the oracle's
0.47 / 0.53 / 0.26; at low reuse they do not exceed the prior-fit arm on II or III.

### 4.3 Experiment 3: abstraction recovery

Recovery of the cohort's active latents by the final library (behavioural criterion
unless stated; means over instances):

| Reuse | Arm | Inventions | Canonical recall | Type recall (perm.) | Behav. precision | Behav. recall | Behav. F1 | Weighted recall |
|---|---|---|---|---|---|---|---|---|
| low | B | 4.7 | 0.00 | 0.44 | 0.04 | 0.03 | 0.03 | 0.03 |
| low | C | 3.7 | 0.00 | 0.56 | 0.07 | 0.03 | 0.05 | 0.03 |
| low | D | 2.7 | 0.00 | 0.33 | 0.00 | 0.00 | 0.00 | 0.00 |
| low | E | 6.7 | 0.03 | 0.67 | 0.03 | 0.03 | 0.03 | 0.03 |
| medium | B | 6.3 | 0.00 | 0.78 | 0.12 | 0.11 | 0.11 | 0.11 |
| medium | C | 6.0 | 0.11 | 0.67 | 0.10 | 0.11 | 0.11 | 0.12 |
| medium | D | 4.0 | 0.11 | 0.67 | 0.19 | 0.11 | 0.14 | 0.12 |
| medium | E | 8.0 | 0.17 | 0.56 | 0.26 | 0.22 | 0.22 | 0.23 |
| high | B | 7.3 | 0.17 | 0.92 | 0.45 | 0.83 | 0.59 | 0.83 |
| high | C | 8.0 | 0.33 | 0.75 | 0.29 | 0.58 | 0.39 | 0.59 |
| high | D | 6.7 | 0.17 | 0.83 | 0.42 | 0.67 | 0.51 | 0.67 |
| high | E | 15.3 | 0.17 | 0.83 | 0.22 | 0.58 | 0.31 | 0.59 |

Behavioural recall by EC iteration (`figures/recall_by_iteration.png`), high reuse:
B 0.58 → 0.83 by iteration 2 and flat thereafter; D 0.33 → 0.67 by iteration 3;
C 0.25 → 0.58; E 0.17 → 0.58 by iteration 4. Medium reuse plateaus at 0.11 (0.22 for
E) by iteration 3–4; low reuse never exceeds 0.03. Recovery therefore happens in the
first two or three rounds or not at all, mirroring the training-set bootstrapping
curves (high reuse: B solves 11 → 24 → 27 → 28 → 28 → 29 of 56 training tasks; the
oracle library starts at 24).

Syntactic recovery is rare: canonical/β recall is 0.17–0.33 even at high reuse
because inventions are typically found in a different but equivalent form
(instance 101: latent `rotate90(translate(x, 1, 1))` is recovered by every arm as a
`translate(rotate90 x, …)` pattern with permuted offsets; latent
`translate(rotate90 x, 0, p)` is recovered by B as the curried invention
`λx. translate (rotate90 x) 0`, whose type `grid → int → grid` equals the latent's).
Type agreement alone (0.33–0.92) is far above behavioural recall and must not be
read as recovery. Precision is low everywhere (0.04–0.45): even the best library
(B at high reuse, 7.3 inventions for 3.3 recovered latents) carries about two
inventions per recovered latent, and the medium- and low-reuse libraries carry
5–20, many of them instantiations of the same latent with the parameter baked in
(B, instance 101: `translate (rotate90 x) 1 −1`, `translate (rotate90 x) 0`, …).

Exposure. Pooling the active latents of the three instances, latents whose final
persistent frontiers structurally contain them in at least two training tasks are
recovered by B in 5/6 (high), 2/5 (medium) and 0/2 (low) cases, whereas latents with
no syntactic frontier support are recovered in 4/5 (high; equivalent-form cases as
above), 0/8 (medium) and 1/30 (low) cases. At low reuse 30 of 36 active latents have
no frontier support at all: the compressor never sees them.

### 4.4 Experiment 4: compression versus generalisation

Final-iteration compression statistics and held-out effective complexity:

| Reuse | Arm | Cumulative ΔMDL | Inventions | Mean ΔL (held-out) | Fraction shortened | Mean ΔL under true library | Solve rate given shortened | given not shortened |
|---|---|---|---|---|---|---|---|---|
| medium | B | 13.9 | 6.3 | 0.56 | 0.28 | 2.76 | 0.43 | 0.24 |
| medium | C | 1.4 | 6.0 | 1.00 | 0.52 | 2.76 | 0.32 | 0.11 |
| medium | D | 10.4 | 4.0 | 0.80 | 0.36 | 2.76 | 0.30 | 0.21 |
| medium | E | 5.2 | 8.0 | 1.28 | 0.61 | 2.76 | 0.24 | 0.11 |
| high | B | 35.8 | 7.3 | 1.02 | 0.45 | 2.52 | 0.47 | 0.44 |
| high | C | 26.0 | 8.0 | 1.77 | 0.78 | 2.52 | 0.46 | 0.14 |
| high | D | 27.8 | 6.7 | 1.49 | 0.82 | 2.52 | 0.44 | 0.14 |
| high | E | 17.1 | 15.3 | 2.24 | 0.92 | 2.52 | 0.41 | 0.10 |

Correlations over learned-arm × instance × iteration cells (n = 108 per cohort):
cumulative ΔMDL versus solve rate has Spearman ρ = 0.03 / 0.63 / 0.17 / 0.58 for
zero / low / medium / high (0.57 pooled); mean ΔL versus solve rate has ρ = 0.02 /
0.67 / 0.34 / −0.27 (0.60 pooled). At the task level, tasks whose generator program
is shortened by the arm's library are solved far more often than unshortened ones
for the Stitch-objective and Stitch-proposal arms (high reuse: 0.40 versus 0.14–0.18),
but for B the two groups are solved equally (0.41 / 0.41) because B's inventions are
frequently behaviourally equivalent to, but syntactically different from, the latent
and therefore do not shorten the *generator* program while still shortening the
program the search actually finds.

Interpretation. Compression (ΔMDL) and shortening (ΔL) are associated with
generalisation across cohorts, but the association is coarse: at high reuse the arms
that shorten the held-out programs most (E: 92% of tasks, ΔL 2.24 of a possible 2.52)
solve fewer tasks than B (45%, 1.02), because E's fifteen inventions dilute the
grammar. Shorter effective programs are necessary but not sufficient; the prior over
the enlarged library matters as much (`O_uniform` versus `O`: +6.8 / +6.9 points at
high / medium reuse for fitted weights over uniform weights on the same true library).

### 4.5 Experiment 5: oracle gap

| Reuse | O−A | O−B | O−D | O−O_uniform | O_uniform−A0 |
|---|---|---|---|---|---|
| zero | 0.000 | −0.073 [−0.146, −0.010] | −0.021 [−0.115, 0.073] | +0.031 [−0.010, 0.083] | 0.000 |
| low | +0.292 [0.195, 0.393] | +0.282 [0.174, 0.390] | +0.271 [0.164, 0.382] | +0.001 [−0.073, 0.075] | +0.336 [0.237, 0.438] |
| medium | +0.262 [0.125, 0.414] | +0.182 [0.057, 0.299] | +0.206 [0.059, 0.345] | +0.069 [0.011, 0.161] | +0.341 [0.193, 0.494] |
| high | +0.161 [0.049, 0.287] | −0.057 [−0.143, 0.001] | +0.010 [−0.105, 0.108] | +0.068 [0.011, 0.159] | +0.266 [0.165, 0.375] |

The oracle gap is large at low reuse (+28 points over B, interval excluding zero),
moderate at medium reuse (+18) and absent at high reuse, where DreamCoder's learned
library matches the true library (O − B = −5.7 points, interval [−0.143, 0.001]) and
its held-out rank profile is similar (mean first-solution rank 2068 versus 1546). The
zero-reuse "oracle" is the base grammar and has no latents, so O = A there.

Perfect-Wake diagnostic (compressors applied to ground-truth programs; behavioural
recall / held-out solve rate at 10000, means over instances):

| Reuse | PW_B | PW_C | PW_D | PW_E | PWS_B | PWS_C | PWS_D | PWS_E | B (Wake) | O |
|---|---|---|---|---|---|---|---|---|---|---|
| low | timeout | 0.00 / 0.20 | 0 inventions / 0.19 | timeout | 0.03 / 0.17 | 0.00 / 0.14 | 0.00 / 0.17 | 0.00 / 0.14 | 0.03 / 0.12 | 1.00 / 0.40 |
| medium | timeout | 0.22 / 0.33 | 0.17 / 0.27 | timeout | 0.33 / 0.43 | 0.17 / 0.34 | 0.33 / 0.35 | 0.17 / 0.34 | 0.11 / 0.27 | 1.00 / 0.46 |
| high | timeout | 1.00 / 0.38 | 1.00 / 0.41 | timeout | 0.92 / 0.41 | 0.83 / 0.36 | 0.75 / 0.35 | 0.92 / 0.39 | 0.83 / 0.46 | 1.00 / 0.40 |

On the full 56-program corpus (`PW`) the DreamCoder-proposal compressors B and E did
not finish within the wall-clock limit in any cohort (1200 s on the first two
cohorts, 120 s afterwards): the inverse-β version space of a depth-8 program is
combinatorially large, so DreamCoder's candidate generation, which is fast on the
short programs Wake actually finds, does not scale to deep corpora. The
Stitch-proposal compressors finish in 3–53 s; with the DreamCoder objective (`PW_D`)
they recover every high-reuse latent with precision 0.89, one in six medium-reuse
latents and nothing at low reuse (no proposal improves the objective on a corpus of
single-program frontiers), and with the Stitch objective (`PW_C`) they accept 12
inventions everywhere, with *negative* DreamCoder ΔMDL at zero and low reuse.

On the shallow corpus (`PWS`, the 24 training programs of depth ≤ 4) every compressor
finishes in 1–33 s. With perfect exposure of the shallow tasks, DreamCoder's
compressor recovers 92% of the high-reuse latents and 33% of the medium-reuse
latents, and its held-out solve rate at medium reuse rises from 0.27 (B with real
Wake) to 0.43 (`PWS_B − B` = +0.159 [0.055, 0.264]), statistically indistinguishable
from the oracle library (`O − PWS_B` = +0.023 [−0.046, 0.092]). At low reuse perfect
exposure changes nothing (`PWS_B` recall 0.03, solve 0.17 versus O 0.40): with one or
two occurrences per latent no objective, Bayesian or leaf-cost, can justify an
invention. At high reuse perfect exposure is unnecessary (`PWS_B − B` = −0.047, the
Wake-found library is already as good as the true one).

### 4.6 Search exposure: Wake budget

Raising the Wake budget from 3000 to 10000 candidates raises the number of solved
training tasks in every cohort (high reuse: B 28.7 → 36.3 of 56; low reuse: 15.7 →
25.0) and the number of inventions, but leaves behavioural recall unchanged at high
and medium reuse (B: 0.83 / 0.11) and raises it only from 0.03 to 0.08 at low reuse.
Held-out solve rates move by +1 to +9 points with intervals that include zero except
D at high reuse (+7.1 [0.000, 0.168]). More exposure alone therefore does not close
the low/medium oracle gap: the additional solved training tasks are mostly deeper
tasks whose solutions reuse already-invented fragments, not new evidence for the
unrecovered latents.

### 4.7 Identical-input comparison (round 1)

With exactly the same base-grammar Wake frontiers, at high reuse B accepts 3
inventions with ΔMDL 19.7 and behavioural recall 0.58 after one round, D 2.7
inventions (ΔMDL 16.2, recall 0.33), C 3 (15.7, 0.25), E 3 (10.8, 0.17); the
resulting held-out solve rates are 0.35 (B) versus 0.28 (C, D) and 0.25 (E). Stitch
proposals selected by the DreamCoder objective (D) recover fewer latents from the
same frontiers than DreamCoder's own proposals (B), and the Stitch objective (C, E)
recovers fewer still, so on this benchmark the DreamCoder candidate generation is not
the weak link and the Bayesian MDL objective is the better selector.

### 4.8 Cost

Training all 96 runs (8 arms × 12 cohorts, 6 rounds) took 5310 s of kernel time on
four cores (Wake 152–664 s and compression 9–1584 s per arm summed over 72 runs;
Stitch-proposal compression is 10× cheaper than DreamCoder's on Wake frontiers);
held-out evaluation took 3454 s of search time for 604 grammars.

## 5. Answers to the five questions

1. **Can DreamCoder recover hidden reusable abstractions?** Yes, when they recur
often enough. With 15–18 deliberate uses per latent (high reuse) DreamCoder's
compressor recovers 83% of the active latents behaviourally (weighted by held-out
usage: 83%) within two EC rounds, and the learned library matches the true library
in held-out solve rate. With about five uses per latent (medium) recall falls to
11–22%, and with one or two uses (low) to 0–3%. Recovery is behavioural rather than
syntactic (canonical recall ≤ 0.33): the inventions are equivalent re-expressions
or curried/instantiated variants, and precision is low (0.04–0.45).

2. **Under what task distributions does abstraction learning help?** It helps in
proportion to reuse: +22 points of held-out solve rate at high reuse, +8 at medium
(interval includes zero), +1 at low, and, surprisingly, +7 at zero reuse through
incidental base-DSL fragments. It helps most on depth 4–6 tasks and transfers to
new outer contexts, new inner contexts and unseen nestings. It does not help when
each latent occurs once or twice in training, although the oracle shows that the
abstractions would have been worth 29 points there.

3. **Is current DreamCoder compression the bottleneck?** Not at high reuse: the
learned library is as good as the true one, so the remaining failures (solve rate
0.46) are search failures shared with the oracle. At medium reuse the bottleneck is
upstream of compression: given the ground-truth programs of the shallow training
tasks, the unchanged compressor triples its recall (0.11 → 0.33) and reaches the
oracle's held-out solve rate (0.43 versus 0.46), while larger Wake budgets add
solved tasks without adding the missing evidence. At low reuse compression *and*
exposure are both insufficient: 30 of 36 latents never appear in a found frontier,
and even with perfect exposure of the shallow tasks no compressor recovers latents
that occur once or twice. Where a latent is exposed in two or more found frontiers,
DreamCoder recovers it in 5/6 (high) but only 2/5 (medium) cases, so a
selection/objective limitation exists but is second-order.

4. **Does Stitch improve abstraction discovery?** No, on this benchmark. Stitch
proposals with the DreamCoder objective (D) and Stitch's own objective (C) recover
fewer latents than B at high reuse (0.67 / 0.58 versus 0.83) and give 6–7 points
lower held-out solve rates with intervals that include zero; they are equal to B
elsewhere. Stitch is 10× faster and scales to deep corpora where DreamCoder's
inverse-β candidate generation does not finish, which matters for perfect-exposure
corpora but not for the short programs Wake actually finds.

5. **Is the remaining gap due to search exposure, abstraction proposal, the
compression objective, or DSL limitations?**
   * Search exposure is the dominant cause at medium reuse: the unrecovered latents
     are not in any frontier, and perfect exposure of the shallow training tasks
     alone closes the oracle gap (`PWS_B` 0.43 versus `O` 0.46). At low reuse the
     cause is the reuse count itself: with one or two occurrences per latent neither
     objective accepts an invention even under perfect exposure, so the 29-point
     oracle gap there is not closable by any compressor in this family.
   * Abstraction proposal is not the cause: DreamCoder's proposals dominate Stitch's
     under the same objective (B > D) and the same proposals under the Stitch
     objective do worse (E ≤ B). Proposal *cost* is a real limitation of DreamCoder
     only on deep corpora (timeouts on the full perfect-Wake corpus), which Wake
     never produces here.
   * The compression objective contributes a second-order loss: exposed latents at
     medium reuse are recovered only 2/5 of the time and every arm has low precision.
   * DSL limitations do not explain the gap on this benchmark (latents are
     expressible and the oracle with the base DSL solves 40–46%), but the deep
     failures shared by every arm including the oracle (depth ≥ 7 solved ≤ 0.3 at
     10000 candidates) are limits of uniform-cost enumeration under the fixed
     grammar semantics, not of abstraction.

Negative results worth keeping: Stitch (in either role) does not beat DreamCoder;
shortening held-out programs is not sufficient for solving them (E shortens most and
solves least at high reuse); and the zero-reuse control is not a clean null.

## 6. Limitations

* Three benchmark instances give wide bootstrap intervals; most compressor
  contrasts include zero. The instance count, not the task count, limits power.
* The recognition model was switched off in every arm, so the results describe the
  library-learning half of the system only; the earlier controlled study measured
  the recognition contribution on a related benchmark.
* The held-out budget is 10000 candidates because of kernel memory; deeper tasks
  might separate arms differently at larger budgets, and the exposure
  sub-experiment stops at a 10000-candidate Wake for the same reason.
* Effective complexity ΔL is exact only in the β-normal subtree/slot rewrite space
  and syntactic exposure is a canonical-form check; both undercount equivalent
  re-expressions, which is why B can recover a latent with zero syntactic exposure.
* Behavioural equivalence uses 40 probes and the latent's valid parameter values;
  it is a witness, not a proof, and inventions that subsume a latent with an extra
  parameter are not credited.
* The perfect-Wake diagnostic ran with wall-clock limits and (for the full corpus)
  a limit lowered after two cohorts; timeouts are recorded as outcomes.
* Cohort sizes differ (23–32 held-out tasks) because some nested-transfer cells of
  the smallest pools could not be populated; the ragged bootstrap accounts for it.
* No claim is made about real ARC tasks or about neural recognition.

## 7. Reproduction and validation

```
python -m experiments.abstraction_learning.run benchmark          # generate, A0-calibrate, freeze (already done; hash-locked)
python -m experiments.abstraction_learning.run train --workers 4
python -m experiments.abstraction_learning.run perfect-wake --workers 2
python -m experiments.abstraction_learning.run evaluate --workers 2
python -m experiments.abstraction_learning.run analyze
python -m experiments.abstraction_learning.figures
python -m pytest tests/test_abstraction_learning.py -q
```

Validation status: `tests/test_abstraction_learning.py` (17 tests: generator
invariants on the three frozen instances, compressor soundness and B parity,
recovery metrics, learner caching, statistics helpers) passes; the pre-existing
suites `faithful/tests` and `tests` pass except for tests that need the pinned
upstream reference checkout (`faithful/reference/ec`, gitignored and absent in this
environment) and two hash checks of the historical controlled dataset whose recorded
digests were computed on CRLF files (the LF checkout hashes differ; verified by
re-hashing with CRLF). Benchmark manifests and the fixed-core hashes were verified
before and after every stage. Environment: Python 3.11, GHC 9.4.7, PyTorch 2.14
(CPU), stitch-core 0.1.29, four CPU cores, 16 GB RAM.

Run status: every stage is complete: training (96 runs), the perfect-Wake diagnostic
(96 compressor calls, 24 of them timeouts of B and E on the full corpus), the held-out
evaluation of 672 grammars (24 static, 576 trained-arm rounds, 72 perfect-Wake
libraries), the analysis and the figures. No evaluation search failed after the
budget cap (`results/abstraction_learning/evaluation_failures.json` does not exist).
