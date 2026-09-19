# DreamCoder semantic core and executable fidelity checks

Independent Haskell symbolic kernel + Python/PyTorch recognition. The original
`dreamcoder/` remains the separate DreamCoder-lite implementation.

## Controlled hierarchical benchmark

Recognition automatically selects CUDA when `torch.cuda.is_available()` is true,
otherwise CPU. CPU feature tensors are moved to the model's current device, and
checkpoint loading supports either device. Use `Recognition(g, device="cpu")` for
an explicit CPU override. Haskell enumeration and compression remain CPU operations.
Launch Python from the desired conda environment; the code does not switch environments.

The historical controlled CPU run remains hash-locked. For a CUDA run with exactly
the same frozen dataset and independent results/checkpoints:

```powershell
conda run -n py312 python -m faithful.python.controlled_run fork-runtime --output faithful/results/controlled_cuda
conda run -n py312 python -m faithful.python.controlled_run train --output faithful/results/controlled_cuda --workers 2
conda run -n py312 python -m faithful.python.controlled_run evaluate --output faithful/results/controlled_cuda --workers 2
```

`fork-runtime` copies only frozen data, records the parent manifest and current
device-runtime revision, and refuses to overwrite an existing directory. Runtime
variant reports are written inside that variant's output directory.

The current benchmark uses a frozen 224-train/168-test distribution with private
generated latent functions, four independent reuse cohorts, three training seeds,
multi-round EC, fitted-prior/shuffle controls and a separately labeled Oracle.
Its generator, learner boundary and evaluator are separate `controlled_*.py` modules;
the accepted core below is unchanged. See the root `CONTROLLED_BENCHMARK_REPORT.md`
and `CONTROLLED_EXPERIMENT_REPORT.md` for results and acceptance limitations.

Resume the frozen experiment and rebuild its reports:

```powershell
python -m faithful.python.controlled_run train --workers 8
python -m faithful.python.controlled_run evaluate --workers 8
python -m faithful.python.controlled_audit
python -m faithful.python.controlled_provenance
python -m faithful.python.controlled_report
```

`benchmark_manifest.json` plus `SHA256SUMS.json` verify data and core hashes.
Search caches include all I/O, grammar and resource settings in their keys; normal
and shuffled recognition share enumeration only when their entire search grammars
match. Their target-task assignments remain distinct. `evaluation_index.json` is
the authoritative selection of cache rows; interim/profiling caches are not added
to final metrics. The finite rewrite-space and probe limitations are explicit in
the reports. The original toy below is regression/smoke evidence only.

## Core and regression commands

From the repository root, using Python with torch, pytest and frozendict:

```powershell
python -m faithful.python.kernel
python -m pytest faithful/tests -q
python -m faithful.python.ec
python -m faithful.python.toy
python -m faithful.run_acceptance
```

`faithful.python.toy` runs the original seed-7 36-train/24-test experiment with
all 24 Grid productions, A/B/C/D, fitted-prior and uniform-library controls, and
fixed task shuffles. Results default to `faithful/results/toy_original/`.
`faithful.python.ec` retains the small five-operation smoke fixture.
The frozen 96/60 calibration dataset can be selected separately:

```powershell
python -m faithful.python.toy --benchmark calibration --max-size 33 --output faithful/results/toy_calibration
```

The original experiment has been run; the calibration command is an available
adapter, not a claim that its full budget sweep has already been rerun.
Recognition uses 1000 optimizer steps by default (`--steps`); this is not the old
histogram model's 100 epochs. Search consumes at most `--max-nodes` complete
programs and `--max-states` popped agenda states. It checks all candidates in that
budget and retains generative top-K, rather than stopping at K guided hits.

The last command also regenerates live OCaml compression references using the
existing WSL `Ubuntu-24.04`; it requires WSL access. Ordinary tests check the saved
reference compression artifacts and run the Python reference afresh. All core
modules in the reference are unmodified. Its eager package `__init__` imports are
bypassed solely to avoid importing unrelated historical domains.

Pinned reference: https://github.com/ellisk42/ec/tree/cb0e63f5c33cd2de360b791038b0f5272750270e

To reconstruct the ignored reference checkout:

```powershell
git clone https://github.com/ellisk42/ec.git faithful/reference/ec
git -C faithful/reference/ec checkout cb0e63f5c33cd2de360b791038b0f5272750270e
```

GHC's bundled base, containers, mtl and parsec suffice; no Hackage packages needed.
Build artifacts are local to `faithful/build`. The executable is independent of
the official source and does not invoke OCaml. Reference code is used only in tests.

See `protocol/README.md`, root `FAITHFUL_DREAMCODER_REPORT.md`, and
`FAITHFUL_VS_LITE.md` for acceptance scope and known differences. This directory's
name is an implementation target, not a claim that tiny tests prove every possible
DreamCoder experiment equivalent.
