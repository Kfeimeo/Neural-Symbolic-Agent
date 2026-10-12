# ARC-TSL: directed parameter completion pilot

One diagnostic task: `63613498`. This is a development pilot, not a held-out benchmark study.

## Result

The directed method finds a program fitting all three training pairs. Its frozen prediction is **incorrect on the one test pair**. This demonstrates a search improvement on this task, but no test-accuracy improvement.

| Condition | Program matching all training pairs | Test tasks correct | Wake states | Final-search states | Total enumeration states | Search pipeline seconds |
|---|---:|---:|---:|---:|---:|---:|
| Fixed DSL | Not found | 0/1 | 0 | 300000 | 300000 | 85.757 |
| tsl | Not found | 0/1 | 189729 | 110271 | 300000 | 53.143 |
| tsl_parameters | Found (3/3 pairs) | 0/1 | 189729 | 1547 | 191276 | 22.356 |

## Learned call and synthesized argument

Wake calls:
```
(#f0 c6 $0)
(#f0 c9 $0)
(#f0 c1 $0)
```

Learned abstraction:
```
#f0 = λx0:Color x1:ObjectSet. (map (λObject. (replace_color $0 $2 c5)) $0)
```

Chosen program (frozen before test scoring):
```
(#f0 (dominant_color (argmax (λObject. (bbox_bottom (nearest $0 $1))) $0)) $0)
```

Completed-call length: 10; expanded base-language length: 14.

The parameter phase constructs 1547 states, checks 39 ground parameter expressions, and verifies 1 complete program. It separately validates 3 Wake witnesses. These validation checks are included in elapsed time, but are not enumeration states.

The selected argument uses nearest-object geometry to choose a color. It matches the training color vector (6, 9, 1), but does not generalize to the test input. Test labels were used only for scoring this already chosen program. No candidate was replaced after test scoring.

## Protocol

- Same fixed DSL and extraction policy (8-connectivity, background 0, mixed-color connected components).
- Same full-task budget: 300,000 enumeration states and 90 seconds; maximum complete-program cost 24.
- Per-pair Wake cap: cost 10, 300,000 states, 20 seconds, top-K 1; Wake also shares the pooled full-task budget.
- Original TSL and directed TSL reuse the same fresh Wake results; each is charged the full Wake cost.
- Sleep time and Wake search time are subtracted before final search. State exhaustion and time limits are retained in JSON. Wall limits are cooperative, as in the original enumerator.
- Complete baseline and TSL searches in this final run were dispatched sequentially. Wall times are machine-dependent; comparison is based primarily on enumerated states.
- Test predictions, including the incorrect grid, are retained in `tsl.json`. No solution means no test prediction.
- `max_cost_reached` in the directed phase refers to the argument-expression cost; it is not directly comparable with full-program cost levels.

## Scope and verification

The method fixes a root call to a learned abstraction and varies only ground-typed arguments. It uses one cheapest Wake witness per pair and witnessed argument-value vectors as sufficient constraints. It can miss other valid programs. No fallback receives an extra budget.

Tests cover learned single-parameter completion and an unseen synthetic input, multiple parameters, invalid or missing Wake witnesses, complete-call cost limits, zero/exhausted state/time budgets, fresh-Wake pipeline integration, and observation equivalence against ordinary enumeration on small grammars (including weighted costs).

Validation: `python -m pytest tests/arctsl -q -p no:cacheprovider` — 59 passed. `git diff --check` passed.

Implementation and data SHA-256 hashes are in `source_manifest.json`. Commands are documented in `arc_tsl/README.md`. The earlier `parameter_pilot` directory records an exploratory eager dependency-scheduling version; it is not the final result.
