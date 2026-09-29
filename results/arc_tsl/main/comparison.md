# Fixed-DSL baseline vs task-specific TSL

## Condition: tsl

- tasks: 130 (in scope: 130); status counts: {'NO_PAIRWISE_SOLUTION': 127, 'SOLVED': 2, 'NO_SHARED_PROGRAM': 1}
- solve rate (all): baseline 0.015 vs tsl 0.015
- solve rate (in scope): baseline 0.015 vs tsl 0.015
- solved by baseline only: []; by tsl only: []
- tasks with >=1 abstraction: 3; solved using an abstraction: 2 (of which whole-program abstractions: 1)

### solved_only (n=2)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 2.441e+04 | 2.441e+04 | 1.784e+04 | 2 |
| tsl_expanded_states | 134 | 134 | 28 | 2 |
| baseline_first_solution_states | 2.441e+04 | 2.441e+04 | 1.784e+04 | 2 |
| tsl_first_solution_states | 134 | 134 | 28 | 2 |
| baseline_first_solution_nodes | 19 | 19 | 12 | 2 |
| tsl_first_solution_nodes | 2 | 2 | 0 | 2 |
| baseline_search_seconds | 2.366 | 2.366 | 2.224 | 2 |
| tsl_search_seconds | 0.007717 | 0.007717 | 0.003205 | 2 |
| baseline_program_length | 6.5 | 6.5 | 0.5 | 2 |
| tsl_program_length | 2.5 | 2.5 | 0.5 | 2 |
| tsl_expanded_program_length | 6.5 | 6.5 | 0.5 | 2 |
| tsl_description_length | 6.5 | 6.5 | 0.5 | 2 |
| total_mdl | 9 | 9 | 0 | 2 |
| tsl_num_abstractions | 1 | 1 | 0 | 2 |
| local_wake_total_states | 4.976e+04 | 4.976e+04 | 2.883e+04 | 2 |
| local_wake_seconds | 2.753 | 2.753 | 2.5 | 2 |
| local_sleep_seconds | 0.0008317 | 0.0008317 | 4.629e-05 | 2 |
| states_ratio | 161.4 | 161.4 | 99.38 | 2 |
| time_ratio | 225.8 | 225.8 | 194.5 | 2 |
| first_states_ratio | 161.4 | 161.4 | 99.38 | 2 |
| total_states_ratio | 0.4243 | 0.4243 | 0.1121 | 2 |
| states_ratio (geomean) | 127 | | | |
| first_states_ratio (geomean) | 127 | | | |
| time_ratio (geomean) | 115 | | | |
| total_states_ratio incl. wake (geomean) | 0.409 | | | |

### solved_only_nontrivial_abstraction (n=1)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 4.224e+04 | 4.224e+04 | 0 | 1 |
| tsl_expanded_states | 162 | 162 | 0 | 1 |
| baseline_first_solution_states | 4.224e+04 | 4.224e+04 | 0 | 1 |
| tsl_first_solution_states | 162 | 162 | 0 | 1 |
| baseline_first_solution_nodes | 31 | 31 | 0 | 1 |
| tsl_first_solution_nodes | 2 | 2 | 0 | 1 |
| baseline_search_seconds | 4.591 | 4.591 | 0 | 1 |
| tsl_search_seconds | 0.01092 | 0.01092 | 0 | 1 |
| baseline_program_length | 7 | 7 | 0 | 1 |
| tsl_program_length | 3 | 3 | 0 | 1 |
| tsl_expanded_program_length | 7 | 7 | 0 | 1 |
| tsl_description_length | 6 | 6 | 0 | 1 |
| total_mdl | 9 | 9 | 0 | 1 |
| tsl_num_abstractions | 1 | 1 | 0 | 1 |
| local_wake_total_states | 7.859e+04 | 7.859e+04 | 0 | 1 |
| local_wake_seconds | 5.253 | 5.253 | 0 | 1 |
| local_sleep_seconds | 0.0007854 | 0.0007854 | 0 | 1 |
| states_ratio | 260.7 | 260.7 | 0 | 1 |
| time_ratio | 420.3 | 420.3 | 0 | 1 |
| first_states_ratio | 260.7 | 260.7 | 0 | 1 |
| total_states_ratio | 0.5364 | 0.5364 | 0 | 1 |
| states_ratio (geomean) | 261 | | | |
| first_states_ratio (geomean) | 261 | | | |
| time_ratio (geomean) | 420 | | | |
| total_states_ratio incl. wake (geomean) | 0.536 | | | |

### all_tasks (n=130)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 1.773e+05 | 1.654e+05 | 1.127e+05 | 130 |
| tsl_expanded_states | 1.774e+05 | 1.725e+05 | 1.133e+05 | 130 |
| baseline_first_solution_states | 2.441e+04 | 2.441e+04 | 1.784e+04 | 2 |
| tsl_first_solution_states | 134 | 134 | 28 | 2 |
| baseline_first_solution_nodes | 19 | 19 | 12 | 2 |
| tsl_first_solution_nodes | 2 | 2 | 0 | 2 |
| baseline_search_seconds | 24.39 | 30.04 | 9.891 | 130 |
| tsl_search_seconds | 24.07 | 30.03 | 10.04 | 130 |
| baseline_program_length | 6.5 | 6.5 | 0.5 | 2 |
| tsl_program_length | 2.5 | 2.5 | 0.5 | 2 |
| tsl_expanded_program_length | 6.5 | 6.5 | 0.5 | 2 |
| tsl_description_length | 0.1615 | 0 | 1.058 | 130 |
| total_mdl | 9 | 9 | 0 | 2 |
| tsl_num_abstractions | 0.02308 | 0 | 0.1501 | 130 |
| local_wake_total_states | 6.37e+05 | 6e+05 | 3.835e+05 | 130 |
| local_wake_seconds | 41.77 | 40.65 | 21.8 | 130 |
| local_sleep_seconds | 4.82e-05 | 8.205e-07 | 0.0001985 | 130 |
| states_ratio | 3.465 | 1 | 23.27 | 130 |
| time_ratio | 4.48 | 1.003 | 36.71 | 130 |
| first_states_ratio | 161.4 | 161.4 | 99.38 | 2 |
| total_states_ratio | 0.2183 | 0.2237 | 0.07706 | 130 |
| states_ratio (geomean) | 1.07 | | | |
| first_states_ratio (geomean) | 127 | | | |
| time_ratio (geomean) | 1.09 | | | |
| total_states_ratio incl. wake (geomean) | 0.202 | | | |

### Per-task table

