# Shared version-space compressor

`haskell/Compression.hs` enumerates each program's refactorings as an explicit
finite set. That reproduces the reference on tiny fixtures but is not the
algorithm of the paper: the set grows exponentially with program size and
arity, and candidate selection and refactoring are decided by a different
procedure. This package ports the reference algorithm itself, from
`solvers/versions.ml` and the single-process path of `solvers/compression.ml`
at the pinned commit. The frozen core is not edited (its hashes still verify);
a separate executable serves the frozen operations unchanged and adds three.

| File | Reference | Content |
|---|---|---|
| `VersionSpace.hs` | `versions.ml` | hash-consed table of `Union / Apply / Abstract / Index / Terminal / Universe / Void`; `substitutions`, `recursive_inversion`, `inline`, `beta_pruning`, `n_step_inversion`; `minimum_cost_inhabitants`, `minimal_inhabitant`, beam costs |
| `VSCompression.hs` | `compression.ml` | `restrict`, candidate proposal, `eta_long`, `rewrite_with_invention`, `grammar_induction_score`, `compression_step`, `compression_loop` |
| `ReferenceLikelihood.hs` | `grammar.ml`, `FastType.ml` | the OCaml likelihood summary, selectable (see below) |
| `VSMain.hs` | | protocol boundary |
| `differential.py` | | corpora, reference runs, comparison |

One step: every frontier program (the `top_k` most probable per task) is
incorporated and inverted `arity` times, all in one table. Candidates are the
minimum-cost inhabitants of every space reachable from at least two tasks. A
single bottom-up pass computes, for all candidates at once, the size of the
corpus if that candidate cost one symbol; the `top_i` best are rescored
exactly: with the candidate available at the cost of one symbol, the cheapest
refactoring of each program is extracted and rewritten in eta-long form, and
the library weights are refitted.
The best candidate is adopted if it does not lower the penalised likelihood.

## Use

```powershell
python -m faithful.compression.versionspace          # build faithful/build/versionspace_kernel.exe
python -m pytest faithful/tests/test_versionspace.py -q
```

```python
from faithful.compression.versionspace import VersionSpaceKernel, VersionSpaceCompressor
with VersionSpaceKernel() as k:
    r = k.call('vs_compress', grammar=g, frontiers=fs, arity=3, iterations=3, top_k=2,
               pseudo_counts=30, structure_penalty=1)         # same result keys as `compress`
    result = VersionSpaceCompressor(k, iterations=3, arity=3).compress(fs, g)   # Compressor interface
```

`VersionSpaceKernel(compress_options={...})` answers a driver's `compress`
requests with `vs_compress`, so the frozen `ec.py` loop runs on the shared
table when that class is substituted for `Kernel`; the driver is not edited
(`test_frozen_ec_driver_runs_on_the_shared_table`).

Options and defaults: `arity` 1, `iterations` 5, `pseudo_counts` 1, `aic` 1,
`structure_penalty` 0.001 (the frozen `compress` defaults); `top_k` all entries,
`top_i` 300, `beam_size` 1000000, `inline` true (the reference defaults);
`likelihood` `"kernel"`; `trace` false. The reference's list-domain script
(`bin/list.py`) uses arity 3, `top_k` 2, pseudo-counts 30, structure penalty 1.

## Agreement with the reference binary

`differential.py` gives identical inputs to this implementation and to the
unmodified OCaml `compression` binary run with `verbose=true`, and compares
everything the reference exposes, for every iteration:

* the number of candidates;
* the rescored candidates in rank order, including the order inside groups of
  equal discrete score;
* each candidate's discrete (beam) score and continuous score;
* each candidate's rewritten frontiers, program by program (the reference
  prints the frontiers that use the candidate);
* the accepted invention and the scores before and after;
* at the end of the run, the library, its weights (1e-9) and every rewritten
  frontier program.

**Result: no difference on any of the 25 corpora** — 77 compression steps
(75 accepted inventions, 2 rejections), 13,969 individually rescored candidates,
up to 175,453 candidates and a table of 3,920,631 spaces in one step, and single
programs with about e^23 (10^10) refactorings.

