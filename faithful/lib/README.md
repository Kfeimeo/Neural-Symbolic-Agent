# `faithful.lib` — the library interface

The frozen modules in `faithful/python` are experiment drivers: they hard-code the
kernel path, the Grid encoder and the Dream generator, and other domains were
attached by rebinding function globals. `faithful.lib` is an interface layer over
the **same** Haskell core and recognition network with explicit dependencies:

| Concern | Module | What changed |
|---|---|---|
| Kernel build / lookup / process | `kernel.py` | Named build targets, `FAITHFUL_*` discovery, auto-build, timeouts, restart, thread lock |
| Execution semantics in Python | `evaluate.py` | Interpreter for protocol v1 programs over Python primitives |
| Domain contract | `domain.py` | `Domain`: DSL + semantics, likelihood, features, dreams |
| Compression backends | `compression.py` | `OriginalCompressor`, `VersionSpaceCompressor`, `StitchCompressor` with one `compress(kernel, grammar, frontiers)` |
| Stitch backend | `stitch.py` | Full `stitch_core` option surface, program ⇄ s-expression conversion |
| Explore–Compress | `ec.py` | `ExploreCompress(domain, kernel, compressor, config)` |
| Examples | `domains/` | `GridDomain` (Haskell semantics), `ListDomain`/`ArithmeticDomain` (Python semantics) |

Nothing hash-locked by the controlled/Stitch studies is modified; the Haskell
sources are compiled unchanged and `faithful.python.recognition.Recognition` is
reused as is.

## Install and build

```powershell
pip install -e .[stitch]          # torch + stitch_core; frozendict only for reference tests
python -m faithful.lib build      # versionspace target: serves every protocol operation
python -m faithful.lib info       # targets, executables and the operations each serves
```

Kernel discovery order: explicit `Kernel(executable=...)` → `FAITHFUL_KERNEL_<TARGET>`
→ `FAITHFUL_BUILD_DIR/<name>[.exe]` → `faithful/build/<name>[.exe]`. A missing
executable is compiled with `ghc` (`FAITHFUL_GHC` overrides the lookup;
`FAITHFUL_AUTO_BUILD=0` disables). `FAITHFUL_TRACE=<file>` logs every request.

```python
from faithful.lib import Kernel
with Kernel(timeout=60) as k:               # default target "versionspace" (superset of core + bridge)
    k.infer(grammar, program); k.score(grammar, request, program); k.call("vs_compress", ...)
```

A kernel that crashes or exceeds `timeout` raises `KernelProcessError` and is
relaunched on the next call (`restart=False` to forbid). A domain with Haskell
semantics (like `domains/DomainMain.hs`) is one more target: `register_target(...)`.

### Kernel pool

One `Kernel` answers one request at a time, so every parent-side loop of
independent calls runs on a single process. `KernelPool(n, ...)` takes the same
arguments and keeps `n` processes behind the same interface:

```python
from faithful.lib import KernelPool
with KernelPool(4, timeout=60) as k:
    priors = k.map(lambda k, p: k.score(grammar, request, p)["log_probability"], programs)
    ec = ExploreCompress(domain, k, StitchCompressor(), ECConfig(rounds=3))
```

`map(fn, items)` evaluates `fn(pool, item)` on up to `n` threads, one borrowed
process each, in input order, with the first exception propagated; Python
releases the GIL while a thread waits on its pipe, so the processes run
concurrently. Calls made outside `map` borrow any idle process; a nested `map`
runs on the calling thread. `Kernel.map` is the serial equivalent, so library
code written against `map` works with either. The driver uses it for the
per-entry rescoring after every Wake (`rescore_all`), the recognition summaries
prepared before training (`faithful.lib.recognition.Recognition`, a subclass of
the frozen network with identical losses), MDL `accounting` and the
beta-equivalence checks of Stitch rewrites. Results are identical to a single
`Kernel`: no state is shared between processes and no response depends on call
order. `FAITHFUL_TRACE`/`trace=` files get a `.kernel-<i>` suffix per process.
The pool does not parallelize the Wake enumeration, compression or dreams; the
`compress`/`vs_compress` operations remain one call each.

