# New Grid DSL in faithful DreamCoder

## Run

From the repository root, with PyTorch and cloudpickle installed:

```powershell
conda run --no-capture-output -n py312 python -m arc_tsl.experiments.run_faithful --task-ids 63613498,007bbfb7 --out results/arc_tsl/faithful_grid_run1 --workers 2 --rounds 2 --limit 3000 --max-states 100000 --dreams 20 --recognition-steps 30
```

`py312` is the verified environment on this machine. There is currently no conda
environment named `minimal-dreamcoder`; that is the Python package name.
For another environment, install the package with `python -m pip install -e .`;
Stitch is optional (`.[stitch]`). The default compressor is the original Haskell
compressor, so Stitch is not required. The existing prebuilt faithful Kernel is
used if available; otherwise faithful requires GHC for its automatic build.

The output directory must be new or empty. `run_experiment.py` and `run_grid.py`
remain separate experiment entry points and do not launch this flow.

## Flow and scope

1. Load each selected ARC task's demonstration pairs as a faithful Task.
2. Run EC rounds: parallel task Wake, compression, dreams, recognition training.
3. With the learned grammar/model, solve the demonstration pairs again to select
   a final program per task. Freeze all selected programs to disk.
4. Only then evaluate the ARC test inputs and compare with available labels.

This learns a shared library across the listed ARC training tasks. It differs
from ARC-TSL's task-local per-pair Wake/compression/parameter-completion method.
The latter is not silently substituted into faithful. `--workers` parallelizes
independent task searches, with one Kernel per worker in a pool that persists
across rounds and the final solve; it does not split one task's search.
`--kernel-threads N` gives the parent a `KernelPool` of N processes for the
per-entry rescoring after each Wake, the recognition summaries and MDL
accounting; results are identical to one process. `--dream-seeding independent`
gives every dream its own child seed so the same workers (or kernel processes)
draw dreams in parallel; the default `sequential` keeps one random stream and
reproduces earlier runs bit for bit. There is no Haskell search-algorithm change.

`--heldout-task-ids ID1,ID2` adds disjoint tasks that are excluded from all EC
learning and dreams. At final solve, only their demonstration pairs are used to
select programs. Their test answers are used only for scoring. Without this
option, results measure new inputs within EC training tasks, not transfer to
previously unseen tasks. Already inspected tasks are development diagnostics.

The domain has 109 primitives. Python n-ary primitive signatures become curried
faithful types and functions. The initial grammar is uniform, so the DSL search
prior is different from the original ARC-TSL weighted AST cost. The simple
recognition features currently summarize dimensions and color frequencies.

## Budgets and output

- `--limit`: maximum emitted candidates per task per Wake.
- `--max-states`: maximum popped Haskell agenda states per task per Wake.
- `--max-size`, `--maximum-depth`: program structure limits.
- `--kernel-timeout`: per-kernel-call timeout; an expiry fails the run explicitly.
  It is not an end-to-end task deadline or a bound on Python primitive execution.
- `--compressor original|stitch|none`: `none` is an ablation, not a full compression run.

Adding workers does not multiply an individual task's budget. Every EC round and
the final solve consume their own per-task budgets. `report.json` sums Wake
states across both phases and records total wall time (including process startup,
compression, dreams and recognition) separately from final scoring time. It does
not measure full-study CPU time or aggregate worker peak RAM.

Outputs: `protocol.json` (source/data hashes and configuration), `kernel.json`
(executable hash), `history.json`, `config.json`, recognition checkpoints,
`selected_programs.json` (saved before scoring), and `report.json` (predictions,
test correctness, task split, program hashes and final Wake traces).

## Validation

```powershell
conda run --no-capture-output -n py312 python -m pytest faithful/tests/test_lib.py faithful/tests/test_arc_parallel.py tests/arctsl -q -p no:cacheprovider
```

Verified: 106 tests passed. New checks cover adapter typing/execution, opaque
black, dream generation, serial/parallel frontier and state-budget equality,
worker/Kernel isolation, full ARC-domain EC round equivalence (including
recognition-guided solve), and worker error propagation.

Real-task smoke run: `results/arc_tsl/faithful_grid_parallel_smoke/report.json`.
Two tasks, two workers, one EC round, at most 1,000 states per task per Wake:
4,000 total Wake states, about 15.25 seconds fit wall time. Neither task solved.
This validates the entry point and bounded flow, not a speedup or generalization
gain. Very short searches can be dominated by Python/PyTorch process startup.