| Corpus | Tasks / programs | Arity | Inventions | Candidates per step | Rescored | Largest table | Largest space | Differences | Ours (s) | Reference (s) |
|---|---:|---:|---:|---|---:|---:|---:|---|---:|---:|
| `list_arity1` | 44 / 53 | 1 | 4 | 400, 381, 241, 222 | 1063 | 7,111 | e^10 | none | 22 | 28 |
| `list_arity2` | 44 / 53 | 2 | 4 | 3,202, 1,670, 1,477, 1,431 | 1200 | 124,236 | e^15 | none | 54 | 220 |
| `list_arity3` | 44 / 53 | 3 | 2 | 24,908, 10,272 | 80 | 2,369,476 | e^22 | none | 66 | 535 |
| `list_cheap_library` | 44 / 53 | 2 | 6 | 3,202, 1,670, 1,477, 1,465, 1,408, 1,085 | 1800 | 124,236 | e^15 | none | 79 | 429 |
| `list_narrow_beam` | 44 / 53 | 2 | 2 | 3,202, 1,670 | 600 | 124,236 | e^15 | none | 28 | 156 |
| `list_narrow_rescoring` | 44 / 53 | 2 | 3 | 3,202, 1,670, 1,477 | 36 | 124,236 | e^15 | none | 4 | 12 |
| `list_no_inline` | 44 / 53 | 2 | 4 | 3,202, 1,642, 1,423, 1,403 | 1200 | 124,236 | e^15 | none | 52 | 207 |
| `list_nothing_to_learn` | 44 / 53 | 1 | 0 | 400 | 300 | 7,111 | e^10 | none | 5 | 7 |
| `list_top1` | 44 / 53 | 2 | 3 | 3,002, 1,465, 1,016 | 900 | 108,921 | e^15 | none | 34 | 144 |
| `list_until_rejected` | 44 / 53 | 1 | 6 | 400, 381, 241, 222, 210, 182, 175 | 1630 | 7,111 | e^10 | none | 33 | 31 |
| `planted_arith_0` | 20 / 27 | 3 | 2 | 37,182, 18,336 | 80 | 2,008,338 | e^17 | none | 48 | 298 |
| `planted_arith_1` | 20 / 27 | 3 | 2 | 77,095, 51,425 | 80 | 2,219,264 | e^15 | none | 56 | 279 |
| `planted_arith_2` | 20 / 25 | 3 | 2 | 72,182, 36,353 | 80 | 2,893,191 | e^16 | none | 70 | 298 |
| `planted_first_order_0` | 40 / 66 | 2 | 3 | 91,009, 23,536, 5,544 | 900 | 1,424,972 | e^17 | none | 123 | 962 |
| `planted_first_order_1` | 40 / 64 | 2 | 3 | 40,785, 24,609, 16,016 | 180 | 1,161,920 | e^20 | none | 47 | 294 |
| `planted_first_order_2` | 40 / 64 | 2 | 3 | 38,932, 15,388, 10,998 | 180 | 1,566,255 | e^21 | none | 51 | 353 |
| `planted_inlining_0` | 36 / 51 | 2 | 3 | 14,888, 7,898, 2,219 | 900 | 870,511 | e^21 | none | 109 | 855 |
| `planted_inlining_1` | 36 / 51 | 2 | 3 | 9,656, 6,704, 2,529 | 180 | 619,442 | e^22 | none | 29 | 129 |
| `planted_inlining_2` | 36 / 55 | 2 | 3 | 28,002, 9,956, 3,258 | 180 | 1,150,859 | e^19 | none | 39 | 188 |
| `planted_large_0` | 100 / 153 | 2 | 2 | 162,955, 80,257 | 60 | 3,920,631 | e^21 | none | 96 | 543 |
| `planted_list_0` | 40 / 58 | 2 | 3 | 40,322, 9,588, 5,451 | 900 | 3,201,362 | e^23 | none | 157 | 1852 |
| `planted_list_1` | 40 / 56 | 2 | 3 | 30,462, 11,596, 6,456 | 180 | 1,276,641 | e^18 | none | 38 | 198 |
| `planted_list_2` | 40 / 57 | 2 | 3 | 34,061, 12,638, 4,374 | 180 | 1,160,533 | e^21 | none | 37 | 180 |
| `planted_weighted_0` | 36 / 85 | 2 | 3 | 175,453, 53,537, 49,260 | 900 | 2,543,238 | e^23 | none | 213 | 1862 |
| `planted_weighted_1` | 36 / 89 | 2 | 3 | 146,604, 38,491, 21,311 | 180 | 2,280,076 | e^20 | none | 90 | 358 |

