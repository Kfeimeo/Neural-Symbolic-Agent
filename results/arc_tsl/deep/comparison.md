# Fixed-DSL baseline vs task-specific TSL

## Condition: tsl

- tasks: 6 (in scope: 6); status counts: {'SOLVED': 2, 'NO_PAIRWISE_SOLUTION': 3, 'NO_SHARED_PROGRAM': 1}
- solve rate (all): baseline 0.333 vs tsl 0.333
- solve rate (in scope): baseline 0.333 vs tsl 0.333
- solved by baseline only: []; by tsl only: []
- tasks with >=1 abstraction: 3; solved using an abstraction: 2 (of which whole-program abstractions: 2)

### solved_only (n=2)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 5.056e+04 | 5.056e+04 | 4.319e+04 | 2 |
| tsl_expanded_states | 106 | 106 | 0 | 2 |
| baseline_first_solution_states | 5.056e+04 | 5.056e+04 | 4.319e+04 | 2 |
| tsl_first_solution_states | 106 | 106 | 0 | 2 |
| baseline_first_solution_nodes | 51 | 51 | 48 | 2 |
| tsl_first_solution_nodes | 2 | 2 | 0 | 2 |
| baseline_search_seconds | 1.1 | 1.1 | 0.9092 | 2 |
| tsl_search_seconds | 0.004571 | 0.004571 | 0.0001688 | 2 |
| baseline_program_length | 7 | 7 | 1 | 2 |
| tsl_program_length | 2 | 2 | 0 | 2 |
| tsl_expanded_program_length | 7 | 7 | 1 | 2 |
| tsl_description_length | 8 | 8 | 1 | 2 |
| total_mdl | 10 | 10 | 1 | 2 |
| tsl_num_abstractions | 1 | 1 | 0 | 2 |
| local_wake_total_states | 1.127e+05 | 1.127e+05 | 9.434e+04 | 2 |
| local_wake_seconds | 1.406 | 1.406 | 1.18 | 2 |
| local_sleep_seconds | 0.001044 | 0.001044 | 5.505e-05 | 2 |
| states_ratio | 476.9 | 476.9 | 407.4 | 2 |
| time_ratio | 233.5 | 233.5 | 190.3 | 2 |
| first_states_ratio | 476.9 | 476.9 | 407.4 | 2 |
| total_states_ratio | 0.4255 | 0.4255 | 0.02699 | 2 |
| states_ratio (geomean) | 248 | | | |
| first_states_ratio (geomean) | 248 | | | |
| time_ratio (geomean) | 135 | | | |
| total_states_ratio incl. wake (geomean) | 0.425 | | | |

### solved_only_nontrivial_abstraction (n=0)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| states_ratio (geomean) |  | | | |
| first_states_ratio (geomean) |  | | | |
| time_ratio (geomean) |  | | | |
| total_states_ratio incl. wake (geomean) |  | | | |

### all_tasks (n=6)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 4.169e+05 | 6e+05 | 2.602e+05 | 6 |
| tsl_expanded_states | 4e+05 | 6e+05 | 2.828e+05 | 6 |
| baseline_first_solution_states | 5.056e+04 | 5.056e+04 | 4.319e+04 | 2 |
| tsl_first_solution_states | 106 | 106 | 0 | 2 |
| baseline_first_solution_nodes | 51 | 51 | 48 | 2 |
| tsl_first_solution_nodes | 2 | 2 | 0 | 2 |
| baseline_search_seconds | 75.94 | 50.35 | 86.33 | 6 |
| tsl_search_seconds | 77.28 | 50.82 | 88.28 | 6 |
| baseline_program_length | 7 | 7 | 1 | 2 |
| tsl_program_length | 2 | 2 | 0 | 2 |
| tsl_expanded_program_length | 7 | 7 | 1 | 2 |
| tsl_description_length | 4 | 3.5 | 4.041 | 6 |
| total_mdl | 10 | 10 | 1 | 2 |
| tsl_num_abstractions | 0.5 | 0.5 | 0.5 | 6 |
| local_wake_total_states | 9.692e+05 | 7.035e+05 | 9.021e+05 | 6 |
| local_wake_seconds | 47.03 | 42.81 | 41.22 | 6 |
| local_sleep_seconds | 0.0006382 | 0.0004952 | 0.0006787 | 6 |
| states_ratio | 159.6 | 1 | 325.1 | 6 |
| time_ratio | 78.5 | 1.001 | 155.2 | 6 |
| first_states_ratio | 476.9 | 476.9 | 407.4 | 2 |
| total_states_ratio | 0.399 | 0.3659 | 0.1822 | 6 |
| states_ratio (geomean) | 6.28 | | | |
| first_states_ratio (geomean) | 248 | | | |
| time_ratio (geomean) | 5.06 | | | |
| total_states_ratio incl. wake (geomean) | 0.363 | | | |

