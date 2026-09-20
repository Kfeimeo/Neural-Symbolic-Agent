# Phase 2 Report: Full Faithful DreamCoder Recognition and the Wake Exposure Bottleneck

All numbers in this report are read from `results/full_dreamcoder/cells.json`,
`contrasts.json`, `per_latent.json`, `gap_closure.json`, `chain.json`,
`training_detail.json` and the generated `results/full_dreamcoder/tables.md`; figures
are in `results/full_dreamcoder/figures/`. The Phase 1 comparison arms (A0, A, B, O,
O_uniform, B_wake10000, PW/PWS) are the unchanged Phase 1 evaluation records in
`results/abstraction_learning/evaluation/`. The benchmark instances, the fixed core
(Haskell kernel, `faithful/python/*.py`, compression bridge) and the Phase 1 protocol
file were hash-verified before and after every stage.

## 1. Question

Phase 1 found that with recognition switched off, DreamCoder's compressor recovers
hidden latent abstractions only where Wake exposes them in at least two training-task
frontiers, that at medium reuse the unrecovered latents are simply absent from the
found frontiers, and that perfect exposure of the shallow training tasks (`PWS_B`)
closes most of the medium-reuse oracle gap without any change to the compressor.
Phase 2 asks whether the missing piece of the faithful system, the neural recognition
model that DreamCoder trains in its Sleep phase and uses to guide Wake, relieves this
bootstrapping bottleneck:

    recognition guidance -> latent exposure in Wake frontiers (ER@2)
                         -> behavioural abstraction recovery
                         -> better learned library
                         -> held-out solve rate.

Every link is measured separately. Training solve rate alone is not accepted as
evidence that the bottleneck is solved.

## 2. What changed and what did not

The only change is that the recognition pathway is switched on. Everything else is
the frozen Phase 1 setup, imported unchanged:

| Component | Phase 1 B | Phase 2 Full-DC |
|---|---|---|
| Benchmark | three frozen instances (seeds 101, 202, 303), four reuse cohorts, 56 training / 23–32 held-out tasks | identical (hash-verified) |
| Symbolic kernel, DSL, type system, enumeration | frozen `faithful/` core | identical |
| Wake budget | 3000 complete candidates per task, 3M-state cap, leaf size 33, depth 14, top-3 persistent frontiers rescored under the generative grammar | identical |
| Compressor | frozen Haskell DreamCoder `compress`, arity 1, up to 3 inventions per round, Bayesian MDL objective, inside-outside prior fit | identical |
| Rounds | 6 Explore–Compress rounds | identical |
| Recognition | off | **on**: after every compression, 64 ancestral Dream draws from the current generative grammar (executed on the inputs of the first training task, failed draws counted), Replay of the persistent frontiers rewritten under the current library, a fresh task-conditioned AST-bigram recognition network (`faithful/python/recognition.py`, root / variable / production × argument contexts) trained for 600 steps of the unchanged `frontierBiasOptimal` objective; the next Wake enumerates every training task under its own search grammar and rescores solutions under the generative grammar before merging |
| Held-out evaluation | one uniform-cost enumeration of 10000 candidates under the learned grammar; prefix-exact solve outcomes at 100, 300, 1000, 3000, 10000 | identical for the `library` mode; two additional modes search every held-out task under its task-conditioned search grammar (`recognition`) or under the grammar of a different held-out task (`shuffle`, a derangement control) |
| Training seeds | none (every stage deterministic) | seed 1 on every cohort (primary); seeds 2 and 3 added on the medium-reuse cohorts, the focus regime |

The recipe is the accepted recognition recipe of the frozen core (the arm D of the
earlier controlled study), applied without modification inside the Phase 1 loop.
Round 1 has no trained model, so it is exactly B's round 1; `results/full_dreamcoder/parity.json`
records that every Full-DC run reproduces B's round-1 frontiers, grammar and Wake
ranks bit for bit, and that re-searching the Phase 1 B grammars of instance 101 with
the kernel compiled on this machine reproduces the Phase 1 first-solution ranks task
by task. No neural decomposition, partial-program mining, Stitch change or other
new method is used.

## 3. Metrics

All metrics use the Phase 1 task splits, frontier representation, equivalence
criteria and budgets.

* **Training solve rate**: solved persistent frontiers / 56 after each round.
* **Latent frontier support** `Support(F_i)`: number of *distinct* training tasks
  whose persistent frontier contains a program that the Phase 1 exact rewrite can
  shorten with `F_i` (the Phase 1 syntactic-exposure criterion; `frontier_support`
  in `experiments/abstraction_learning/evaluation.py`), computed after every round.
* **ER@k** = fraction of active latents with `Support >= k`; ER@2 is the primary
  exposure metric.
* **Behavioural recovery**: Phase 1 criterion (type-compatible up to argument order,
  identical outputs on the 40 recovery probes for every valid parameter value, no
  credit for inventions with more parameters); precision over inventions, recall over
  active latents, F1, and `P(recovered | Support >= 2)` versus `P(recovered | Support < 2)`.
