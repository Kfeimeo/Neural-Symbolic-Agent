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

<!-- RESULTS -->