### Per-task table

| task | status | pairs | base states | base first | base L | tsl states | tsl first | tsl L | L(expanded) | wake states | #A | used | L(A) | MDL | states ratio | time ratio |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 25ff71a9 | SOLVED | 4 | 7370 | 7370 | 6 | 106 | 106 | 2 | 6 | 18388 | 1 | 1 | 7 | 9 | 69.5 | 43.3 |
| a79310a0 | SOLVED | 3 | 93743 | 93743 | 8 | 106 | 106 | 2 | 8 | 207071 | 1 | 1 | 9 | 11 | 884 | 424 |
| bb43febb | NO_PAIRWISE_SOLUTION | 2 | 600000 |  |  | 600000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 0.958 |
| 5521c0d9 | NO_PAIRWISE_SOLUTION | 3 | 600000 |  |  | 600000 |  |  |  | 1800000 | 0 | 0 | 0 |  | 1 | 0.952 |
| 67385a82 | NO_PAIRWISE_SOLUTION | 4 | 600000 |  |  | 600000 |  |  |  | 2400000 | 0 | 0 | 0 |  | 1 | 1.02 |
| 63613498 | NO_SHARED_PROGRAM | 3 | 600000 |  |  | 600000 |  |  |  | 189729 | 1 | 0 | 8 |  | 1 | 0.983 |

## Condition: reweight

- tasks: 6 (in scope: 6); status counts: {'SOLVED': 2, 'NO_PAIRWISE_SOLUTION': 3, 'NO_SHARED_PROGRAM': 1}
- solve rate (all): baseline 0.333 vs reweight 0.333
- solve rate (in scope): baseline 0.333 vs reweight 0.333
- solved by baseline only: []; by reweight only: []
- tasks with >=1 abstraction: 0; solved using an abstraction: 0 (of which whole-program abstractions: 0)

### solved_only (n=2)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 5.056e+04 | 5.056e+04 | 4.319e+04 | 2 |
| tsl_expanded_states | 2135 | 2135 | 1744 | 2 |
| baseline_first_solution_states | 5.056e+04 | 5.056e+04 | 4.319e+04 | 2 |
| tsl_first_solution_states | 2135 | 2135 | 1744 | 2 |
| baseline_first_solution_nodes | 51 | 51 | 48 | 2 |
| tsl_first_solution_nodes | 9.5 | 9.5 | 7.5 | 2 |
| baseline_search_seconds | 1.1 | 1.1 | 0.9092 | 2 |
| tsl_search_seconds | 0.0806 | 0.0806 | 0.05615 | 2 |
| baseline_program_length | 7 | 7 | 1 | 2 |
| tsl_program_length | 7 | 7 | 1 | 2 |
| tsl_expanded_program_length | 7 | 7 | 1 | 2 |
| tsl_description_length | 0 | 0 | 0 | 2 |
| total_mdl | 7 | 7 | 1 | 2 |
| tsl_num_abstractions | 0 | 0 | 0 | 2 |
| local_wake_total_states | 1.127e+05 | 1.127e+05 | 9.434e+04 | 2 |
| local_wake_seconds | 1.406 | 1.406 | 1.18 | 2 |
| local_sleep_seconds | 8.255e-05 | 8.255e-05 | 1.053e-06 | 2 |
| states_ratio | 21.51 | 21.51 | 2.659 | 2 |
| time_ratio | 11.24 | 11.24 | 3.451 | 2 |
| first_states_ratio | 21.51 | 21.51 | 2.659 | 2 |
| total_states_ratio | 0.4184 | 0.4184 | 0.02596 | 2 |
| states_ratio (geomean) | 21.3 | | | |
| first_states_ratio (geomean) | 21.3 | | | |
| time_ratio (geomean) | 10.7 | | | |
| total_states_ratio incl. wake (geomean) | 0.418 | | | |

### solved_only_nontrivial_abstraction (n=0)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| states_ratio (geomean) |  | | | |
| first_states_ratio (geomean) |  | | | |
| time_ratio (geomean) |  | | | |
| total_states_ratio incl. wake (geomean) |  | | | |