## The `Domain` interface

A domain delivers four things; defaults cover the common cases.

```python
from faithful.lib import Domain, Primitive, ast
import torch

INT = ast.base("int")

class Arithmetic(Domain):
    name, request, feature_dim = "arith", ast.arrow(INT, INT), 4
    primitives = [Primitive("incr", ast.arrow(INT, INT), lambda n: n + 1),          # 1. DSL + semantics
                  Primitive("+", ast.arrows(INT, INT, INT), lambda a, b: a + b),
                  Primitive("1", INT, 1)]
    # 2. likelihood: default is deterministic I/O matching (0 / -inf); override log_likelihood(task, program, outputs)
    def features(self, task):                                                     # 3. task encoder
        return torch.tensor([len(task.examples), *task.outputs[:3]], dtype=torch.float32)
    # 4. dreams: default evaluates the sampled program on a training task's inputs; override dream()/dream_inputs()
```

* Primitive implementations are n-ary Python callables (curried automatically from
  the type) or constants; functions passed into primitives are one-argument
  callables. Set `evaluator = KernelEvaluator()` when semantics live in Haskell.
* `Task(name, examples=[(inputs, output)], request)` holds only I/O examples.
* `FunctionalDomain(...)` assembles a domain from plain functions without subclassing.

## Running Explore–Compress

```python
from faithful.lib import Kernel, ExploreCompress, ECConfig, SearchConfig, StitchCompressor
domain = Arithmetic()
tasks = [domain.unary_task("add2", [(0, 2), (5, 7)]), domain.unary_task("add3", [(0, 3), (5, 8)])]
with Kernel() as kernel:
    ec = ExploreCompress(domain, kernel, StitchCompressor(iterations=3),
                         ECConfig(rounds=3, seed=7, search=SearchConfig(limit=3000, top_k=5), output="results/arith"))
    history = ec.run(tasks)              # RoundRecord: grammar, frontiers, compression, dream, losses, traces
    held_out = ec.solve(more_tasks)      # wake only, recognition-guided
```

Wake enumerates with `enumerate_budget` and scores candidates through the domain;
kernel-evaluated domains with the default likelihood use the kernel's I/O filter
(`search_tasks`). Pass `wake=` to inject another search, `recognition_factory=` to
replace the network, `base_grammar=` to start from a learned library.

## Compressors

### Task-parallel Wake and solve

Set `ECConfig(workers=4)` to parallelize the task searches in both `run()` and
`solve()`. The default remains one worker. The driver creates one `WakePool` of
`workers` spawned processes on its first parallel Wake and reuses it for every
later `solve()` and round; each process owns a persistent Kernel. `ec.close()`
(or `with ExploreCompress(...) as ec:`) releases it, and the next parallel Wake
builds a fresh one. The parent computes recognition-conditioned grammars, merges
results in input-task order, and performs compression/dream/recognition.
Search limits remain **per task per Wake**, not per worker or per whole study.
Parallel tasks do not share one Kernel or split a single task's search tree.

`cloudpickle` (a package dependency) transports trusted local Domain definitions
and wake callbacks, including lambda-based primitives, once, when the pool is
created; the grammar, the search grammar and the driver configuration travel
with every job, so later rounds and a changed `ec.config` are seen by the
workers without rebuilding the pool. Models, locks and live Kernel handles must
not be stored in Domains or captured callbacks. A custom wake callback gets a
worker-local EC object and the explicit frozen grammars; it must not depend on
the parent's model, history, frontiers or mutable state. Use the usual
`if __name__ == "__main__":` guard in standalone scripts because the executor
uses `spawn` on every platform. One-task and empty batches use the serial path.
Workers close their Kernels on shutdown. A job that raises propagates to the
caller and leaves the pool usable; a worker process that dies closes the pool
so the next parallel Wake rebuilds it.

