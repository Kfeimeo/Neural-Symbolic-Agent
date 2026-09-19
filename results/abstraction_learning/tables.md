# Generated tables (experiments/abstraction_learning/analysis.py)

## Benchmark instances

| Instance | Reuse | Train tasks | Test tasks | Pool size | Active latents | Mean deliberate train uses / latent | Range | Mean test uses / latent | Incidental uses | Nested train pairs |
|---|---|---|---|---|---|---|---|---|---|---|
| 101 | zero | 56 | 32 | 0 | 0 | n/a | n/a | n/a | 18 | 0 |
| 101 | low | 56 | 31 | 12 | 12 | 1.2 | 1-2 | 3.2 | 9 | 0 |
| 101 | medium | 56 | 30 | 6 | 6 | 5.2 | 5-6 | 6.0 | 4 | 3 |
| 101 | high | 56 | 31 | 4 | 4 | 17.5 | 17-18 | 9.8 | 4 | 7 |
| 202 | zero | 56 | 32 | 0 | 0 | n/a | n/a | n/a | 14 | 0 |
| 202 | low | 56 | 32 | 12 | 12 | 1.2 | 1-2 | 3.3 | 5 | 0 |
| 202 | medium | 56 | 29 | 6 | 6 | 4.8 | 4-5 | 5.7 | 15 | 2 |
| 202 | high | 56 | 23 | 4 | 4 | 15.2 | 15-16 | 5.8 | 10 | 3 |
| 303 | zero | 56 | 32 | 0 | 0 | n/a | n/a | n/a | 22 | 0 |
| 303 | low | 56 | 29 | 12 | 12 | 1.2 | 1-2 | 2.8 | 18 | 2 |
| 303 | medium | 56 | 29 | 6 | 6 | 5.7 | 5-7 | 5.7 | 14 | 4 |
| 303 | high | 56 | 24 | 4 | 4 | 17.2 | 17-18 | 6.2 | 12 | 9 |

A0 calibration (uniform base grammar, held-out tasks, solve rate by depth and candidate budget; inspected before freezing):

| Instance | Reuse | Depth | Tasks | 100 | 300 | 1000 | 3000 | 10000 |
|---|---|---|---|---|---|---|---|---|
| 101 | zero | 3 | 4 | 0.00 | 0.00 | 0.25 | 0.25 | 0.50 | 0.75 |
| 101 | zero | 4 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.25 |
| 101 | zero | 5 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.17 |
| 101 | zero | 6 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 101 | zero | 7 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 101 | zero | 8 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 101 | low | 3 | 4 | 0.00 | 0.00 | 0.00 | 0.25 | 0.50 | 0.50 |
| 101 | low | 4 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.25 |
| 101 | low | 5 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.33 |
| 101 | low | 6 | 5 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 101 | low | 7 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 101 | low | 8 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 101 | medium | 3 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.25 |
| 101 | medium | 4 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 101 | medium | 5 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.17 |
| 101 | medium | 6 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.17 |
| 101 | medium | 7 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 101 | medium | 8 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 101 | high | 3 | 3 | 0.00 | 0.00 | 0.00 | 0.00 | 0.33 | 0.67 |
| 101 | high | 4 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.25 |
| 101 | high | 5 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.17 |
| 101 | high | 6 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 101 | high | 7 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 101 | high | 8 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 202 | zero | 3 | 4 | 0.00 | 0.00 | 0.75 | 1.00 | 1.00 | 1.00 |
| 202 | zero | 4 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.25 | 0.25 |
| 202 | zero | 5 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.17 |
| 202 | zero | 6 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 202 | zero | 7 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 202 | zero | 8 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 202 | low | 3 | 4 | 0.00 | 0.00 | 0.00 | 0.50 | 0.50 | 0.50 |
| 202 | low | 4 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.50 |
| 202 | low | 5 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.17 |
| 202 | low | 6 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 202 | low | 7 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 202 | low | 8 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 202 | medium | 3 | 4 | 0.00 | 0.00 | 0.00 | 0.50 | 0.50 | 0.50 |
| 202 | medium | 4 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 202 | medium | 5 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 202 | medium | 6 | 5 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.40 |
| 202 | medium | 7 | 5 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.20 |
| 202 | medium | 8 | 5 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 202 | high | 3 | 3 | 0.00 | 0.00 | 0.00 | 0.67 | 0.67 | 0.67 |
| 202 | high | 4 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.25 |
| 202 | high | 5 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 202 | high | 6 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 202 | high | 7 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 202 | high | 8 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 303 | zero | 3 | 4 | 0.00 | 0.00 | 0.25 | 0.50 | 0.75 | 0.75 |
| 303 | zero | 4 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.50 |
| 303 | zero | 5 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 303 | zero | 6 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 303 | zero | 7 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 303 | zero | 8 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 303 | low | 3 | 4 | 0.00 | 0.00 | 0.00 | 0.50 | 0.50 | 1.00 |
| 303 | low | 4 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 303 | low | 5 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.17 |
| 303 | low | 6 | 5 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 303 | low | 7 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.17 |
| 303 | low | 8 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 303 | medium | 3 | 4 | 0.00 | 0.00 | 0.00 | 0.50 | 0.50 | 1.00 |
| 303 | medium | 4 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.50 |
| 303 | medium | 5 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.50 |
| 303 | medium | 6 | 6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 303 | medium | 7 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 303 | medium | 8 | 5 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 303 | high | 3 | 3 | 0.00 | 0.00 | 0.00 | 0.33 | 0.67 | 1.00 |
| 303 | high | 4 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.25 |
| 303 | high | 5 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 303 | high | 6 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.25 |
| 303 | high | 7 | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 303 | high | 8 | 5 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

