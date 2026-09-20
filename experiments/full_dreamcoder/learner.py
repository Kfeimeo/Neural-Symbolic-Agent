"""Full faithful DreamCoder learner: the Phase 1 Explore-Compress loop with the recognition pathway enabled.

Phase 1 (``experiments/abstraction_learning/learner.py``) ran Wake -> Compress ->
prior fit with the neural recognition model deliberately switched off.  This module
runs *exactly* the same loop (same bounded typed enumeration, same persistent
top-K frontiers, same frozen DreamCoder compressor and inside-outside fit, same
budgets) and adds the accepted faithful recognition recipe of the frozen core
(``faithful/python/controlled_learner.py``, arm D):

* Dream: ancestral draws from the current generative grammar, executed on the
  inputs of the first training task; failed draws are counted, never replaced.
* Replay: the actual persistent frontiers (rewritten under the current library).
* Recognition: a fresh task-conditioned AST-bigram model per round, trained with
  the ``frontierBiasOptimal`` objective on Replay + Dream data.
* Guided Wake: from round 2 on, every training task is enumerated under its own
  task-conditioned search grammar; solutions are rescored under the generative
  grammar before frontier merging (guidance and posterior stay separate).

Round 1 has no trained model yet and therefore reproduces the Phase 1 B round 1
exactly (checked in the analysis as a parity test).  Nothing in this module reads
the latent library or private metadata; only task names and I/O enter.
"""
import copy
import random
import time
from pathlib import Path

import torch

from faithful.compression.interface import BridgeKernel
from faithful.python.grid import grammar, REQUEST, features
from faithful.python.recognition import Recognition
from faithful.python.ec import dream
from faithful.python.toy import search, learning_frontier
from experiments.abstraction_learning.learner import (SEARCH, WAKE_LIMIT, ROUNDS, COMPRESSOR_ITERATIONS,
                                                       merge, save_json, read_json, round_path)
from experiments.abstraction_learning.compressors import make_compressor, METHODS

# Accepted recognition recipe of the frozen core (controlled study): 64 ancestral Dream
# draws per round, 600 optimizer steps of the unchanged bias-optimal objective, a fresh
# network every round.  These are the only additions to the Phase 1 loop.
DREAM_DRAWS = 64
RECOGNITION_STEPS = 600
RECOGNITION_OBJECTIVE = 'bias_optimal'


def checkpoint_path(output, iteration):
    return Path(output) / f'round_{iteration}_recognition.pt'


def load_model(output, iteration, g):
    """Recognition model saved after ``iteration``; its grammar must be the round's grammar."""
    checkpoint = torch.load(checkpoint_path(output, iteration), map_location='cpu', weights_only=True)
    assert checkpoint['grammar'] == g, 'checkpoint grammar differs from the round grammar'
    model = Recognition(g, device='cpu')
    model.load_state_dict(checkpoint['state_dict'])
    model.eval()
    return model


def guided_search(k, tasks, g, model, options, guide_tasks=None):
    """One enumeration per task under its task-conditioned search grammar, rescored under ``g``.

    ``guide_tasks`` (same length as ``tasks``) selects whose features condition each
    search; the default is the task itself, a derangement gives the shuffle control.
    """
    guide_tasks = tasks if guide_tasks is None else guide_tasks
    rows, seconds, guidance = [], 0., 0.
    for t, gt in zip(tasks, guide_tasks):
        start = time.perf_counter()
        sg = model.search_grammar(features(gt))
        guidance += time.perf_counter() - start
        rr, s = search(k, [t], g, sg, options)
        rows.extend(rr)
        seconds += s
    return rows, seconds, guidance


def tuples(x):
    return tuple(map(tuples, x)) if isinstance(x, list) else x


