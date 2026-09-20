# Full faithful DreamCoder (Phase 2)

Phase 2 of the abstraction-discovery study: the Phase 1 system with the neural
recognition pathway switched **on**.  Everything else is the frozen Phase 1 setup:
benchmark instances (hash-locked), Haskell symbolic kernel, DreamCoder compressor
(arm B), Bayesian MDL objective, inside-outside prior fit, search budgets
(3000-candidate Wake, 10000-candidate held-out evaluation), rounds, top-K frontiers
and evaluation protocol.  No new algorithm is introduced.

```
python -m experiments.full_dreamcoder.run train    --workers 4   # FullDC EC loops (recognition ON)
python -m experiments.full_dreamcoder.run evaluate --workers 4   # held-out evaluation: library / recognition / shuffle modes
python -m experiments.full_dreamcoder.run parity                 # round-1 parity with B, Phase 1 grammar re-evaluation
python -m experiments.full_dreamcoder.run analyze                # results/full_dreamcoder/*.json and tables.md
python -m experiments.full_dreamcoder.run figures                # results/full_dreamcoder/figures/*.png
python -m pytest tests/test_full_dreamcoder.py -q
```

| Module | Role |
|---|---|
| `learner.py` | Phase 1 Explore–Compress loop plus the accepted recognition recipe of the frozen core: ancestral Dream (64 draws), Replay of the persistent frontiers, a fresh task-conditioned AST-bigram recognition network per round (600 bias-optimal steps), and a recognition-guided Wake (one enumeration per training task, rescored under the generative grammar). Round 1 has no model and reproduces B's round 1 exactly. |
| `evaluation.py` | Held-out evaluation in three modes: `library` (Phase 1 protocol, generative grammar alone), `recognition` (task-conditioned search grammars), `shuffle` (deranged guidance control). |
| `run.py` | Protocol file, training/evaluation jobs, parity checks. Arm `FullDC` = B + recognition; training seed 1 on every cohort, seeds 2 and 3 added on the medium-reuse cohorts. |
| `exposure.py` | Evaluation-only diagnostic: behavioural frontier exposure (a frontier subexpression computes `F(t(x), v)` on the recovery probes, in any syntactic form), computed by `run.py behavioural-exposure` for the final frontiers of B, B_wake10000, PWS_B and every FullDC run. |
| `analysis.py` | Training solve rate, latent frontier support, ER@1/ER@2, behavioural recovery, solve curves S(B), first-solution ranks, recovery conditional on support, exposure transitions and decomposition (solved versus syntactically / behaviourally supported), gap closure against B / PWS_B / O, per-cohort causal-chain deltas. Reads the Phase 1 evaluation records as comparison arms. |
| `figures.py` | Static figures for `PHASE2_REPORT.md`. |

Results: `results/full_dreamcoder/` (`protocol.json`, `parity.json`, `cells.json`,
`contrasts.json`, `per_latent.json`, `gap_closure.json`, `chain.json`,
`training_detail.json`, `tables.md`, `figures/`, per-round run and evaluation records).
