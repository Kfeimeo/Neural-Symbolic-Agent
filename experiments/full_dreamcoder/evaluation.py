"""Held-out evaluation for the full DreamCoder arm.

Two evaluation modes share the Phase 1 protocol (same held-out tasks, same
10000-candidate uniform-cost enumeration, same bounds, prefix-exact solve
outcomes at every smaller budget, same probe-consistency, effective complexity
and recovery metrics):

* ``library``      the learned generative grammar alone (Phase 1 protocol, one
                   enumeration shared by all held-out tasks): isolates the
                   effect of the learned library.
* ``recognition``  the learned grammar with the round's recognition model: every
                   held-out task is enumerated under its own task-conditioned
                   search grammar and rescored under the generative grammar (the
                   full DreamCoder test-time system).
* ``shuffle``      as ``recognition`` but every task is guided by the features of
                   a different held-out task (derangement): a control for how much
                   of the guided gain is task-specific.

All searches are cached by the full input hash (task I/O, generative grammar,
search grammar, budgets, bounds).  Evaluation-only: reads private metadata.
"""
import random
from pathlib import Path

from faithful.python.grid import features
from faithful.python.toy import search, wire
from experiments.abstraction_learning.learner import sha, save_json, read_json
from experiments.abstraction_learning.evaluation import (BUDGETS, EVAL_SEARCH, budgets_up_to, cached_search,
                                                          effective_complexity, summarize)

MODES = ['library', 'recognition', 'shuffle']


def derangement(n, seed):
    if n < 2:
        raise ValueError('a derangement needs at least two tasks')
    rng = random.Random(seed)
    order = list(range(n))
    while True:
        rng.shuffle(order)
        if all(i != j for i, j in enumerate(order)):
            return order


def guided_cached_search(k, tasks, g, model, cache_dir, limit=max(BUDGETS), guide_tasks=None):
    """Per-task recognition-guided held-out search, cached per task by the full input hash."""
    guide_tasks = tasks if guide_tasks is None else guide_tasks
    rows, seconds, all_cached = [], 0., True
    for t, gt in zip(tasks, guide_tasks):
        sg = model.search_grammar(features(gt))
        key = sha({'tasks': [wire(t)], 'grammar': g, 'search_grammar': sg, 'budgets': budgets_up_to(limit), 'options': EVAL_SEARCH})
        path = Path(cache_dir) / f'{key}.json.gz'
        record = read_json(path) if path.exists() else None
        if record is not None and record['input_hash'] == key:
            rows.extend(record['rows'])
            seconds += record['seconds']
            continue
        rr, s = search(k, [t], g, sg, dict(EVAL_SEARCH, limit=limit))
        save_json(path, {'input_hash': key, 'rows': rr, 'seconds': s, 'budgets': budgets_up_to(limit), 'options': EVAL_SEARCH,
                         'guide_task': gt.name, 'prefix_method': 'uniform-cost enumeration under the fixed search grammar is prefix invariant'})
        rows.extend(rr)
        seconds += s
        all_cached = False
    return rows, seconds, all_cached


def per_task_metrics(k, g, tasks, rows, meta, probes, ground_truth_outputs):
    """Phase 1 per-task record (solve outcome, first-solution rank, probe consistency, ΔL) from search rows."""
    learned = [p for p in g['productions'] if 'invented' in p['program']]
    per_task = []
    for t, row in zip(tasks, rows):
        assert row['name'] == t.name
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
                         'latents': sorted({u['latent'] for u in m['latent_uses'] if u['deliberate']}),
                         'enumerated_nodes': row.get('enumerated_nodes'), 'expanded_states': row.get('expanded_states'), 'stop_reason': row.get('stop_reason')})
    return per_task


def evaluate_mode(k, g, model, mode, tasks, meta, probes, cache_dir, ground_truth_outputs, limit=max(BUDGETS), shuffle_seed=0):
    """Search all held-out tasks under ``g`` in ``mode`` and compute the Phase 1 per-task metrics."""
    guide = None
    if mode == 'library':
        rows, seconds, cached = cached_search(k, tasks, g, cache_dir, limit)
    else:
        if mode == 'shuffle':
            order = derangement(len(tasks), shuffle_seed)
            guide = [tasks[j] for j in order]
        rows, seconds, cached = guided_cached_search(k, tasks, g, model, cache_dir, limit, guide_tasks=guide)
    per_task = per_task_metrics(k, g, tasks, rows, meta, probes, ground_truth_outputs)
    batch = {'mode': mode, 'seconds': seconds, 'cached': cached, 'limit': limit, 'budgets': budgets_up_to(limit),
             'enumerated_nodes': rows[0]['enumerated_nodes'] if rows else 0, 'expanded_states': rows[0]['expanded_states'] if rows else 0,
             'stop_reason': rows[0]['stop_reason'] if rows else None,
             'per_task_searches': len(rows) if mode != 'library' else 1,
             'guide_tasks': [t.name for t in guide] if guide else None,
             'max_expanded_states': max(r['expanded_states'] for r in rows) if rows else 0,
             'state_limited_tasks': sum(r['stop_reason'] != 'candidate_budget' for r in rows) if rows else 0}
    return per_task, batch, summarize(per_task, limit)
