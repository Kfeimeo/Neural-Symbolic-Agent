# Fixed-DSL baseline vs task-specific TSL

## Condition: tsl

- tasks: 10 (in scope: 10); status counts: {'NO_PAIRWISE_SOLUTION': 10}
- solve rate (all): baseline 0.000 vs tsl 0.000
- solve rate (in scope): baseline 0.000 vs tsl 0.000
- solved by baseline only: []; by tsl only: []
- tasks with >=1 abstraction: 0; solved using an abstraction: 0 (of which whole-program abstractions: 0)

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

### all_tasks (n=10)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 2.218e+05 | 2.824e+05 | 9.149e+04 | 10 |
| tsl_expanded_states | 2.282e+05 | 2.847e+05 | 8.566e+04 | 10 |
| baseline_search_seconds | 42.08 | 49.35 | 20.71 | 10 |
| tsl_search_seconds | 41.32 | 47.81 | 20.88 | 10 |
| tsl_description_length | 0 | 0 | 0 | 10 |
| tsl_num_abstractions | 0 | 0 | 0 | 10 |
| local_wake_total_states | 1.034e+06 | 9e+05 | 6.091e+05 | 10 |
| local_wake_seconds | 81.6 | 70.89 | 55.15 | 10 |
| local_sleep_seconds | 5.574e-05 | 7.125e-07 | 0.000165 | 10 |
| states_ratio | 0.9577 | 1 | 0.08995 | 10 |
| time_ratio | 1.014 | 1.004 | 0.08353 | 10 |
| total_states_ratio | 0.1826 | 0.168 | 0.05861 | 10 |
| states_ratio (geomean) | 0.953 | | | |
| first_states_ratio (geomean) |  | | | |
| time_ratio (geomean) | 1.01 | | | |
| total_states_ratio incl. wake (geomean) | 0.173 | | | |

### Per-task table

| task | status | pairs | base states | base first | base L | tsl states | tsl first | tsl L | L(expanded) | wake states | #A | used | L(A) | MDL | states ratio | time ratio |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 67a423a3 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.917 |
| f15e1fac | NO_PAIRWISE_SOLUTION | 3 | 143872 |  |  | 178176 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.807 | 0.979 |
| 05269061 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.862 |
| 045e512c | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.08 |
| 2dd70a9a | NO_PAIRWISE_SOLUTION | 3 | 71680 |  |  | 71680 |  |  |  | 524256 | 0 | 0 | 0 |  | 1 | 0.995 |
| 2bee17df | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.15 |
| 1f876c06 | NO_PAIRWISE_SOLUTION | 3 | 146944 |  |  | 142336 |  |  |  | 800736 | 0 | 0 | 0 |  | 1.03 | 1.01 |
| 794b24be | NO_PAIRWISE_SOLUTION | 10 | 300000 |  |  | 300000 |  |  |  | 2774986 | 0 | 0 | 0 |  | 1 | 1.13 |
| b527c5c6 | NO_PAIRWISE_SOLUTION | 4 | 264704 |  |  | 269312 |  |  |  | 1200000 | 0 | 0 | 0 |  | 0.983 | 1 |
| 7e0986d6 | NO_PAIRWISE_SOLUTION | 2 | 91136 |  |  | 120832 |  |  |  | 536064 | 0 | 0 | 0 |  | 0.754 | 1.02 |

## Condition: reweight

- tasks: 10 (in scope: 10); status counts: {'NO_PAIRWISE_SOLUTION': 10}
- solve rate (all): baseline 0.000 vs reweight 0.000
- solve rate (in scope): baseline 0.000 vs reweight 0.000
- solved by baseline only: []; by reweight only: []
- tasks with >=1 abstraction: 0; solved using an abstraction: 0 (of which whole-program abstractions: 0)

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

### all_tasks (n=10)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 2.218e+05 | 2.824e+05 | 9.149e+04 | 10 |
| tsl_expanded_states | 2.079e+05 | 2.237e+05 | 9.023e+04 | 10 |
| baseline_search_seconds | 42.08 | 49.35 | 20.71 | 10 |
| tsl_search_seconds | 39.88 | 47.81 | 22.44 | 10 |
| tsl_description_length | 0 | 0 | 0 | 10 |
| tsl_num_abstractions | 0 | 0 | 0 | 10 |
| local_wake_total_states | 1.034e+06 | 9e+05 | 6.091e+05 | 10 |
| local_wake_seconds | 81.6 | 70.89 | 55.15 | 10 |
| local_sleep_seconds | 1.547e-05 | 6.645e-07 | 4.444e-05 | 10 |
| states_ratio | 1.168 | 1 | 0.6519 | 10 |
| time_ratio | 1.176 | 1.004 | 0.5288 | 10 |
| total_states_ratio | 0.1833 | 0.168 | 0.05764 | 10 |
| states_ratio (geomean) | 1.07 | | | |
| first_states_ratio (geomean) |  | | | |
| time_ratio (geomean) | 1.1 | | | |
| total_states_ratio incl. wake (geomean) | 0.174 | | | |