### all_tasks (n=6)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 4.169e+05 | 6e+05 | 2.602e+05 | 6 |
| tsl_expanded_states | 3.329e+05 | 3.965e+05 | 2.746e+05 | 6 |
| baseline_first_solution_states | 5.056e+04 | 5.056e+04 | 4.319e+04 | 2 |
| tsl_first_solution_states | 2135 | 2135 | 1744 | 2 |
| baseline_first_solution_nodes | 51 | 51 | 48 | 2 |
| tsl_first_solution_nodes | 9.5 | 9.5 | 7.5 | 2 |
| baseline_search_seconds | 75.94 | 50.35 | 86.33 | 6 |
| tsl_search_seconds | 48.98 | 50.82 | 39.54 | 6 |
| baseline_program_length | 7 | 7 | 1 | 2 |
| tsl_program_length | 7 | 7 | 1 | 2 |
| tsl_expanded_program_length | 7 | 7 | 1 | 2 |
| tsl_description_length | 0 | 0 | 0 | 6 |
| total_mdl | 7 | 7 | 1 | 2 |
| tsl_num_abstractions | 0 | 0 | 0 | 6 |
| local_wake_total_states | 9.692e+05 | 7.035e+05 | 9.021e+05 | 6 |
| local_wake_seconds | 47.03 | 42.81 | 41.22 | 6 |
| local_sleep_seconds | 4.268e-05 | 4.129e-05 | 4.189e-05 | 6 |
| states_ratio | 8.187 | 2.054 | 9.572 | 6 |
| time_ratio | 4.715 | 1.95 | 5.071 | 6 |
| first_states_ratio | 21.51 | 21.51 | 2.659 | 2 |
| total_states_ratio | 0.5313 | 0.3629 | 0.4706 | 6 |
| states_ratio (geomean) | 3.35 | | | |
| first_states_ratio (geomean) | 21.3 | | | |
| time_ratio (geomean) | 2.6 | | | |
| total_states_ratio incl. wake (geomean) | 0.407 | | | |

### Per-task table

| task | status | pairs | base states | base first | base L | tsl states | tsl first | tsl L | L(expanded) | wake states | #A | used | L(A) | MDL | states ratio | time ratio |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 25ff71a9 | SOLVED | 4 | 7370 | 7370 | 6 | 391 | 391 | 6 | 6 | 18388 | 0 | 0 | 0 | 6 | 18.8 | 7.79 |
| a79310a0 | SOLVED | 3 | 93743 | 93743 | 8 | 3879 | 3879 | 8 | 8 | 207071 | 0 | 0 | 0 | 8 | 24.2 | 14.7 |
| bb43febb | NO_PAIRWISE_SOLUTION | 2 | 600000 |  |  | 600000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 0.958 |
| 5521c0d9 | NO_PAIRWISE_SOLUTION | 3 | 600000 |  |  | 600000 |  |  |  | 1800000 | 0 | 0 | 0 |  | 1 | 0.952 |
| 67385a82 | NO_PAIRWISE_SOLUTION | 4 | 600000 |  |  | 600000 |  |  |  | 2400000 | 0 | 0 | 0 |  | 1 | 1.02 |
| 63613498 | NO_SHARED_PROGRAM | 3 | 600000 |  |  | 193050 |  |  |  | 189729 | 0 | 0 | 0 |  | 3.11 | 2.88 |

## Condition: tsl_reweight

- tasks: 6 (in scope: 6); status counts: {'SOLVED': 2, 'NO_PAIRWISE_SOLUTION': 3, 'NO_SHARED_PROGRAM': 1}
- solve rate (all): baseline 0.333 vs tsl_reweight 0.333
- solve rate (in scope): baseline 0.333 vs tsl_reweight 0.333
- solved by baseline only: []; by tsl_reweight only: []
- tasks with >=1 abstraction: 3; solved using an abstraction: 2 (of which whole-program abstractions: 2)

