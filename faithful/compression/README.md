# Controlled compression study

This package adds compressor boundaries without editing the frozen symbolic or
recognition implementation. `OriginalCompressor` delegates to the existing
Haskell compressor. `StitchCompressor` calls the real Rust-backed `stitch_core`
package for proposals and checks their native rewrites, then applies the same
Haskell rewrite/MDL acceptance protocol as Original. It stops on a rejected
top-ranked proposal; this limitation is intentional and reported, not a claim
about unrestricted Stitch.

`Compressor.compress(frontiers, grammar)` returns a `CompressionResult` with
inventions, corresponding rewritten frontiers, before/after MDL accounting,
updated grammar, history and statistics. Unsolved frontiers are preserved.
Inputs are never mutated. Grammar likelihoods and invention types are computed
by Haskell. MDL improvements are positive when code length decreases.

## Reproduce (PowerShell, from repository root)

```powershell
$studyPython = 'E:\anaconda3\envs\py312\python.exe'
& $studyPython -m pip install --target faithful/vendor -r faithful/compression/requirements.txt
& $studyPython -c "from faithful.compression.interface import build_bridge; build_bridge()"
& $studyPython -m faithful.domains.official
& $studyPython -m faithful.compression.study frozen
& $studyPython -m faithful.compression.study ec --workers 8
$env:PYTHONPATH = (Resolve-Path faithful/vendor).Path
& $studyPython -m pytest faithful/tests tests -q --junitxml=results/stitch/regression.xml
& $studyPython -m faithful.compression.report
```

The CLI reuses completed artifacts for this exact fixed study and resumes EC
at completed round boundaries, restoring recognition checkpoints and RNG state.
It is not a general configuration cache. Archive the result directory before
changing experiment definitions or dependency versions. Four regimes, paired
seed 11 and five rounds are specified in `study.py`; the full controlled
benchmark task set and search budgets are preserved. No multi-seed confidence
claim is made. Held-out evaluation occurs at iterations 0 and 5.

`study.py` and `report.py` are evaluation-only: they can read generator metadata
for cohort selection, diagnostics and recovery measurement. The compressor
modules do not import these modules or read latent definitions. Oracle material
is restricted to the separate Oracle experiment. `train_condition` runs with
only an injected compression dispatch; its function bytecode and all other
global dependencies remain unchanged.

The separate `faithful/domains/official.py` adapter binds the domain evaluator,
encoder and Wake boundary into the existing generic EC driver. Official source
files are read only for provenance; official OCaml is never used as runtime.
