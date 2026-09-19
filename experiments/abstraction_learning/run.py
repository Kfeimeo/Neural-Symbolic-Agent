"""Experiment pipeline for the abstraction-learning study.

::

    python -m experiments.abstraction_learning.run benchmark      # generate, A0-calibrate and freeze the instances
    python -m experiments.abstraction_learning.run train          # every arm x cohort x instance (EC loops)
    python -m experiments.abstraction_learning.run perfect-wake   # compression on ground-truth training programs
    python -m experiments.abstraction_learning.run evaluate       # held-out evaluation of every saved grammar
    python -m experiments.abstraction_learning.run analyze        # aggregate into results/*.json
    python -m experiments.abstraction_learning.run all

The protocol (arms, rounds, budgets, seeds) is written to ``results/abstraction_learning/protocol.json``
before any arm runs and is never edited afterwards.  Learners receive task names and
I/O only; the oracle arms and the evaluation stage are the only readers of the
latent library and private metadata.
"""
import argparse
import concurrent.futures
import copy
import json
import time
from pathlib import Path

from faithful.compression.interface import BridgeKernel, ROOT
from faithful.python.grid import grammar, REQUEST
from benchmarks.latent_abstraction import generator as bench
from .learner import run_condition, read_json, save_json, round_path, ROUNDS, WAKE_LIMIT, SEARCH
from .evaluation import recovery, frontier_support, evaluate_grammar, summarize, BUDGETS, EVAL_SEARCH
from .compressors import METHODS, DESCRIPTIONS, make_compressor, STITCH_CONFIGS, STITCH_ITERATIONS

RESULTS = ROOT / 'results' / 'abstraction_learning'
DATA = bench.DATA
SEEDS = bench.DEFAULT_SEEDS
REGIMES = bench.REGIMES
ARMS = {
    'A': dict(method='A', wake=WAKE_LIMIT, oracle=False, group='main'),
    'B': dict(method='B', wake=WAKE_LIMIT, oracle=False, group='main'),
    'C': dict(method='C', wake=WAKE_LIMIT, oracle=False, group='main'),
    'D': dict(method='D', wake=WAKE_LIMIT, oracle=False, group='main'),
    'E': dict(method='E', wake=WAKE_LIMIT, oracle=False, group='main'),
    'O': dict(method='A', wake=WAKE_LIMIT, oracle=True, group='main'),
    'B_wake10000': dict(method='B', wake=10000, oracle=False, group='exposure'),
    'D_wake10000': dict(method='D', wake=10000, oracle=False, group='exposure'),
}
# A 30000-candidate Wake needs ~1M agenda states and ~10 GB of kernel memory per process on
# this machine (measured), so the exposure sub-experiment stops at 10000 candidates.
STATIC = ['A0', 'O_uniform']
INTERMEDIATE_BUDGET = 10000   # rounds 1..ROUNDS-1 are searched to 10000 candidates; final, static and perfect-Wake grammars to 30000
PERFECT_WAKE_METHODS = ['B', 'C', 'D', 'E']
PERFECT_WAKE_ITERATIONS = 12


def instance_dir(seed):
    return DATA / f'seed_{seed}'


def cohort_tasks(seed, split, regime):
    """Learner-facing selection by task name prefix only."""
    return [t for t in bench.load_tasks(instance_dir(seed) / f'{split}.json') if t.name.startswith(f'{split}-{regime}-')]


def oracle_grammar(seed, regime):
    """Base grammar plus the cohort's deliberately used latents with uniform weights (evaluation-side knowledge)."""
    g = grammar()
    for f in bench.read(instance_dir(seed) / 'latent_library.json'):
        if f['reuse'][regime]['deliberate_active']:
            g['productions'].append({'program': f['program'], 'type': f['type'], 'log_weight': 0.})
    return g


def benchmark(seeds):
    for seed in seeds:
        out = instance_dir(seed)
        if not (out / 'train.json').exists():
            stats = bench.generate_instance(seed, out)
            print(json.dumps({k: stats[k] for k in ['seed', 'train_count', 'test_count', 'rejections', 'generation_seconds']}), flush=True)
        if not (out / 'calibration.json').exists():
            bench.calibrate(out)
            print(f'calibrated {out}', flush=True)
        if not (out / 'manifest.json').exists():
            bench.freeze(out)
            print(f'frozen {out}', flush=True)
        bench.verify(out)