* **Held-out solve rate** `S(B)` at B ∈ {100, 300, 1000, 3000, 10000}; primary
  endpoint `S(10000)`; unsolved tasks have `r_t > 10000`.
* **First-solution rank** `r_t` over solved tasks (mean, median, quartiles) and the
  full curve `S(B)`, so that search efficiency is compared without conditioning on the
  solved set.
* **Gap closure**: `(FullDC − B) / (reference − B)` with reference = perfect-Wake
  support (exposure), `PWS_B` and the oracle (recovery), `O` (solve rate).
* Statistics: means ± sample SD over the three instances; contrasts use the Phase 1
  two-way paired bootstrap (instances × held-out tasks, 2000 draws). With three
  instances the intervals are wide and conditional on the generated instances.


## 4. Results

Unless stated otherwise, numbers are means over the three instances at the final
(sixth) round, primary training seed; `B` is the Phase 1 arm; `FullDC` is the
Full-DC library evaluated alone (Phase 1 protocol), `FullDC_rec` the same library
searched with its recognition model, `FullDC_shuffle` the deranged-guidance control.

### 4.1 Training solve rate: recognition relieves the search half of the bottleneck

Solved persistent frontiers / 56 after each round (`tables.md`, "Training solve rate"):

| Reuse | Arm | it 1 | it 2 | it 3 | it 4 | it 5 | it 6 |
|---|---|---|---|---|---|---|---|
| low | B | 0.190 | 0.250 | 0.268 | 0.274 | 0.280 | 0.280 |
| low | FullDC | 0.190 | 0.333 | 0.387 | 0.446 | 0.470 | 0.500 |
| medium | B | 0.185 | 0.244 | 0.268 | 0.280 | 0.280 | 0.280 |
| medium | FullDC | 0.185 | 0.292 | 0.345 | 0.357 | 0.381 | 0.411 |
| high | B | 0.196 | 0.423 | 0.482 | 0.500 | 0.506 | 0.512 |
| high | FullDC | 0.196 | 0.429 | 0.524 | 0.583 | 0.613 | 0.631 |
| zero | B | 0.202 | 0.244 | 0.280 | 0.280 | 0.280 | 0.280 |
| zero | FullDC | 0.202 | 0.333 | 0.393 | 0.423 | 0.446 | 0.458 |

Round 1 is identical by construction. From round 2 on, the guided Wake solves more
training tasks in every cohort and keeps improving where B has plateaued: after six
rounds Full-DC solves 12.3 (low), 7.3 (medium), 6.7 (high) and 10.0 (zero) more
training tasks than B on average and loses none; the new tasks are almost all of
depth 4–8 (`training_detail.json`). The final Full-DC training solve rate is above
the oracle library's (`O`: 0.339 at low and medium reuse) and comparable to a
10000-candidate unguided Wake (`B_wake10000`: 0.446 / 0.399 / 0.649) at one third
of the candidate budget. Per round, the guided Wake also finds solutions earlier
(mean first-solution rank of the tasks solved in that round at high reuse: 192 for
B versus 124 for Full-DC in round 6). This is the direct, expected effect of
recognition, and by itself it says nothing about abstraction.

### 4.2 Latent frontier support and exposure recall: the exposure gap barely moves

ER@1 / ER@2 by round (fraction of active latents with support in ≥ 1 / ≥ 2 distinct
training tasks; Phase 1 syntactic criterion):

| Reuse | Arm | Metric | it 1 | it 2 | it 3 | it 4 | it 5 | it 6 | perfect Wake | PWS_B |
|---|---|---|---|---|---|---|---|---|---|---|
| low | B | ER@2 | 0.03 | 0.06 | 0.03 | 0.06 | 0.06 | 0.06 | 0.50 | 0.08 |
| low | FullDC | ER@2 | 0.03 | 0.06 | 0.08 | 0.14 | 0.17 | 0.14 | | |
| low | B | ER@1 | 0.19 | 0.19 | 0.17 | 0.17 | 0.17 | 0.17 | | |
| low | FullDC | ER@1 | 0.19 | 0.28 | 0.28 | 0.31 | 0.25 | 0.28 | | |
| medium | B | ER@2 | 0.06 | 0.22 | 0.22 | 0.28 | 0.28 | 0.28 | 1.00 | 1.00 |
| medium | FullDC | ER@2 | 0.06 | 0.28 | 0.39 | 0.33 | 0.33 | 0.39 | | |
| medium | B | ER@1 | 0.72 | 0.61 | 0.61 | 0.56 | 0.56 | 0.56 | | |
| medium | FullDC | ER@1 | 0.72 | 0.72 | 0.61 | 0.56 | 0.56 | 0.61 | | |
| high | B | ER@2 | 1.00 | 0.58 | 0.50 | 0.50 | 0.50 | 0.50 | 1.00 | 1.00 |
| high | FullDC | ER@2 | 1.00 | 0.75 | 0.50 | 0.58 | 0.50 | 0.50 | | |

Support distribution at the final round (mean support per active latent; histogram
of latents with support 0 / 1 / 2 / 3 / 4 / 5 / ≥ 6, pooled over instances):

