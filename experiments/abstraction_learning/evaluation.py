"""Held-out evaluation, abstraction recovery and effective-complexity metrics.

Evaluation-only module: it reads the private benchmark metadata and the latent
library.  Nothing computed here is ever passed back into a learner.

Abstraction recovery compares every learned invention with every *active*
latent of the cohort (latents deliberately used by the generator in that
cohort's training or held-out tasks) under five criteria:

* ``syntactic``  identical body,
* ``canonical``  identical body after canonicalization (dihedral group,
  involutions, identity/constant argument rules) of the beta-normal form,
* ``beta``       identical beta-normal form,
* ``type``       identical polymorphic type (``type_permuted`` also accepts the
  same argument types in another order),
* ``behavioral`` type-compatible (up to argument order) and identical outputs on
  the independent recovery probes for every valid parameter value of the latent.

Precision counts learned inventions matching some active latent, recall counts
active latents matched by some invention, and weighted recall weights latents
by their deliberate held-out occurrence count.  An invention with *more*
parameters than a latent is not counted as recovering it (subsumption is not
credited), and finite probes are witnesses, not an equivalence proof.
"""
import collections
import statistics
from pathlib import Path

from faithful.python.toy import search, wire
from faithful.python.controlled_metrics import best_rewrite, canonical_ast
from .learner import sha, save_json, read_json

# Memory of one search grows with the agenda: 30000 candidates need ~1M states and ~10 GB
# with the high-cohort oracle grammar, and the 36-production low-cohort oracle grammar
# (uniform weights) already needs ~580k states and ~9 GB for 10000 candidates. The
# maximum budget is therefore 10000 candidates, as in the earlier controlled study.
BUDGETS = [100, 300, 1000, 3000, 10000]
EVAL_SEARCH = dict(max_states=3000000, max_size=33, maximum_depth=14, upper_bound=100, top_k=3)
VALUE = {'red': 1, 'blue': 2, 'green': 3, 'zero': 0, 'one': 1, 'minus_one': -1}
CRITERIA = ['syntactic', 'canonical', 'beta', 'type', 'type_permuted', 'behavioral']


def budgets_up_to(limit):
    return [n for n in BUDGETS if n <= limit]


def cached_search(k, tasks, g, cache_dir, limit=max(BUDGETS)):
    """Held-out search with ``limit`` complete candidates; cached by the full input hash.

    Uniform-cost enumeration is prefix invariant, so one search at ``limit`` gives
    the exact solve outcome at every smaller budget.
    """
    rows_in = [wire(t) for t in tasks]
    key = sha({'tasks': rows_in, 'grammar': g, 'budgets': budgets_up_to(limit), 'options': EVAL_SEARCH})
    path = Path(cache_dir) / f'{key}.json.gz'
    if path.exists():
        record = read_json(path)
        if record['input_hash'] == key:
            return record['rows'], record['seconds'], True
    rows, seconds = search(k, tasks, g, g, dict(EVAL_SEARCH, limit=limit))
    save_json(path, {'input_hash': key, 'rows': rows, 'seconds': seconds, 'budgets': budgets_up_to(limit), 'options': EVAL_SEARCH,
                     'prefix_method': 'uniform-cost enumeration is prefix invariant: first_solution_nodes <= N gives the exact solve outcome at budget N'})
    return rows, seconds, False


def arg_types(t):
    args = []
    while t.get('constructor') == '->':
        a, t = t['arguments']
        args.append(a)
    return args, t


def type_name(t):
    return t.get('constructor') if 'constructor' in t else f"var{t.get('var')}"


def outputs(k, program, argtypes, probes, values):
    """Evaluate ``program`` on every (value, probe) pair, feeding arguments by type.

    Grid arguments receive the probe, colour/integer arguments the parameter
    value; this makes the comparison invariant to argument order.
    """
    sets = []
    for v in values:
        for x in probes:
            inputs = []
            for a in argtypes:
                n = type_name(a)
                if n == 'grid':
                    inputs.append(x)
                elif n in ('color', 'int') and v is not None:
                    inputs.append(v)
                else:
                    return None
            sets.append(inputs)
    ys = k.call('evaluate_batch', program=program, input_sets=sets)['values']
    return None if any(y is None for y in ys) else ys