### Per-task table

| task | status | pairs | base states | base first | base L | tsl states | tsl first | tsl L | L(expanded) | wake states | #A | used | L(A) | MDL | states ratio | time ratio |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 67a423a3 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.917 |
| f15e1fac | NO_PAIRWISE_SOLUTION | 3 | 143872 |  |  | 178176 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.807 | 0.979 |
| 05269061 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.862 |
| 045e512c | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.08 |
| 2dd70a9a | NO_PAIRWISE_SOLUTION | 3 | 71680 |  |  | 71680 |  |  |  | 524256 | 0 | 0 | 0 |  | 1 | 0.995 |
| 2bee17df | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.15 |
| 1f876c06 | NO_PAIRWISE_SOLUTION | 3 | 146944 |  |  | 142336 |  |  |  | 800736 | 0 | 0 | 0 |  | 1.03 | 1.01 |
| 794b24be | NO_PAIRWISE_SOLUTION | 10 | 300000 |  |  | 96594 |  |  |  | 2774986 | 0 | 0 | 0 |  | 3.11 | 2.75 |
| b527c5c6 | NO_PAIRWISE_SOLUTION | 4 | 264704 |  |  | 269312 |  |  |  | 1200000 | 0 | 0 | 0 |  | 0.983 | 1 |
| 7e0986d6 | NO_PAIRWISE_SOLUTION | 2 | 91136 |  |  | 120832 |  |  |  | 536064 | 0 | 0 | 0 |  | 0.754 | 1.02 |

## Condition: tsl_reweight

- tasks: 10 (in scope: 10); status counts: {'NO_PAIRWISE_SOLUTION': 10}
- solve rate (all): baseline 0.000 vs tsl_reweight 0.000
- solve rate (in scope): baseline 0.000 vs tsl_reweight 0.000
- solved by baseline only: []; by tsl_reweight only: []
- tasks with >=1 abstraction: 0; solved using an abstraction: 0 (of which whole-program abstractions: 0)

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

### all_tasks (n=10)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 2.218e+05 | 2.824e+05 | 9.149e+04 | 10 |
| tsl_expanded_states | 2.079e+05 | 2.237e+05 | 9.023e+04 | 10 |
| baseline_search_seconds | 42.08 | 49.35 | 20.71 | 10 |
| tsl_search_seconds | 39.88 | 47.81 | 22.44 | 10 |
| tsl_description_length | 0 | 0 | 0 | 10 |
| tsl_num_abstractions | 0 | 0 | 0 | 10 |
| local_wake_total_states | 1.034e+06 | 9e+05 | 6.091e+05 | 10 |
| local_wake_seconds | 81.6 | 70.89 | 55.15 | 10 |
| local_sleep_seconds | 4.617e-05 | 5.245e-07 | 0.0001369 | 10 |
| states_ratio | 1.168 | 1 | 0.6519 | 10 |
| time_ratio | 1.176 | 1.004 | 0.5288 | 10 |
| total_states_ratio | 0.1833 | 0.168 | 0.05764 | 10 |
| states_ratio (geomean) | 1.07 | | | |
| first_states_ratio (geomean) |  | | | |
| time_ratio (geomean) | 1.1 | | | |
| total_states_ratio incl. wake (geomean) | 0.174 | | | |

### Per-task table

| task | status | pairs | base states | base first | base L | tsl states | tsl first | tsl L | L(expanded) | wake states | #A | used | L(A) | MDL | states ratio | time ratio |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 67a423a3 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.917 |
| f15e1fac | NO_PAIRWISE_SOLUTION | 3 | 143872 |  |  | 178176 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.807 | 0.979 |
| 05269061 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.862 |
| 045e512c | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.08 |
| 2dd70a9a | NO_PAIRWISE_SOLUTION | 3 | 71680 |  |  | 71680 |  |  |  | 524256 | 0 | 0 | 0 |  | 1 | 0.995 |
| 2bee17df | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.15 |
| 1f876c06 | NO_PAIRWISE_SOLUTION | 3 | 146944 |  |  | 142336 |  |  |  | 800736 | 0 | 0 | 0 |  | 1.03 | 1.01 |
| 794b24be | NO_PAIRWISE_SOLUTION | 10 | 300000 |  |  | 96594 |  |  |  | 2774986 | 0 | 0 | 0 |  | 3.11 | 2.75 |
| b527c5c6 | NO_PAIRWISE_SOLUTION | 4 | 264704 |  |  | 269312 |  |  |  | 1200000 | 0 | 0 | 0 |  | 0.983 | 1 |
| 7e0986d6 | NO_PAIRWISE_SOLUTION | 2 | 91136 |  |  | 120832 |  |  |  | 536064 | 0 | 0 | 0 |  | 0.754 | 1.02 |