| task | status | pairs | base states | base first | base L | tsl states | tsl first | tsl L | L(expanded) | wake states | #A | used | L(A) | MDL | states ratio | time ratio |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 67a423a3 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.978 |
| f15e1fac | NO_PAIRWISE_SOLUTION | 3 | 102400 |  |  | 101888 |  |  |  | 493568 | 0 | 0 | 0 |  | 1.01 | 1.01 |
| 05269061 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1 |
| 045e512c | NO_PAIRWISE_SOLUTION | 3 | 205312 |  |  | 198144 |  |  |  | 771040 | 0 | 0 | 0 |  | 1.04 | 1 |
| 2dd70a9a | NO_PAIRWISE_SOLUTION | 3 | 38912 |  |  | 38912 |  |  |  | 157696 | 0 | 0 | 0 |  | 1 | 1.06 |
| 2bee17df | NO_PAIRWISE_SOLUTION | 3 | 256512 |  |  | 269824 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.951 | 1 |
| 1f876c06 | NO_PAIRWISE_SOLUTION | 3 | 74240 |  |  | 94720 |  |  |  | 320000 | 0 | 0 | 0 |  | 0.784 | 0.982 |
| 794b24be | NO_PAIRWISE_SOLUTION | 10 | 294400 |  |  | 300000 |  |  |  | 2764118 | 0 | 0 | 0 |  | 0.981 | 1.11 |
| b527c5c6 | NO_PAIRWISE_SOLUTION | 4 | 88064 |  |  | 89088 |  |  |  | 866784 | 0 | 0 | 0 |  | 0.989 | 1.03 |
| 7e0986d6 | NO_PAIRWISE_SOLUTION | 2 | 40960 |  |  | 41472 |  |  |  | 105984 | 0 | 0 | 0 |  | 0.988 | 1.02 |
| 321b1fc6 | NO_PAIRWISE_SOLUTION | 2 | 210432 |  |  | 209408 |  |  |  | 557024 | 0 | 0 | 0 |  | 1 | 0.997 |
| ce9e57f2 | NO_PAIRWISE_SOLUTION | 3 | 101888 |  |  | 102400 |  |  |  | 623616 | 0 | 0 | 0 |  | 0.995 | 0.986 |
| 1caeab9d | NO_PAIRWISE_SOLUTION | 3 | 208384 |  |  | 227840 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.915 | 1 |
| 444801d8 | NO_PAIRWISE_SOLUTION | 3 | 278016 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.927 | 1.04 |
| 150deff5 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.903 |
| 6e19193c | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1 |
| a3df8b1e | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.51 |
| 32597951 | NO_PAIRWISE_SOLUTION | 3 | 33280 |  |  | 35840 |  |  |  | 228352 | 0 | 0 | 0 |  | 0.929 | 0.999 |
| 928ad970 | NO_PAIRWISE_SOLUTION | 3 | 116736 |  |  | 114688 |  |  |  | 436736 | 0 | 0 | 0 |  | 1.02 | 0.97 |
| f1cefba8 | NO_PAIRWISE_SOLUTION | 3 | 156672 |  |  | 157184 |  |  |  | 592864 | 0 | 0 | 0 |  | 0.997 | 0.991 |
| db3e9e38 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 0.962 |
| ddf7fa4f | NO_PAIRWISE_SOLUTION | 3 | 77312 |  |  | 58880 |  |  |  | 437760 | 0 | 0 | 0 |  | 1.31 | 1.01 |
| dbc1a6ce | NO_PAIRWISE_SOLUTION | 4 | 66560 |  |  | 78336 |  |  |  | 288768 | 0 | 0 | 0 |  | 0.85 | 0.994 |
| 272f95fa | NO_PAIRWISE_SOLUTION | 2 | 202752 |  |  | 201728 |  |  |  | 546784 | 0 | 0 | 0 |  | 1.01 | 0.992 |
| 6855a6e4 | NO_PAIRWISE_SOLUTION | 3 | 129024 |  |  | 137216 |  |  |  | 492032 | 0 | 0 | 0 |  | 0.94 | 0.998 |
| 97999447 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.05 |
| 54d82841 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.05 |
| e26a3af2 | NO_PAIRWISE_SOLUTION | 3 | 92160 |  |  | 92160 |  |  |  | 463360 | 0 | 0 | 0 |  | 1 | 0.997 |
| b782dc8a | NO_PAIRWISE_SOLUTION | 2 | 46080 |  |  | 46080 |  |  |  | 170496 | 0 | 0 | 0 |  | 1 | 1 |
| 44d8ac46 | NO_PAIRWISE_SOLUTION | 4 | 133632 |  |  | 128000 |  |  |  | 478829 | 0 | 0 | 0 |  | 1.04 | 1.02 |
| ba97ae07 | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 0.986 |
| 760b3cac | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.02 |
| 4c5c2cf0 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.02 |
| c0f76784 | NO_PAIRWISE_SOLUTION | 3 | 140288 |  |  | 148480 |  |  |  | 725984 | 0 | 0 | 0 |  | 0.945 | 0.997 |
| 67385a82 | NO_PAIRWISE_SOLUTION | 4 | 267776 |  |  | 237056 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1.13 | 1 |
| 810b9b61 | NO_PAIRWISE_SOLUTION | 3 | 57344 |  |  | 56832 |  |  |  | 474478 | 0 | 0 | 0 |  | 1.01 | 1 |
| a78176bb | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.02 |
| f25ffba3 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.11 |
| a699fb00 | NO_PAIRWISE_SOLUTION | 3 | 68096 |  |  | 68608 |  |  |  | 420320 | 0 | 0 | 0 |  | 0.993 | 1.02 |
| b8cdaf2b | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 0.995 |
| a8d7556c | NO_PAIRWISE_SOLUTION | 3 | 15872 |  |  | 20480 |  |  |  | 141824 | 0 | 0 | 0 |  | 0.775 | 1.01 |
| bb43febb | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 0.966 |
| e73095fd | NO_PAIRWISE_SOLUTION | 3 | 171520 |  |  | 181248 |  |  |  | 811488 | 0 | 0 | 0 |  | 0.946 | 1 |
| b60334d2 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 298496 |  |  |  | 591840 | 0 | 0 | 0 |  | 1.01 | 0.993 |
| d2abd087 | NO_PAIRWISE_SOLUTION | 3 | 75776 |  |  | 59904 |  |  |  | 521696 | 0 | 0 | 0 |  | 1.26 | 0.995 |
| 29623171 | NO_PAIRWISE_SOLUTION | 3 | 43520 |  |  | 44032 |  |  |  | 327168 | 0 | 0 | 0 |  | 0.988 | 1.01 |
| d5d6de2d | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.03 |
| 941d9a10 | NO_PAIRWISE_SOLUTION | 3 | 289280 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.964 | 1.03 |
| d6ad076f | NO_PAIRWISE_SOLUTION | 3 | 234496 |  |  | 241152 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.972 | 1.04 |
| 6cdd2623 | NO_PAIRWISE_SOLUTION | 3 | 43008 |  |  | 43520 |  |  |  | 100352 | 0 | 0 | 0 |  | 0.988 | 1.01 |
| 1b60fb0c | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.03 |
| d4f3cd78 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.06 |
| e8dc4411 | NO_PAIRWISE_SOLUTION | 3 | 91136 |  |  | 104448 |  |  |  | 442880 | 0 | 0 | 0 |  | 0.873 | 1.01 |
| d23f8c26 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.907 |
| 3bdb4ada | NO_PAIRWISE_SOLUTION | 2 | 158720 |  |  | 159232 |  |  |  | 430592 | 0 | 0 | 0 |  | 0.997 | 1 |
| 88a10436 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.995 |
| 41e4d17e | NO_PAIRWISE_SOLUTION | 2 | 68608 |  |  | 68608 |  |  |  | 233472 | 0 | 0 | 0 |  | 1 | 1.11 |
| 508bd3b6 | NO_PAIRWISE_SOLUTION | 3 | 247808 |  |  | 241664 |  |  |  | 900000 | 0 | 0 | 0 |  | 1.03 | 1 |
| 3aa6fb7a | SOLVED | 2 | 42241 | 42241 | 7 | 162 | 162 | 3 | 7 | 78587 | 1 | 1 | 6 | 9 | 261 | 420 |
| ea786f4a | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.03 |
| 29ec7d0e | NO_PAIRWISE_SOLUTION | 4 | 30720 |  |  | 32768 |  |  |  | 356864 | 0 | 0 | 0 |  | 0.938 | 0.932 |
| a9f96cdd | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 1.01 |
| 3e980e27 | NO_PAIRWISE_SOLUTION | 4 | 160256 |  |  | 159232 |  |  |  | 983488 | 0 | 0 | 0 |  | 1.01 | 1 |
| c1d99e64 | NO_PAIRWISE_SOLUTION | 3 | 27648 |  |  | 27648 |  |  |  | 152064 | 0 | 0 | 0 |  | 1 | 1.01 |
| 913fb3ed | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 633864 | 0 | 0 | 0 |  | 1 | 1.08 |
| 9565186b | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 917448 | 0 | 0 | 0 |  | 1 | 1.01 |
| 93b581b8 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.958 |
| 5168d44c | NO_PAIRWISE_SOLUTION | 3 | 146432 |  |  | 144896 |  |  |  | 627168 | 0 | 0 | 0 |  | 1.01 | 0.998 |
| 5521c0d9 | NO_PAIRWISE_SOLUTION | 3 | 150528 |  |  | 147456 |  |  |  | 809920 | 0 | 0 | 0 |  | 1.02 | 0.992 |
| 31aa019c | NO_PAIRWISE_SOLUTION | 3 | 53760 |  |  | 49664 |  |  |  | 182784 | 0 | 0 | 0 |  | 1.08 | 0.988 |
| 484b58aa | NO_PAIRWISE_SOLUTION | 3 | 10240 |  |  | 10240 |  |  |  | 44032 | 0 | 0 | 0 |  | 1 | 1.01 |
| 6d58a25d | NO_PAIRWISE_SOLUTION | 3 | 49664 |  |  | 43008 |  |  |  | 121856 | 0 | 0 | 0 |  | 1.15 | 1.08 |
| 8403a5d5 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.37 |
| 1bfc4729 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.23 |
| c3f564a4 | NO_PAIRWISE_SOLUTION | 3 | 76288 |  |  | 64512 |  |  |  | 400384 | 0 | 0 | 0 |  | 1.18 | 1 |
| 5c2c9af4 | NO_PAIRWISE_SOLUTION | 3 | 165376 |  |  | 163840 |  |  |  | 851968 | 0 | 0 | 0 |  | 1.01 | 0.987 |
| a5f85a15 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.888 |
| 3c9b0459 | SOLVED | 4 | 6570 | 6570 | 6 | 106 | 106 | 2 | 6 | 20932 | 1 | 1 | 7 | 9 | 62 | 31.4 |
| 8f2ea7aa | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.944 |
| 00d62c1b | NO_PAIRWISE_SOLUTION | 5 | 46080 |  |  | 41472 |  |  |  | 1217287 | 0 | 0 | 0 |  | 1.11 | 0.999 |
| bd4472b8 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.01 |
| 4093f84a | NO_PAIRWISE_SOLUTION | 3 | 40448 |  |  | 40448 |  |  |  | 137216 | 0 | 0 | 0 |  | 1 | 0.991 |
| 63613498 | NO_SHARED_PROGRAM | 3 | 83456 |  |  | 82944 |  |  |  | 189729 | 1 | 0 | 8 |  | 1.01 | 0.993 |
| 91714a58 | NO_PAIRWISE_SOLUTION | 3 | 38400 |  |  | 38400 |  |  |  | 100864 | 0 | 0 | 0 |  | 1 | 0.952 |
| 3ac3eb23 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.25 |
| 3345333e | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.08 |
| 1a07d186 | NO_PAIRWISE_SOLUTION | 3 | 37376 |  |  | 37888 |  |  |  | 207360 | 0 | 0 | 0 |  | 0.986 | 0.998 |
| a2fd1cf0 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.12 |
| 56ff96f3 | NO_PAIRWISE_SOLUTION | 4 | 172032 |  |  | 181760 |  |  |  | 1200000 | 0 | 0 | 0 |  | 0.946 | 1.05 |
| e21d9049 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.13 |
| 0a938d79 | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 1.05 |
| 6c434453 | NO_PAIRWISE_SOLUTION | 2 | 139264 |  |  | 137728 |  |  |  | 325632 | 0 | 0 | 0 |  | 1.01 | 0.996 |
| 3bd67248 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.13 |
| 54d9e175 | NO_PAIRWISE_SOLUTION | 4 | 65024 |  |  | 63488 |  |  |  | 605696 | 0 | 0 | 0 |  | 1.02 | 0.983 |
| 08ed6ac7 | NO_PAIRWISE_SOLUTION | 2 | 136704 |  |  | 136704 |  |  |  | 347136 | 0 | 0 | 0 |  | 1 | 1.01 |
| a64e4611 | NO_PAIRWISE_SOLUTION | 3 | 14848 |  |  | 14848 |  |  |  | 46080 | 0 | 0 | 0 |  | 1 | 1.01 |
| d511f180 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.669 |
| d43fd935 | NO_PAIRWISE_SOLUTION | 3 | 71168 |  |  | 73728 |  |  |  | 339456 | 0 | 0 | 0 |  | 0.965 | 1 |
| b775ac94 | NO_PAIRWISE_SOLUTION | 3 | 223744 |  |  | 223744 |  |  |  | 801216 | 0 | 0 | 0 |  | 1 | 0.985 |
| 868de0fa | NO_PAIRWISE_SOLUTION | 5 | 46080 |  |  | 47104 |  |  |  | 1087424 | 0 | 0 | 0 |  | 0.978 | 0.961 |
| b27ca6d3 | NO_PAIRWISE_SOLUTION | 2 | 60416 |  |  | 67584 |  |  |  | 104448 | 0 | 0 | 0 |  | 0.894 | 1.01 |
| 6aa20dc0 | NO_PAIRWISE_SOLUTION | 3 | 27648 |  |  | 27648 |  |  |  | 119296 | 0 | 0 | 0 |  | 1 | 1.09 |
| 28e73c20 | NO_PAIRWISE_SOLUTION | 5 | 5568 |  |  | 5568 |  |  |  | 27840 | 0 | 0 | 0 |  | 1 | 0.697 |
| e9614598 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.19 |
| 85c4e7cd | NO_PAIRWISE_SOLUTION | 4 | 165376 |  |  | 185856 |  |  |  | 1127840 | 0 | 0 | 0 |  | 0.89 | 0.983 |
| e8593010 | NO_PAIRWISE_SOLUTION | 3 | 229376 |  |  | 250368 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.916 | 0.999 |
| db93a21d | NO_PAIRWISE_SOLUTION | 4 | 113152 |  |  | 112640 |  |  |  | 924640 | 0 | 0 | 0 |  | 1 | 0.998 |
| 7447852a | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.04 |
| d364b489 | NO_PAIRWISE_SOLUTION | 2 | 112128 |  |  | 111616 |  |  |  | 303104 | 0 | 0 | 0 |  | 1 | 1.02 |
| 1f0c79e5 | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 1.05 |
| 99fa7670 | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 0.935 |
| e509e548 | NO_PAIRWISE_SOLUTION | 3 | 39936 |  |  | 40448 |  |  |  | 440832 | 0 | 0 | 0 |  | 0.987 | 1 |
| 3631a71a | NO_PAIRWISE_SOLUTION | 4 | 8704 |  |  | 9216 |  |  |  | 50176 | 0 | 0 | 0 |  | 0.944 | 1.01 |
| 6a1e5592 | NO_PAIRWISE_SOLUTION | 2 | 119296 |  |  | 113152 |  |  |  | 279552 | 0 | 0 | 0 |  | 1.05 | 1 |
| d406998b | NO_PAIRWISE_SOLUTION | 4 | 85504 |  |  | 77312 |  |  |  | 742880 | 0 | 0 | 0 |  | 1.11 | 0.992 |
| 1f642eb9 | NO_PAIRWISE_SOLUTION | 3 | 88064 |  |  | 89088 |  |  |  | 451584 | 0 | 0 | 0 |  | 0.989 | 1 |
| 0962bcdd | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 0.902 |
| 3befdf3e | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.12 |
| fcc82909 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 270848 |  |  |  | 900000 | 0 | 0 | 0 |  | 1.11 | 0.951 |
| 50846271 | NO_PAIRWISE_SOLUTION | 4 | 17920 |  |  | 17920 |  |  |  | 461280 | 0 | 0 | 0 |  | 1 | 1.03 |
| 7f4411dc | NO_PAIRWISE_SOLUTION | 3 | 42496 |  |  | 41984 |  |  |  | 336384 | 0 | 0 | 0 |  | 1.01 | 1.04 |
| 2204b7a8 | NO_PAIRWISE_SOLUTION | 3 | 49664 |  |  | 47616 |  |  |  | 319488 | 0 | 0 | 0 |  | 1.04 | 0.998 |
| 834ec97d | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.51 |
| 6e82a1ae | NO_PAIRWISE_SOLUTION | 3 | 114176 |  |  | 114688 |  |  |  | 496640 | 0 | 0 | 0 |  | 0.996 | 0.999 |
| b7249182 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.907 |
| 39e1d7f9 | NO_PAIRWISE_SOLUTION | 3 | 30208 |  |  | 28672 |  |  |  | 144896 | 0 | 0 | 0 |  | 1.05 | 1.1 |
| 56dc2b01 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.98 |
| 8d510a79 | NO_PAIRWISE_SOLUTION | 2 | 57344 |  |  | 71680 |  |  |  | 130560 | 0 | 0 | 0 |  | 0.8 | 1 |
| d037b0a7 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.2 |
| 73251a56 | NO_PAIRWISE_SOLUTION | 3 | 23040 |  |  | 23040 |  |  |  | 138240 | 0 | 0 | 0 |  | 1 | 1.07 |