def recovery(k, g, latents, regime, probes):
    learned = [p for p in g['productions'] if 'invented' in p['program']]
    active = [f for f in latents if f['reuse'][regime]['deliberate_active']]
    normal_learned = [k.call('beta', program=p['program'])['program'] for p in learned]
    pairs = {name: [] for name in CRITERIA}
    for i, f in enumerate(active):
        f_args, f_res = arg_types(f['type'])
        values = [VALUE[v] for v in f['parameter_values']] if f['parameter_values'] else [None]
        expected = outputs(k, f['body'], f_args, probes, values)
        normal_f = k.call('beta', program=f['body'])['program']
        canonical_f = canonical_ast(normal_f)
        for j, (p, normal_p) in enumerate(zip(learned, normal_learned)):
            p_args, p_res = arg_types(p['type'])
            same_type = p['type'] == f['type']
            permuted = (not same_type) and p_res == f_res and sorted(map(type_name, p_args)) == sorted(map(type_name, f_args))
            behavioral = False
            if (same_type or permuted) and expected is not None:
                behavioral = outputs(k, p['program'], p_args, probes, values) == expected
            matches = {'syntactic': p['program']['invented'] == f['body'], 'canonical': canonical_ast(normal_p) == canonical_f,
                       'beta': normal_p == normal_f, 'type': same_type, 'type_permuted': same_type or permuted, 'behavioral': behavioral}
            for name, yes in matches.items():
                if yes:
                    pairs[name].append([i, j])
    metrics = {}
    total_weight = sum(f['reuse'][regime]['test_deliberate_count'] for f in active)
    for name, ps in pairs.items():
        recovered, matched = {i for i, _ in ps}, {j for _, j in ps}
        precision = len(matched) / len(learned) if learned else None
        recall = len(recovered) / len(active) if active else None
        if precision is None or recall is None:
            f1 = None
        else:
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.
        metrics[name] = {'precision': precision, 'recall': recall, 'f1': f1,
                         'weighted_recall': sum(active[i]['reuse'][regime]['test_deliberate_count'] for i in recovered) / total_weight if total_weight else None,
                         'recovered_latents': sorted(active[i]['id'] for i in recovered), 'pairs': ps}
    return {'learned_count': len(learned), 'active_latents': [f['id'] for f in active], 'metrics': metrics,
            'learned_inventions': [{'program': p['program'], 'type': p['type'], 'beta': n} for p, n in zip(learned, normal_learned)],
            'notes': ['type agreement alone is not recovery', 'behavioural equality on finite probes is a witness, not a proof',
                      'inventions with more parameters than a latent are not credited (no subsumption)']}


def effective_complexity(k, meta_task, learned):
    r = best_rewrite(k, meta_task['ground_truth'], learned)
    return {'base_leaf_size': r['base_leaf_size'], 'effective_leaf_size': r['effective_leaf_size'], 'delta_L': r['delta_L'],
            'base_ast_depth': r['base_ast_depth'], 'effective_ast_depth': r['effective_ast_depth'], 'delta_d': r['delta_d']}


def frontier_support(k, frontiers, task_names, active):
    """Evaluation-only exposure diagnostic: training tasks whose frontier structurally contains each latent."""
    support = {}
    for f in active:
        production = [{'program': f['program'], 'type': f['type']}]
        tasks = [n for n, fr in zip(task_names, frontiers) if any(best_rewrite(k, e['program'], production)['delta_L'] > 0 for e in fr['entries'])]
        support[f['id']] = {'tasks': tasks, 'count': len(tasks), 'minimum_two_task_support': len(tasks) >= 2}
    return support


def solve_curve(per_task, budgets=BUDGETS):
    if not per_task:
        return {str(n): None for n in budgets}
    return {str(n): sum(t['first_solution_nodes'] is not None and t['first_solution_nodes'] <= n for t in per_task) / len(per_task) for n in budgets}