## Experiment 1: effect of reuse (final iteration, solve rate at 10000 candidates)

| Reuse | A0 | O_uniform |
|---|---|---|
| zero | 0.062 ± 0.000 | 0.062 ± 0.000 |
| low | 0.065 ± 0.000 | n/a |
| medium | n/a | n/a |
| high | n/a | n/a |

Same at 10000 candidates:

| Reuse | A0 | O_uniform |
|---|---|---|
| zero | 0.062 ± 0.000 | 0.062 ± 0.000 |
| low | 0.065 ± 0.000 | n/a |
| medium | n/a | n/a |
| high | n/a | n/a |

Probe-consistent solution rate (top-K solution reproduces the generator program on 40 independent probes):

| Reuse | A0 | O_uniform |
|---|---|---|
| zero | 0.062 ± 0.000 | 0.062 ± 0.000 |
| low | 0.065 ± 0.000 | n/a |
| medium | n/a | n/a |
| high | n/a | n/a |

Paired contrasts at 10000 candidates (mean difference in solve rate; two-way bootstrap over instances and task positions):

| Reuse | Contrast | Mean diff | Instance SD | 95% CI | Instances |
|---|---|---|---|---|---|
| zero | O_uniform-A0 | 0.000 | 0.000 | [0.000, 0.000] | 1 |

## Experiment 2: effect of complexity (solve rate at 10000 by depth, final iteration)

Reuse = zero:

| Arm | d=3 | d=4 | d=5 | d=6 | d=7 | d=8 |
|---|---|---|---|---|---|---|
| A0 | 0.50 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| O_uniform | 0.50 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |

Reuse = low:

| Arm | d=3 | d=4 | d=5 | d=6 | d=7 | d=8 |
|---|---|---|---|---|---|---|
| A0 | 0.50 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |

Reuse = medium:

| Arm |
|---|

Reuse = high:

| Arm |
|---|

Solve rate at 10000 by held-out transfer type (final iteration):

Reuse = zero:

| Arm | control |
|---|---|
| A0 | 0.06 ± 0.00 |
| O_uniform | 0.06 ± 0.00 |

Reuse = low:

| Arm | I | II | III |
|---|---|---|---|
| A0 | 0.08 ± 0.00 | 0.08 ± 0.00 | 0.00 ± 0.00 |

Reuse = medium:

| Arm |
|---|

Reuse = high:

| Arm |
|---|

## Experiment 3: abstraction recovery

| Reuse | Arm | Inventions | Canonical recall | Beta recall | Type recall (perm.) | Behav. precision | Behav. recall | Behav. F1 | Weighted behav. recall |
|---|---|---|---|---|---|---|---|---|---|

Behavioral recall by EC iteration (mean over instances):

Training tasks solved by EC iteration (mean over instances, out of 56):

