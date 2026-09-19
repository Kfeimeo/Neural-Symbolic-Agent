# Protocol v1

Transport: a persistent Haskell process, UTF-8 JSON, one request/response per line.
Python never substitutes a symbolic solver if the process fails. Build with
`python -m faithful.python.kernel` from the repository root.

Every request contains `version: 1` and `operation`. Response:
`{"version":1,"ok":true,"result":...}` or `ok:false,error:string`.
Malformed requests and unknown versions are errors, not empty successful results.

Types: `{"var":0}` or `{"constructor":"grid","arguments":[]}`;
arrows use `constructor:"->",arguments:[domain,codomain]`.
Primitive schemes universally quantify their type variables. Environment entries
are monomorphic bound-variable types, most recent binder first.

AST alternatives (exactly one key):

* `primitive`: primitive name
* `index`: nonnegative de Bruijn index
* `application`: `[function,argument]`
* `abstraction`: body
* `invented`: closed body (definitions retained recursively)

Grammar: `log_variable`, `productions:[{program,type,log_weight}]`.
Weights are unnormalized log weights. Optional `contexts` maps context names to
vectors `[variable,production1,...]`. `root`, `variable`, and `i:a` denote the
root, variable parent, and production i's argument a (i is one-based, a zero-based).
Lambdas preserve the parent context. Missing context vectors inherit base weights.

Operations:

| Operation | Additional request | Result |
|---|---|---|
| unify | left, right | unified canonical type; failure is an error |
| infer | grammar, program, optional environment | canonical principal type and unchanged AST |
| beta | program | β-normal form, inventions expanded |
| score | grammar, request, program, optional environment | full log probability and per-expansion sufficient-statistic events |
| enumerate | grammar, optional search_grammar, request, environment, upper_bound, maximum_depth, limit | probability-sorted programs, generative log_prior, separate search_log_score, bounded_complete, candidates_in_bound |
| enumerate_budget | same, plus max_size and max_states | uniform-cost prefix with real complete-program/state caps, stop_reason and expanded_states |
| search_tasks | grammar, search_grammar, request, tasks, enumeration budgets, top_k | Haskell I/O filtering; per-task frontier, first solution rank, separate scores and batch search statistics |
| evaluate_batch | program, input_sets | results aligned to inputs; failed evaluations represented by null |
| frontier | grammar, frontier | log marginal, per-entry generative prior, likelihood, normalized posterior |
| update | base grammar, frontiers, positive pseudo_counts, iterations | updated grammar using fresh expected statistics each iteration |
| evaluate | program, inputs | concrete value; currently the separate Grid evaluator and tiny test primitives |
| sample | grammar, request, uniforms | ancestral sample and generative log probability; exhausted randomness is a failed draw |
| versions | program, arity | explicit finite inverse-β versions |
| compression_candidates | grammar, frontiers, arity | closed invented candidates |
| compress | grammar, frontiers, arity, iterations, pseudo_counts, aic, structure_penalty | updated grammar, rewritten frontiers, improvement history |

A frontier is `{request,entries:[{program,log_likelihood}]}`. Unsatisfied
deterministic programs are omitted. Extra entry metadata is not used by learning.
No operation takes ground-truth labels for real held-out tasks.

Enumeration traverses the complete finite cost/depth bound before sorting and
returning `limit` entries. `limit` is an output budget, **not** a bound on work.
`bounded_complete` refers only to this finite bound, never the unbounded language.
The toy runner uses `enumerate_budget`/`search_tasks`, not exhaustive `enumerate`.
For these operations size counts primitive/invented/index leaves (matching the
old first-order DSL size), not application/lambda scaffolding. State counts include
popped complete states. Tasks contain `{name,examples:[{inputs:[...],output:...}]}`.
The same candidate stream can service several tasks; reported wall time is the
whole batch's measured time, not an invented per-task time estimate.
Maximum depth follows the official Python enumerator's convention. Costs are
never renormalized by depth/size/output limits. There is no wall-clock cancellation
inside the kernel yet; use an external process timeout for untrusted large bounds.

Sampling consumes independent uniform values in [0,1), without forced terminals.
Insufficient fuel rejects that draw; rejection counts must be retained. Accepted
draws under finite fuel are conditional on termination within that fuel. No claim
is made that discarding such failures leaves the unconditional distribution intact.

Non-finite result numbers serialize as null (e.g. an empty frontier log marginal).
Requests require finite numeric weights and likelihoods; omit impossible entries.