| Reuse | Arm | Mean support | Median | ER@1 | ER@2 | Histogram |
|---|---|---|---|---|---|---|
| low | B | 0.36 | 0.0 | 0.17 | 0.06 | 30 / 4 / 1 / 0 / 0 / 0 / 1 |
| low | FullDC | 0.50 | 0.0 | 0.28 | 0.14 | 26 / 5 / 2 / 3 / 0 / 0 / 0 |
| low | B_wake10000 | 0.64 | 0.0 | 0.25 | 0.14 | 27 / 4 / 2 / 1 / 0 / 1 / 1 |
| medium | B | 1.39 | 0.7 | 0.56 | 0.28 | 8 / 5 / 2 / 1 / 0 / 1 / 1 |
| medium | FullDC | 1.78 | 1.0 | 0.61 | 0.39 | 7 / 4 / 2 / 2 / 2 / 0 / 1 |
| medium | B_wake10000 | 2.06 | 1.3 | 0.72 | 0.33 | 5 / 7 / 1 / 1 / 1 / 0 / 3 |
| medium | PWS_B | 2.22 | 2.2 | 1.00 | 1.00 | 0 / 0 / 14 / 4 / 0 / 0 / 0 |
| high | B | 4.67 | 4.2 | 0.58 | 0.50 | 5 / 1 / 1 / 0 / 1 / 0 / 4 |
| high | FullDC | 6.58 | 6.2 | 0.67 | 0.50 | 4 / 2 / 0 / 0 / 0 / 0 / 6 |

Recognition raises ER@2 from 0.28 to 0.39 at medium reuse and from 0.06 to 0.14 at
low reuse, and leaves it at 0.50 at high reuse. Against the perfect-Wake reference
(ER@2 = 1.00 at medium and high, 0.50 at low, from the generating programs) this
closes 15% (medium), 19% (low) and 0% (high) of the exposure gap; the remaining
gap is 0.61 (medium), 0.36 (low) and 0.50 (high) in ER@2. The latents that had no
frontier support under B mostly still have none: 7 of 18 medium-reuse latents and
26 of 36 low-reuse latents. Support rose for 7 medium latents, fell for 3 and was
unchanged for 8; the same 10000-candidate unguided Wake of Phase 1 (`B_wake10000`)
reaches a similar ER@2 (0.33 medium, 0.14 low), so guided search at 3000 candidates
exposes about as many latents as brute-force search at 10000.

Why does a 60–80% increase in solved latent-bearing training tasks not translate
into support? The decomposition over (active latent, deliberate training task)
pairs (`tables.md`, "Exposure decomposition"):

| Reuse | Arm | Pairs | Solved | P(solved) | Supported | P(supported given solved) | Latents with no deliberate task solved | Latents solved but never supported |
|---|---|---|---|---|---|---|---|---|
| low | B | 42 | 10 | 0.24 | 5 | 0.50 | 26 / 36 | 5 |
| low | FullDC | 42 | 18 | 0.43 | 6 | 0.33 | 18 / 36 | 12 |
| medium | B | 93 | 25 | 0.27 | 15 | 0.60 | 5 / 18 | 3 |
| medium | FullDC | 93 | 41 | 0.44 | 14 | 0.34 | 2 / 18 | 6 |
| high | B | 200 | 99 | 0.49 | 39 | 0.39 | 0 / 12 | 6 |
| high | FullDC | 200 | 123 | 0.61 | 52 | 0.42 | 0 / 12 | 4 |

At medium reuse the guided Wake solves 41 instead of 25 of the 93 latent-bearing
training tasks (the number of latents none of whose tasks is solved falls from 5 to
2), but the fraction of solved tasks whose frontier structurally contains the latent
falls from 0.60 to 0.34, so the number of supported pairs is unchanged (15 versus
14). The additional solutions are re-expressions: programs that compute the task
but do not contain the latent in the syntactic form the inverse-β candidate
generator needs (commuted stages such as `recolor(trim x)` for `trim(recolor x)`,
permuted translation offsets, or instantiations through earlier inventions). The
same happens at low reuse (0.50 → 0.33) while at high reuse, where most latents are
already exposed, the fraction is stable (0.39 → 0.42).

To separate "the task is solved in another form" from "the task is solved by a
different decomposition", a behavioural exposure diagnostic was added
(`experiments/full_dreamcoder/exposure.py`; `behavioural_exposure.json`): a frontier
behaviourally exposes latent `F` when it contains a subexpression `s` and a strict
sub-subexpression `t` (possibly the task input) with `s(x) = F(t(x), v)` on the 40
recovery probes for some valid parameter value `v`, in any syntactic form, and with
`F` acting non-trivially on `t`. Final round, pooled over instances:

