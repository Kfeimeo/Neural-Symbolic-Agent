"""I/O-only controlled runner. No imports of generator/evaluation modules.

All symbolic operations and all recognition objectives use the accepted core.
Configuration switches enable/disable mechanisms; they do not replace them.
"""
import copy
import hashlib
import json
import random
import time
from pathlib import Path
import torch
from .kernel import Kernel
from .grid import Task, grammar, REQUEST, features
from .recognition import Recognition
from .ec import dream
from .toy import search, learning_frontier, save

SEARCH = dict(max_states=500000, max_size=33, maximum_depth=14, upper_bound=100, top_k=3)
TRAIN_NODES = 3000
STEPS = 600
DREAM_DRAWS = 64


def load_io(path):
    data = json.loads(Path(path).read_text(encoding='utf8'))
    assert all(set(t) == {'name', 'examples'} for t in data)
    return [Task(t['name'], [(e['inputs'], e['output']) for e in t['examples']]) for t in data]


def sha(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def merge(k, g, old, new):
    unique = {sha(e['program']): e for e in old['entries'] + new['entries']}
    entries = list(unique.values())
    scores = {sha(e['program']): k.call('score', grammar=g, request=REQUEST, program=e['program'])['log_probability'] for e in entries}
    return {'request': REQUEST, 'entries': sorted(entries, key=lambda e: scores[sha(e['program'])], reverse=True)[:SEARCH['top_k']]}


def train_condition(tasks, label, seed, output, rounds=5):
    """Only Task I/O enters Wake, Replay, Dream, compression and recognition."""
    output = Path(output)
    if (output/'complete.json').exists(): return
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    g = grammar()
    model = None
    rng = random.Random(seed)
    persistent = [{'request': REQUEST, 'entries': []} for _ in tasks]
    library = label in ['B', 'D']
    recognition = label in ['C', 'D']
    with Kernel() as k:
        for r in range(1, rounds+1):
            folder = output / f'round_{r}'
            if (folder/'round.json').exists():
                record = json.loads((folder/'round.json').read_text())
                g = record['grammar']; persistent = record['frontiers']
                # Restore RNG exactly, including failed dream draws.
                def tuples(x): return tuple(map(tuples, x)) if isinstance(x, list) else x
                rng.setstate(tuples(record['rng_state']))
                if recognition:
                    model = Recognition(g)
                    checkpoint = torch.load(folder/'recognition.pt', map_location=model.device, weights_only=True)
                    model.load_state_dict(checkpoint['state_dict'])
                continue
            print(f'{label} seed={seed} round={r} wake ({len(tasks)} tasks)', flush=True)
            start = time.perf_counter()
            if model is None:
                rows, _ = search(k, tasks, g, g, dict(SEARCH, limit=TRAIN_NODES))
            else:
                rows = []
                for t in tasks:
                    rr, _ = search(k, [t], g, model.search_grammar(features(t)), dict(SEARCH, limit=TRAIN_NODES))
                    rows.extend(rr)
            persistent = [merge(k, g, f, learning_frontier(row)) for f, row in zip(persistent, rows)]
            times = {'wake_seconds': time.perf_counter()-start}
            solved = [f for f in persistent if f['entries']]
            start = time.perf_counter()
            if library:
                result = k.call('compress', grammar=g, frontiers=solved, arity=1, iterations=3)
                g = result['grammar']
                it = iter(result['frontiers'])
                persistent = [next(it) if f['entries'] else f for f in persistent]
                history = result['history']
            elif label == 'E':
                g = k.call('update', grammar=g, frontiers=solved, iterations=1)
                history = []
            else:
                history = []
            times['compression_or_prior_seconds'] = time.perf_counter()-start
            # Accepted EC recipe: ancestral Dream, actual posterior frontiers for
            # Replay, fresh recognition network each round, unchanged loss.
            start = time.perf_counter()
            dreamed, stats = dream(k, g, REQUEST, [e[0][0] for e in tasks[0].examples], rng, draws=DREAM_DRAWS)
            times['dream_seconds'] = time.perf_counter()-start
            replay = [(features(t), f) for t, f in zip(tasks, persistent) if f['entries']]
            start = time.perf_counter()
            losses = []
            if recognition:
                torch.manual_seed(seed + 1000 + r * 10000)
                model = Recognition(g)
                losses = model.fit_frontiers(k, replay+dreamed, steps=STEPS, seed=seed+r)
                folder.mkdir(parents=True, exist_ok=True)
                torch.save({'grammar': g, 'state_dict': model.state_dict(), 'device': str(model.device)}, folder/'recognition.pt')
            times['recognition_seconds'] = time.perf_counter()-start
            marginals = [k.call('frontier', grammar=g, frontier=f)['log_marginal'] for f in persistent if f['entries']]
            def leaf(p):
                if 'application' in p: return sum(map(leaf, p['application']))
                if 'abstraction' in p: return leaf(p['abstraction'])
                return 1
            penalty = len(g['productions']) + .001 * sum(leaf(p['program'].get('invented', p['program'])) for p in g['productions'])
            save(folder/'dreams.json', {'stats': stats, 'inputs': [e[0][0] for e in tasks[0].examples],
                'feature_frontier_pairs': [{'features': x.tolist(), 'frontier': f} for x, f in dreamed]})
            save(folder/'round.json', {'iteration': r, 'label': label, 'training_seed': seed,
                'recognition_initialization_seed': seed+1000+r*10000, 'grammar': g, 'frontiers': persistent,
                'recognition_device': str(model.device) if model is not None else None,
                'task_names': [t.name for t in tasks], 'compression_history': history, 'timings': times,
                'recognition_losses': losses, 'dream': stats, 'solved_training_tasks': len(solved),
                'library_objective': sum(marginals)-penalty, 'frontier_log_marginal': sum(marginals),
                'rng_state': rng.getstate(), 'options': dict(SEARCH, training_nodes=TRAIN_NODES, compression_arity=1, compression_iterations=3, recognition_steps=STEPS)})
            print(f'{label} seed={seed} round={r}: {len(solved)}/{len(tasks)} solved, {len(g["productions"])-24} inventions, {times}', flush=True)
    save(output/'complete.json', {'rounds': rounds})


def derangement(n, seed):
    if n < 2: raise ValueError('Derangement needs at least two tasks')
    rng = random.Random(seed)
    order = list(range(n))
    while True:
        rng.shuffle(order)
        if all(i != j for i, j in enumerate(order)): return order


def evaluate_job(job):
    """Standalone cached worker; only I/O and an already selected grammar."""
    path, task_rows, g, sg, budgets = job
    path = Path(path)
    expected = sha({'tasks': task_rows, 'grammar': g, 'search_grammar': sg, 'budgets': budgets, 'options': SEARCH})
    if path.exists():
        try: result = json.loads(path.read_text())
        except json.JSONDecodeError: result = None  # Interrupted cache write; recompute exactly.
        if result is not None:
            if result['input_hash'] != expected: raise ValueError('Stale search cache')
            return str(path)
    tasks = [Task(t['name'], [(e['inputs'], e['output']) for e in t['examples']]) for t in task_rows]
    with Kernel() as k:
        rows, seconds = search(k, tasks, g, sg, dict(SEARCH, limit=max(budgets)))
    # Uniform-cost enumeration is prefix invariant under the complete-candidate
    # cap. First-solution ranks give exact SolveRate(N) for every shorter prefix.
    # We do not claim smaller-budget frontier membership from the max-budget top K.
    temporary = path.with_suffix('.partial')
    save(temporary, {'input_hash': expected, 'rows': rows, 'seconds': seconds, 'budgets': budgets,
        'prefix_method': 'first_solution_nodes <= N, exact under fixed grammar/bounds/state cap'})
    temporary.replace(path)
    return str(path)