Each worker uses one PyTorch CPU thread to avoid oversubscription. Kernel
timeouts and executable options are inherited; trace files receive per-worker
PID suffixes. `WakeTrace.worker_pid` and `kernel_pid` identify parallel workers.
Launching processes has measurable overhead and increases memory consumption;
small tasks may be slower than a serial run. This is not single-task parallelism.
`explore_compress(..., kernel_threads=n)` combines both: a `KernelPool` of `n`
processes in the parent and the worker pool for Wake.

### ARC local-shape DSL

`faithful.lib.domains.arc_shapes.ARCShapesDomain` adapts all productions from
`arc_tsl.language.grid_library()`. Search/type inference stay in Haskell;
execution uses the existing Python primitive semantics. Shape and ShapeId remain
distinct types. `convert_term()` converts base ARC-TSL AST expressions; expand
ARC-TSL inventions first and wrap the result in `ast.abstraction()` for a complete
Grid -> Grid program. Faithful inventions use its native AST/evaluator.

Recognition currently uses a simple 24-dimensional feature vector: input/output
height, width and color proportions averaged over demonstration pairs. Dream
inputs are sampled only from the EC training tasks, and malformed/invalid output
grids are rejected. This is a baseline encoder, not a learned spatial encoder.
The initial faithful grammar is uniform; it does not reproduce ARC-TSL's integer
AST costs or its observational-equivalence pruning.

See [the ARC runner](../../docs/ARC_TSL_FAITHFUL.md) for complete commands and
evaluation boundaries.

```python
OriginalCompressor(arity=1, iterations=3)               # frozen Haskell `compress`
VersionSpaceCompressor(iterations=3, arity=1, top_i=300, beam_size=10**6)   # `vs_compress`
StitchCompressor(iterations=3, options=StitchOptions(max_arity=2), mode="iterative", rewrite="auto", gate="none")
```

All return `CompressionResult(grammar, frontiers, inventions, history, statistics)`;
unsolved frontiers pass through, inputs are never mutated, and rewritten programs
are β-equivalent, η-long and typed (`faithful/tests/test_lib.py::test_compressors_share_contract`).

### Stitch

`faithful.lib.stitch` wraps `stitch_core` 0.1.29 completely: `StitchOptions` lists
every backend flag (`extra={}` passes unknown ones through), `compress()` returns
abstractions as `invented` ASTs plus rewritten programs and the raw JSON, and
`rewrite()` applies existing abstractions. `StitchCompressor` then adds what Stitch
does not know about — the DreamCoder type system and η-long grammar:

* `strip_request_lambdas=True`: Stitch sees program bodies with the request's outer
  lambdas removed (inputs are free `$i`), so proposals are closed inventions
  (`#(map (lambda (+ $0 $0)))`) rather than wrappers around η-long scaffolding.
* `no_curried_metavars` defaults to `True`: in η-long programs a metavariable in
  function position only abstracts `(lambda (#0 $0))`, which the kernel restores.
* `rewrite="auto"` uses Stitch's rewrites when they are β-equivalent and scorable,
  else the kernel's inverse-β rewrite (`compression_trial`); `"kernel"` always uses
  the latter (the frozen study's protocol), `"stitch"` keeps originals on failure.
* `gate="mdl"` reproduces the study's acceptance rule (DreamCoder MDL must improve,
  stop at first rejection); `gate="none"` accepts every well-typed abstraction.
* `mode="batch"` makes one backend call for all iterations (Stitch's own hierarchy).

Known backend limits found while wrapping (vendored Windows wheel): Stitch's
`eta_long` means lambda-rooted abstractions passed as bare arguments, which the
kernel's η-long form rejects — leave it off; `utility_by_rewrite=True` overflows
the Rust stack. Both are documented on `StitchOptions`.

## Tests

```powershell
python -m pytest faithful/tests/test_lib.py faithful/tests/test_pool.py -q
```