| Reuse | Arm | Behav. ER@1 | Behav. ER@2 (syntactic ER@2) | Mean behav. support (syntactic) | Solved pairs | Behav. supported | Syntactic supported | Latents behav. ≥ 2 (syntactic ≥ 2) |
|---|---|---|---|---|---|---|---|---|
| low | B | 0.44 | 0.14 (0.06) | 0.78 (0.36) | 10 | 8 | 5 | 5/36 (2/36) |
| low | FullDC | 0.69 | 0.39 (0.14) | 1.58 (0.50) | 18 | 11 | 6 | 14/36 (5/36) |
| low | B_wake10000 | 0.56 | 0.31 (0.14) | 1.56 (0.64) | 16 | 11 | 7 | 11/36 (5/36) |
| low | PWS_B | 0.64 | 0.17 (0.08) | 0.83 (0.67) | 18 | 18 | 18 | 6/36 (3/36) |
| medium | B | 0.94 | 0.56 (0.28) | 2.83 (1.39) | 25 | 23 | 15 | 10/18 (5/18) |
| medium | FullDC | 0.94 | 0.78 (0.39) | 4.33 (1.78) | 41 | 34 | 14 | 14/18 (7/18) |
| medium | FullDC_t2 | 1.00 | 0.89 | 4.06 | 43 | 35 | | 16/18 |
| medium | FullDC_t3 | 0.94 | 0.89 | 4.89 | 41 | 34 | | 16/18 |
| medium | B_wake10000 | 0.94 | 0.78 (0.33) | 4.50 (2.06) | 44 | 39 | 23 | 14/18 (6/18) |
| medium | PWS_B | 1.00 | 1.00 (1.00) | 2.44 (2.22) | 37 | 37 | 37 | 18/18 (18/18) |
| high | B | 1.00 | 1.00 (0.50) | 11.58 (4.67) | 99 | 90 | 39 | 12/12 (6/12) |
| high | FullDC | 1.00 | 1.00 (0.50) | 16.75 (6.58) | 123 | 114 | 52 | 12/12 (6/12) |

Behaviourally, recognition *does* bring the latents into the Wake frontiers: at
medium reuse the fraction of active latents computed inside at least two solved
frontiers rises from 0.56 (B) to 0.78 (0.89 for both replication seeds), at low
reuse from 0.14 to 0.39, and 83–93% of the solved latent-bearing tasks contain the
latent behaviourally under every arm. The syntactic criterion that the frozen
compressor's candidate generation actually relies on sees a third of this (0.39 and
0.14). The perfect-Wake reference is the only arm where behavioural and syntactic
exposure coincide (its frontiers *are* the generating programs), and it is also the
only arm whose compressor recovers a third of the medium-reuse latents. The Wake
exposure bottleneck of Phase 1 is therefore relieved in the sense that matters for
search (the latent-bearing tasks are solved and the latents are present as
computations) but not in the sense that matters for DreamCoder's compressor, which
proposes inventions only from syntactically identical inverse-β fragments.

### 4.3 Behavioural abstraction recovery: one more latent at medium reuse

| Reuse | Arm | Inventions | Behav. precision | Behav. recall | Behav. F1 | Weighted recall |
|---|---|---|---|---|---|---|
| low | B | 4.7 | 0.037 | 0.028 | 0.032 | 0.026 |
| low | FullDC | 13.0 | 0.024 | 0.028 | 0.026 | 0.026 |
| low | B_wake10000 | 10.0 | 0.107 | 0.083 | 0.090 | 0.078 |
| low | PWS_B | 5.7 | 0.037 | 0.028 | 0.032 | 0.026 |
| medium | B | 6.3 | 0.117 | 0.111 | 0.108 | 0.114 |
| medium | FullDC | 11.0 | 0.095 | 0.167 | 0.120 | 0.173 |
| medium | B_wake10000 | 9.3 | 0.083 | 0.111 | 0.093 | 0.118 |
| medium | PWS_B | 10.3 | 0.187 | 0.333 | 0.239 | 0.327 |
| high | B | 7.3 | 0.452 | 0.833 | 0.586 | 0.826 |
| high | FullDC | 14.3 | 0.246 | 0.833 | 0.378 | 0.826 |
| high | PWS_B | 6.3 | 0.579 | 0.917 | 0.709 | 0.923 |

Recall by round at medium reuse: B 0.00 / 0.06 / 0.06 / 0.11 / 0.11 / 0.11, Full-DC
0.00 / 0.06 / 0.11 / 0.17 / 0.17 / 0.17. Full-DC recovers one more medium-reuse
latent (on instance 303) and nothing more at low or high reuse; it accepts about
twice as many inventions as B (11–14 versus 5–7), so precision and F1 fall. Against
`PWS_B` (recall 0.333 at medium reuse) this closes 25% of the recovery gap at medium
reuse and 0% at low and high; against the oracle (recall 1) it closes 6% at medium
reuse. The remaining recovery gap to the oracle is 0.83 (medium) and 0.97 (low).

Recovery conditional on support, latents pooled over instances (final round):

| Reuse | Arm | P(recovered given support ≥ 2) | P(recovered given support < 2) |
|---|---|---|---|
| low | B | 0/2 | 1/34 |
| low | FullDC | 0/5 | 1/31 |
| medium | B | 2/5 = 0.40 | 0/13 |
| medium | FullDC | 2/7 = 0.29 | 1/11 = 0.09 |
| medium | PWS_B | 6/18 = 0.33 | – |
| high | B | 5/6 = 0.83 | 5/6 = 0.83 |
| high | FullDC | 5/6 = 0.83 | 5/6 = 0.83 |

