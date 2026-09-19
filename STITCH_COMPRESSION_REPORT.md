# Stitch Controlled Compression Report

## Research scope

Real [Stitch](https://github.com/mlb2251/stitch) Python bindings `stitch-core==0.1.29` are used. The primary comparison replaces proposal search with Stitch and retains the original Haskell inverse-beta rewrite, type validation, inside-outside fitting and MDL acceptance. This controlled adapter is **not unrestricted vanilla Stitch**. Its conclusions must not be generalized to all Stitch configurations.

Stitch proposes one abstraction per step using native leaf cost (primitive/variable/invention-variable=100, application/lambda=0), maximum abstraction arity 1, task-aware input, one thread. The existing compressor also uses arity 1 and at most three accepted inventions per round. A proposal is accepted only when the same DreamCoder objective improves; the Stitch arm stops if its top proposal fails typing or MDL. It does not search the next-best native proposal after a rejection. Native proposals, native utility and rejection reasons are retained. That proposal-selection/MDL mismatch is an explicit experimental limitation.

The frozen solver, typed enumeration, grammar implementation, original compressor, recognition network/loss, Dream, Replay, EC loop source, benchmark files and all search bounds remain unchanged. Both full-EC arms run the exact existing controlled learner bytecode with only its Kernel compression dispatch substituted. New bridge/domain files import the original core. `core_sha256.json` verifies source preservation; original frozen benchmark SHA256 sums are checked before and after the study.

## Shared evaluation protocol

The frozen input is one fresh uniform base-grammar Wake at the unchanged 3000-candidate training budget on all 224 original training tasks, grouped into the four original 56-task cohorts. Both compressors receive identical solved frontiers and grammar, including all retained top-3 entries and their likelihoods. Unsolved frontiers are excluded from compression exactly as in the original EC driver; all Wake results, including failures, remain in `frozen_input.json`. Input hashes are recorded in each result.

MDL = -sum log marginal(frontier | fitted grammar) + library cost; library cost = production count + 0.001 × sum body leaf sizes. The baseline is fitted by the same single inside-outside step, so the reported positive ΔMDL means improvement over a shared fitted baseline, not over the unfitted uniform prior. Corpus savings and library-cost increase are recorded separately. Native Stitch AST utility is never substituted for this MDL.

Recovery compares learned inventions against active generator latents. Beta matching uses the Haskell beta normalizer. Behavioral matching requires equal types and identical outputs on the original independent recovery probes and configured parameter values; it is not a universal equivalence proof. Precision counts matched learned inventions; recall counts recovered active latents; duplicate/equivalent latents can create many-to-many matches. F1 uses these two rates. Type alone is not recovery. Zero-reuse has no active latent denominator and reports N/A.

## Frozen frontier results

| Reuse | Backend | New inventions | Beta recall | Behavior precision | Behavior recall | Behavior F1 | ΔMDL | Corpus savings | Δlibrary cost | Tasks rewritten | Σ AST reduction | Σ depth reduction |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero | original | 3 | N/A | 0.000 | N/A | N/A | 4.460 | 7.469 | 3.009 | 7 | 30 | 15 |
| zero | stitch | 1 | N/A | 0.000 | N/A | N/A | 0.700 | 1.706 | 1.006 | 2 | 6 | 2 |
| low | original | 2 | 0.000 | 0.500 | 0.111 | 0.182 | 1.483 | 3.491 | 2.008 | 4 | 24 | 12 |
| low | stitch | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 |
| medium | original | 2 | 0.000 | 0.000 | 0.000 | 0.000 | 5.078 | 7.087 | 2.009 | 3 | 24 | 12 |
| medium | stitch | 2 | 0.000 | 0.000 | 0.000 | 0.000 | 4.996 | 7.004 | 2.008 | 3 | 16 | 8 |
| high | original | 3 | 0.000 | 0.333 | 0.250 | 0.286 | 8.692 | 11.704 | 3.012 | 5 | 32 | 16 |
| high | stitch | 2 | 0.250 | 0.500 | 0.250 | 0.333 | 6.098 | 8.106 | 2.008 | 4 | 22 | 11 |

AST/depth reductions count the actual corresponding rewritten frontier entries, treating invented function references as atomic. They are sums across retained programs, not ground-truth-program complexity and not expanded-body savings. Full before/after AST witnesses, invention types and type arities are in the JSON outputs.

A concrete high-reuse example is latent F00: both backends recover its behavior, but only Stitch has an invention whose expanded beta-normal body exactly equals F00. Original reaches the same probe behavior through a different rotation/translation expression. Therefore the frozen exact-match gain is partly representational alignment, not evidence of recovering an additional distinct behavior. The high-reuse Oracle behavioral gain (3/4 versus 2/4) is stronger evidence, restricted to the diagnostic corpus.

## Exposure separation

The existing `latent_frontier_support.json` is preserved with its hash in `historical_exposure_reference.json`. It describes earlier iteration-5 frontiers, so its labels cannot be assigned to this new round-zero corpus. We recompute the same beta-normal structural coverage on the exact input, separating any support (at least one task), minimum two-task support, and zero support. The support computation is evaluation-only and never enters compression.

| Reuse | Backend | Supported behavior recall | Unsupported behavior recall | Supported latent count | Unsupported latent count |
|---|---|---|---|---|---|
| zero | original | N/A | N/A | 0 | 0 |
| zero | stitch | N/A | N/A | 0 | 0 |
| low | original | 0.500 | 0.000 | 2 | 7 |
| low | stitch | 0.000 | 0.000 | 2 | 7 |
| medium | original | 0.000 | 0.000 | 2 | 5 |
| medium | stitch | 0.000 | 0.000 | 2 | 5 |
| high | original | 0.333 | 0.000 | 3 | 1 |
| high | stitch | 0.333 | 0.000 | 3 | 1 |

## Oracle-frontier diagnostic

Only true latent fragment bodies used by training tasks are supplied, in the base DSL, one frontier per distinct training-task/latent pair. Repeated occurrences within the same task do not inflate support. Cross-task repetition is retained. This differs from the Wake corpus and is diagnostic only; no oracle material enters normal training or evaluation. The zero-reuse cohort has an empty oracle corpus. Recall still includes active held-out-only latents; exposure-conditioned results show what the oracle actually contains.

| Reuse | Backend | New inventions | Beta recall | Behavior precision | Behavior recall | Behavior F1 | ΔMDL | Corpus savings | Δlibrary cost | Tasks rewritten | Σ AST reduction | Σ depth reduction |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero | original | 0 | N/A | 0.000 | N/A | N/A | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 |
| zero | stitch | 0 | N/A | 0.000 | N/A | N/A | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 |
| low | original | 3 | 0.111 | 0.333 | 0.111 | 0.167 | 24.075 | 27.091 | 3.016 | 9 | 42 | 25 |
| low | stitch | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 |
| medium | original | 3 | 0.000 | 0.333 | 0.143 | 0.200 | 39.472 | 42.489 | 3.017 | 18 | 72 | 48 |
| medium | stitch | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 |
| high | original | 3 | 0.000 | 0.667 | 0.500 | 0.571 | 187.711 | 190.724 | 3.013 | 56 | 208 | 104 |
| high | stitch | 3 | 0.750 | 1.000 | 0.750 | 0.857 | 180.032 | 183.049 | 3.017 | 50 | 298 | 149 |

## Full EC

Paired seed 11, all four frozen cohorts, five persistent rounds, original 600 recognition steps, 64 ancestral Dream draws, training budget 3000, test budgets 100/300/600/1000/3000/10000; state cap 500000, leaf size 33, depth 14, description length 100, frontier top-K 3. Single-seed results do not support significance or robustness claims. Failed dreams and state-censored searches remain counted. Each per-task first-solution rank supplies exact shorter-budget solve curves; it does not reconstruct shorter-budget top-K frontiers.

**Full EC has not finished; no full-EC conclusion is available yet.**

## Answers to Q1–Q5

1. **More latent abstractions?** In the high-reuse frozen corpus, Stitch recovers one exact beta latent (25%) while Original recovers none exactly. Behavioral recall is tied at 25%. Thus this is improved exact recovery, not a blanket improvement in behavioral discovery. High-reuse oracle exact/behavioral recall is 75% for Stitch, versus 0%/50% for Original.
2. **Recall rather than extra macros?** The high-reuse frozen gain uses two inventions versus three for Original. It is not explained by larger macro count. Other cohorts do not show a general recall gain; low-reuse frozen behavior recall is worse. Precision/F1 and all matching pairs are saved, including non-latent macros.
3. **Effective complexity?** Accepted Stitch inventions produce verified beta-equivalent frontier rewrites and positive measured AST/leaf savings, but total common MDL improvements are below Original on all nonempty frozen cohorts. Macro discovery alone is not evidence of superior compression.
4. **Search efficiency?** Pending full EC; frozen compression cannot answer this question.
5. **Failure analysis.** Separate zero-exposure latents (Wake limitation) from exposed but unrecovered latents (compression/selection limitation). Low/medium oracle failures persist despite direct exposure: the top Stitch AST-cost proposal fails the common probabilistic MDL gate. The adapter stops instead of enumerating lower-ranked proposals. This implicates proposal utility/acceptance mismatch in this configuration, not proof that Stitch search fundamentally cannot discover useful functions. High-reuse oracle success shows the abstraction space can represent useful latents. Remaining full-EC failures may reflect recognition guidance, search ordering or state caps; these data do not uniquely identify the synthesis bottleneck.

## Correctness, provenance and reproduction

All accepted rewrites are checked by Haskell beta normalization and scored against the typed grammar. Native Stitch rewrites are independently beta checked before common rewriting. Tests include evaluator output agreement, shared MDL calculations, identical input hashes, no input mutation, no private benchmark imports in compressor modules, unsolved-frontier preservation, exact original-adapter parity, and polymorphic/higher-order invented function evaluation. Full existing and added regression results: **117 passed; 0 failed/error** (`results/stitch/regression.xml`). The first regression attempt lacked `frozendict` in py312; after installing that reference-test dependency, the unchanged tests passed.

Install `faithful/compression/requirements.txt` into `faithful/vendor`, build with `python -c "from faithful.compression.interface import build_bridge; build_bridge()"`, then run `python -m faithful.domains.official`, `python -m faithful.compression.study frozen`, `python -m faithful.compression.study ec --workers 4`, and `python -m faithful.compression.report`. Set `PYTHONPATH` to the absolute `faithful/vendor` path for official-reference subprocess tests. This study used `E:\anaconda3\envs\py312\python.exe` with CUDA. Saved checkpoints support round-boundary resume; result caches are for this frozen study only, not interchangeable configurations.