def write_protocol(seeds):
    path = RESULTS / 'protocol.json'
    if path.exists():
        return read_json(path)
    protocol = {'seeds': seeds, 'regimes': REGIMES, 'arms': ARMS, 'static': STATIC, 'descriptions': DESCRIPTIONS,
                'rounds': ROUNDS, 'training_search': SEARCH, 'wake_limit_main': WAKE_LIMIT, 'compressor_iterations': 3,
                'evaluation_budgets': BUDGETS, 'intermediate_round_budget': INTERMEDIATE_BUDGET, 'evaluation_search': EVAL_SEARCH,
                'recognition': 'off in every arm',
                'stitch': {'configs': STITCH_CONFIGS, 'iterations_per_config': STITCH_ITERATIONS, 'version': '0.1.29'},
                'perfect_wake': {'methods': PERFECT_WAKE_METHODS, 'iterations': PERFECT_WAKE_ITERATIONS},
                'benchmark_manifests': {str(seed): bench.read(instance_dir(seed) / 'manifest.json')['sha256'] for seed in seeds},
                'policy': ['Protocol fixed before any arm was run; benchmark instances frozen and hash-verified before and after every stage.',
                           'No arm, budget, seed or benchmark parameter is changed after observing results.'],
                'written': time.strftime('%Y-%m-%d %H:%M:%S')}
    save_json(path, protocol, compact=False)
    return protocol


def train_job(job):
    seed, regime, arm = job
    spec = ARMS[arm]
    bench.verify(instance_dir(seed))
    tasks = cohort_tasks(seed, 'train', regime)
    initial = oracle_grammar(seed, regime) if spec['oracle'] else None
    run_condition(tasks, spec['method'], RESULTS / 'runs' / f'seed_{seed}' / regime / arm, rounds=ROUNDS,
                  wake_limit=spec['wake'], initial_grammar=initial, label=f'{seed}/{regime}/{arm}')
    return job


