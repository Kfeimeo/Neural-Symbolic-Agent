# Phase 3 — Equivalence-aware abstraction discovery

Separate adapters around the frozen Full Faithful DreamCoder pipeline. B0 uses
the original compressor; B1 normalizes R; B2 extracts a cost-defined E/R
representative before the original inverse-beta compressor; B3 anti-unifies
e-classes and scores candidates with the original Bayesian MDL objective.

`learner.py` executes the Phase 2 function's original code object with an isolated
compressor factory binding. Recognition, Wake, six EC rounds, frontier limit,
Dream/Replay, inside-outside fitting, and held-out evaluation are unchanged.
No latent library, private data, or probes enter the compressor.

Read [EQUATIONS.md](EQUATIONS.md) for the rule proofs, confluence analysis,
resource bounds, and the first-order AU / witness-selection limitations.

```powershell
$env:PYTHONPATH = 'E:\dev\AI\ARC-AGI-3\faithful\vendor'
& 'E:\anaconda3\envs\py312\python.exe' -m pytest tests/test_equivalence_abstraction.py tests/test_full_dreamcoder.py -q
& 'E:\anaconda3\envs\py312\python.exe' -m experiments.equivalence_abstraction.run verify
& 'E:\anaconda3\envs\py312\python.exe' -m experiments.equivalence_abstraction.run train --workers 2
& 'E:\anaconda3\envs\py312\python.exe' -m experiments.equivalence_abstraction.run evaluate --workers 2
& 'E:\anaconda3\envs\py312\python.exe' -m experiments.equivalence_abstraction.run analyze
```

The default schedule is all three benchmark seeds, all four reuse regimes, and
the Phase 2 training seed schedule (three training seeds for medium reuse).
Use `--seeds 101 --regimes medium --training-seeds 1` for a **subset**, preserving
the actual search/training budgets. Analysis lists every missing full-study cell.
`--output` isolates a revised source/protocol version; a frozen output directory
rejects changed source hashes. It never overwrites a frozen manifest to resume.

`replay` is a paired diagnostic that recompresses saved Phase 2 final frontiers
under their existing grammar. It does not reconstruct pre-compression Wake
frontiers and is not a substitute for six-round EC or held-out evaluation.

Metrics include syntactic, behavioural and equivalence-usable ER@1/2 (distinct
tasks), behavioural invention precision/recall/F1, parameterised latent recall,
the numerator/denominator of conditional parametric recovery, specialisation
witnesses, invention count, cumulative compression ΔMDL, training solve rate,
held-out S(B), and per-task first-solution rank. Empty conditional denominators
are `null`, never zero. Finite behavioural witnesses are never admitted as
equations. Normalization/extraction MDL changes are recorded separately from
invention acceptance gains.

Current analysis labels all five empirical questions pending until the paired
results are interpreted. A completed implementation or a passing smoke test is
not evidence of experimental improvement.
