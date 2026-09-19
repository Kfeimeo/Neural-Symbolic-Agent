# Official DreamCoder Domain Validation

## Scope and source provenance
Arithmetic follows the [official tutorial](https://github.com/ellisk42/ec/blob/master/docs/creating-new-domains.md): `incr : int -> int`, `incr2 : int -> int`; train add1/add2/add3, held-out add4. List uses official `map double`, `map increment`, `map negation` training functions and held-out `map quadruple`, `map add 3` from [makeListTasks.py](https://github.com/ellisk42/ec/blob/master/dreamcoder/domains/list/makeListTasks.py), with the `map`, `+`, `-`, `0`, `1` subset of bootstrapTarget primitives. `map : (a -> b) -> list(a) -> list(b)` is polymorphic and higher-order.

Examples are compact deterministic samples of the official task functions, not the original randomized 5000-example arithmetic training sets. This validates external domain semantics, not reproduction of published performance. The locally pinned reference commit is `cb0e63f5c33cd2de360b791038b0f5272750270e`; exact domain source hashes are in `official_source_sha256.json`. Only names, type requests and I/O examples enter learning; no ground-truth AST enters either domain learner.

## Runtime and unchanged algorithm
`DomainMain.hs` supplies domain primitive values to the existing Haskell evaluator and delegates symbolic operations to the existing core. The original Haskell files are unchanged; no official OCaml runtime is used. Python binds domain evaluator, 40-dimensional I/O task encoder and Wake boundary into the exact existing `ec.explore_compress` function bytecode. Wake uses the existing typed budget enumerator and evaluator, retaining generative top-5 frontiers. This is a domain adapter, not a replacement solver.

Three persistent rounds execute Wake -> frontier merge -> original compression -> grammar update -> ancestral Dream -> posterior-frontier Replay -> unchanged PyTorch recognition training -> next Wake. Each round uses 20 Dream draws and 30 optimizer steps from the existing domain EC recipe; Wake uses 3000 complete candidates, 500000 expanded states, leaf-size 33, depth 14. Arithmetic and List use the same recipe. CUDA is used for recognition.

## Measured trajectories

| Domain | Round | Solved | Library size | New inventions | MDL | Frontier sizes | First solution candidate ranks | Accepted dreams / 20 |
|---|---|---|---|---|---|---|---|---|
| arithmetic | 1 | 3/3 | 2 | 0 | 8.300 | 1/2/3 | 2/3/5 | 20 |
| arithmetic | 2 | 3/3 | 2 | 0 | 8.245 | 1/2/3 | 2/3/4 | 20 |
| arithmetic | 3 | 3/3 | 2 | 0 | 8.218 | 1/2/3 | 2/3/5 | 20 |
| list | 1 | 3/3 | 5 | 0 | 20.493 | 5/5/5 | 24/21/27 | 20 |
| list | 2 | 3/3 | 5 | 0 | 20.124 | 5/5/5 | 14/13/25 | 20 |
| list | 3 | 3/3 | 5 | 0 | 20.094 | 5/5/5 | 14/15/22 | 20 |

MDL = negative summed frontier log-marginal + number of productions + 0.001 × production body leaf cost, in natural-log units. Initial and later frontier sets may differ: trajectory changes are not a fixed-corpus compression contrast.

## Held-out and recognition effect

| Domain | Task | Guidance | First solution rank | Emitted candidates | Expanded states | Stop |
|---|---|---|---|---|---|---|
| arithmetic | add4 | generative | 8 | 3000 | 8439 | candidate_budget |
| arithmetic | add4 | recognition | 6 | 3000 | 9904 | candidate_budget |
| list | map quadruple | generative | 136 | 3000 | 42299 | candidate_budget |
| list | map quadruple | recognition | 1285 | 3000 | 36092 | candidate_budget |
| list | map add 3 | generative | None | 3000 | 42299 | candidate_budget |
| list | map add 3 | recognition | None | 3000 | 36151 | candidate_budget |

The arithmetic training tasks are solved in all three rounds and add4 transfers. List training tasks are also solved, but map add 3 is unsolved under the fixed bound. Recognition helps arithmetic add4 and hurts List map quadruple in this run; no universal recognition gain is claimed.

## Inventions and limits

Neither small training corpus accepted a new invention. The full compression phase ran and grammar weights evolved; absence of an accepted invention is a measured outcome. Learned invention discovery on these official subsets is therefore **not established**. A separate correctness test constructs a polymorphic higher-order invented map wrapper, verifies inference, lambda binding, beta equivalence and evaluation on int/bool lists; this checks representation support, not learned recovery. Controlled Grid experiments supply the learned-invention evidence.

## Reproduction

From the project root, run `E:\anaconda3\envs\py312\python.exe -m faithful.domains.official`. Results and checkpoints are in `results/stitch/domains/`. Source hashes and the complete regression results are recorded with the Stitch study.
