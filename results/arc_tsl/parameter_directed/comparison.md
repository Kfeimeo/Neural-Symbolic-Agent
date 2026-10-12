# Fixed-DSL baseline vs task-specific TSL

## Condition: tsl

- tasks: 1 (in scope: 1); status counts: {'NO_SHARED_PROGRAM': 1}
- training-fit rate (all): baseline 0.000 vs tsl 0.000
- training-fit rate (in scope): baseline 0.000 vs tsl 0.000
- labeled test tasks correct: baseline 0/1 vs tsl 0/1
- solved by baseline only: []; by tsl only: []
- tasks with >=1 abstraction: 1; solved using an abstraction: 0 (of which whole-program abstractions: 0)

### solved_only (n=0)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| states_ratio (geomean) |  | | | |
| first_states_ratio (geomean) |  | | | |
| time_ratio (geomean) |  | | | |
| total_states_ratio incl. wake (geomean) |  | | | |

### solved_only_nontrivial_abstraction (n=0)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| states_ratio (geomean) |  | | | |
| first_states_ratio (geomean) |  | | | |
| time_ratio (geomean) |  | | | |
| total_states_ratio incl. wake (geomean) |  | | | |

### all_tasks (n=1)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 3e+05 | 3e+05 | 0 | 1 |
| tsl_expanded_states | 1.103e+05 | 1.103e+05 | 0 | 1 |
| baseline_search_seconds | 85.76 | 85.76 | 0 | 1 |
| tsl_search_seconds | 30.87 | 30.87 | 0 | 1 |
| tsl_description_length | 8 | 8 | 0 | 1 |
| tsl_num_abstractions | 1 | 1 | 0 | 1 |
| local_wake_total_states | 1.897e+05 | 1.897e+05 | 0 | 1 |
| local_wake_seconds | 22.27 | 22.27 | 0 | 1 |
| local_sleep_seconds | 0.003566 | 0.003566 | 0 | 1 |
| states_ratio | 2.721 | 2.721 | 0 | 1 |
| time_ratio | 2.778 | 2.778 | 0 | 1 |
| total_states_ratio | 1 | 1 | 0 | 1 |
| states_ratio (geomean) | 2.72 | | | |
| first_states_ratio (geomean) |  | | | |
| time_ratio (geomean) | 2.78 | | | |
| total_states_ratio incl. wake (geomean) | 1 | | | |

### Per-task table

| task | status | pairs | base states | base first | base L | tsl states | tsl first | tsl L | L(expanded) | wake states | #A | used | L(A) | MDL | states ratio | time ratio |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 63613498 | NO_SHARED_PROGRAM | 3 | 300000 |  |  | 110271 |  |  |  | 189729 | 1 | 0 | 8 |  | 2.72 | 2.78 |

## Condition: tsl_parameters

- tasks: 1 (in scope: 1); status counts: {'SOLVED': 1}
- training-fit rate (all): baseline 0.000 vs tsl_parameters 1.000
- training-fit rate (in scope): baseline 0.000 vs tsl_parameters 1.000
- labeled test tasks correct: baseline 0/1 vs tsl_parameters 0/1
- solved by baseline only: []; by tsl_parameters only: ['63613498']
- tasks with >=1 abstraction: 1; solved using an abstraction: 1 (of which whole-program abstractions: 0)

### solved_only (n=0)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| states_ratio (geomean) |  | | | |
| first_states_ratio (geomean) |  | | | |
| time_ratio (geomean) |  | | | |
| total_states_ratio incl. wake (geomean) |  | | | |

### solved_only_nontrivial_abstraction (n=0)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| states_ratio (geomean) |  | | | |
| first_states_ratio (geomean) |  | | | |
| time_ratio (geomean) |  | | | |
| total_states_ratio incl. wake (geomean) |  | | | |

### all_tasks (n=1)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 3e+05 | 3e+05 | 0 | 1 |
| tsl_expanded_states | 1547 | 1547 | 0 | 1 |
| tsl_first_solution_states | 1547 | 1547 | 0 | 1 |
| tsl_first_solution_nodes | 1 | 1 | 0 | 1 |
| baseline_search_seconds | 85.76 | 85.76 | 0 | 1 |
| tsl_search_seconds | 0.0852 | 0.0852 | 0 | 1 |
| tsl_program_length | 10 | 10 | 0 | 1 |
| tsl_expanded_program_length | 14 | 14 | 0 | 1 |
| tsl_description_length | 8 | 8 | 0 | 1 |
| total_mdl | 18 | 18 | 0 | 1 |
| tsl_num_abstractions | 1 | 1 | 0 | 1 |
| local_wake_total_states | 1.897e+05 | 1.897e+05 | 0 | 1 |
| local_wake_seconds | 22.27 | 22.27 | 0 | 1 |
| local_sleep_seconds | 0.0029 | 0.0029 | 0 | 1 |
| states_ratio | 193.9 | 193.9 | 0 | 1 |
| time_ratio | 1007 | 1007 | 0 | 1 |
| total_states_ratio | 1.568 | 1.568 | 0 | 1 |
| states_ratio (geomean) | 194 | | | |
| first_states_ratio (geomean) |  | | | |
| time_ratio (geomean) | 1.01e+03 | | | |
| total_states_ratio incl. wake (geomean) | 1.57 | | | |

### Per-task table

| task | status | pairs | base states | base first | base L | tsl states | tsl first | tsl L | L(expanded) | wake states | #A | used | L(A) | MDL | states ratio | time ratio |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 63613498 | SOLVED | 3 | 300000 |  |  | 1547 | 1547 | 10 | 14 | 189729 | 1 | 1 | 8 | 18 | 194 | 1.01e+03 |
