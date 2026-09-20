# Abstraction-learning study (Phase 1)

Studies how a neural-symbolic system discovers reusable abstractions from examples,
on the frozen DreamCoder core, using the latent-abstraction benchmark in
`benchmarks/latent_abstraction/`. The symbolic kernel, type system, program
representation, enumeration, grammar semantics, frontier and recognition
objectives and the evaluator are unchanged; every arm differs only in its
compressor (or in the Wake budget of the exposure sub-experiment).

```
python -m experiments.abstraction_learning.run benchmark     # generate, A0-calibrate, freeze (hash-locked)
python -m experiments.abstraction_learning.run train         # EC loops: arms x cohorts x instances
python -m experiments.abstraction_learning.run perfect-wake  # compressors on ground-truth training programs
python -m experiments.abstraction_learning.run evaluate      # held-out search, recovery, effective complexity
python -m experiments.abstraction_learning.run analyze       # results/*.json and results/abstraction_learning/tables.md
python -m pytest tests/test_abstraction_learning.py -q
```

## Modules

| Module | Role |
|---|---|
| `compressors.py` | One interface `Frontiers + Grammar -> new library + updated grammar`. `A` prior fit only; `B` frozen DreamCoder compressor; `C` Stitch proposals + Stitch leaf-cost utility; `D` Stitch proposals + DreamCoder MDL; `E` DreamCoder proposals + Stitch utility. C/D/E share one greedy loop on the frozen typed rewrite (`compression_trial`). |
| `learner.py` | Multi-round Wake -> Compress -> prior-fit loop (recognition off, deterministic), cached rounds. Reads task names and I/O only. |
| `evaluation.py` | Held-out search curves (prefix-exact solve rate at 100…30000 candidates), first-solution ranks, probe-consistent solutions, effective complexity ΔL (exact DP rewrite), recovery metrics (syntactic / canonical / beta / type / behavioural; precision, recall, F1, held-out-weighted recall), latent frontier exposure. |
| `run.py` | Protocol file, training/evaluation job orchestration, oracle arms, perfect-Wake diagnostic. |
| `analysis.py` | Aggregation over instances, paired bootstrap contrasts, correlations, markdown tables. |

## Arms

| Arm | Library learning | Wake budget |
|---|---|---|
| `A0` | none (uniform base grammar, static) | – |
| `A` | none; inside-outside prior fit each round | 3000 |
| `B` | DreamCoder compression | 3000 |
| `C` | Stitch compression | 3000 |
| `D` | hybrid: Stitch proposals, DreamCoder MDL selection | 3000 |
| `E` | DreamCoder proposals, Stitch utility selection | 3000 |
| `O` | true active latents added, prior fit each round | 3000 |
| `O_uniform` | true active latents added, uniform weights, static | – |
| `B_wake10000`, `D_wake10000` | as B / D | 10000 |
| `PW_B`, `PW_C`, `PW_D`, `PW_E` | compressor applied once (up to 12 inventions) to the ground-truth programs of all training tasks | – |

Six rounds per arm; held-out evaluation after every round (rounds 1–5 to 10000
candidates, the final round, static and perfect-Wake grammars to 20000 candidates;
prefix-exact solve rates at 100, 300, 1000, 3000, 10000, 20000; 3M expanded-state
cap, leaf size 33, depth 14). Three benchmark instances (seeds 101, 202, 303) x four
reuse cohorts.
Results: `results/solve_curves.json`, `results/abstraction_recovery.json`,
`results/compression_results.json`; per-run artefacts under `results/abstraction_learning/`.