The exposure transition table shows where the medium-reuse recall gain comes from.
Of the 18 medium-reuse latents, 4 had support ≥ 2 under both arms (2 recovered by
both), 3 gained support ≥ 2 only under Full-DC (0 recovered), 1 lost it (0
recovered) and 10 stay below 2 under both. The one additional recovery (instance
303, `translate(transpose x, −1, −1)`) has support 0 under both arms: it was found
as a behaviourally equivalent invention of a different form, exactly like the
zero-support recoveries of Phase 1 at high reuse. None of the three latents that
recognition newly exposed in two or more frontiers (support 2, 2 and 3) was
accepted by the compressor. The exposure → recovery link therefore did not fire on
the latents recognition exposed, and the recovery gain did not come through
exposure.

### 4.4 Held-out solve rate and search cost

Solve curves S(B) at the final round (fraction of held-out tasks whose first
solution has rank ≤ B; unsolved tasks have r > 10000):

| Reuse | Arm | S(100) | S(300) | S(1000) | S(3000) | S(10000) |
|---|---|---|---|---|---|---|
| low | A | 0.000 | 0.000 | 0.022 | 0.066 | 0.110 |
| low | B | 0.000 | 0.000 | 0.011 | 0.033 | 0.121 |
| low | FullDC | 0.022 | 0.022 | 0.044 | 0.153 | 0.260 |
| low | FullDC_rec | 0.033 | 0.033 | 0.086 | 0.239 | 0.283 |
| low | FullDC_shuffle | 0.033 | 0.033 | 0.086 | 0.207 | 0.284 |
| low | B_wake10000 | 0.000 | 0.000 | 0.033 | 0.086 | 0.140 |
| low | PWS_B | 0.011 | 0.022 | 0.034 | 0.120 | 0.174 |
| low | O | 0.011 | 0.076 | 0.185 | 0.271 | 0.402 |
| medium | A | 0.011 | 0.011 | 0.023 | 0.080 | 0.194 |
| medium | B | 0.023 | 0.069 | 0.103 | 0.160 | 0.274 |
| medium | FullDC | 0.023 | 0.034 | 0.114 | 0.206 | 0.320 |
| medium | FullDC_rec | 0.011 | 0.046 | 0.149 | 0.285 | 0.388 |
| medium | FullDC_shuffle | 0.023 | 0.046 | 0.149 | 0.239 | 0.377 |
| medium | B_wake10000 | 0.011 | 0.046 | 0.114 | 0.194 | 0.365 |
| medium | PWS_B | 0.034 | 0.080 | 0.148 | 0.273 | 0.433 |
| medium | O | 0.023 | 0.114 | 0.183 | 0.297 | 0.456 |
| high | A | 0.000 | 0.000 | 0.014 | 0.103 | 0.241 |
| high | B | 0.039 | 0.081 | 0.248 | 0.355 | 0.459 |
| high | FullDC | 0.054 | 0.121 | 0.248 | 0.370 | 0.512 |
| high | FullDC_rec | 0.064 | 0.128 | 0.246 | 0.367 | 0.473 |
| high | FullDC_shuffle | 0.039 | 0.103 | 0.235 | 0.352 | 0.416 |
| high | B_wake10000 | 0.039 | 0.092 | 0.220 | 0.394 | 0.470 |
| high | PWS_B | 0.036 | 0.117 | 0.184 | 0.291 | 0.412 |
| high | O | 0.068 | 0.081 | 0.234 | 0.352 | 0.402 |
| zero | B | 0.021 | 0.021 | 0.042 | 0.094 | 0.208 |
| zero | FullDC | 0.010 | 0.042 | 0.083 | 0.125 | 0.229 |
| zero | FullDC_rec | 0.021 | 0.083 | 0.115 | 0.156 | 0.292 |
| zero | FullDC_shuffle | 0.010 | 0.062 | 0.104 | 0.146 | 0.260 |

Paired contrasts at 10000 candidates (mean difference, two-way bootstrap 95% CI):

| Reuse | FullDC − B | FullDC_rec − B | FullDC_rec − FullDC | FullDC_rec − FullDC_shuffle | O − FullDC | O − FullDC_rec | PWS_B − FullDC |
|---|---|---|---|---|---|---|---|
| zero | +0.021 [−0.062, 0.104] | +0.083 [−0.021, 0.198] | +0.062 [−0.042, 0.167] | +0.031 [0.000, 0.083] | −0.094 [−0.188, 0.000] | −0.156 [−0.292, −0.031] | −0.010 [−0.115, 0.115] |
| low | +0.139 [0.031, 0.246] | +0.162 [0.046, 0.284] | +0.023 [−0.115, 0.143] | −0.001 [−0.046, 0.042] | +0.143 [0.016, 0.256] | +0.120 [0.021, 0.233] | −0.086 [−0.189, 0.011] |
| medium | +0.046 [−0.057, 0.184] | +0.115 [−0.010, 0.253] | +0.069 [−0.034, 0.172] | +0.011 [−0.057, 0.080] | +0.136 [0.011, 0.264] | +0.068 [−0.047, 0.180] | +0.113 [−0.034, 0.253] |
| high | +0.053 [−0.037, 0.155] | +0.014 [−0.071, 0.102] | −0.039 [−0.121, 0.055] | +0.057 [0.000, 0.158] | −0.110 [−0.226, −0.014] | −0.071 [−0.202, 0.039] | −0.100 [−0.232, 0.011] |

