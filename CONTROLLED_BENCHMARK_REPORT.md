# Controlled Synthetic Benchmark

## Scope and frozen files

The accepted Haskell/PyTorch core was not edited. Original 36/24 toy results are
smoke/regression evidence only. This experiment uses 224 training
and 168 held-out tasks, split into four independent reuse cohorts
(56 train / 42 test each). Learners see only six I/O examples per task.
`train.json` and `test.json` contain no programs, latent labels, or private features.
`evaluation_private.json` and `latent_library.json` belong exclusively to evaluation.

The generator constructs 12 two-stage latent functions using randomized typed
composition: four Grid→Grid, four Grid→Color→Grid, four Grid→Int→Grid. Their bodies
contain only the known 24-production base DSL. No latent enters A/B/C/D/E initialization,
Wake, compression, or recognition targets. Oracle O is explicitly separate.

Training deliberate reuse fractions are 0, 1/4, 1/2, 1 for zero/low/medium/high,
with pool concentration increasing. Test latent functions must have appeared in the
same cohort's training generator. Incidental base-fragment reuse in the zero control
is possible and is not called zero mathematical subprogram overlap.

## Complexity and transfer

Operator-tree depth d runs from 2 through 8 in training. Each record also stores raw
AST depth/size, beta-normalized size, primitive leaves, base leaf size, and effective
hidden-library leaf size. The independent controls are requested depth, deliberate
reuse rate, and search budget; other complexity statistics are measured, not assumed
identical across cohorts. Cohort comparisons therefore are descriptive, not a
randomized causal estimate independent of all semantic distribution differences.

I: latent in a new outer Grid context. II: latent receives a new input transformation.
III: two distinct, type-compatible latent calls nest. IV: latent enters the `objects`
argument under `crop(largest(objects(...)))`, absent from training contexts.
Zero reuse has matched count/depth strata and the label `control`, not fictitious latent transfer.
The minimum depths are I/II=3, III=4, IV=5; these structural holes are explicit in
`structural_statistics.json`. At feasible cells there are two held-out tasks per cohort.
Thus nested/novel context is not falsely asserted at d=2.

## Degeneracy and separation

Canonicalization includes the dihedral group, involutions, identity, local trim/border
and constant-argument identities. Six fresh examples, 32 independent split probes,
40 separate recovery probes, and an enumerated 10,000-base-program behavioral reference
bank screen identity, near-constant behavior, known shorter-depth equivalents, and
single-stage deletions. These are finite witness checks, not a minimality proof.

Split validation: `{"ground_truth_overlap": 0, "canonical_program_overlap": 0, "fingerprint_overlap": 0, "complete_io_overlap": 0, "shared_nontrivial_subprograms": 96, "passed": true}`.
Shared subprograms are intentional. Full/canonical programs, complete task I/O and
probe fingerprints have zero train/test overlap. The validation includes all cohorts,
not merely separate per-cohort checks. Latent occurrence/task/context/reuse counts are
in the frozen latent file. A distinct program context here includes instantiated
arguments and the surrounding input/output transformation context.

## Benchmark calibration

Only A was used before permanent freeze. Structural development first exposed missing
training latent coverage and inadequate single-deletion screening; both were corrected
before B/C/D/O were run. Final A solves 5/168 held-out tasks at 10,000 candidates.
The held-out distribution is hard and is not advertised as smoothly calibrated across
all depths. Easy and transition strata exist mainly in training and shallow held-out
cells. Deep failure remains an explicit research outcome, not a reason to regenerate
after viewing other configurations.

## Final frozen experiment

`benchmark_manifest.json` and `SHA256SUMS.json` freeze all benchmark files and accepted
core hashes before nonbase runs. `RESULT_SHA256SUMS.json` additionally covers final
artifacts and checkpoints. Manifest self-hashing is avoided using the sidecar checksum.
Dataset seed=20260918; training seeds=11,23,47; recognition base seeds=1011,1023,1047
plus iteration×10000; shuffle seeds=2011,2023,2047. No seed was selected for performance.

Reproduce from this frozen dataset:

```powershell
python -m pytest faithful/tests -q
python -m faithful.python.controlled_run train --workers 8
python -m faithful.python.controlled_run evaluate --workers 8
python -m faithful.python.controlled_report
```

To create an independent new study use a new output directory; the generator refuses
to overwrite a frozen benchmark. Existing artifacts are resumed by content hash.
