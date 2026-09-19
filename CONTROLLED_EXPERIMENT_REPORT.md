# Controlled DreamCoder Experiment

## Final frozen experiment

All configurations use the same frozen tasks. O is an oracle diagnostic, not a fair algorithm competitor.

| Reuse | Configuration | Solve rate at N=10000, iteration 5 | Seed SD | Probe-consistent top-K rate | Mean ΔL |
|---|---|---:|---:|---:|---:|
| zero | A | 0.000 | 0.000 | 0.000 | 0.00 |
| zero | B | 0.167 | 0.000 | 0.167 | 0.57 |
| zero | C | 0.246 | 0.014 | 0.246 | 0.00 |
| zero | D | 0.302 | 0.077 | 0.302 | 1.22 |
| zero | E | 0.095 | 0.000 | 0.095 | 0.00 |
| zero | C_shuffle | 0.230 | 0.036 | 0.230 | 0.00 |
| zero | D_shuffle | 0.222 | 0.050 | 0.222 | 1.22 |
| zero | O | 0.000 | 0.000 | 0.000 | 0.00 |
| low | A | 0.095 | 0.000 | 0.095 | 0.00 |
| low | B | 0.143 | 0.000 | 0.143 | 0.24 |
| low | C | 0.143 | 0.048 | 0.135 | 0.00 |
| low | D | 0.135 | 0.027 | 0.119 | 0.41 |
| low | E | 0.095 | 0.000 | 0.095 | 0.00 |
| low | C_shuffle | 0.135 | 0.036 | 0.119 | 0.00 |
| low | D_shuffle | 0.143 | 0.024 | 0.127 | 0.41 |
| low | O | 0.333 | 0.000 | 0.333 | 3.10 |
| medium | A | 0.024 | 0.000 | 0.000 | 0.00 |
| medium | B | 0.143 | 0.000 | 0.095 | 0.57 |
| medium | C | 0.190 | 0.086 | 0.159 | 0.00 |
| medium | D | 0.238 | 0.048 | 0.214 | 1.21 |
| medium | E | 0.119 | 0.000 | 0.095 | 0.00 |
| medium | C_shuffle | 0.167 | 0.071 | 0.143 | 0.00 |
| medium | D_shuffle | 0.238 | 0.024 | 0.198 | 1.21 |
| medium | O | 0.310 | 0.000 | 0.286 | 3.50 |
| high | A | 0.000 | 0.000 | 0.000 | 0.00 |
| high | B | 0.238 | 0.000 | 0.238 | 1.48 |
| high | C | 0.246 | 0.077 | 0.246 | 0.00 |
| high | D | 0.310 | 0.024 | 0.310 | 1.90 |
| high | E | 0.119 | 0.000 | 0.119 | 0.00 |
| high | C_shuffle | 0.167 | 0.041 | 0.167 | 0.00 |
| high | D_shuffle | 0.302 | 0.027 | 0.302 | 1.90 |
| high | O | 0.286 | 0.000 | 0.286 | 3.21 |

## Controls and budgets

A is the uniform base grammar; B learns library and generative weights; C uses base-only recognition; D combines library and recognition; E fits only base generative weights. C/D shuffle use task-grammar derangements within each cohort. Iteration 0 has no trained recognition. Iterations 1,2,3,5 are saved from the same persistent five-round run.

Training uses 3000 complete candidates, arity-1 faithful compression with up to three accepted inventions per round, 64 ancestral Dream draws and 600 unchanged recognition optimizer steps. Failed dreams are counted, not silently replaced. Persistent frontiers are rescored under the current grammar and merged by generative top-K. Every round records library, weights, frontiers, Dream feature/frontier data with inputs, recognition checkpoint where enabled, and the actual objective.

Evaluation budgets are 100,300,600,1000,3000,10000 complete candidates with 500000 expanded states, DSL leaf-size bound 33, depth bound 14 and description-length bound 100. The same maximum-budget enumeration supplies exact shorter-budget first-solution outcomes by prefix rank. This optimization does not reconstruct lower-budget top-K frontiers. Cache keys include full grammar, guidance, I/O and resource bounds. Prefix correctness and state censoring have regression tests.

Each curve reports the fraction actually reaching its nominal candidate budget; a state-limited search must not be described as having exhausted 10000 candidates. First-solution nodes for failures are right-censored at actual emissions. Shared batch timing is not summed per task.