def stratified(per_task, field, budgets=BUDGETS):
    groups = collections.defaultdict(list)
    for t in per_task:
        groups[str(t[field])].append(t)
    return {value: dict(count=len(rows), **solve_curve(rows, budgets)) for value, rows in sorted(groups.items())}


def evaluate_grammar(k, g, tasks, meta, probes, cache_dir, ground_truth_outputs, limit=max(BUDGETS)):
    """Search all held-out tasks under ``g`` and compute per-task synthesis and complexity metrics."""
    rows, seconds, cached = cached_search(k, tasks, g, cache_dir, limit)
    learned = [p for p in g['productions'] if 'invented' in p['program']]
    per_task = []
    for t, row in zip(tasks, rows):
        m = meta[t.name]
        ec = effective_complexity(k, m, learned)
        solved = row['first_solution_nodes'] is not None
        consistent = False
        if solved:
            expected = ground_truth_outputs[t.name]
            for s in row['solutions']:
                ys = k.call('evaluate_batch', program=s['program'], input_sets=[[x] for x in probes])['values']
                if ys == expected:
                    consistent = True
                    break
        per_task.append({'name': t.name, 'depth': m['depth'], 'transfer': m['transfer'], 'first_solution_nodes': row['first_solution_nodes'],
                         'solved': solved, 'probe_consistent': consistent,
                         'solutions': [{'program': s['program'], 'search_rank': s['search_rank'], 'log_prior': s['log_prior']} for s in row['solutions']],
                         'delta_L': ec['delta_L'], 'effective_leaf_size': ec['effective_leaf_size'], 'base_leaf_size': ec['base_leaf_size'],
                         'delta_d': ec['delta_d'], 'effective_ast_depth': ec['effective_ast_depth'],
                         'true_delta_L': m['effective_complexity']['delta_L'], 'true_effective_leaf_size': m['effective_complexity']['effective_leaf_size'],
                         'latents': sorted({u['latent'] for u in m['latent_uses'] if u['deliberate']})})
    batch = {'enumerated_nodes': rows[0]['enumerated_nodes'] if rows else 0, 'expanded_states': rows[0]['expanded_states'] if rows else 0,
             'stop_reason': rows[0]['stop_reason'] if rows else None, 'seconds': seconds, 'cached': cached, 'limit': limit,
             'budgets': budgets_up_to(limit)}
    return per_task, batch


def summarize(per_task, limit=max(BUDGETS)):
    solved = [t for t in per_task if t['solved']]
    budgets = budgets_up_to(limit)
    return {'task_count': len(per_task), 'solved_at_max_budget': len(solved), 'limit': limit, 'curve': solve_curve(per_task, budgets),
            'by_depth': stratified(per_task, 'depth', budgets), 'by_transfer': stratified(per_task, 'transfer', budgets),
            'probe_consistent_rate': sum(t['probe_consistent'] for t in per_task) / len(per_task) if per_task else None,
            'mean_first_solution_nodes_solved': statistics.mean(t['first_solution_nodes'] for t in solved) if solved else None,
            'median_first_solution_nodes_solved': statistics.median(t['first_solution_nodes'] for t in solved) if solved else None,
            'mean_delta_L': statistics.mean(t['delta_L'] for t in per_task) if per_task else None,
            'fraction_shortened': sum(t['delta_L'] > 0 for t in per_task) / len(per_task) if per_task else None,
            'mean_true_delta_L': statistics.mean(t['true_delta_L'] for t in per_task) if per_task else None,
            'solve_rate_when_shortened': (sum(t['solved'] for t in per_task if t['delta_L'] > 0) / sum(t['delta_L'] > 0 for t in per_task)) if any(t['delta_L'] > 0 for t in per_task) else None,
            'solve_rate_when_not_shortened': (sum(t['solved'] for t in per_task if t['delta_L'] <= 0) / sum(t['delta_L'] <= 0 for t in per_task)) if any(t['delta_L'] <= 0 for t in per_task) else None}
