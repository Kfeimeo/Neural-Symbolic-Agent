"""Phase 2 pipeline: full faithful DreamCoder (recognition ON) against the Phase 1 B arm.

::

    python -m experiments.full_dreamcoder.run train     --workers 4    # FullDC EC loops: instances x cohorts x training seeds
    python -m experiments.full_dreamcoder.run evaluate  --workers 4    # held-out evaluation (library / recognition / shuffle modes)
    python -m experiments.full_dreamcoder.run parity                   # round-1 parity with B and re-evaluation of a Phase 1 grammar
    python -m experiments.full_dreamcoder.run analyze                  # results/full_dreamcoder/*.json + tables.md
    python -m experiments.full_dreamcoder.run all

Nothing of Phase 1 is re-run or modified: the frozen benchmark instances, the Phase 1
learner, compressors, evaluation functions and budgets are imported unchanged, and the
Phase 1 evaluation records (arms A0, A, B, O, O_uniform, B_wake10000, PW*/PWS*) are read
as the comparison arms.  The only change is the recognition pathway of the learner.
The protocol file is written before any run and never edited afterwards.
"""
import argparse
import concurrent.futures
import json
import time
from pathlib import Path

import torch

from faithful.compression.interface import BridgeKernel, ROOT
from faithful.python.grid import grammar
from benchmarks.latent_abstraction import generator as bench
from experiments.abstraction_learning.learner import read_json, save_json, round_path, ROUNDS, WAKE_LIMIT, SEARCH, COMPRESSOR_ITERATIONS
from experiments.abstraction_learning.evaluation import recovery, frontier_support, BUDGETS, EVAL_SEARCH
from experiments.abstraction_learning.run import cohort_tasks, instance_dir, evaluation_path as phase1_evaluation_path, RESULTS as PHASE1
from .learner import run_condition, load_model, DREAM_DRAWS, RECOGNITION_STEPS, RECOGNITION_OBJECTIVE
from .evaluation import evaluate_mode, MODES

RESULTS = ROOT / 'results' / 'full_dreamcoder'
SEEDS = bench.DEFAULT_SEEDS
REGIMES = bench.REGIMES
ARM = 'FullDC'
METHOD = 'B'                       # identical compressor to the Phase 1 B arm
TRAINING_SEEDS = {'zero': [1], 'low': [1], 'medium': [1, 2, 3], 'high': [1]}   # primary seed 1 everywhere; replication on the focus regime
PRIMARY_SEED = 1
FINAL_ONLY_MODES = ['shuffle']     # the derangement control is evaluated on the final library only
COMPARISON_ARMS = ['A0', 'A', 'B', 'O', 'O_uniform', 'B_wake10000', 'PWS_B', 'PWS_D', 'PW_D', 'PW_C', 'PWS_C']
SHUFFLE_SEED_BASE = 2000


def run_name(training_seed):
    return f'{ARM}_t{training_seed}'


def run_dir(seed, regime, training_seed):
    return RESULTS / 'runs' / f'seed_{seed}' / regime / run_name(training_seed)


def evaluation_path(seed, regime, training_seed, mode, iteration):
    return RESULTS / 'evaluation' / f'seed_{seed}' / regime / f'{run_name(training_seed)}_{mode}_{iteration}.json.gz'