## Paired contrasts at iteration 5

| Reuse | Contrast | Mean difference | Paired bootstrap 95% CI |
|---|---|---:|---|
| zero | B-A | 0.167 | [0.048, 0.286] |
| zero | D-C | 0.056 | [-0.071, 0.175] |
| zero | E-A | 0.095 | [0.024, 0.190] |
| zero | B-E | 0.071 | [-0.048, 0.190] |
| zero | C-C_shuffle | 0.016 | [-0.056, 0.079] |
| zero | D-D_shuffle | 0.079 | [0.016, 0.167] |
| zero | O-B | -0.167 | [-0.286, -0.048] |
| zero | O-D | -0.302 | [-0.452, -0.167] |
| zero | C-A | 0.246 | [0.135, 0.365] |
| zero | D-B | 0.135 | [0.000, 0.278] |
| low | B-A | 0.048 | [0.000, 0.119] |
| low | D-C | -0.008 | [-0.087, 0.079] |
| low | E-A | 0.000 | [0.000, 0.000] |
| low | B-E | 0.048 | [0.000, 0.119] |
| low | C-C_shuffle | 0.008 | [-0.032, 0.056] |
| low | D-D_shuffle | -0.008 | [-0.032, 0.000] |
| low | O-B | 0.190 | [0.071, 0.333] |
| low | O-D | 0.198 | [0.063, 0.333] |
| low | C-A | 0.048 | [0.000, 0.135] |
| low | D-B | -0.008 | [-0.095, 0.079] |
| medium | B-A | 0.119 | [0.024, 0.214] |
| medium | D-C | 0.048 | [-0.119, 0.198] |
| medium | E-A | 0.095 | [0.024, 0.190] |
| medium | B-E | 0.024 | [-0.095, 0.143] |
| medium | C-C_shuffle | 0.024 | [-0.040, 0.095] |
| medium | D-D_shuffle | 0.000 | [-0.048, 0.048] |
| medium | O-B | 0.167 | [0.024, 0.310] |
| medium | O-D | 0.071 | [-0.056, 0.198] |
| medium | C-A | 0.167 | [0.056, 0.302] |
| medium | D-B | 0.095 | [-0.016, 0.214] |
| high | B-A | 0.238 | [0.119, 0.381] |
| high | D-C | 0.063 | [-0.063, 0.198] |
| high | E-A | 0.119 | [0.024, 0.214] |
| high | B-E | 0.119 | [0.024, 0.238] |
| high | C-C_shuffle | 0.079 | [0.000, 0.167] |
| high | D-D_shuffle | 0.008 | [-0.040, 0.063] |
| high | O-B | 0.048 | [-0.071, 0.167] |
| high | O-D | -0.024 | [-0.143, 0.095] |
| high | C-A | 0.246 | [0.119, 0.381] |
| high | D-B | 0.071 | [-0.032, 0.190] |

The bootstrap resamples training seeds and shared task IDs in pairs (2000 draws). These intervals are conditional on one generated dataset. Three seeds do not establish cross-dataset robustness.

## Recovery and effective complexity

| Reuse | Learner | Mean inventions | Behavioral precision | Recall | F1 | Held-out weighted recall |
|---|---|---:|---:|---:|---:|---:|
| zero | B | 8.00 | 0.0 | None | None | None |
| zero | D | 11.67 | 0.0 | None | None | None |
| low | B | 4.00 | 0.25 | 0.1111111111111111 | 0.15384615384615383 | 0.07692307692307693 |
| low | D | 9.67 | 0.13468013468013468 | 0.14814814814814814 | 0.14074074074074072 | 0.11538461538461539 |
| medium | B | 4.00 | 0.25 | 0.14285714285714285 | 0.18181818181818182 | 0.038461538461538464 |
| medium | D | 9.00 | 0.1537037037037037 | 0.19047619047619047 | 0.16977124183006537 | 0.11538461538461538 |
| high | B | 6.00 | 0.16666666666666666 | 0.25 | 0.2 | 0.3269230769230769 |
| high | D | 14.00 | 0.14175824175824175 | 0.5 | 0.2207315674807935 | 0.46794871794871795 |

