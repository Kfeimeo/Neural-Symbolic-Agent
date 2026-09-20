# Latent-abstraction benchmark

Synthetic ARC-1-style grid tasks generated from a *hidden* library of latent
abstractions. The learner receives only `train.json` / `test.json` (task names and
input/output grids). `latent_library.json` and `private.json` hold the latent
definitions, generator programs, labels and probes; they are evaluation-only and
must never be imported by a learner.

```
python -m benchmarks.latent_abstraction.generator all        # generate, A0-calibrate, freeze seeds 101 202 303
python -m benchmarks.latent_abstraction.generator verify     # hash-check frozen instances and the fixed core
```

## Instance layout (`data/seed_<s>/`)

| File | Reader | Content |
|---|---|---|
| `train.json`, `test.json` | learner | `{name, examples:[{inputs:[grid], output:grid}]}`; names encode split and cohort (`train-high-0012`) |
| `latent_library.json` | evaluation | id, kind, depth, expression, body (typed λ-term), type, valid parameter values, per-cohort reuse counts, contexts used |
| `private.json` | evaluation | per task: cohort, depth, transfer type, novelty condition, generator program, canonical expression, fingerprint, latent uses (with outer/inner contexts), AST statistics, effective complexity under the true library; split and recovery probes |
| `split_validation.json` | evaluation | zero train/test overlap of programs, fingerprints and complete I/O sets; shared sub-structure counts |
| `structural_statistics.json` | evaluation | cell counts, rejection counters, pools, incidental uses, nested pairs, novelty levels |
| `calibration.json` | evaluation | uniform-base-grammar (A0) solve rates by depth and budget, inspected before freezing |
| `manifest.json`, `SHA256SUMS.json` | everyone | SHA-256 of every benchmark file and of the fixed symbolic core |

## Hidden library

Each instance generates 12 latents automatically: four `grid -> grid`, four
`grid -> color -> grid` and four `grid -> int -> grid`, with internal operator depth 2
(three per kind) or 3 (one per kind). A latent is a canonical composition of base
operator stages (`rotate90, rotate180, flipH, flipV, transpose, invert, border, trim,
translate, recolor, solid`) with one parameter slot for the parameterised kinds. It is
accepted only if, for at least two parameter values (all values for grid latents),
its instantiation is not identity or near-constant on 32 split probes, not
behaviourally equal to a shallower reference program (600 random single stages plus
the first 10000 base programs of the uniform enumerator), not equal to any single-stage
deletion, and behaviourally distinct from every previously accepted latent. Degenerate
parameter values (e.g. `recolor(_, red, red)`) are dropped from the latent.

## Independent variables

* **Complexity.** Requested operator-tree depth `d` of the expanded base program:
  2-8 in training (8 tasks per depth and cohort), 3-8 held-out. AST size/depth,
  primitive counts, beta-normal size and *effective complexity* (leaf size after the
  exact best rewrite with the true active latents) are stored per task.
* **Reuse.** Four independent cohorts of 56 training tasks. `zero`: independently
  generated base programs. `low`: 2 of 8 tasks per depth use a latent from a 12-latent
  pool. `medium`: 4 of 8 from a 6-latent pool (nesting probability 0.3). `high`: 8 of 8
  from a 4-latent pool (nesting probability 0.4). Pools are nested (`high ⊂ medium ⊂ low`);
  inside a pool the least-used latent is chosen, so reuse level is set by pool size and
  share rather than sampling noise. Incidental (non-deliberate) syntactic occurrences
  are detected and counted separately.
* **Compositional generalisation.** Held-out programs never coincide with training
  programs (canonical expression, behaviour fingerprint and complete I/O sets are
  disjoint) but must share latent sub-structure. Transfer types, with the novelty
  condition checked on the *detected* contexts of the canonical program:
  `I` g(F_i(·)) with an outer operator never applied to F_i in training;
  `II` F_i(h(·)) with an inner operator never feeding F_i in training;
  `III` F_i(F_j(·)) with an ordered pair never nested in training (from depth 5, so that at
  least one base stage remains). The zero cohort receives matched-depth `control` tasks.
  Held-out latents are always exposed in the same cohort's training tasks.

For every latent and cohort the library records training/test occurrence counts
(deliberate and total), distinct tasks, distinct (outer, inner) contexts and the full
list of contexts used.

## Screening and freeze policy

Every task is canonicalised (dihedral group, involutions, identity/constant argument
rules), must keep its requested depth, must keep every deliberate latent syntactically
intact, must not be behaviourally equal to a shallower reference program or to any
single-stage deletion, and must have six fresh examples with at least three distinct
outputs. These are finite witnesses, not proofs of minimality. Only the uniform base
grammar (A0) is run before `freeze`; the frozen instances are never regenerated or
tuned after any learned-library method is run. Structural adjustments made while
developing the generator (before any learned-library run) are listed in
`PHASE1_REPORT.md`.