def write_protocol():
    path = RESULTS / 'protocol.json'
    if path.exists():
        return read_json(path)
    protocol = {'phase': 2, 'seeds': SEEDS, 'regimes': REGIMES,
                'arm': {ARM: dict(method=METHOD, wake=WAKE_LIMIT, recognition='on', rounds=ROUNDS, compressor_iterations=COMPRESSOR_ITERATIONS,
                                  dream_draws=DREAM_DRAWS, recognition_steps=RECOGNITION_STEPS, recognition_objective=RECOGNITION_OBJECTIVE,
                                  recognition_model='task-conditioned AST bigram MLP of the frozen core (faithful/python/recognition.py)',
                                  training_seeds=TRAINING_SEEDS, primary_training_seed=PRIMARY_SEED)},
                'control_arm': 'B (Phase 1): identical system with recognition off; read from results/abstraction_learning/evaluation',
                'comparison_arms': COMPARISON_ARMS,
                'training_search': SEARCH, 'evaluation_search': EVAL_SEARCH, 'evaluation_budgets': BUDGETS, 'evaluation_modes': MODES,
                'final_only_modes': FINAL_ONLY_MODES,
                'metrics': ['training solve rate per iteration', 'latent frontier support (distinct training tasks; Phase 1 structural criterion)',
                            'ER@1, ER@2 per iteration', 'behavioural precision / recall / F1 (Phase 1 criterion)',
                            'held-out solve rate at 100/300/1000/3000/10000 (library-only and recognition-guided)',
                            'first-solution rank distribution and S(B) with unsolved tasks as r > 10000',
                            'P(recovered | support >= 2) versus P(recovered | support < 2)', 'exposure / recovery / oracle gap closure against B, PWS_B and O'],
                'benchmark_manifests': {str(seed): bench.read(instance_dir(seed) / 'manifest.json')['sha256'] for seed in SEEDS},
                'phase1_protocol_sha256': __import__('hashlib').sha256((PHASE1 / 'protocol.json').read_bytes()).hexdigest(),
                'policy': ['Protocol fixed before any Phase 2 run; benchmark instances and the fixed core are hash-verified before and after every stage.',
                           'No compressor, DSL, solver, benchmark, budget or Phase 1 artefact is modified; the only change is recognition ON.',
                           'No arm, budget, seed or parameter is changed after observing results.'],
                'written': time.strftime('%Y-%m-%d %H:%M:%S')}
    save_json(path, protocol, compact=False)
    return protocol


def train_job(job):
    seed, regime, training_seed = job
    bench.verify(instance_dir(seed))
    tasks = cohort_tasks(seed, 'train', regime)
    run_condition(tasks, METHOD, run_dir(seed, regime, training_seed), rounds=ROUNDS, wake_limit=WAKE_LIMIT, seed=training_seed,
                  label=f'{seed}/{regime}/{run_name(training_seed)}')
    return job


JOB_ORDER = ['medium', 'high', 'low', 'zero']   # focus regime first so that its evaluation can start early


def training_jobs(regimes=None, training_seeds=None):
    """Primary-seed runs of every regime first (focus regime leading), then the replication seeds."""
    regimes = [r for r in JOB_ORDER if r in (regimes or REGIMES)]
    jobs = [(seed, regime, PRIMARY_SEED) for regime in regimes for seed in SEEDS if PRIMARY_SEED in (training_seeds or TRAINING_SEEDS[regime])]
    jobs += [(seed, regime, ts) for regime in regimes for ts in (training_seeds or TRAINING_SEEDS[regime]) if ts != PRIMARY_SEED for seed in SEEDS]
    return jobs