Findings. (i) The Full-DC *library* alone improves held-out solving at every reuse
level, significantly so at low reuse (+13.9 points, interval excluding zero) and
nominally at medium (+4.6) and high (+5.3). The low-reuse gain is not an
abstraction-recovery effect (recall stays at 0.03): the library has 13 inventions
instead of 5, more solved training tasks feed the prior fit, and the depth profile
(d = 4–7: 0.42 / 0.22 / 0.23 / 0.17 versus B 0.17 / 0.11 / 0.07 / 0.00) shows a
general search-prior improvement rather than the oracle's profile. (ii) Searching
held-out tasks with the recognition model adds a further +2 to +7 points at zero,
low and medium reuse and −4 at high reuse (all intervals include zero). (iii) The
deranged-guidance control matches the task-specific guidance almost everywhere
(`FullDC_rec − FullDC_shuffle`: −0.001 low, +0.011 medium; +0.057 [0.000, 0.158]
high): the test-time recognition gain is a generic learned bigram prior (trained
on dreams and replayed frontiers), not task conditioning. The same was found in the
earlier controlled study on a related benchmark. (iv) The oracle gap closes by 49%
(library) / 58% (recognition) at low reuse and by 25% / 63% at medium reuse; the
remaining gap to `O` is +0.14 / +0.12 (low) and +0.14 / +0.07 (medium), with the
library-only gaps still excluding zero. At high reuse Full-DC exceeds the oracle
library (`O − FullDC` = −0.110 [−0.226, −0.014]) as B already nearly did. (v) The
perfect-Wake shallow library `PWS_B` still beats the Full-DC library at medium reuse
by +11 points (interval includes zero) with a third of the inventions: perfect
exposure of the shallow tasks remains a better path to the library than recognition.

First-solution ranks over solved held-out tasks (final round, mean over instances):

| Reuse | Arm | Solved tasks | Mean rank | Median | Q1 | Q3 |
|---|---|---|---|---|---|---|
| low | B | 3.7 | 4217 | 4308 | 3087 | 5352 |
| low | FullDC | 8.0 | 3333 | 3288 | 1409 | 4953 |
| low | FullDC_rec | 8.7 | 2005 | 1592 | 844 | 2290 |
| low | O | 12.3 | 2186 | 1474 | 474 | 3447 |
| medium | B | 8.0 | 3007 | 1994 | 633 | 5688 |
| medium | FullDC | 9.3 | 2711 | 2075 | 741 | 3759 |
| medium | FullDC_rec | 11.3 | 2555 | 1286 | 694 | 3499 |
| medium | O | 13.3 | 2719 | 1762 | 550 | 4197 |
| high | B | 11.7 | 2068 | 914 | 532 | 2372 |
| high | FullDC | 13.0 | 2591 | 1207 | 388 | 4278 |
| high | FullDC_rec | 12.0 | 1677 | 750 | 323 | 1898 |
| high | O | 10.3 | 1546 | 759 | 399 | 1831 |

Full-DC solves more tasks *and* solves them earlier: the full curves above show the
mass shifting to smaller budgets (low reuse S(3000): 0.033 → 0.153 → 0.239 for
B → FullDC → FullDC_rec; medium 0.160 → 0.206 → 0.285), so the lower conditional
mean ranks are not an artefact of a changed solved set. At high reuse the library
alone solves more tasks at a slightly higher mean rank (the new solutions are deep
tasks) and recognition at test time lowers the ranks without adding tasks. No
search was state-limited (maximum 60k expanded states at 10000 candidates).

### 4.5 The causal chain, cohort by cohort

Per-cohort deltas (Full-DC − B, final round; `chain.json`):

| Reuse | Instance | Δ training solve | Δ ER@2 | Δ recall | Δ solve (library) | Δ solve (recognition) |
|---|---|---|---|---|---|---|
| low | 101 | +0.143 | 0.00 | 0.00 | +0.129 | +0.258 |
| low | 202 | +0.250 | +0.08 | 0.00 | +0.219 | +0.125 |
| low | 303 | +0.268 | +0.17 | 0.00 | +0.069 | +0.103 |
| medium | 101 | +0.054 | +0.17 | 0.00 | 0.000 | +0.033 |
| medium | 202 | +0.089 | 0.00 | 0.00 | −0.034 | +0.103 |
| medium | 303 | +0.250 | +0.17 | +0.17 | +0.172 | +0.207 |
| high | 101 | +0.054 | 0.00 | 0.00 | +0.032 | 0.000 |
| high | 202 | +0.179 | 0.00 | 0.00 | +0.043 | +0.043 |
| high | 303 | +0.125 | 0.00 | 0.00 | +0.083 | 0.000 |

