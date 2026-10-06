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
python -m pytest faithful/tests/test_lib.py -q
```