## Condition: reweight

- tasks: 130 (in scope: 130); status counts: {'NO_PAIRWISE_SOLUTION': 127, 'SOLVED': 2, 'NO_SHARED_PROGRAM': 1}
- solve rate (all): baseline 0.015 vs reweight 0.015
- solve rate (in scope): baseline 0.015 vs reweight 0.015
- solved by baseline only: []; by reweight only: []
- tasks with >=1 abstraction: 0; solved using an abstraction: 0 (of which whole-program abstractions: 0)

### solved_only (n=2)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 2.441e+04 | 2.441e+04 | 1.784e+04 | 2 |
| tsl_expanded_states | 1004 | 1004 | 690.5 | 2 |
| baseline_first_solution_states | 2.441e+04 | 2.441e+04 | 1.784e+04 | 2 |
| tsl_first_solution_states | 1004 | 1004 | 690.5 | 2 |
| baseline_first_solution_nodes | 19 | 19 | 12 | 2 |
| tsl_first_solution_nodes | 2.5 | 2.5 | 0.5 | 2 |
| baseline_search_seconds | 2.366 | 2.366 | 2.224 | 2 |
| tsl_search_seconds | 0.09565 | 0.09565 | 0.04918 | 2 |
| baseline_program_length | 6.5 | 6.5 | 0.5 | 2 |
| tsl_program_length | 6.5 | 6.5 | 0.5 | 2 |
| tsl_expanded_program_length | 6.5 | 6.5 | 0.5 | 2 |
| tsl_description_length | 0 | 0 | 0 | 2 |
| total_mdl | 6.5 | 6.5 | 0.5 | 2 |
| tsl_num_abstractions | 0 | 0 | 0 | 2 |
| local_wake_total_states | 4.976e+04 | 4.976e+04 | 2.883e+04 | 2 |
| local_wake_seconds | 2.753 | 2.753 | 2.5 | 2 |
| local_sleep_seconds | 9.273e-05 | 9.273e-05 | 4.684e-06 | 2 |
| states_ratio | 22.96 | 22.96 | 1.973 | 2 |
| time_ratio | 17.37 | 17.37 | 14.33 | 2 |
| first_states_ratio | 22.96 | 22.96 | 1.973 | 2 |
| total_states_ratio | 0.4177 | 0.4177 | 0.1085 | 2 |
| states_ratio (geomean) | 22.9 | | | |
| first_states_ratio (geomean) | 22.9 | | | |
| time_ratio (geomean) | 9.83 | | | |
| total_states_ratio incl. wake (geomean) | 0.403 | | | |

### solved_only_nontrivial_abstraction (n=0)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| states_ratio (geomean) |  | | | |
| first_states_ratio (geomean) |  | | | |
| time_ratio (geomean) |  | | | |
| total_states_ratio incl. wake (geomean) |  | | | |