def train(workers, regimes=None, training_seeds=None):
    write_protocol()
    jobs = training_jobs(regimes, training_seeds)
    pending = [j for j in jobs if not (run_dir(*j) / 'complete.json').exists()]
    print(f'{len(jobs)} training runs, {len(pending)} pending, {workers} workers', flush=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for job in pool.map(train_job, pending):
            print('trained', job, flush=True)
    for seed in SEEDS:
        bench.verify(instance_dir(seed))


def evaluate_job(job):
    seed, regime, training_seed = job
    torch.set_num_threads(1)
    data = instance_dir(seed)
    bench.verify(data)
    private = bench.read(data / 'private.json')
    meta, probes = private['tasks'], private['recovery_probes']
    latents = bench.read(data / 'latent_library.json')
    active = [f for f in latents if f['reuse'][regime]['deliberate_active']]
    tasks = cohort_tasks(seed, 'test', regime)
    train_names = [t.name for t in cohort_tasks(seed, 'train', regime)]
    cache = RESULTS / 'search_cache'
    folder = run_dir(seed, regime, training_seed)
    pending = [(r, mode) for r in range(1, ROUNDS + 1) for mode in MODES
               if (mode not in FINAL_ONLY_MODES or r == ROUNDS) and not evaluation_path(seed, regime, training_seed, mode, r).exists()]
    failures = []
    if not pending:
        return job, failures
    k = BridgeKernel()
    try:
        truth = {t.name: k.call('evaluate_batch', program=meta[t.name]['ground_truth'], input_sets=[[x] for x in probes])['values'] for t in tasks}
        exposure_cache, recovery_cache = {}, {}
        for iteration, mode in pending:
            record = read_json(round_path(folder, iteration))
            g = record['grammar']
            model = load_model(folder, iteration, g) if mode != 'library' else None
            try:
                per_task, batch, summary = evaluate_mode(k, g, model, mode, tasks, meta, probes, cache, truth, max(BUDGETS),
                                                         shuffle_seed=SHUFFLE_SEED_BASE + seed)
                if iteration not in recovery_cache:
                    recovery_cache[iteration] = recovery(k, g, latents, regime, probes)
                    exposure_cache[iteration] = frontier_support(k, record['frontiers'], train_names, active)
            except (json.JSONDecodeError, BrokenPipeError, OSError, ValueError) as exc:
                failures.append({'seed': seed, 'regime': regime, 'training_seed': training_seed, 'iteration': iteration, 'mode': mode,
                                 'error': f'{type(exc).__name__}: {exc}'})
                print(f'FAILED {seed}/{regime}/{run_name(training_seed)}@{iteration}/{mode}: {type(exc).__name__}', flush=True)
                try:
                    k.process.kill()
                except Exception:
                    pass
                k = BridgeKernel()
                continue
            training = {'solved': record['wake']['solved'], 'newly_found': record['wake']['newly_found'],
                        'wake_first_solution_nodes': record['wake']['first_solution_nodes'], 'wake_per_task': record['wake']['per_task'],
                        'wake_guided': record['wake']['guided'], 'wake_seconds': record['wake']['seconds'], 'guidance_seconds': record['wake']['guidance_seconds'],
                        'inventions': record['compression']['inventions'], 'mdl': record['compression']['mdl'], 'history': record['compression']['history'],
                        'invention_count': record['invention_count'], 'library_size': record['library_size'],
                        'compression_seconds': record['compression']['seconds'], 'dream': record['dream'],
                        'recognition': {key: v for key, v in record['recognition'].items() if key != 'losses'},
                        'recognition_loss_first': record['recognition']['losses'][:20], 'recognition_loss_last': record['recognition']['losses'][-20:],
                        'task_count': len(train_names)}
            out = {'seed': seed, 'regime': regime, 'arm': run_name(training_seed), 'base_arm': ARM, 'training_seed': training_seed, 'method': METHOD,
                   'mode': mode, 'iteration': iteration, 'summary': summary, 'per_task': per_task, 'batch': batch,
                   'recovery': recovery_cache[iteration], 'library_size': len(g['productions']),
                   'inventions': [p for p in g['productions'] if 'invented' in p['program']],
                   'training': training, 'exposure': exposure_cache[iteration], 'active_latents': [f['id'] for f in active]}
            save_json(evaluation_path(seed, regime, training_seed, mode, iteration), out)
            timing = 'cached' if batch['cached'] else f"{batch['seconds']:.0f}s"
            print(f"evaluated {seed}/{regime}/{run_name(training_seed)}@{iteration}/{mode}: solve@10000={summary['curve']['10000']:.3f} "
                  f"recall={recovery_cache[iteration]['metrics']['behavioral']['recall']} train_solved={training['solved']} {timing}", flush=True)
    finally:
        try:
            k.process.kill()
        except Exception:
            pass
    return job, failures


def evaluate(workers, regimes=None, training_seeds=None):
    jobs = [j for j in training_jobs(regimes, training_seeds) if (run_dir(*j) / 'complete.json').exists()]
    print(f'{len(jobs)} evaluation jobs, {workers} workers', flush=True)
    failures = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for job, fails in pool.map(evaluate_job, jobs):
            failures.extend(fails)
    if failures:
        retry = sorted({(f['seed'], f['regime'], f['training_seed']) for f in failures})
        print(f'retrying {len(retry)} runs serially after {len(failures)} failed searches', flush=True)
        remaining = []
        for job in retry:
            remaining.extend(evaluate_job(job)[1])
        save_json(RESULTS / 'evaluation_failures.json', {'first_pass': failures, 'after_serial_retry': remaining}, compact=False)
    for seed in SEEDS:
        bench.verify(instance_dir(seed))


def parity():
    """Reproducibility checks that tie Phase 2 to Phase 1 on this machine.

    1. Round 1 of every FullDC run has no recognition model yet and must reproduce
       the Phase 1 B round 1 record exactly (same frontiers, same grammar).
    2. One Phase 1 held-out evaluation (B, final round, every cohort of instance 101)
       is re-searched with the kernel compiled here and compared rank by rank.
    """
    report = {'round1': [], 'phase1_reevaluation': []}
    for seed in SEEDS:
        for regime in REGIMES:
            for ts in TRAINING_SEEDS[regime]:
                path = round_path(run_dir(seed, regime, ts), 1)
                if not path.exists():
                    continue
                ours = read_json(path)
                theirs = read_json(round_path(PHASE1 / 'runs' / f'seed_{seed}' / regime / 'B', 1))
                report['round1'].append({'seed': seed, 'regime': regime, 'training_seed': ts,
                                         'same_frontiers': ours['frontiers'] == theirs['frontiers'], 'same_grammar': ours['grammar'] == theirs['grammar'],
                                         'same_wake_ranks': ours['wake']['first_solution_nodes'] == theirs['wake']['first_solution_nodes'],
                                         'solved': [ours['wake']['solved'], theirs['wake']['solved']]})
    from experiments.abstraction_learning.evaluation import cached_search
    seed = SEEDS[0]
    with BridgeKernel() as k:
        for regime in REGIMES:
            record = read_json(phase1_evaluation_path(seed, regime, 'B', ROUNDS))
            g = read_json(round_path(PHASE1 / 'runs' / f'seed_{seed}' / regime / 'B', ROUNDS))['grammar']
            tasks = cohort_tasks(seed, 'test', regime)
            rows, seconds, cached = cached_search(k, tasks, g, RESULTS / 'search_cache', max(BUDGETS))
            theirs = {t['name']: t['first_solution_nodes'] for t in record['per_task']}
            ours = {r['name']: r['first_solution_nodes'] for r in rows}
            report['phase1_reevaluation'].append({'seed': seed, 'regime': regime, 'arm': 'B', 'iteration': ROUNDS, 'identical_first_solution_ranks': ours == theirs,
                                                  'differences': {n: [ours[n], theirs[n]] for n in ours if ours[n] != theirs.get(n)},
                                                  'seconds': seconds, 'cached': cached})
    report['all_pass'] = all(r['same_frontiers'] and r['same_grammar'] for r in report['round1']) and all(r['identical_first_solution_ranks'] for r in report['phase1_reevaluation'])
    save_json(RESULTS / 'parity.json', report, compact=False)
    print(json.dumps({'round1_checks': len(report['round1']), 'all_pass': report['all_pass']}), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['train', 'evaluate', 'parity', 'analyze', 'figures', 'all'])
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--regimes', nargs='+', default=None)
    parser.add_argument('--training-seeds', type=int, nargs='+', default=None)
    args = parser.parse_args()
    if args.command in ['train', 'all']:
        train(args.workers, args.regimes, args.training_seeds)
    if args.command in ['evaluate', 'all']:
        evaluate(args.workers, args.regimes, args.training_seeds)
    if args.command in ['parity', 'all']:
        parity()
    if args.command in ['analyze', 'all']:
        from .analysis import analyze
        analyze()
    if args.command in ['figures', 'all']:
        from .figures import main as figures
        figures()


if __name__ == '__main__':
    main()