Reuse = zero:

| Arm | it 1 | it 2 | it 3 | it 4 | it 5 | it 6 |
|---|---|---|---|---|---|---|

Reuse = low:

| Arm | it 1 | it 2 | it 3 | it 4 | it 5 | it 6 |
|---|---|---|---|---|---|---|

Reuse = medium:

| Arm | it 1 | it 2 | it 3 | it 4 | it 5 | it 6 |
|---|---|---|---|---|---|---|

Reuse = high:

| Arm | it 1 | it 2 | it 3 | it 4 | it 5 | it 6 |
|---|---|---|---|---|---|---|

Exposure and recovery per active latent (final iteration; latents pooled over instances): behaviorally recovered / latents with frontier support in >=2, 1, 0 training tasks:

| Reuse | Arm | Active latents | >=2 tasks | 1 task | 0 tasks |
|---|---|---|---|---|---|

## Experiment 4: compression versus generalization

| Reuse | Arm | Cumulative ΔMDL | Inventions | Mean ΔL (held-out) | Fraction shortened | Mean ΔL under true library | Solve rate | shortened | Solve rate | not shortened | Solve rate |
|---|---|---|---|---|---|---|---|---|---|

Correlations across (learned arm x instance x iteration) cells:

| Scope | Cells | ΔMDL vs solve: Pearson | Spearman | ΔL vs solve: Pearson | Spearman |
|---|---|---|---|---|---|
| zero | 0 | n/a | n/a | n/a | n/a |
| low | 0 | n/a | n/a | n/a | n/a |
| medium | 0 | n/a | n/a | n/a | n/a |
| high | 0 | n/a | n/a | n/a | n/a |
| all | 0 | n/a | n/a | n/a | n/a |

Task-level association pooled over iterations and instances (a task counts once per arm x instance x iteration):

| Reuse | Arm | Shortened task-cells | Solve rate | Unshortened task-cells | Solve rate |
|---|---|---|---|---|---|

## Experiment 5: oracle gap

| Reuse | Arm | Solve rate @10000 | Probe-consistent | Behav. recall | Mean ΔL | Mean first-solution rank (solved) |
|---|---|---|---|---|---|---|
| zero | O_uniform | 0.062 ± 0.000 | 0.062 ± 0.000 | n/a | 0.00 ± 0.00 | 1953 ± 0 |

Oracle and perfect-Wake contrasts at 10000 candidates:

| Reuse | Contrast | Mean diff | 95% CI |
|---|---|---|---|
| zero | O_uniform-A0 | 0.000 | [0.000, 0.000] |

Perfect-Wake diagnostic (PW: ground-truth programs of all 56 training tasks; PWS: training tasks of depth <= 4; up to 12 inventions; a missing row means the compressor timed out):

| Reuse | Arm | Inventions | ΔMDL | Canonical recall | Behav. precision | Behav. recall | Weighted recall | Mean ΔL | Solve rate @10000 |
|---|---|---|---|---|---|---|---|---|---|

## Search exposure: Wake budget

| Reuse | Arm | Training solved (final) | Solve rate @10000 | Behav. recall | Weighted recall | Mean ΔL | Inventions |
|---|---|---|---|---|---|---|---|

| Reuse | Contrast | Mean diff | 95% CI |
|---|---|---|---|

## Identical-input compressor comparison (round 1: same base-grammar Wake frontiers for every compressor)

| Reuse | Arm | Inventions | ΔMDL | Canonical recall | Behav. precision | Behav. recall | Mean ΔL | Solve rate @10000 after round 1 |
|---|---|---|---|---|---|---|---|---|

## Held-out solve rate at 10000 candidates by EC iteration

Reuse = zero:

| Arm | it 1 | it 2 | it 3 | it 4 | it 5 | it 6 |
|---|---|---|---|---|---|---|

Reuse = low:

| Arm | it 1 | it 2 | it 3 | it 4 | it 5 | it 6 |
|---|---|---|---|---|---|---|

Reuse = medium:

| Arm | it 1 | it 2 | it 3 | it 4 | it 5 | it 6 |
|---|---|---|---|---|---|---|

Reuse = high:

| Arm | it 1 | it 2 | it 3 | it 4 | it 5 | it 6 |
|---|---|---|---|---|---|---|