### all_tasks (n=130)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 1.773e+05 | 1.654e+05 | 1.127e+05 | 130 |
| tsl_expanded_states | 1.718e+05 | 1.582e+05 | 1.131e+05 | 130 |
| baseline_first_solution_states | 2.441e+04 | 2.441e+04 | 1.784e+04 | 2 |
| tsl_first_solution_states | 1004 | 1004 | 690.5 | 2 |
| baseline_first_solution_nodes | 19 | 19 | 12 | 2 |
| tsl_first_solution_nodes | 2.5 | 2.5 | 0.5 | 2 |
| baseline_search_seconds | 24.39 | 30.04 | 9.891 | 130 |
| tsl_search_seconds | 23.74 | 30.03 | 10.24 | 130 |
| baseline_program_length | 6.5 | 6.5 | 0.5 | 2 |
| tsl_program_length | 6.5 | 6.5 | 0.5 | 2 |
| tsl_expanded_program_length | 6.5 | 6.5 | 0.5 | 2 |
| tsl_description_length | 0 | 0 | 0 | 130 |
| total_mdl | 6.5 | 6.5 | 0.5 | 2 |
| tsl_num_abstractions | 0 | 0 | 0 | 130 |
| local_wake_total_states | 6.37e+05 | 6e+05 | 3.835e+05 | 130 |
| local_wake_seconds | 41.77 | 40.65 | 21.8 | 130 |
| local_sleep_seconds | 6.63e-06 | 8.54e-07 | 2.144e-05 | 130 |
| states_ratio | 1.452 | 1 | 2.832 | 130 |
| time_ratio | 1.331 | 1.005 | 2.713 | 130 |
| first_states_ratio | 22.96 | 22.96 | 1.973 | 2 |
| total_states_ratio | 0.2197 | 0.2274 | 0.07872 | 130 |
| states_ratio (geomean) | 1.09 | | | |
| first_states_ratio (geomean) | 22.9 | | | |
| time_ratio (geomean) | 1.08 | | | |
| total_states_ratio incl. wake (geomean) | 0.203 | | | |

### Per-task table