Recovery JSON separates raw syntax, canonical, β, type and independent-probe matches; precision/recall/F1 and weighted recall are supplied for each. Type agreement alone does not establish recovery. Zero-reuse latent recall is undefined rather than spuriously 100%.

Effective complexity uses an exact dynamic program within the explicitly bounded space of β-normal subtree/slot coverings, retaining the request lambda structure. Every rewrite witness is β-checked by Haskell. This is not a claim of the globally shortest program over all β-equivalent inverse expansions or all semantically equivalent Grid programs. `effective_rewrites.json` preserves witnesses. Δd is the AST depth change of the minimum-leaf rewrite, with depth as tie-breaker.

## Research questions and limits

Does library learning help without deliberate reuse? zero: B-A=+0.167, D-C=+0.056; low: B-A=+0.048, D-C=-0.008; medium: B-A=+0.119, D-C=+0.048; high: B-A=+0.238, D-C=+0.063.

Does benefit grow with reuse? zero: B-A=+0.167, D-C=+0.056; low: B-A=+0.048, D-C=-0.008; medium: B-A=+0.119, D-C=+0.048; high: B-A=+0.238, D-C=+0.063.

Does recognition guidance survive a task shuffle? zero: C-C_shuffle=+0.016, D-D_shuffle=+0.079; low: C-C_shuffle=+0.008, D-D_shuffle=-0.008; medium: C-C_shuffle=+0.024, D-D_shuffle=+0.000; high: C-C_shuffle=+0.079, D-D_shuffle=+0.008.

How large is the oracle gap? zero: O-B=-0.167, O-D=-0.302; low: O-B=+0.190, O-D=+0.198; medium: O-B=+0.167, O-D=+0.071; high: O-B=+0.048, O-D=-0.024.

For recovery, consult the table and `abstraction_recovery.json`; for complexity-to-search association, `budget_curves.json` explicitly stratifies by ΔL and Δd, depth, AST size, transfer type, budget and EC iteration. `per_task_results.json` supports paired task-level investigation. These are associations; the experiment does not identify a causal effect of program shortening independently of grammar probability changes.

Type I/II/III/IV results are separate curve strata. No aggregate score substitutes for them. Higher-depth failure can be attributed only within tested budgets and priors; even O failure does not establish an impossibility result. Oracle uniformly adds the true active latent definitions, so probability dilution may affect its search.

No D>C>B>A ordering is imposed. Stitch is not added by this study. A positive oracle gap together with poor latent recovery motivates a follow-up compression study; an absent gap motivates task/prior/search analysis first. The hard A distribution and finite semantic checks remain material acceptance limitations.

`latent_frontier_support.json` additionally distinguishes generated exposure from actual I/O-driven frontier support. The accepted compressor requires support in at least two tasks. If a latent is absent from found frontiers, low recovery cannot by itself be attributed to candidate ranking/compression, and a different compressor alone is not demonstrated to fix it.

## Profiling and validation

The pre-study profile is in `profile.json`. Real per-round costs, objective values and hierarchy counts are in `experiment_summary.json`; no compression algorithm was replaced. All accepted-core hashes are verified before and after evaluation. The faithful test suite and new benchmark tests are run separately and their live outputs retained in the task execution.

Benchmark calibration and frozen outcomes are separate artifacts. Re-running the report never regenerates tasks or alters learner data.

## Transfer and shortening diagnostics at iteration 5

| Reuse | Configuration | Fraction shortened | Mean ΔL | I | II | III | IV | Control |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| zero | B | 0.405 | 0.57 | — | — | — | — | 0.167 |
| zero | C | 0.000 | 0.00 | — | — | — | — | 0.246 |
| zero | D | 0.738 | 1.22 | — | — | — | — | 0.302 |
| zero | O | 0.000 | 0.00 | — | — | — | — | 0.000 |
| low | B | 0.119 | 0.24 | 0.167 | 0.167 | 0.100 | 0.125 | — |
| low | C | 0.000 | 0.00 | 0.194 | 0.111 | 0.067 | 0.208 | — |
| low | D | 0.262 | 0.41 | 0.083 | 0.056 | 0.167 | 0.292 | — |
| low | O | 1.000 | 3.10 | 0.250 | 0.333 | 0.400 | 0.375 | — |
| medium | B | 0.310 | 0.57 | 0.167 | 0.083 | 0.100 | 0.250 | — |
| medium | C | 0.000 | 0.00 | 0.139 | 0.250 | 0.133 | 0.250 | — |
| medium | D | 0.492 | 1.21 | 0.194 | 0.306 | 0.167 | 0.292 | — |
| medium | O | 1.000 | 3.50 | 0.167 | 0.333 | 0.400 | 0.375 | — |
| high | B | 0.762 | 1.48 | 0.333 | 0.083 | 0.400 | 0.125 | — |
| high | C | 0.000 | 0.00 | 0.306 | 0.194 | 0.233 | 0.250 | — |
| high | D | 0.841 | 1.90 | 0.361 | 0.111 | 0.467 | 0.333 | — |
| high | O | 1.000 | 3.21 | 0.167 | 0.167 | 0.500 | 0.375 | — |