def run_condition(tasks, method, output, rounds=ROUNDS, wake_limit=WAKE_LIMIT, seed=1, initial_grammar=None,
                  compressor_iterations=COMPRESSOR_ITERATIONS, dream_draws=DREAM_DRAWS,
                  recognition_steps=RECOGNITION_STEPS, label=None, verbose=True):
    """Run ``rounds`` guided Wake -> Compress -> fit -> Dream/Replay -> recognition rounds.

    ``seed`` is the training seed of the stochastic stages (Dream draws, network
    initialisation, replay sampling).  Completed rounds are cached on disk together
    with the RNG state and the recognition checkpoint and are resumed exactly.
    """
    output = Path(output)
    label = label or method
    if (output / 'complete.json').exists():
        return output
    assert method in METHODS, method
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    g = copy.deepcopy(initial_grammar) if initial_grammar is not None else grammar()
    persistent = [{'request': REQUEST, 'entries': []} for _ in tasks]
    rng = random.Random(seed)
    model = None
    dream_inputs = [e[0][0] for e in tasks[0].examples]
    with BridgeKernel() as k:
        compressor = make_compressor(method, k, compressor_iterations)
        for r in range(1, rounds + 1):
            path = round_path(output, r)
            if path.exists():
                record = read_json(path)
                g, persistent = record['grammar'], record['frontiers']
                rng.setstate(tuples(record['rng_state']))
                model = load_model(output, r, g)
                continue
            # ---- Wake: guided by the previous round's recognition model (none in round 1)
            start = time.perf_counter()
            options = dict(SEARCH, limit=wake_limit)
            guided = model is not None
            if not guided:
                rows, _ = search(k, tasks, g, g, options)
                guidance_seconds = 0.
            else:
                rows, _, guidance_seconds = guided_search(k, tasks, g, model, options)
            wake_seconds = time.perf_counter() - start
            found = [learning_frontier(row) for row in rows]
            persistent = [merge(k, g, f, new) for f, new in zip(persistent, found)]
            solved = [f for f in persistent if f['entries']]
            # ---- Sleep (abstraction): the unchanged Phase 1 compressor and prior fit
            start = time.perf_counter()
            result = compressor.compress(persistent, g)
            compression_seconds = time.perf_counter() - start
            g, persistent = result.grammar_updates, result.rewritten_programs
            # ---- Sleep (dreaming): ancestral Dream + Replay, fresh recognition network
            start = time.perf_counter()
            dreamed, dream_stats = dream(k, g, REQUEST, dream_inputs, rng, draws=dream_draws)
            dream_seconds = time.perf_counter() - start
            replay = [(features(t), f) for t, f in zip(tasks, persistent) if f['entries']]
            start = time.perf_counter()
            torch.manual_seed(seed + 1000 + r * 10000)
            model = Recognition(g, device='cpu')
            losses = model.fit_frontiers(k, replay + dreamed, steps=recognition_steps, seed=seed + r, objective=RECOGNITION_OBJECTIVE)
            model.eval()
            recognition_seconds = time.perf_counter() - start
            output.mkdir(parents=True, exist_ok=True)
            torch.save({'grammar': g, 'state_dict': model.state_dict()}, checkpoint_path(output, r))
            record = {'iteration': r, 'method': method, 'label': label, 'training_seed': seed, 'grammar': g, 'frontiers': persistent,
                      'wake': {'solved': len(solved), 'newly_found': sum(bool(f['entries']) for f in found),
                               'first_solution_nodes': {t.name: row['first_solution_nodes'] for t, row in zip(tasks, rows)},
                               'per_task': {t.name: {'enumerated_nodes': row['enumerated_nodes'], 'expanded_states': row['expanded_states'],
                                                     'stop_reason': row['stop_reason']} for t, row in zip(tasks, rows)},
                               'enumerated_nodes': rows[0]['enumerated_nodes'] if rows else 0,
                               'expanded_states': rows[0]['expanded_states'] if rows else 0,
                               'stop_reason': rows[0]['stop_reason'] if rows else None,
                               'guided': guided, 'seconds': wake_seconds, 'guidance_seconds': guidance_seconds, 'limit': wake_limit},
                      'compression': {'inventions': result.invented_abstractions, 'mdl': result.mdl_accounting,
                                      'history': result.history, 'statistics': result.statistics, 'seconds': compression_seconds},
                      'dream': dict(dream_stats, seconds=dream_seconds, inputs=len(dream_inputs)),
                      'recognition': {'steps': recognition_steps, 'objective': RECOGNITION_OBJECTIVE, 'replay_frontiers': len(replay),
                                      'dream_frontiers': len(dreamed), 'losses': losses, 'seconds': recognition_seconds,
                                      'initialization_seed': seed + 1000 + r * 10000, 'context_count': len(model.keys)},
                      'library_size': len(g['productions']),
                      'invention_count': sum('invented' in p['program'] for p in g['productions']),
                      'task_names': [t.name for t in tasks], 'rng_state': rng.getstate(),
                      'options': dict(SEARCH, wake_limit=wake_limit, compressor_iterations=compressor_iterations, recognition='on',
                                      dream_draws=dream_draws, recognition_steps=recognition_steps, training_seed=seed)}
            save_json(path, record)
            if verbose:
                print(f'{label} round {r}: {len(solved)}/{len(tasks)} solved, {record["invention_count"]} inventions, '
                      f'wake {wake_seconds:.1f}s (guided={record["wake"]["guided"]}), compression {compression_seconds:.1f}s, '
                      f'dream {dream_stats["accepted"]}/{dream_stats["draws"]}, recognition {recognition_seconds:.1f}s, '
                      f'dMDL {result.mdl_accounting["delta_mdl"]:.2f}', flush=True)
    save_json(output / 'complete.json', {'rounds': rounds, 'method': method, 'label': label, 'training_seed': seed, 'recognition': 'on'}, compact=False)
    return output