| task | status | pairs | base states | base first | base L | tsl states | tsl first | tsl L | L(expanded) | wake states | #A | used | L(A) | MDL | states ratio | time ratio |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 67a423a3 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.978 |
| f15e1fac | NO_PAIRWISE_SOLUTION | 3 | 102400 |  |  | 101888 |  |  |  | 493568 | 0 | 0 | 0 |  | 1.01 | 1.01 |
| 05269061 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1 |
| 045e512c | NO_PAIRWISE_SOLUTION | 3 | 205312 |  |  | 198144 |  |  |  | 771040 | 0 | 0 | 0 |  | 1.04 | 1 |
| 2dd70a9a | NO_PAIRWISE_SOLUTION | 3 | 38912 |  |  | 38912 |  |  |  | 157696 | 0 | 0 | 0 |  | 1 | 1.06 |
| 2bee17df | NO_PAIRWISE_SOLUTION | 3 | 256512 |  |  | 269824 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.951 | 1 |
| 1f876c06 | NO_PAIRWISE_SOLUTION | 3 | 74240 |  |  | 94720 |  |  |  | 320000 | 0 | 0 | 0 |  | 0.784 | 0.982 |
| 794b24be | NO_PAIRWISE_SOLUTION | 10 | 294400 |  |  | 96594 |  |  |  | 2764118 | 0 | 0 | 0 |  | 3.05 | 2.57 |
| b527c5c6 | NO_PAIRWISE_SOLUTION | 4 | 88064 |  |  | 89088 |  |  |  | 866784 | 0 | 0 | 0 |  | 0.989 | 1.03 |
| 7e0986d6 | NO_PAIRWISE_SOLUTION | 2 | 40960 |  |  | 41472 |  |  |  | 105984 | 0 | 0 | 0 |  | 0.988 | 1.02 |
| 321b1fc6 | NO_PAIRWISE_SOLUTION | 2 | 210432 |  |  | 209408 |  |  |  | 557024 | 0 | 0 | 0 |  | 1 | 0.997 |
| ce9e57f2 | NO_PAIRWISE_SOLUTION | 3 | 101888 |  |  | 102400 |  |  |  | 623616 | 0 | 0 | 0 |  | 0.995 | 0.986 |
| 1caeab9d | NO_PAIRWISE_SOLUTION | 3 | 208384 |  |  | 227840 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.915 | 1 |
| 444801d8 | NO_PAIRWISE_SOLUTION | 3 | 278016 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.927 | 1.04 |
| 150deff5 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.903 |
| 6e19193c | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1 |
| a3df8b1e | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.51 |
| 32597951 | NO_PAIRWISE_SOLUTION | 3 | 33280 |  |  | 35840 |  |  |  | 228352 | 0 | 0 | 0 |  | 0.929 | 0.999 |
| 928ad970 | NO_PAIRWISE_SOLUTION | 3 | 116736 |  |  | 114688 |  |  |  | 436736 | 0 | 0 | 0 |  | 1.02 | 0.97 |
| f1cefba8 | NO_PAIRWISE_SOLUTION | 3 | 156672 |  |  | 157184 |  |  |  | 592864 | 0 | 0 | 0 |  | 0.997 | 0.991 |
| db3e9e38 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 0.962 |
| ddf7fa4f | NO_PAIRWISE_SOLUTION | 3 | 77312 |  |  | 58880 |  |  |  | 437760 | 0 | 0 | 0 |  | 1.31 | 1.01 |
| dbc1a6ce | NO_PAIRWISE_SOLUTION | 4 | 66560 |  |  | 78336 |  |  |  | 288768 | 0 | 0 | 0 |  | 0.85 | 0.994 |
| 272f95fa | NO_PAIRWISE_SOLUTION | 2 | 202752 |  |  | 201728 |  |  |  | 546784 | 0 | 0 | 0 |  | 1.01 | 0.992 |
| 6855a6e4 | NO_PAIRWISE_SOLUTION | 3 | 129024 |  |  | 137216 |  |  |  | 492032 | 0 | 0 | 0 |  | 0.94 | 0.998 |
| 97999447 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.05 |
| 54d82841 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.05 |
| e26a3af2 | NO_PAIRWISE_SOLUTION | 3 | 92160 |  |  | 92160 |  |  |  | 463360 | 0 | 0 | 0 |  | 1 | 0.997 |
| b782dc8a | NO_PAIRWISE_SOLUTION | 2 | 46080 |  |  | 46080 |  |  |  | 170496 | 0 | 0 | 0 |  | 1 | 1 |
| 44d8ac46 | NO_PAIRWISE_SOLUTION | 4 | 133632 |  |  | 65954 |  |  |  | 478829 | 0 | 0 | 0 |  | 2.03 | 1.29 |
| ba97ae07 | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 0.986 |
| 760b3cac | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.02 |
| 4c5c2cf0 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.02 |
| c0f76784 | NO_PAIRWISE_SOLUTION | 3 | 140288 |  |  | 148480 |  |  |  | 725984 | 0 | 0 | 0 |  | 0.945 | 0.997 |
| 67385a82 | NO_PAIRWISE_SOLUTION | 4 | 267776 |  |  | 237056 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1.13 | 1 |
| 810b9b61 | NO_PAIRWISE_SOLUTION | 3 | 57344 |  |  | 72193 |  |  |  | 474478 | 0 | 0 | 0 |  | 0.794 | 1.05 |
| a78176bb | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.02 |
| f25ffba3 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.11 |
| a699fb00 | NO_PAIRWISE_SOLUTION | 3 | 68096 |  |  | 68608 |  |  |  | 420320 | 0 | 0 | 0 |  | 0.993 | 1.02 |
| b8cdaf2b | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 0.995 |
| a8d7556c | NO_PAIRWISE_SOLUTION | 3 | 15872 |  |  | 20480 |  |  |  | 141824 | 0 | 0 | 0 |  | 0.775 | 1.01 |
| bb43febb | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 0.966 |
| e73095fd | NO_PAIRWISE_SOLUTION | 3 | 171520 |  |  | 181248 |  |  |  | 811488 | 0 | 0 | 0 |  | 0.946 | 1 |
| b60334d2 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 298496 |  |  |  | 591840 | 0 | 0 | 0 |  | 1.01 | 0.993 |
| d2abd087 | NO_PAIRWISE_SOLUTION | 3 | 75776 |  |  | 59904 |  |  |  | 521696 | 0 | 0 | 0 |  | 1.26 | 0.995 |
| 29623171 | NO_PAIRWISE_SOLUTION | 3 | 43520 |  |  | 44032 |  |  |  | 327168 | 0 | 0 | 0 |  | 0.988 | 1.01 |
| d5d6de2d | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.03 |
| 941d9a10 | NO_PAIRWISE_SOLUTION | 3 | 289280 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.964 | 1.03 |
| d6ad076f | NO_PAIRWISE_SOLUTION | 3 | 234496 |  |  | 241152 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.972 | 1.04 |
| 6cdd2623 | NO_PAIRWISE_SOLUTION | 3 | 43008 |  |  | 43520 |  |  |  | 100352 | 0 | 0 | 0 |  | 0.988 | 1.01 |
| 1b60fb0c | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.03 |
| d4f3cd78 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.06 |
| e8dc4411 | NO_PAIRWISE_SOLUTION | 3 | 91136 |  |  | 104448 |  |  |  | 442880 | 0 | 0 | 0 |  | 0.873 | 1.01 |
| d23f8c26 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.907 |
| 3bdb4ada | NO_PAIRWISE_SOLUTION | 2 | 158720 |  |  | 159232 |  |  |  | 430592 | 0 | 0 | 0 |  | 0.997 | 1 |
| 88a10436 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.995 |
| 41e4d17e | NO_PAIRWISE_SOLUTION | 2 | 68608 |  |  | 68608 |  |  |  | 233472 | 0 | 0 | 0 |  | 1 | 1.11 |
| 508bd3b6 | NO_PAIRWISE_SOLUTION | 3 | 247808 |  |  | 241664 |  |  |  | 900000 | 0 | 0 | 0 |  | 1.03 | 1 |
| 3aa6fb7a | SOLVED | 2 | 42241 | 42241 | 7 | 1694 | 1694 | 7 | 7 | 78587 | 0 | 0 | 0 | 7 | 24.9 | 31.7 |
| ea786f4a | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.03 |
| 29ec7d0e | NO_PAIRWISE_SOLUTION | 4 | 30720 |  |  | 32768 |  |  |  | 356864 | 0 | 0 | 0 |  | 0.938 | 0.932 |
| a9f96cdd | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 1.01 |
| 3e980e27 | NO_PAIRWISE_SOLUTION | 4 | 160256 |  |  | 159232 |  |  |  | 983488 | 0 | 0 | 0 |  | 1.01 | 1 |
| c1d99e64 | NO_PAIRWISE_SOLUTION | 3 | 27648 |  |  | 27648 |  |  |  | 152064 | 0 | 0 | 0 |  | 1 | 1.01 |
| 913fb3ed | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 61377 |  |  |  | 633864 | 0 | 0 | 0 |  | 4.89 | 2.45 |
| 9565186b | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 30863 |  |  |  | 917448 | 0 | 0 | 0 |  | 9.72 | 5.36 |
| 93b581b8 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.958 |
| 5168d44c | NO_PAIRWISE_SOLUTION | 3 | 146432 |  |  | 144896 |  |  |  | 627168 | 0 | 0 | 0 |  | 1.01 | 0.998 |
| 5521c0d9 | NO_PAIRWISE_SOLUTION | 3 | 150528 |  |  | 147456 |  |  |  | 809920 | 0 | 0 | 0 |  | 1.02 | 0.992 |
| 31aa019c | NO_PAIRWISE_SOLUTION | 3 | 53760 |  |  | 49664 |  |  |  | 182784 | 0 | 0 | 0 |  | 1.08 | 0.988 |
| 484b58aa | NO_PAIRWISE_SOLUTION | 3 | 10240 |  |  | 10240 |  |  |  | 44032 | 0 | 0 | 0 |  | 1 | 1.01 |
| 6d58a25d | NO_PAIRWISE_SOLUTION | 3 | 49664 |  |  | 43008 |  |  |  | 121856 | 0 | 0 | 0 |  | 1.15 | 1.08 |
| 8403a5d5 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.37 |
| 1bfc4729 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.23 |
| c3f564a4 | NO_PAIRWISE_SOLUTION | 3 | 76288 |  |  | 64512 |  |  |  | 400384 | 0 | 0 | 0 |  | 1.18 | 1 |
| 5c2c9af4 | NO_PAIRWISE_SOLUTION | 3 | 165376 |  |  | 163840 |  |  |  | 851968 | 0 | 0 | 0 |  | 1.01 | 0.987 |
| a5f85a15 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.888 |
| 3c9b0459 | SOLVED | 4 | 6570 | 6570 | 6 | 313 | 313 | 6 | 6 | 20932 | 0 | 0 | 0 | 6 | 21 | 3.05 |
| 8f2ea7aa | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.944 |
| 00d62c1b | NO_PAIRWISE_SOLUTION | 5 | 46080 |  |  | 51712 |  |  |  | 1217287 | 0 | 0 | 0 |  | 0.891 | 1.01 |
| bd4472b8 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.01 |
| 4093f84a | NO_PAIRWISE_SOLUTION | 3 | 40448 |  |  | 40448 |  |  |  | 137216 | 0 | 0 | 0 |  | 1 | 0.991 |
| 63613498 | NO_SHARED_PROGRAM | 3 | 83456 |  |  | 99840 |  |  |  | 189729 | 0 | 0 | 0 |  | 0.836 | 1.05 |
| 91714a58 | NO_PAIRWISE_SOLUTION | 3 | 38400 |  |  | 38400 |  |  |  | 100864 | 0 | 0 | 0 |  | 1 | 0.952 |
| 3ac3eb23 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.25 |
| 3345333e | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.08 |
| 1a07d186 | NO_PAIRWISE_SOLUTION | 3 | 37376 |  |  | 37888 |  |  |  | 207360 | 0 | 0 | 0 |  | 0.986 | 0.998 |
| a2fd1cf0 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.12 |
| 56ff96f3 | NO_PAIRWISE_SOLUTION | 4 | 172032 |  |  | 181760 |  |  |  | 1200000 | 0 | 0 | 0 |  | 0.946 | 1.05 |
| e21d9049 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.13 |
| 0a938d79 | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 1.05 |
| 6c434453 | NO_PAIRWISE_SOLUTION | 2 | 139264 |  |  | 137728 |  |  |  | 325632 | 0 | 0 | 0 |  | 1.01 | 0.996 |
| 3bd67248 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.13 |
| 54d9e175 | NO_PAIRWISE_SOLUTION | 4 | 65024 |  |  | 63488 |  |  |  | 605696 | 0 | 0 | 0 |  | 1.02 | 0.983 |
| 08ed6ac7 | NO_PAIRWISE_SOLUTION | 2 | 136704 |  |  | 136704 |  |  |  | 347136 | 0 | 0 | 0 |  | 1 | 1.01 |
| a64e4611 | NO_PAIRWISE_SOLUTION | 3 | 14848 |  |  | 14848 |  |  |  | 46080 | 0 | 0 | 0 |  | 1 | 1.01 |
| d511f180 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.669 |
| d43fd935 | NO_PAIRWISE_SOLUTION | 3 | 71168 |  |  | 73728 |  |  |  | 339456 | 0 | 0 | 0 |  | 0.965 | 1 |
| b775ac94 | NO_PAIRWISE_SOLUTION | 3 | 223744 |  |  | 223744 |  |  |  | 801216 | 0 | 0 | 0 |  | 1 | 0.985 |
| 868de0fa | NO_PAIRWISE_SOLUTION | 5 | 46080 |  |  | 47104 |  |  |  | 1087424 | 0 | 0 | 0 |  | 0.978 | 0.961 |
| b27ca6d3 | NO_PAIRWISE_SOLUTION | 2 | 60416 |  |  | 67584 |  |  |  | 104448 | 0 | 0 | 0 |  | 0.894 | 1.01 |
| 6aa20dc0 | NO_PAIRWISE_SOLUTION | 3 | 27648 |  |  | 27648 |  |  |  | 119296 | 0 | 0 | 0 |  | 1 | 1.09 |
| 28e73c20 | NO_PAIRWISE_SOLUTION | 5 | 5568 |  |  | 5568 |  |  |  | 27840 | 0 | 0 | 0 |  | 1 | 0.697 |
| e9614598 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.19 |
| 85c4e7cd | NO_PAIRWISE_SOLUTION | 4 | 165376 |  |  | 185856 |  |  |  | 1127840 | 0 | 0 | 0 |  | 0.89 | 0.983 |
| e8593010 | NO_PAIRWISE_SOLUTION | 3 | 229376 |  |  | 250368 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.916 | 0.999 |
| db93a21d | NO_PAIRWISE_SOLUTION | 4 | 113152 |  |  | 112640 |  |  |  | 924640 | 0 | 0 | 0 |  | 1 | 0.998 |
| 7447852a | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.04 |
| d364b489 | NO_PAIRWISE_SOLUTION | 2 | 112128 |  |  | 111616 |  |  |  | 303104 | 0 | 0 | 0 |  | 1 | 1.02 |
| 1f0c79e5 | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 1.05 |
| 99fa7670 | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 0.935 |
| e509e548 | NO_PAIRWISE_SOLUTION | 3 | 39936 |  |  | 40448 |  |  |  | 440832 | 0 | 0 | 0 |  | 0.987 | 1 |
| 3631a71a | NO_PAIRWISE_SOLUTION | 4 | 8704 |  |  | 9216 |  |  |  | 50176 | 0 | 0 | 0 |  | 0.944 | 1.01 |
| 6a1e5592 | NO_PAIRWISE_SOLUTION | 2 | 119296 |  |  | 113152 |  |  |  | 279552 | 0 | 0 | 0 |  | 1.05 | 1 |
| d406998b | NO_PAIRWISE_SOLUTION | 4 | 85504 |  |  | 77312 |  |  |  | 742880 | 0 | 0 | 0 |  | 1.11 | 0.992 |
| 1f642eb9 | NO_PAIRWISE_SOLUTION | 3 | 88064 |  |  | 89088 |  |  |  | 451584 | 0 | 0 | 0 |  | 0.989 | 1 |
| 0962bcdd | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 0.902 |
| 3befdf3e | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.12 |
| fcc82909 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 270848 |  |  |  | 900000 | 0 | 0 | 0 |  | 1.11 | 0.951 |
| 50846271 | NO_PAIRWISE_SOLUTION | 4 | 17920 |  |  | 17920 |  |  |  | 461280 | 0 | 0 | 0 |  | 1 | 1.03 |
| 7f4411dc | NO_PAIRWISE_SOLUTION | 3 | 42496 |  |  | 41984 |  |  |  | 336384 | 0 | 0 | 0 |  | 1.01 | 1.04 |
| 2204b7a8 | NO_PAIRWISE_SOLUTION | 3 | 49664 |  |  | 47616 |  |  |  | 319488 | 0 | 0 | 0 |  | 1.04 | 0.998 |
| 834ec97d | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.51 |
| 6e82a1ae | NO_PAIRWISE_SOLUTION | 3 | 114176 |  |  | 114688 |  |  |  | 496640 | 0 | 0 | 0 |  | 0.996 | 0.999 |
| b7249182 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.907 |
| 39e1d7f9 | NO_PAIRWISE_SOLUTION | 3 | 30208 |  |  | 28672 |  |  |  | 144896 | 0 | 0 | 0 |  | 1.05 | 1.1 |
| 56dc2b01 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.98 |
| 8d510a79 | NO_PAIRWISE_SOLUTION | 2 | 57344 |  |  | 71680 |  |  |  | 130560 | 0 | 0 | 0 |  | 0.8 | 1 |
| d037b0a7 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.2 |
| 73251a56 | NO_PAIRWISE_SOLUTION | 3 | 23040 |  |  | 23040 |  |  |  | 138240 | 0 | 0 | 0 |  | 1 | 1.07 |

