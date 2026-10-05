# Execution trace: ARC task `3c9b0459`

## Training pairs (input → output)

### pair 0

```
221
212
281

→

182
212
122
```

### pair 1

```
924
244
292

→

292
442
429
```

### pair 2

```
888
558
855

→

558
855
888
```

### pair 3

```
329
999
233

→

332
999
923
```

## Baseline A: fixed ML+DSA search over all pairs

```
solved: True
expanded_states: 6570
retained_terms: 1269
evaluated_programs: 7
equivalent_terms: 5037
dead_terms: 264
first_solution_nodes: 7
first_solution_states: 6570
first_solution_seconds: 0.14154925999991974
seconds: 0.1415674959998796
termination_reason: frontier_complete
max_cost_reached: 6
best_program: (map (λObject. (rotate $0 r180)) $0)
best_program_length: 6
```

## Method B (tsl_reweight): local wake → local compression → TSL_τ → re-wake

### Local wake (one micro-task per pair)

- pair 0: solved=True expanded_states=5310 first_solution_states=5310 seconds=0.06
  - frontier: ['(map (λObject. (rotate $0 r180)) $0)']
- pair 1: solved=True expanded_states=5310 first_solution_states=5310 seconds=0.06
  - frontier: ['(map (λObject. (rotate $0 r180)) $0)']
- pair 2: solved=True expanded_states=5002 first_solution_states=5002 seconds=0.06
  - frontier: ['(map (λObject. (rotate $0 r180)) $0)']
- pair 3: solved=True expanded_states=5310 first_solution_states=5310 seconds=0.06
  - frontier: ['(map (λObject. (rotate $0 r180)) $0)']

### Local sleep (compression)

- MDL before: 24  after: 15  L(A_τ) = 7
- sleep seconds: 0.001365246999739611
- pruned: []
- accepted `#f0 = λx0:ObjectSet. (map (λObject. (rotate $0 r180)) $0)` (MDL 24 → 15, 3 candidates scored)
- rewritten frontiers:
  - pair 0: ['(#f0 $0)']
  - pair 1: ['(#f0 $0)']
  - pair 2: ['(#f0 $0)']
  - pair 3: ['(#f0 $0)']
- final TSL_τ abstractions:
  - `#f0 = λx0:ObjectSet. (map (λObject. (rotate $0 r180)) $0)`
- θ_τ (non-unit costs): {'i0': 2, 'i1': 2, 'i2': 2, 'i3': 2, 'add': 2, 'sub': 2, 'neg': 2, 'eq_int': 2, 'lt': 2, 'not': 2, 'and': 2, 'or': 2, 'vec': 2, 'up': 2, 'down': 2, 'left': 2, 'right': 2, 'vadd': 2, 'vsub': 2, 'vneg': 2, 'vscale': 2, 'map': 2, 'filter': 2, 'argmin': 2, 'argmax': 2, 'unique': 2, 'count': 2, 'insert': 2, 'delete': 2, 'replace': 2, 'others': 2, 'if_obj': 2, 'c0': 2, 'c1': 2, 'c2': 2, 'c3': 2, 'c4': 2, 'c5': 2, 'c6': 2, 'c7': 2, 'c8': 2, 'c9': 2, 'r90': 2, 'r180': 2, 'r270': 2, 'axis_h': 2, 'axis_v': 2, 'axis_d': 2, 'rg_support': 2, 'rg_bbox': 2, 'rg_bbox_minus_support': 2, 'rg_boundary': 2, 'rg_neighbors4': 2, 'rg_neighbors8': 2, 'rg_row_span': 2, 'rg_column_span': 2, 'rg_minimal_square_hull': 2, 'translate': 2, 'rotate': 2, 'reflect': 2, 'recolor': 2, 'replace_color': 2, 'add_region': 2, 'remove_region': 2, 'size': 2, 'center': 2, 'bbox_top': 2, 'bbox_left': 2, 'bbox_bottom': 2, 'bbox_right': 2, 'height': 2, 'width': 2, 'color_set': 2, 'dominant_color': 2, 'num_colors': 2, 'shape_id': 2, 'orientation': 2, 'has_color': 2, 'eq_color': 2, 'eq_shape': 2, 'same_shape': 2, 'same_color': 2, 'left_of': 2, 'right_of': 2, 'above': 2, 'below': 2, 'touch4': 2, 'touch8': 2, 'distance': 2, 'center_delta': 2, 'nearest': 2}

### Local re-wake (one program for all pairs in TSL_τ)

```
solved: True
expanded_states: 7
retained_terms: 6
evaluated_programs: 2
equivalent_terms: 1
dead_terms: 0
first_solution_nodes: 2
first_solution_states: 7
first_solution_seconds: 0.008664190000672534
seconds: 0.008680431000357203
termination_reason: frontier_complete
max_cost_reached: 2
best_program: (#f0 $0)
best_program_length: 2
```

- status: **SOLVED**
- program: `(#f0 $0)`
- expanded program: `(map (λObject. (rotate $0 r180)) $0)`
- L(p_τ | TSL_τ) = 2, L(expanded) = 6, total MDL = L(TSL_τ) + L(p_τ|TSL_τ) = 9
- abstractions used: ['#f0']

## Comparison

- expanded states: baseline 6570 vs TSL 7 (ratio 938.57)
- first-solution states: baseline 6570 vs TSL 7
- search seconds: baseline 0.14 vs TSL 0.01
- program length: baseline 6 vs TSL 2 (expanded 6)
- TSL total search incl. wake: 20939 states