The `list_*` corpora are 44 list-processing tasks written in the style of the
published list domain (map, fold, filter-like folds, indexing), nine of them
with two alternative solutions; the variants cover arity 1–3, `top_k` 1/2/5, a
binding beam (`beam_size` 6), a binding rescoring cut (`top_i` 12), inlining
off, six consecutive inventions, and runs that end because nothing improves
the objective. On them the compressor rediscovers, for example,
`(lambda (lambda (fold $1 empty (lambda (lambda (if ($2 $1) (cons $1 $0) $0))))))`
(filter). The `planted_*` corpora are sampled around hidden latent functions
that are then inlined; they are structurally dense rather than meaningful, and
cover first-order, higher-order and polymorphic libraries, frontiers of up to
three programs with unequal likelihoods, and libraries that already contain
inventions (which exercises inlining). The timings were taken with several
reference processes running at once and are not a benchmark.

Two limits of this evidence. The reference could not finish every corpus
first tried: at arity 3 on 30 arithmetic tasks of up to 20 leaves it reached
14 GB resident in a 15 GB WSL and was stopped. The arity-3 comparisons
therefore use shorter programs or fewer rescored candidates. And
the corpora use the reference's registered list and arithmetic primitives,
because its binary cannot parse the Grid library; Grid frontiers are covered
only by the invariants in the test suite, not by a reference comparison.

Reproduce (the second command needs WSL and about three hours; its saved
outputs are in `faithful/results/versionspace`, the logs gzipped):

```powershell
python -m faithful.versionspace.differential generate
python -m faithful.versionspace.differential official
python -m faithful.versionspace.differential compare     # writes comparison.json
$env:FAITHFUL_VS_FULL = '1'; python -m pytest faithful/tests/test_versionspace.py -q
```

`compare` and the full test run take about half an hour. Without
`FAITHFUL_VS_FULL` the test suite reruns six of the corpora.

### What had to be reproduced beyond the algorithm

The algorithm leaves ties open, and the reference resolves them by accident of
implementation. Three such behaviours are reproduced and marked in the source.
The third was added after `list_cheap_library` differed without it; the first
two were built in from the start, so how often they matter was not measured.

* **Identifier order.** Union members are sorted by table identifier and
  `minimum_by` keeps the last minimum, so the refactoring chosen among equally
  cheap ones depends on allocation order. OCaml evaluates arguments right to
  left; the port sequences allocations the same way.
* **Hash-table order.** `substitutions`, `reachable_versions` and
  `occurs_multiple_times` iterate Core hash tables. Their order is a function
  of the key set (bucket = `caml_hash` masked by the table length, buckets in
  key order, length doubling from 128 — Base v0.11.1, the version linked into
  the binary) and is recomputed rather than approximated.
* **Rounding.** Costs are accumulated in the reference's order. Likelihoods
  are summed per distinct production rather than per event, so two programs
  with equal counts tie exactly and the stable sort in `restrict` keeps their
  input order, as in the reference.

### Differences that remain

* **Likelihood on polymorphic libraries.** The frozen kernel follows the
  Python reference. The OCaml compressor's own likelihood differs from it:
  request types are passed down without applying the typing context, and
  `FastType.compile_unifier` binds a request variable without consulting its
  existing binding, so a request that is an already-bound type variable admits
  every production as a competitor (first seen on `(map f (map g xs))`). The
  two references thus disagree with each other. `likelihood: "ocaml"`
  selects the OCaml definition and is what the comparison above uses;
  the default keeps the kernel's, so that scores agree with `score`,
  `frontier` and `update`. For monomorphic libraries, including the Grid
  domain, the two are the same function and the outputs are identical
  (`test_original_reference_fixtures`). On the list corpus the two settings
  choose the same inventions and rewrites; only intermediate scores differ.
* **Library order.** A new invention is appended, as the frozen protocol does;
  the reference prepends it. Weights and programs are unaffected.
* **Unscorable rewrites.** The reference gives a rewritten program that its
  likelihood cannot parse probability zero and still returns it. Here the
  original program is kept instead, so every returned program can be scored;
  `rewrite_fallbacks` counts these. None occurred in any corpus.
* **Not ported.** The multi-process master/worker path (`CPUs > 1`), which
  partitions frontiers before proposing candidates and can therefore return
  different results from the single-process path in the reference itself; the
  experimental `factored_apply` substitution; `continuation_type`.
* **Exact float ties between different candidates.** The final choice among
  candidates whose continuous scores are mathematically equal depends on the
  last bit of sums whose order the reference takes from hashes of whole
  programs. This was not reproduced and did not arise.
* **Resources.** The table is a persistent map, not a mutable array. Peak
  memory was 0.5 GB on `list_arity2`, 3–3.5 GB on `list_arity3` and
  `planted_weighted_0` and 5 GB on `planted_large_0`; the reference was seen
  at about 1 GB on the same runs (sampled, not instrumented). Wall time was
  lower than the reference's, largely because the reference compacts its heap
  before every rescored candidate.