## Condition: tsl_reweight

- tasks: 130 (in scope: 130); status counts: {'NO_PAIRWISE_SOLUTION': 127, 'SOLVED': 2, 'NO_SHARED_PROGRAM': 1}
- solve rate (all): baseline 0.015 vs tsl_reweight 0.015
- solve rate (in scope): baseline 0.015 vs tsl_reweight 0.015
- solved by baseline only: []; by tsl_reweight only: []
- tasks with >=1 abstraction: 3; solved using an abstraction: 2 (of which whole-program abstractions: 1)

### solved_only (n=2)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 2.441e+04 | 2.441e+04 | 1.784e+04 | 2 |
| tsl_expanded_states | 59.5 | 59.5 | 52.5 | 2 |
| baseline_first_solution_states | 2.441e+04 | 2.441e+04 | 1.784e+04 | 2 |
| tsl_first_solution_states | 59.5 | 59.5 | 52.5 | 2 |
| baseline_first_solution_nodes | 19 | 19 | 12 | 2 |
| tsl_first_solution_nodes | 2 | 2 | 0 | 2 |
| baseline_search_seconds | 2.366 | 2.366 | 2.224 | 2 |
| tsl_search_seconds | 0.008594 | 0.008594 | 8.604e-05 | 2 |
| baseline_program_length | 6.5 | 6.5 | 0.5 | 2 |
| tsl_program_length | 2.5 | 2.5 | 0.5 | 2 |
| tsl_expanded_program_length | 6.5 | 6.5 | 0.5 | 2 |
| tsl_description_length | 6.5 | 6.5 | 0.5 | 2 |
| total_mdl | 9 | 9 | 0 | 2 |
| tsl_num_abstractions | 1 | 1 | 0 | 2 |
| local_wake_total_states | 4.976e+04 | 4.976e+04 | 2.883e+04 | 2 |
| local_wake_seconds | 2.753 | 2.753 | 2.5 | 2 |
| local_sleep_seconds | 0.001088 | 0.001088 | 0.0002772 | 2 |
| states_ratio | 657.9 | 657.9 | 280.7 | 2 |
| time_ratio | 277.9 | 277.9 | 261.6 | 2 |
| first_states_ratio | 657.9 | 657.9 | 280.7 | 2 |
| total_states_ratio | 0.4253 | 0.4253 | 0.1115 | 2 |
| states_ratio (geomean) | 595 | | | |
| first_states_ratio (geomean) | 595 | | | |
| time_ratio (geomean) | 93.8 | | | |
| total_states_ratio incl. wake (geomean) | 0.41 | | | |

### solved_only_nontrivial_abstraction (n=1)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 4.224e+04 | 4.224e+04 | 0 | 1 |
| tsl_expanded_states | 112 | 112 | 0 | 1 |
| baseline_first_solution_states | 4.224e+04 | 4.224e+04 | 0 | 1 |
| tsl_first_solution_states | 112 | 112 | 0 | 1 |
| baseline_first_solution_nodes | 31 | 31 | 0 | 1 |
| tsl_first_solution_nodes | 2 | 2 | 0 | 1 |
| baseline_search_seconds | 4.591 | 4.591 | 0 | 1 |
| tsl_search_seconds | 0.008508 | 0.008508 | 0 | 1 |
| baseline_program_length | 7 | 7 | 0 | 1 |
| tsl_program_length | 3 | 3 | 0 | 1 |
| tsl_expanded_program_length | 7 | 7 | 0 | 1 |
| tsl_description_length | 6 | 6 | 0 | 1 |
| total_mdl | 9 | 9 | 0 | 1 |
| tsl_num_abstractions | 1 | 1 | 0 | 1 |
| local_wake_total_states | 7.859e+04 | 7.859e+04 | 0 | 1 |
| local_wake_seconds | 5.253 | 5.253 | 0 | 1 |
| local_sleep_seconds | 0.0008109 | 0.0008109 | 0 | 1 |
| states_ratio | 377.2 | 377.2 | 0 | 1 |
| time_ratio | 539.5 | 539.5 | 0 | 1 |
| first_states_ratio | 377.2 | 377.2 | 0 | 1 |
| total_states_ratio | 0.5367 | 0.5367 | 0 | 1 |
| states_ratio (geomean) | 377 | | | |
| first_states_ratio (geomean) | 377 | | | |
| time_ratio (geomean) | 540 | | | |
| total_states_ratio incl. wake (geomean) | 0.537 | | | |

### all_tasks (n=130)

| metric | mean | median | std | n |
|---|---:|---:|---:|---:|
| baseline_expanded_states | 1.773e+05 | 1.654e+05 | 1.127e+05 | 130 |
| tsl_expanded_states | 1.715e+05 | 1.582e+05 | 1.133e+05 | 130 |
| baseline_first_solution_states | 2.441e+04 | 2.441e+04 | 1.784e+04 | 2 |
| tsl_first_solution_states | 59.5 | 59.5 | 52.5 | 2 |
| baseline_first_solution_nodes | 19 | 19 | 12 | 2 |
| tsl_first_solution_nodes | 2 | 2 | 0 | 2 |
| baseline_search_seconds | 24.39 | 30.04 | 9.891 | 130 |
| tsl_search_seconds | 23.75 | 30.03 | 10.25 | 130 |
| baseline_program_length | 6.5 | 6.5 | 0.5 | 2 |
| tsl_program_length | 2.5 | 2.5 | 0.5 | 2 |
| tsl_expanded_program_length | 6.5 | 6.5 | 0.5 | 2 |
| tsl_description_length | 0.1615 | 0 | 1.058 | 130 |
| total_mdl | 9 | 9 | 0 | 2 |
| tsl_num_abstractions | 0.02308 | 0 | 0.1501 | 130 |
| local_wake_total_states | 6.37e+05 | 6e+05 | 3.835e+05 | 130 |
| local_wake_seconds | 41.77 | 40.65 | 21.8 | 130 |
| local_sleep_seconds | 5.808e-05 | 4.565e-07 | 0.0002517 | 130 |
| states_ratio | 11.22 | 1 | 88.01 | 130 |
| time_ratio | 5.339 | 1.005 | 47.05 | 130 |
| first_states_ratio | 657.9 | 657.9 | 280.7 | 2 |
| total_states_ratio | 0.2201 | 0.2274 | 0.07949 | 130 |
| states_ratio (geomean) | 1.15 | | | |
| first_states_ratio (geomean) | 595 | | | |
| time_ratio (geomean) | 1.12 | | | |
| total_states_ratio incl. wake (geomean) | 0.203 | | | |

### Per-task table

