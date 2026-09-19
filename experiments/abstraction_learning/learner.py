"""Multi-round Explore-Compress learner shared by every abstraction-discovery arm.

The loop is the library-learning half of DreamCoder's wake/sleep cycle on the
frozen core: bounded typed enumeration (Wake), frontier merging under the
current generative grammar, a pluggable compressor (Sleep: abstraction) and the
frozen inside-outside prior fit.  The neural recognition model is deliberately
switched off in this phase so that the *only* difference between arms is the
compressor; every stage is then deterministic given the benchmark instance, and
replication is spent on independent benchmark instances instead of on training
seeds.

Only task names and (input, output) examples enter this module.  It never
imports the benchmark generator or the private evaluation metadata.
"""
import copy
import gzip
import hashlib
import json
import os
import time
from pathlib import Path

from faithful.compression.interface import BridgeKernel
from faithful.python.grid import grammar, REQUEST
from faithful.python.toy import search, learning_frontier
from .compressors import make_compressor, METHODS

# Same bounds as the earlier controlled study except the expanded-state cap, which is
# raised so that the 30000-candidate Wake arms are candidate-limited, not state-limited.
SEARCH = dict(max_states=3000000, max_size=33, maximum_depth=14, upper_bound=100, top_k=3)
WAKE_LIMIT = 3000
ROUNDS = 6
COMPRESSOR_ITERATIONS = 3


def sha(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def save_json(path, value, compact=True):
    """Atomic JSON (optionally gzip) write: a concurrent reader never sees a partial file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, separators=(',', ':')) if compact else json.dumps(value, indent=1)
    temporary = path.with_name(path.name + f'.{os.getpid()}.partial')
    if path.suffix == '.gz':
        with gzip.open(temporary, 'wt', encoding='utf8') as f:
            f.write(text)
    else:
        temporary.write_text(text, encoding='utf8')
    os.replace(temporary, path)


def read_json(path):
    path = Path(path)
    if path.suffix == '.gz':
        with gzip.open(path, 'rt', encoding='utf8') as f:
            return json.load(f)
    return json.loads(path.read_text(encoding='utf8'))


def merge(k, g, old, new, top_k=SEARCH['top_k']):
    """Persistent frontier: union of previous and newly found programs, top-K by prior under ``g``."""
    unique = {sha(e['program']): e for e in old['entries'] + new['entries']}
    entries = list(unique.values())
    scores = {sha(e['program']): k.call('score', grammar=g, request=REQUEST, program=e['program'])['log_probability'] for e in entries}
    return {'request': REQUEST, 'entries': sorted(entries, key=lambda e: scores[sha(e['program'])], reverse=True)[:top_k]}


def round_path(output, iteration):
    return Path(output) / f'round_{iteration}.json.gz'


def run_condition(tasks, method, output, rounds=ROUNDS, wake_limit=WAKE_LIMIT, initial_grammar=None,
                  compressor_iterations=COMPRESSOR_ITERATIONS, label=None, verbose=True):
    """Run ``rounds`` Wake -> Compress -> fit rounds for one method on one task cohort.

    ``method`` is a key of :data:`compressors.METHODS`; oracle arms pass the
    oracle library as ``initial_grammar`` and use method ``'A'`` (prior fit only).
    Completed rounds are cached and resumed by content.
    """
    output = Path(output)
    label = label or method
    if (output / 'complete.json').exists():
        return output
    g = copy.deepcopy(initial_grammar) if initial_grammar is not None else grammar()
    persistent = [{'request': REQUEST, 'entries': []} for _ in tasks]
    assert method in METHODS, method
    with BridgeKernel() as k:
        compressor = make_compressor(method, k, compressor_iterations)
        for r in range(1, rounds + 1):
            path = round_path(output, r)
            if path.exists():
                record = read_json(path)
                g, persistent = record['grammar'], record['frontiers']
                continue
            start = time.perf_counter()
            rows, _ = search(k, tasks, g, g, dict(SEARCH, limit=wake_limit))
            wake_seconds = time.perf_counter() - start
            found = [learning_frontier(row) for row in rows]
            persistent = [merge(k, g, f, new) for f, new in zip(persistent, found)]
            solved = [f for f in persistent if f['entries']]
            start = time.perf_counter()
            result = compressor.compress(persistent, g)
            compression_seconds = time.perf_counter() - start
            g, persistent = result.grammar_updates, result.rewritten_programs
            record = {'iteration': r, 'method': method, 'label': label, 'grammar': g, 'frontiers': persistent,
                      'wake': {'solved': len(solved), 'newly_found': sum(bool(f['entries']) for f in found),
                               'first_solution_nodes': {t.name: row['first_solution_nodes'] for t, row in zip(tasks, rows)},
                               'enumerated_nodes': rows[0]['enumerated_nodes'] if rows else 0,
                               'expanded_states': rows[0]['expanded_states'] if rows else 0,
                               'stop_reason': rows[0]['stop_reason'] if rows else None,
                               'seconds': wake_seconds, 'limit': wake_limit},
                      'compression': {'inventions': result.invented_abstractions, 'mdl': result.mdl_accounting,
                                      'history': result.history, 'statistics': result.statistics, 'seconds': compression_seconds},
                      'library_size': len(g['productions']),
                      'invention_count': sum('invented' in p['program'] for p in g['productions']),
                      'task_names': [t.name for t in tasks],
                      'options': dict(SEARCH, wake_limit=wake_limit, compressor_iterations=compressor_iterations, recognition='off')}
            save_json(path, record)
            if verbose:
                print(f'{label} round {r}: {len(solved)}/{len(tasks)} solved, {record["invention_count"]} inventions, '
                      f'wake {wake_seconds:.1f}s, compression {compression_seconds:.1f}s, '
                      f'dMDL {result.mdl_accounting["delta_mdl"]:.2f}', flush=True)
    save_json(output / 'complete.json', {'rounds': rounds, 'method': method, 'label': label}, compact=False)
    return output
