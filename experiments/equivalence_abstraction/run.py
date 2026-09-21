"""Phase 3 runner. Primary training and evaluation inherit all Phase 2 budgets."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
from types import FunctionType

from faithful.compression.interface import ROOT, BridgeKernel
from experiments.full_dreamcoder import run as phase2
from experiments.abstraction_learning.learner import read_json, save_json, round_path, ROUNDS
from .learner import ARMS, run_condition

RESULTS = ROOT / 'results' / 'equivalence_abstraction'


def run_dir(arm, seed, regime, ts):
    return RESULTS / 'runs' / f'seed_{seed}' / regime / f'{arm}_t{ts}'


def evaluation_path(arm, seed, regime, ts, mode, iteration):
    return RESULTS / 'evaluation' / f'seed_{seed}' / regime / f'{arm}_t{ts}_{mode}_{iteration}.json.gz'


def source_hashes():
    files = []
    for folder, suffix in [('faithful/haskell', '*.hs'), ('faithful/python', '*.py'),
                           ('faithful/compression', '*.py'), ('faithful/compression', '*.hs'),
                           ('experiments/full_dreamcoder', '*.py'), ('experiments/abstraction_learning', '*.py'),
                           ('experiments/equivalence_abstraction', '*.py')]:
        files.extend((ROOT / folder).glob(suffix))
    files.append(phase2.RESULTS / 'protocol.json')
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}


def protocol():
    path = RESULTS / 'protocol.json'
    current = {'phase': 3, 'parent': read_json(phase2.RESULTS / 'protocol.json'), 'source_hashes': source_hashes(),
               'arms': list(ARMS), 'cost': '(AST node count, lexicographic immutable term)',
               'equation_system': 'equations.py; semantics-derived; no probe-based equations',
               'saturation_cap': 512, 'au_pair_cap': 256, 'max_au_parameters': 2,
               'on_resource_limit': 'fail cell explicitly; no truncated equivalence-space claim',
               'frontier_policy': 'preserve likelihood, deduplicate identical representations; never pad or add solutions',
               'au_scope': 'first-order application bodies; inventions opaque; at most grid + one parameter',
               'mdl': 'frozen Haskell compression_objective/compression_trial, unchanged constants and inside-outside',
               'parameter_metric': 'same argument types up to permutation, all valid values; finite-probe witness',
               'primary_questions': ['RR recovery improvement', 'canonical exposure gap closure', 'B3 versus B2',
                                     'parameter generalisation versus specialisation', 'medium syntactic gap attribution']}
    if path.exists():
        if read_json(path) != current:
            raise RuntimeError('Frozen protocol/source mismatch; use a new results directory for revised experiments')
    else:
        save_json(path, current, compact=False)
    for seed in phase2.SEEDS:
        phase2.bench.verify(phase2.instance_dir(seed))
    return current


def train(arm, seed, regime, ts):
    tasks = phase2.cohort_tasks(seed, 'train', regime)
    return run_condition(tasks, arm, run_dir(arm, seed, regime, ts), seed=ts,
                         label=f'{seed}/{regime}/{arm}_t{ts}')


def evaluate(arm, seed, regime, ts):
    # Reuse the exact held-out routine, including library/recognition/shuffle,
    # 10k candidate budget, caching, independent probes and first-solution ranks.
    env = dict(phase2.evaluate_job.__globals__, RESULTS=RESULTS, ARM=arm, METHOD=arm,
               run_name=lambda s: f'{arm}_t{s}',
               run_dir=lambda s, r, t: run_dir(arm, s, r, t),
               evaluation_path=lambda s, r, t, m, i: evaluation_path(arm, s, r, t, m, i))
    fn = FunctionType(phase2.evaluate_job.__code__, env)
    result = fn((seed, regime, ts))
    if result[1]:
        raise RuntimeError(result[1])


def replay(arm, seed, regime, ts):
    """Paired compressor diagnostic on saved Phase 2 final frontiers; NOT a new EC run."""
    from .compressor import make_compressor
    source = round_path(phase2.run_dir(seed, regime, ts), ROUNDS)
    record = read_json(source)
    target = RESULTS / 'replay' / f'{seed}_{regime}_{ts}_{arm}.json.gz'
    if target.exists():
        return
    with BridgeKernel() as k:
        result = make_compressor(arm, k).compress(record['frontiers'], record['grammar'])
    save_json(target, {'source': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                       'diagnostic_only': True, 'arm': arm, 'seed': seed, 'regime': regime, 'training_seed': ts,
                       'result': result.to_dict()})
    print(f'replay {arm} {seed}/{regime}/t{ts}: inventions={len(result.invented_abstractions)} '
          f'dMDL={result.mdl_accounting["delta_mdl"]:.4f}', flush=True)


def execute_job(job):
    global RESULTS
    output, command, arm, seed, regime, ts = job
    RESULTS = Path(output)
    if command in ('train', 'all'):
        train(arm, seed, regime, ts)
    if command in ('evaluate', 'all'):
        evaluate(arm, seed, regime, ts)
    if command == 'replay':
        replay(arm, seed, regime, ts)
    return arm, seed, regime, ts


def main():
    global RESULTS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['verify', 'train', 'evaluate', 'replay', 'analyze', 'all'])
    parser.add_argument('--arms', nargs='+', choices=ARMS, default=list(ARMS))
    parser.add_argument('--seeds', nargs='+', type=int, default=phase2.SEEDS)
    parser.add_argument('--regimes', nargs='+', choices=phase2.REGIMES, default=['medium', 'high', 'low', 'zero'])
    parser.add_argument('--training-seeds', nargs='+', type=int)
    parser.add_argument('--output', type=Path, default=RESULTS)
    parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args()
    RESULTS = args.output.resolve()
    protocol()
    if args.command == 'verify':
        print('Source and benchmark hashes verified')
        return
    if args.command in ('analyze', 'all'):
        if args.command == 'analyze':
            from .analysis import analyze
            analyze(RESULTS)
            return
    jobs = []
    for regime in args.regimes:
        for seed in args.seeds:
            for ts in args.training_seeds or phase2.TRAINING_SEEDS[regime]:
                if ts not in phase2.TRAINING_SEEDS[regime]:
                    raise ValueError('Training seed outside the frozen regime schedule')
                for arm in args.arms:
                    jobs.append((str(RESULTS), args.command, arm, seed, regime, ts))
    if args.workers == 1:
        for job in jobs:
            execute_job(job)
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            for job in pool.map(execute_job, jobs):
                print('completed', job, flush=True)
    if args.command == 'all':
        from .analysis import analyze
        analyze(RESULTS)
    protocol()


if __name__ == '__main__':
    main()