| task | status | pairs | base states | base first | base L | tsl states | tsl first | tsl L | L(expanded) | wake states | #A | used | L(A) | MDL | states ratio | time ratio |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 67a423a3 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.978 |
| f15e1fac | NO_PAIRWISE_SOLUTION | 3 | 102400 |  |  | 101888 |  |  |  | 493568 | 0 | 0 | 0 |  | 1.01 | 1.01 |
| 05269061 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1 |
| 045e512c | NO_PAIRWISE_SOLUTION | 3 | 205312 |  |  | 198144 |  |  |  | 771040 | 0 | 0 | 0 |  | 1.04 | 1 |
| 2dd70a9a | NO_PAIRWISE_SOLUTION | 3 | 38912 |  |  | 38912 |  |  |  | 157696 | 0 | 0 | 0 |  | 1 | 1.06 |
| 2bee17df | NO_PAIRWISE_SOLUTION | 3 | 256512 |  |  | 269824 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.951 | 1 |
| 1f876c06 | NO_PAIRWISE_SOLUTION | 3 | 74240 |  |  | 94720 |  |  |  | 320000 | 0 | 0 | 0 |  | 0.784 | 0.982 |
| 794b24be | NO_PAIRWISE_SOLUTION | 10 | 294400 |  |  | 96594 |  |  |  | 2764118 | 0 | 0 | 0 |  | 3.05 | 2.57 |
| b527c5c6 | NO_PAIRWISE_SOLUTION | 4 | 88064 |  |  | 89088 |  |  |  | 866784 | 0 | 0 | 0 |  | 0.989 | 1.03 |
| 7e0986d6 | NO_PAIRWISE_SOLUTION | 2 | 40960 |  |  | 41472 |  |  |  | 105984 | 0 | 0 | 0 |  | 0.988 | 1.02 |
| 321b1fc6 | NO_PAIRWISE_SOLUTION | 2 | 210432 |  |  | 209408 |  |  |  | 557024 | 0 | 0 | 0 |  | 1 | 0.997 |
| ce9e57f2 | NO_PAIRWISE_SOLUTION | 3 | 101888 |  |  | 102400 |  |  |  | 623616 | 0 | 0 | 0 |  | 0.995 | 0.986 |
| 1caeab9d | NO_PAIRWISE_SOLUTION | 3 | 208384 |  |  | 227840 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.915 | 1 |
| 444801d8 | NO_PAIRWISE_SOLUTION | 3 | 278016 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.927 | 1.04 |
| 150deff5 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.903 |
| 6e19193c | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1 |
| a3df8b1e | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.51 |
| 32597951 | NO_PAIRWISE_SOLUTION | 3 | 33280 |  |  | 35840 |  |  |  | 228352 | 0 | 0 | 0 |  | 0.929 | 0.999 |
| 928ad970 | NO_PAIRWISE_SOLUTION | 3 | 116736 |  |  | 114688 |  |  |  | 436736 | 0 | 0 | 0 |  | 1.02 | 0.97 |
| f1cefba8 | NO_PAIRWISE_SOLUTION | 3 | 156672 |  |  | 157184 |  |  |  | 592864 | 0 | 0 | 0 |  | 0.997 | 0.991 |
| db3e9e38 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 0.962 |
| ddf7fa4f | NO_PAIRWISE_SOLUTION | 3 | 77312 |  |  | 58880 |  |  |  | 437760 | 0 | 0 | 0 |  | 1.31 | 1.01 |
| dbc1a6ce | NO_PAIRWISE_SOLUTION | 4 | 66560 |  |  | 78336 |  |  |  | 288768 | 0 | 0 | 0 |  | 0.85 | 0.994 |
| 272f95fa | NO_PAIRWISE_SOLUTION | 2 | 202752 |  |  | 201728 |  |  |  | 546784 | 0 | 0 | 0 |  | 1.01 | 0.992 |
| 6855a6e4 | NO_PAIRWISE_SOLUTION | 3 | 129024 |  |  | 137216 |  |  |  | 492032 | 0 | 0 | 0 |  | 0.94 | 0.998 |
| 97999447 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.05 |
| 54d82841 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.05 |
| e26a3af2 | NO_PAIRWISE_SOLUTION | 3 | 92160 |  |  | 92160 |  |  |  | 463360 | 0 | 0 | 0 |  | 1 | 0.997 |
| b782dc8a | NO_PAIRWISE_SOLUTION | 2 | 46080 |  |  | 46080 |  |  |  | 170496 | 0 | 0 | 0 |  | 1 | 1 |
| 44d8ac46 | NO_PAIRWISE_SOLUTION | 4 | 133632 |  |  | 65954 |  |  |  | 478829 | 0 | 0 | 0 |  | 2.03 | 1.29 |
| ba97ae07 | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 0.986 |
| 760b3cac | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.02 |
| 4c5c2cf0 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.02 |
| c0f76784 | NO_PAIRWISE_SOLUTION | 3 | 140288 |  |  | 148480 |  |  |  | 725984 | 0 | 0 | 0 |  | 0.945 | 0.997 |
| 67385a82 | NO_PAIRWISE_SOLUTION | 4 | 267776 |  |  | 237056 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1.13 | 1 |
| 810b9b61 | NO_PAIRWISE_SOLUTION | 3 | 57344 |  |  | 72193 |  |  |  | 474478 | 0 | 0 | 0 |  | 0.794 | 1.05 |
| a78176bb | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.02 |
| f25ffba3 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.11 |
| a699fb00 | NO_PAIRWISE_SOLUTION | 3 | 68096 |  |  | 68608 |  |  |  | 420320 | 0 | 0 | 0 |  | 0.993 | 1.02 |
| b8cdaf2b | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 0.995 |
| a8d7556c | NO_PAIRWISE_SOLUTION | 3 | 15872 |  |  | 20480 |  |  |  | 141824 | 0 | 0 | 0 |  | 0.775 | 1.01 |
| bb43febb | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 0.966 |
| e73095fd | NO_PAIRWISE_SOLUTION | 3 | 171520 |  |  | 181248 |  |  |  | 811488 | 0 | 0 | 0 |  | 0.946 | 1 |
| b60334d2 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 298496 |  |  |  | 591840 | 0 | 0 | 0 |  | 1.01 | 0.993 |
| d2abd087 | NO_PAIRWISE_SOLUTION | 3 | 75776 |  |  | 59904 |  |  |  | 521696 | 0 | 0 | 0 |  | 1.26 | 0.995 |
| 29623171 | NO_PAIRWISE_SOLUTION | 3 | 43520 |  |  | 44032 |  |  |  | 327168 | 0 | 0 | 0 |  | 0.988 | 1.01 |
| d5d6de2d | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.03 |
| 941d9a10 | NO_PAIRWISE_SOLUTION | 3 | 289280 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.964 | 1.03 |
| d6ad076f | NO_PAIRWISE_SOLUTION | 3 | 234496 |  |  | 241152 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.972 | 1.04 |
| 6cdd2623 | NO_PAIRWISE_SOLUTION | 3 | 43008 |  |  | 43520 |  |  |  | 100352 | 0 | 0 | 0 |  | 0.988 | 1.01 |
| 1b60fb0c | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.03 |
| d4f3cd78 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.06 |
| e8dc4411 | NO_PAIRWISE_SOLUTION | 3 | 91136 |  |  | 104448 |  |  |  | 442880 | 0 | 0 | 0 |  | 0.873 | 1.01 |
| d23f8c26 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.907 |
| 3bdb4ada | NO_PAIRWISE_SOLUTION | 2 | 158720 |  |  | 159232 |  |  |  | 430592 | 0 | 0 | 0 |  | 0.997 | 1 |
| 88a10436 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.995 |
| 41e4d17e | NO_PAIRWISE_SOLUTION | 2 | 68608 |  |  | 68608 |  |  |  | 233472 | 0 | 0 | 0 |  | 1 | 1.11 |
| 508bd3b6 | NO_PAIRWISE_SOLUTION | 3 | 247808 |  |  | 241664 |  |  |  | 900000 | 0 | 0 | 0 |  | 1.03 | 1 |
| 3aa6fb7a | SOLVED | 2 | 42241 | 42241 | 7 | 112 | 112 | 3 | 7 | 78587 | 1 | 1 | 6 | 9 | 377 | 540 |
| ea786f4a | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.03 |
| 29ec7d0e | NO_PAIRWISE_SOLUTION | 4 | 30720 |  |  | 32768 |  |  |  | 356864 | 0 | 0 | 0 |  | 0.938 | 0.932 |
| a9f96cdd | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 1.01 |
| 3e980e27 | NO_PAIRWISE_SOLUTION | 4 | 160256 |  |  | 159232 |  |  |  | 983488 | 0 | 0 | 0 |  | 1.01 | 1 |
| c1d99e64 | NO_PAIRWISE_SOLUTION | 3 | 27648 |  |  | 27648 |  |  |  | 152064 | 0 | 0 | 0 |  | 1 | 1.01 |
| 913fb3ed | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 61377 |  |  |  | 633864 | 0 | 0 | 0 |  | 4.89 | 2.45 |
| 9565186b | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 30863 |  |  |  | 917448 | 0 | 0 | 0 |  | 9.72 | 5.36 |
| 93b581b8 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.958 |
| 5168d44c | NO_PAIRWISE_SOLUTION | 3 | 146432 |  |  | 144896 |  |  |  | 627168 | 0 | 0 | 0 |  | 1.01 | 0.998 |
| 5521c0d9 | NO_PAIRWISE_SOLUTION | 3 | 150528 |  |  | 147456 |  |  |  | 809920 | 0 | 0 | 0 |  | 1.02 | 0.992 |
| 31aa019c | NO_PAIRWISE_SOLUTION | 3 | 53760 |  |  | 49664 |  |  |  | 182784 | 0 | 0 | 0 |  | 1.08 | 0.988 |
| 484b58aa | NO_PAIRWISE_SOLUTION | 3 | 10240 |  |  | 10240 |  |  |  | 44032 | 0 | 0 | 0 |  | 1 | 1.01 |
| 6d58a25d | NO_PAIRWISE_SOLUTION | 3 | 49664 |  |  | 43008 |  |  |  | 121856 | 0 | 0 | 0 |  | 1.15 | 1.08 |
| 8403a5d5 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.37 |
| 1bfc4729 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.23 |
| c3f564a4 | NO_PAIRWISE_SOLUTION | 3 | 76288 |  |  | 64512 |  |  |  | 400384 | 0 | 0 | 0 |  | 1.18 | 1 |
| 5c2c9af4 | NO_PAIRWISE_SOLUTION | 3 | 165376 |  |  | 163840 |  |  |  | 851968 | 0 | 0 | 0 |  | 1.01 | 0.987 |
| a5f85a15 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.888 |
| 3c9b0459 | SOLVED | 4 | 6570 | 6570 | 6 | 7 | 7 | 2 | 6 | 20932 | 1 | 1 | 7 | 9 | 939 | 16.3 |
| 8f2ea7aa | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.944 |
| 00d62c1b | NO_PAIRWISE_SOLUTION | 5 | 46080 |  |  | 51712 |  |  |  | 1217287 | 0 | 0 | 0 |  | 0.891 | 1.01 |
| bd4472b8 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.01 |
| 4093f84a | NO_PAIRWISE_SOLUTION | 3 | 40448 |  |  | 40448 |  |  |  | 137216 | 0 | 0 | 0 |  | 1 | 0.991 |
| 63613498 | NO_SHARED_PROGRAM | 3 | 83456 |  |  | 59904 |  |  |  | 189729 | 1 | 0 | 8 |  | 1.39 | 1.01 |
| 91714a58 | NO_PAIRWISE_SOLUTION | 3 | 38400 |  |  | 38400 |  |  |  | 100864 | 0 | 0 | 0 |  | 1 | 0.952 |
| 3ac3eb23 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.25 |
| 3345333e | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.08 |
| 1a07d186 | NO_PAIRWISE_SOLUTION | 3 | 37376 |  |  | 37888 |  |  |  | 207360 | 0 | 0 | 0 |  | 0.986 | 0.998 |
| a2fd1cf0 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.12 |
| 56ff96f3 | NO_PAIRWISE_SOLUTION | 4 | 172032 |  |  | 181760 |  |  |  | 1200000 | 0 | 0 | 0 |  | 0.946 | 1.05 |
| e21d9049 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.13 |
| 0a938d79 | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 1.05 |
| 6c434453 | NO_PAIRWISE_SOLUTION | 2 | 139264 |  |  | 137728 |  |  |  | 325632 | 0 | 0 | 0 |  | 1.01 | 0.996 |
| 3bd67248 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.13 |
| 54d9e175 | NO_PAIRWISE_SOLUTION | 4 | 65024 |  |  | 63488 |  |  |  | 605696 | 0 | 0 | 0 |  | 1.02 | 0.983 |
| 08ed6ac7 | NO_PAIRWISE_SOLUTION | 2 | 136704 |  |  | 136704 |  |  |  | 347136 | 0 | 0 | 0 |  | 1 | 1.01 |
| a64e4611 | NO_PAIRWISE_SOLUTION | 3 | 14848 |  |  | 14848 |  |  |  | 46080 | 0 | 0 | 0 |  | 1 | 1.01 |
| d511f180 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.669 |
| d43fd935 | NO_PAIRWISE_SOLUTION | 3 | 71168 |  |  | 73728 |  |  |  | 339456 | 0 | 0 | 0 |  | 0.965 | 1 |
| b775ac94 | NO_PAIRWISE_SOLUTION | 3 | 223744 |  |  | 223744 |  |  |  | 801216 | 0 | 0 | 0 |  | 1 | 0.985 |
| 868de0fa | NO_PAIRWISE_SOLUTION | 5 | 46080 |  |  | 47104 |  |  |  | 1087424 | 0 | 0 | 0 |  | 0.978 | 0.961 |
| b27ca6d3 | NO_PAIRWISE_SOLUTION | 2 | 60416 |  |  | 67584 |  |  |  | 104448 | 0 | 0 | 0 |  | 0.894 | 1.01 |
| 6aa20dc0 | NO_PAIRWISE_SOLUTION | 3 | 27648 |  |  | 27648 |  |  |  | 119296 | 0 | 0 | 0 |  | 1 | 1.09 |
| 28e73c20 | NO_PAIRWISE_SOLUTION | 5 | 5568 |  |  | 5568 |  |  |  | 27840 | 0 | 0 | 0 |  | 1 | 0.697 |
| e9614598 | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 1.19 |
| 85c4e7cd | NO_PAIRWISE_SOLUTION | 4 | 165376 |  |  | 185856 |  |  |  | 1127840 | 0 | 0 | 0 |  | 0.89 | 0.983 |
| e8593010 | NO_PAIRWISE_SOLUTION | 3 | 229376 |  |  | 250368 |  |  |  | 900000 | 0 | 0 | 0 |  | 0.916 | 0.999 |
| db93a21d | NO_PAIRWISE_SOLUTION | 4 | 113152 |  |  | 112640 |  |  |  | 924640 | 0 | 0 | 0 |  | 1 | 0.998 |
| 7447852a | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.04 |
| d364b489 | NO_PAIRWISE_SOLUTION | 2 | 112128 |  |  | 111616 |  |  |  | 303104 | 0 | 0 | 0 |  | 1 | 1.02 |
| 1f0c79e5 | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 1.05 |
| 99fa7670 | NO_PAIRWISE_SOLUTION | 4 | 300000 |  |  | 300000 |  |  |  | 1200000 | 0 | 0 | 0 |  | 1 | 0.935 |
| e509e548 | NO_PAIRWISE_SOLUTION | 3 | 39936 |  |  | 40448 |  |  |  | 440832 | 0 | 0 | 0 |  | 0.987 | 1 |
| 3631a71a | NO_PAIRWISE_SOLUTION | 4 | 8704 |  |  | 9216 |  |  |  | 50176 | 0 | 0 | 0 |  | 0.944 | 1.01 |
| 6a1e5592 | NO_PAIRWISE_SOLUTION | 2 | 119296 |  |  | 113152 |  |  |  | 279552 | 0 | 0 | 0 |  | 1.05 | 1 |
| d406998b | NO_PAIRWISE_SOLUTION | 4 | 85504 |  |  | 77312 |  |  |  | 742880 | 0 | 0 | 0 |  | 1.11 | 0.992 |
| 1f642eb9 | NO_PAIRWISE_SOLUTION | 3 | 88064 |  |  | 89088 |  |  |  | 451584 | 0 | 0 | 0 |  | 0.989 | 1 |
| 0962bcdd | NO_PAIRWISE_SOLUTION | 2 | 300000 |  |  | 300000 |  |  |  | 600000 | 0 | 0 | 0 |  | 1 | 0.902 |
| 3befdf3e | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.12 |
| fcc82909 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 270848 |  |  |  | 900000 | 0 | 0 | 0 |  | 1.11 | 0.951 |
| 50846271 | NO_PAIRWISE_SOLUTION | 4 | 17920 |  |  | 17920 |  |  |  | 461280 | 0 | 0 | 0 |  | 1 | 1.03 |
| 7f4411dc | NO_PAIRWISE_SOLUTION | 3 | 42496 |  |  | 41984 |  |  |  | 336384 | 0 | 0 | 0 |  | 1.01 | 1.04 |
| 2204b7a8 | NO_PAIRWISE_SOLUTION | 3 | 49664 |  |  | 47616 |  |  |  | 319488 | 0 | 0 | 0 |  | 1.04 | 0.998 |
| 834ec97d | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.51 |
| 6e82a1ae | NO_PAIRWISE_SOLUTION | 3 | 114176 |  |  | 114688 |  |  |  | 496640 | 0 | 0 | 0 |  | 0.996 | 0.999 |
| b7249182 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.907 |
| 39e1d7f9 | NO_PAIRWISE_SOLUTION | 3 | 30208 |  |  | 28672 |  |  |  | 144896 | 0 | 0 | 0 |  | 1.05 | 1.1 |
| 56dc2b01 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 0.98 |
| 8d510a79 | NO_PAIRWISE_SOLUTION | 2 | 57344 |  |  | 71680 |  |  |  | 130560 | 0 | 0 | 0 |  | 0.8 | 1 |
| d037b0a7 | NO_PAIRWISE_SOLUTION | 3 | 300000 |  |  | 300000 |  |  |  | 900000 | 0 | 0 | 0 |  | 1 | 1.2 |
| 73251a56 | NO_PAIRWISE_SOLUTION | 3 | 23040 |  |  | 23040 |  |  |  | 138240 | 0 | 0 | 0 |  | 1 | 1.07 |