## Interpretation of this completed run

The negative control does not support a universal “no benefit without latent reuse” claim: zero-reuse B solves 16.7% versus A 0%, while E already solves 9.5%. The small base DSL still produces incidental reusable fragments. Across the deliberately reused cohorts B−A rises from 4.8 to 11.9 to 23.8 percentage points, but including zero reuse breaks monotonicity. D−C is not monotone, and its paired intervals include zero in every cohort.

Latent recovery is incomplete and strongest at high reuse: D’s held-out-weighted behavioral recall is 11.5%, 11.5%, and 46.8% for low/medium/high. High-reuse D shortens 84.1% of held-out task/seed instances by a mean 1.90 leaves. Shortening is not sufficient for synthesis success: low-reuse B solves none of the five held-out tasks that its library shortens. Grammar probabilities and search ordering matter alongside representation length.

The recognition shuffle does not generally erase the recognition advantage. At high reuse C loses 7.9 percentage points under shuffle, but its paired interval touches zero; D loses only 0.8 points. The clearest positive D conditioning effect here is zero reuse (+7.9 points, interval [1.6,16.7]). Much of the observed recognition benefit therefore survives exchanging task-conditioned grammars and cannot be attributed solely to task-specific guidance.

Outer reuse is the weakest raw D transfer stratum in low and high reuse (5.6% and 11.1% solved); nested reuse is weakest in medium reuse (16.7%). These are descriptive strata with different feasible depth ranges, so the per-depth data should be used before attributing a causal difference to contextual position.

Every final and intermediate evaluation reaches all requested candidate budgets: the expanded-state cap does not censor these runs. Nevertheless, Oracle solves at most 12.5% at depth 7–8 in the reused cohorts. Giving the true library therefore does not remove the deep-search problem at N=10000. Larger budgets and alternate priors remain unresolved explanations; the experiment does not prove a solver impossibility or a compression-only cause. Multi-round improvements are also not monotone: high-reuse D falls from 32.5% at round 3 to 31.0% at round 5.

Oracle is not a strict upper bound on the full system: it supplies the true latent functions with uniform weights and no recognition. High-reuse D reaches 31.0% versus Oracle 28.6%; this is compatible with different priors, guidance and learned fragments. Zero-reuse Oracle has no latent additions and equals A.

Decision on Stitch: the low/medium Oracle−B gaps (+19.0/+16.7 points, paired intervals excluding zero) and poor recovery justify a separate controlled compressor comparison on identical found frontiers. They do not justify replacing the accepted core or claiming that Stitch alone will fix the benchmark. In low reuse, seven of nine active latents have no beta-normal structural coverage in the final B frontiers, and the same seven remain absent in D for all seeds; candidate discovery cannot be diagnosed independently of this missing Wake evidence. A follow-up should separate this exposure bottleneck from compression on fragments supported by at least two found task frontiers. No Stitch code is integrated in this stage.

The completed experiment provides all planned measurements, but the hard calibration, one dataset seed, finite probes and restricted rewrite optimum remain explicit limits on scientific acceptance. The outputs support mechanism-specific findings, not a blanket claim that every generalization question has been settled.

Validation: 74 faithful/benchmark tests passed. Benchmark and final artifact SHA-256 checks passed. Summed per-round recorded stage times are approximately 54,054 s Wake, 2,598 s compression/prior fitting, 284 s Dream and 600 s recognition; these are concurrent-job wall-time sums, not elapsed study time. Recognition accounts for about 1% of this training-stage total. This run used CPU-only PyTorch; a GPU would not automatically accelerate the Haskell stages.