Sign counts over the nine reuse cohorts: Δ training solve > 0 in 9/9; Δ ER@2 > 0 in
4/9 (0 in 5/9); Δ recall > 0 in 1/9; Δ held-out solve (library) > 0 in 7/9. The
chain `recognition → ER@2 → recovery → library → held-out` holds at its first link
everywhere, weakens at the second (exposure moves in fewer than half the cohorts,
and by one latent where it does), and breaks at the third (one cohort recovers one
more latent, and not through exposure). The held-out gains occur in cohorts with no
recovery change at all, so they travel through a different route: a larger solved
training set, a better-fitted grammar with more (incidental) inventions, and, with
recognition at test time, a learned generic bigram prior. Rank correlations over the
nine cohorts (Spearman: Δ ER@2 versus Δ recall 0.30; Δ recall versus Δ solve 0.41;
Δ ER@2 versus Δ solve 0.14) are weak and not interpretable with n = 9.

### 4.6 Medium reuse in detail

Per latent (instance / latent / expression / deliberate uses / support B → Full-DC /
recovered by B, Full-DC, PWS_B):

| Instance | Latent | Expression | Uses | Support B → FullDC | Full-DC support by round | Rec. B / FullDC / PWS_B |
|---|---|---|---|---|---|---|
| 101 | F00 | `rotate90(translate(x, 1, 1))` | 6 | 0 → 0 | 1 1 0 0 0 0 | no / no / yes |
| 101 | F01 | `trim(recolor(x, red, blue))` | 5 | 0 → 0 | 0 0 0 0 0 0 | no / no / yes |
| 101 | F04 | `solid(flipV x, p)` | 5 | 3 → 3 | 1 1 1 2 3 3 | yes / yes / no |
| 101 | F05 | `recolor(flipV x, blue, p)` | 5 | 1 → 2 | 1 1 1 1 1 2 | no / no / no |
| 101 | F08 | `translate(rotate90 x, 0, p)` | 5 | 8 → 10 | 1 4 6 8 8 10 | no / no / no |
| 101 | F09 | `translate(recolor(x, red, green), p, 0)` | 5 | 0 → 0 | 0 0 0 0 0 0 | no / no / no |
| 202 | F00 | `border(solid(x, blue))` | 4 | 5 → 4 | 4 4 6 4 4 4 | yes / yes / yes |
| 202 | F01 | `solid(flipV x, blue)` | 5 | 0 → 0 | 0 0 0 0 0 0 | no / no / yes |
| 202 | F04 | `recolor(rotate90 x, p, red)` | 5 | 1 → 2 | 1 1 2 2 2 2 | no / no / no |
| 202 | F05 | `flipH(solid(x, p))` | 5 | 2 → 1 | 1 1 1 0 0 1 | no / no / no |
| 202 | F08 | `solid(translate(x, p, 0), blue)` | 5 | 1 → 1 | 1 1 1 1 1 1 | no / no / yes |
| 202 | F09 | `translate(recolor(x, red, green), p, 0)` | 5 | 0 → 0 | 0 0 0 0 0 0 | no / no / no |
| 303 | F00 | `translate(transpose x, −1, −1)` | 5 | 0 → 0 | 1 1 0 0 0 0 | no / **yes** / no |
| 303 | F01 | `flipH(recolor(x, red, blue))` | 5 | 2 → 4 | 1 2 2 4 4 4 | no / no / yes |
| 303 | F04 | `transpose(solid(x, p))` | 6 | 0 → 1 | 1 1 2 1 1 1 | no / no / no |
| 303 | F05 | `rotate180(solid(x, p))` | 5 | 1 → 0 | 1 2 2 1 0 0 | no / no / no |
| 303 | F08 | `translate(rotate90 x, p, −1)` | 7 | 0 → 1 | 0 0 0 0 1 1 | no / no / no |
| 303 | F09 | `flipH(translate(x, p, 0))` | 6 | 1 → 3 | 1 2 2 3 3 3 | no / no / no |

Three patterns stand out. First, the latents that B never exposed (`F00`, `F01`,
`F09` of instance 101; `F01`, `F09` of 202; `F00` of 303) are still unexposed after
six guided rounds, although several of their tasks are now solved: they are
compositions of commuting or offset-permutable stages whose found solutions take
another form (`trim(recolor(...))` versus `recolor(trim(...))`, `rotate90 ∘
translate` versus `translate ∘ rotate90`). Second, support that grows across
rounds (101 `F08`: 1 → 10; 303 `F01`: 1 → 4; 303 `F09`: 1 → 3) does so through
tasks solved with the *same* instantiation of the latent, and the compressor then
accepts instantiated inventions with the parameter baked in (as in Phase 1) rather
than the parametrised latent, so recall does not move. Third, `PWS_B`, which sees
the shallow generating programs once, recovers five of these latents that Full-DC
does not, confirming that the missing ingredient is the syntactic form in which
the latent enters the frontier, not the number of solved tasks.

REPLICATION_PLACEHOLDER

### 4.7 Cost

