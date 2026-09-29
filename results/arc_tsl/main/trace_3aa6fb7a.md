# Execution trace: ARC task `3aa6fb7a`

## Training pairs (input → output)

### pair 0

```
0000000
0800000
0880000
0000880
0000080
0000000
0000000

→

0000000
0810000
0880000
0000880
0000180
0000000
0000000
```

### pair 1

```
0000880
0000080
0080000
0088000
0000000
0000800
0008800

→

0000880
0000180
0081000
0088000
0000000
0001800
0008800
```

## Baseline A: fixed ML+DSA search over all pairs

```
solved: True
expanded_states: 42241
retained_terms: 8868
evaluated_programs: 31
equivalent_terms: 31707
dead_terms: 1666
first_solution_nodes: 31
first_solution_states: 42241
first_solution_seconds: 4.590521603999605
seconds: 4.590544893999777
termination_reason: frontier_complete
max_cost_reached: 7
best_program: (map (λObject. (add_region $0 rg_bbox c1)) $0)
best_program_length: 7
```

## Method B (tsl): local wake → local compression → TSL_τ → re-wake

### Local wake (one micro-task per pair)

- pair 0: solved=True expanded_states=36916 first_solution_states=36916 seconds=3.08
  - frontier: ['(map (λObject. (add_region $0 rg_bbox c1)) $0)']
- pair 1: solved=True expanded_states=41671 first_solution_states=41671 seconds=2.17
  - frontier: ['(map (λObject. (add_region $0 rg_bbox c1)) $0)']

### Local sleep (compression)

- MDL before: 14  after: 12  L(A_τ) = 6
- sleep seconds: 0.0007853639999666484
- pruned: []
- accepted `#f0 = λ. (λObject. (add_region $0 rg_bbox c1))` (MDL 14 → 12, 3 candidates scored)
- rewritten frontiers:
  - pair 0: ['(map #f0 $0)']
  - pair 1: ['(map #f0 $0)']
- final TSL_τ abstractions:
  - `#f0 = λ. (λObject. (add_region $0 rg_bbox c1))`

### Local re-wake (one program for all pairs in TSL_τ)

```
solved: True
expanded_states: 162
retained_terms: 145
evaluated_programs: 2
equivalent_terms: 17
dead_terms: 0
first_solution_nodes: 2
first_solution_states: 162
first_solution_seconds: 0.010877977000745886
seconds: 0.010922252000455046
termination_reason: frontier_complete
max_cost_reached: 3
best_program: (map #f0 $0)
best_program_length: 3
```

- status: **SOLVED**
- program: `(map #f0 $0)`
- expanded program: `(map (λObject. (add_region $0 rg_bbox c1)) $0)`
- L(p_τ | TSL_τ) = 3, L(expanded) = 7, total MDL = L(TSL_τ) + L(p_τ|TSL_τ) = 9
- abstractions used: ['#f0']

## Comparison

- expanded states: baseline 42241 vs TSL 162 (ratio 260.75)
- first-solution states: baseline 42241 vs TSL 162
- search seconds: baseline 4.59 vs TSL 0.01
- program length: baseline 7 vs TSL 3 (expanded 7)
- TSL total search incl. wake: 78749 states