def train(seeds, workers, arms=None):
    write_protocol(seeds)
    jobs = [(seed, regime, arm) for arm in (arms or ARMS) for seed in seeds for regime in REGIMES]
    pending = [j for j in jobs if not (RESULTS / 'runs' / f'seed_{j[0]}' / j[1] / j[2] / 'complete.json').exists()]
    print(f'{len(jobs)} training runs, {len(pending)} pending, {workers} workers', flush=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for job in pool.map(train_job, pending):
            print('trained', job, flush=True)
    for seed in seeds:
        bench.verify(instance_dir(seed))


def perfect_wake_job(job):
    """Compression diagnostic with perfect exposure: frontiers are the ground-truth training programs."""
    seed, regime, method = job
    path = RESULTS / 'perfect_wake' / f'seed_{seed}' / regime / f'{method}.json.gz'
    if path.exists():
        return job
    data = instance_dir(seed)
    private = bench.read(data / 'private.json')
    meta = private['tasks']
    names = [n for n, m in meta.items() if m['split'] == 'train' and m['regime'] == regime]
    frontiers = [{'request': REQUEST, 'entries': [{'program': meta[n]['ground_truth'], 'log_likelihood': 0.}]} for n in names]
    with BridgeKernel() as k:
        start = time.perf_counter()
        result = make_compressor(method, k, iterations=PERFECT_WAKE_ITERATIONS).compress(frontiers, grammar())
        seconds = time.perf_counter() - start
        record = {'seed': seed, 'regime': regime, 'method': method, 'iterations': PERFECT_WAKE_ITERATIONS, 'seconds': seconds,
                  'task_names': names, 'grammar': result.grammar_updates, 'inventions': result.invented_abstractions,
                  'mdl': result.mdl_accounting, 'history': result.history, 'statistics': result.statistics,
                  'rewritten': result.rewritten_programs,
                  'note': 'Diagnostic only: every training task is given its generating program, so exposure is perfect and only the compressor is tested.'}
    save_json(path, record)
    return job


def perfect_wake(seeds, workers):
    jobs = [(seed, regime, method) for seed in seeds for regime in REGIMES for method in PERFECT_WAKE_METHODS]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for job in pool.map(perfect_wake_job, jobs):
            print('perfect-wake', job, flush=True)


def evaluation_path(seed, regime, arm, iteration):
    return RESULTS / 'evaluation' / f'seed_{seed}' / regime / f'{arm}_{iteration}.json.gz'


def evaluate_job(job):
    seed, regime, arm = job
    data = instance_dir(seed)
    bench.verify(data)
    private = bench.read(data / 'private.json')
    meta, probes = private['tasks'], private['recovery_probes']
    latents = bench.read(data / 'latent_library.json')
    active = [f for f in latents if f['reuse'][regime]['deliberate_active']]
    tasks = cohort_tasks(seed, 'test', regime)
    train_names = [t.name for t in cohort_tasks(seed, 'train', regime)]
    cache = RESULTS / 'search_cache'
    if arm in STATIC:
        grammars = [(0, grammar() if arm == 'A0' else oracle_grammar(seed, regime), None)]
    elif arm.startswith('PW_'):
        record = read_json(RESULTS / 'perfect_wake' / f'seed_{seed}' / regime / f'{arm[3:]}.json.gz')
        grammars = [(1, record['grammar'], {'perfect_wake': True, 'solved': len(record['task_names']), 'inventions': record['inventions'],
                                            'mdl': record['mdl'], 'history': record['history'], 'frontiers': record['rewritten'],
                                            'invention_count': len(record['inventions']), 'library_size': len(record['grammar']['productions'])})]
    else:
        grammars = []
        for r in range(1, ROUNDS + 1):
            record = read_json(round_path(RESULTS / 'runs' / f'seed_{seed}' / regime / arm, r))
            grammars.append((r, record['grammar'], {'solved': record['wake']['solved'], 'newly_found': record['wake']['newly_found'],
                                                     'wake_first_solution_nodes': record['wake']['first_solution_nodes'],
                                                     'inventions': record['compression']['inventions'], 'mdl': record['compression']['mdl'],
                                                     'history': record['compression']['history'], 'frontiers': record['frontiers'],
                                                     'invention_count': record['invention_count'], 'library_size': record['library_size'],
                                                     'wake_seconds': record['wake']['seconds'], 'compression_seconds': record['compression']['seconds']}))
    pending = [(it, g, tr) for it, g, tr in grammars if not evaluation_path(seed, regime, arm, it).exists()]
    if not pending:
        return job
    with BridgeKernel() as k:
        truth = {t.name: k.call('evaluate_batch', program=meta[t.name]['ground_truth'], input_sets=[[x] for x in probes])['values'] for t in tasks}
        for iteration, g, training in pending:
            final = 1 if arm.startswith('PW_') else ROUNDS
            limit = max(BUDGETS) if iteration in (0, final) else INTERMEDIATE_BUDGET
            per_task, batch = evaluate_grammar(k, g, tasks, meta, probes, cache, truth, limit)
            rec = recovery(k, g, latents, regime, probes)
            exposure = frontier_support(k, training['frontiers'], train_names, active) if training and 'frontiers' in training else None
            if training:
                training = {key: v for key, v in training.items() if key != 'frontiers'}
            record = {'seed': seed, 'regime': regime, 'arm': arm, 'method': ARMS[arm]['method'] if arm in ARMS else arm,
                      'iteration': iteration, 'summary': summarize(per_task, limit), 'per_task': per_task, 'batch': batch,
                      'recovery': rec, 'library_size': len(g['productions']),
                      'inventions': [p for p in g['productions'] if 'invented' in p['program']],
                      'training': training, 'exposure': exposure, 'active_latents': [f['id'] for f in active]}
            save_json(evaluation_path(seed, regime, arm, iteration), record)
            solve_rate = record['summary']['curve'][str(limit)]
            timing = 'cached' if batch['cached'] else f"{batch['seconds']:.0f}s"
            print(f"evaluated {seed}/{regime}/{arm}@{iteration}: solve@max={solve_rate:.3f} "
                  f"recall={rec['metrics']['behavioral']['recall']} {timing}", flush=True)
    return job


def evaluate(seeds, workers, arms=None):
    jobs = [(seed, regime, arm) for seed in seeds for regime in REGIMES for arm in STATIC]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for job in pool.map(evaluate_job, jobs):
            pass
    jobs = [(seed, regime, arm) for arm in (arms or list(ARMS) + [f'PW_{m}' for m in PERFECT_WAKE_METHODS]) for seed in seeds for regime in REGIMES]
    jobs = [j for j in jobs if not j[2].startswith('PW_') or (RESULTS / 'perfect_wake' / f'seed_{j[0]}' / j[1] / f'{j[2][3:]}.json.gz').exists()]
    jobs = [j for j in jobs if j[2].startswith('PW_') or (RESULTS / 'runs' / f'seed_{j[0]}' / j[1] / j[2] / 'complete.json').exists()]
    print(f'{len(jobs)} evaluation jobs, {workers} workers', flush=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for job in pool.map(evaluate_job, jobs):
            pass
    for seed in seeds:
        bench.verify(instance_dir(seed))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['benchmark', 'train', 'perfect-wake', 'evaluate', 'analyze', 'all'])
    parser.add_argument('--seeds', type=int, nargs='+', default=SEEDS)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--arms', nargs='+', default=None)
    args = parser.parse_args()
    if args.command in ['benchmark', 'all']:
        benchmark(args.seeds)
    if args.command in ['train', 'all']:
        train(args.seeds, args.workers, args.arms)
    if args.command in ['perfect-wake', 'all']:
        perfect_wake(args.seeds, args.workers)
    if args.command in ['evaluate', 'all']:
        evaluate(args.seeds, args.workers, args.arms)
    if args.command in ['analyze', 'all']:
        from .analysis import analyze
        analyze(args.seeds)


if __name__ == '__main__':
    main()