Per run (six rounds, primary seed, mean over instances): guided Wake 590–625 s
(B: 13 s; the enumeration under a task-conditioned grammar is repeated per task
instead of once per cohort), compression 105–115 s, Dream 2.5 s, recognition
training 14 s. Held-out evaluation per round: 7 s with the library alone, 260–283 s
with per-task recognition-guided search. Training all 18 runs took 65 minutes on
four cores; the evaluation of 234 grammar × mode cells about 130 minutes.

## 5. Answers

**Does full faithful DreamCoder recognition significantly relieve the Wake →
abstraction bootstrapping bottleneck found in Phase 1?** Only its search half.
Recognition-guided Wake raises the training solve rate in every cohort (by 7–12
tasks of 56, mostly at depth 4–8) and, downstream, the held-out solve rate (library
alone: +13.9 points at low reuse with an interval excluding zero, +4.6 at medium,
+5.3 at high; with recognition at test time +16.2 / +11.5 / +1.4). But the
exposure → recovery half is essentially untouched:

* exposure: ER@2 rises from 0.28 to 0.39 at medium reuse and from 0.06 to 0.14 at
  low reuse (15% and 19% of the exposure gap to a perfect Wake), and not at all at
  high reuse; the count of supported (latent, task) pairs is unchanged at medium
  reuse (15 → 14) because the additional solved latent-bearing tasks are solved in
  re-expressed forms (P(supported | solved) 0.60 → 0.34);
* recovery: one more latent at medium reuse (recall 0.11 → 0.17, 25% of the gap to
  `PWS_B`, 6% of the gap to the oracle), recovered in an equivalent form without
  syntactic exposure; none of the three latents recognition newly exposed was
  accepted; nothing at low or high reuse, with precision halved by twice as many
  inventions;
* oracle gap: 25% (library) / 63% (with test-time recognition) closed at medium
  reuse and 49% / 58% at low reuse, but the recognition part of the closure is a
  generic learned bigram prior (the deranged control performs the same) rather than
  a better library, and `PWS_B` still beats the Full-DC library at medium reuse.

Training solve rate and held-out solve rate therefore improve without the causal
chain through abstraction: the recognition model makes search better, not
abstraction discovery.

**Where is the remaining bottleneck?** At the link between *solving a latent-bearing
task* and *the latent appearing in the frontier in a form the compressor can
propose from*. Recognition brings the tasks into the solved set and the latents
into the frontiers as computations (behavioural ER@2 at medium reuse 0.56 → 0.78–0.89,
at low reuse 0.14 → 0.39; 83–93% of solved latent-bearing tasks contain the latent
behaviourally), but the found programs contain them in other syntactic forms
(commuted stages, permuted offsets, baked-in parameters), so the syntactic ER@2
stays at 0.39 / 0.14; the inverse-β candidate generator needs the same syntactic
fragment in two tasks and never sees it, and where it does (support 2–3) the MDL
objective still does not accept the latent (0/3). The evidence for a next-stage
algorithm therefore points to (i) candidate generation that is closed under the
benchmark's semantic equivalences (canonicalising commuting stages and offsets, or
proposing abstractions from behavioural co-occurrence of subexpressions across
frontiers rather than syntactic co-occurrence), and (ii) generalising instantiated
occurrences into parametrised abstractions before scoring, so that a latent seen
with different parameter values in different tasks counts as one candidate. More
exposure by search (a 10000-candidate Wake, Phase 1) and better exposure by
guidance (this phase) both saturate at the same ER@2 of about 0.35–0.40 at medium
reuse, which is the ceiling of a syntactic proposal mechanism on frontiers found by
an MDL-driven search.

## 6. Limitations

* Three benchmark instances and, except at medium reuse, one training seed: most
  contrasts have intervals that include zero, and the medium-reuse replication seeds
  show that the single-latent recovery gain is not stable across seeds.
* Recognition is the accepted recipe of the frozen core (64 dreams, 600 steps, a
  fresh network per round, hand-designed grid features); a larger or better-trained
  recognition model could guide search differently, but it would face the same
  syntactic proposal limit.
* Exposure uses the Phase 1 syntactic criterion, as required; the behavioural
  exposure diagnostic of §4.2 is a finite-probe witness and counts instantiated
  occurrences.
* Guided held-out search costs about 35 times the library-only search; budgets were
  matched in candidates, not in wall-clock time.
* No claim is made about real ARC tasks.

## 7. Reproduction

```
python -m experiments.full_dreamcoder.run train --workers 4
python -m experiments.full_dreamcoder.run evaluate --workers 4
python -m experiments.full_dreamcoder.run parity
python -m experiments.full_dreamcoder.run behavioural-exposure
python -m experiments.full_dreamcoder.run analyze
python -m experiments.full_dreamcoder.run figures
python -m pytest tests/test_full_dreamcoder.py tests/test_abstraction_learning.py -q
```

Environment: Python 3.11, GHC 9.4.7, PyTorch 2.14 (CPU), stitch-core 0.1.29,
four cores, 15 GB RAM. Benchmark manifests and fixed-core hashes were verified before
and after every stage; `results/full_dreamcoder/parity.json` records the round-1
parity of every run with B and the rank-exact re-evaluation of the Phase 1 B
grammars of instance 101.

