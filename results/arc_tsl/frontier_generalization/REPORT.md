# ARC-TSL generalization and total-cost diagnostic

The known case is a development diagnostic. Its test answer was already inspected before this work; this is not an untouched benchmark claim.

Each leave-one-out fold relearns Wake, compression and parameters from the remaining training pairs. Fold results do not select or modify the full-task program.

| Arm / split | Train-consistent | Held-out correct | Total states | Solve wall (s) | Solve CPU (s) | Peak RSS (MiB) |
|---|---:|---:|---:|---:|---:|---:|
| baseline / full | 0/1 | 0/1 | 247808 | 90.145 | 88.797 | 4740.9 |
| parameters / full | 1/1 | 0/1 | 191276 | 23.019 | 22.891 | 468.3 |
| parameters / loo | 0/3 | 0/3 | 379458 | 46.538 | 45.828 | 434.2 |
| demand_single / full | 1/1 | 0/1 | 3627 | 0.212 | 0.219 | 30.2 |
| demand_single / loo | 0/3 | 0/3 | 4160 | 0.250 | 0.234 | 28.6 |
| diverse / full | 1/1 | 0/1 | 270075 | 32.103 | 31.734 | 637.2 |
| diverse / loo | 0/3 | 0/3 | 535344 | 59.413 | 58.656 | 614.5 |

`full` scores the task test; `loo` sums separate leave-one-training-pair-out runs. States and time are summed; memory is the maximum per fresh worker. Unsolved labeled runs count as incorrect. Missing labels are excluded, not scored as failures.

## Full-task frontiers and selected programs

### 63613498 / baseline

- Wake frontier sizes: []
- Wake structure counts: []
- Learned abstractions: 0
- Test correct: False

```
No training-consistent program returned.
```

### 63613498 / parameters

- Wake frontier sizes: [1, 1, 1]
- Wake structure counts: [1, 1, 1]
- Learned abstractions: 1
- Test correct: False

```
(#f0 (dominant_color (argmax (λObject. (bbox_bottom (nearest $0 $1))) $0)) $0)
```

### 63613498 / demand_single

- Wake frontier sizes: [1, 1, 1]
- Wake structure counts: [1, 1, 1]
- Learned abstractions: 1
- Test correct: False

```
(#f0 (dominant_color (argmax (λObject. (bbox_bottom (nearest $0 $1))) $0)) $0)
```

### 63613498 / diverse

- Wake frontier sizes: [5, 5, 5]
- Wake structure counts: [5, 5, 5]
- Learned abstractions: 1
- Test correct: False

```
(#f0 (dominant_color (argmax (λObject. (bbox_bottom (nearest $0 $1))) $0)) $0)
```

## Protocol and limits

- All arms use the same per-run total state/time budget, DSL and extraction policy; all Wake cost is charged. The conditional prior is unchanged.
- `parameters`: prior single-witness Wake; `demand_single`: demand-driven Wake with one solution; `diverse`: demand-driven Wake, K=5 distinct structures and at most 2 representatives per observational class. `baseline` is fixed-DSL full-task enumeration.
- Diversity preserves operator/lambda/variable structure and ignores literal-only changes. These are syntactic alternatives, not proven semantic equivalence classes.
- Parameter synthesis considers up to 64 cost-ordered witness assignments across pairs. Truncation, frontier sizes, additional OE representatives and cell caps are recorded.
- Each arm/fold runs sequentially in a new process, with no cross-fold caches. OS peak RSS includes the interpreter and imports. Parent launch/transport time is recorded separately.
- Search time limits are cooperative. `resources.solve_wall_seconds` includes the complete fit; scoring and job startup/transport are reported separately. Compression and witness validation are included in time, not enumeration-state counts.
- Validation budgets are additional diagnostic expenditure, not free inference. Full-task and validation totals are reported separately above; sum both to obtain study cost.
- No test/validation label or reference program enters synthesis or candidate selection. Fold scores are descriptive and correlated; one task does not establish a general accuracy gain.

See `protocol.json` for frozen settings and source/data hashes and `runs/*/result.json` for programs, predictions, metrics and failures.