### solved_only (n=2)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 5.056e+04 | 5.056e+04 | 4.319e+04 | 2 |
| tsl_expanded_states | 7 | 7 | 0 | 2 |
| baseline_first_solution_states | 5.056e+04 | 5.056e+04 | 4.319e+04 | 2 |
| tsl_first_solution_states | 7 | 7 | 0 | 2 |
| baseline_first_solution_nodes | 51 | 51 | 48 | 2 |
| tsl_first_solution_nodes | 2 | 2 | 0 | 2 |
| baseline_search_seconds | 1.1 | 1.1 | 0.9092 | 2 |
| tsl_search_seconds | 0.005504 | 0.005504 | 0.001672 | 2 |
| baseline_program_length | 7 | 7 | 1 | 2 |
| tsl_program_length | 2 | 2 | 0 | 2 |
| tsl_expanded_program_length | 7 | 7 | 1 | 2 |
| tsl_description_length | 8 | 8 | 1 | 2 |
| total_mdl | 10 | 10 | 1 | 2 |
| tsl_num_abstractions | 1 | 1 | 0 | 2 |
| local_wake_total_states | 1.127e+05 | 1.127e+05 | 9.434e+04 | 2 |
| local_wake_seconds | 1.406 | 1.406 | 1.18 | 2 |
| local_sleep_seconds | 0.001083 | 0.001083 | 0.000283 | 2 |
| states_ratio | 7222 | 7222 | 6170 | 2 |
| time_ratio | 164.8 | 164.8 | 115.1 | 2 |
| first_states_ratio | 7222 | 7222 | 6170 | 2 |
| total_states_ratio | 0.4267 | 0.4267 | 0.02602 | 2 |
| states_ratio (geomean) | 3.75e+03 | | | |
| first_states_ratio (geomean) | 3.75e+03 | | | |
| time_ratio (geomean) | 118 | | | |
| total_states_ratio incl. wake (geomean) | 0.426 | | | |

### solved_only_nontrivial_abstraction (n=0)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| states_ratio (geomean) |  | | | |
| first_states_ratio (geomean) |  | | | |
| time_ratio (geomean) |  | | | |
| total_states_ratio incl. wake (geomean) |  | | | |

### all_tasks (n=6)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 4.169e+05 | 6e+05 | 2.602e+05 | 6 |
| tsl_expanded_states | 3.148e+05 | 3.443e+05 | 2.868e+05 | 6 |
| baseline_first_solution_states | 5.056e+04 | 5.056e+04 | 4.319e+04 | 2 |
| tsl_first_solution_states | 7 | 7 | 0 | 2 |
| baseline_first_solution_nodes | 51 | 51 | 48 | 2 |
| tsl_first_solution_nodes | 2 | 2 | 0 | 2 |
| baseline_search_seconds | 75.94 | 50.35 | 86.33 | 6 |
| tsl_search_seconds | 43.81 | 50.82 | 36.01 | 6 |
| baseline_program_length | 7 | 7 | 1 | 2 |
| tsl_program_length | 2 | 2 | 0 | 2 |
| tsl_expanded_program_length | 7 | 7 | 1 | 2 |
| tsl_description_length | 4 | 3.5 | 4.041 | 6 |
| total_mdl | 10 | 10 | 1 | 2 |
| tsl_num_abstractions | 0.5 | 0.5 | 0.5 | 6 |
| local_wake_total_states | 9.692e+05 | 7.035e+05 | 9.021e+05 | 6 |
| local_wake_seconds | 47.03 | 42.81 | 41.22 | 6 |
| local_sleep_seconds | 0.0006249 | 0.0004003 | 0.0006664 | 6 |
| states_ratio | 2409 | 3.89 | 4927 | 6 |
| time_ratio | 56.17 | 2.728 | 101.6 | 6 |
| first_states_ratio | 7222 | 7222 | 6170 | 2 |
| total_states_ratio | 0.6322 | 0.367 | 0.6869 | 6 |
| states_ratio (geomean) | 21.4 | | | |
| first_states_ratio (geomean) | 3.75e+03 | | | |
| time_ratio (geomean) | 6.21 | | | |
| total_states_ratio incl. wake (geomean) | 0.432 | | | |

### Per-task table

| task | status | pairs | base states | base first | base L | tsl states | tsl first | tsl L | L(expanded) | wake states | #A | used | L(A) | MDL | states ratio | time ratio |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 25ff71a9 | SOLVED | 4 | 7370 | 7370 | 6 | 7 | 7 | 2 | 6 | 18388 | 1 | 1 | 7 | 9 | 1.05e+03 | 49.7 |
| a79310a0 | SOLVED | 3 | 93743 | 93743 | 8 | 7 | 7 | 2 | 8 | 207071 | 1 | 1 | 9 | 11 | 1.34e+04 | 280 |
| bb43febb | NO_PAIRWISE_SOLUTION | 2 | 600000 |  |  | 600000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 0.958 |
| 5521c0d9 | NO_PAIRWISE_SOLUTION | 3 | 600000 |  |  | 600000 |  |  |  | 1800000 | 0 | 0 | 0 |  | 1 | 0.952 |
| 67385a82 | NO_PAIRWISE_SOLUTION | 4 | 600000 |  |  | 600000 |  |  |  | 2400000 | 0 | 0 | 0 |  | 1 | 1.02 |
| 63613498 | NO_SHARED_PROGRAM | 3 | 600000 |  |  | 88508 |  |  |  | 189729 | 1 | 0 | 8 |  | 6.78 | 4.44 |
