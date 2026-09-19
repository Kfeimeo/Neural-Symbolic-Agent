"""Reproducible calibration, freeze, training and frozen evaluation commands."""
import argparse
import concurrent.futures
import hashlib
import json
import shutil
from pathlib import Path
import time
import torch
from .kernel import Kernel, ROOT
from .grid import grammar, features
from .recognition import Recognition
from .toy import save, search, wire
from .controlled_learner import load_io, train_condition, evaluate_job, derangement, sha, SEARCH

OUT = ROOT/'faithful/results/controlled'
REGIMES = ['zero', 'low', 'medium', 'high']
SEEDS = [11, 23, 47]
ROUNDS = [0, 1, 2, 3, 5]
BUDGETS = [100, 300, 600, 1000, 3000, 10000]


def read(path): return json.loads(Path(path).read_text(encoding='utf8'))


def verify(out, *, check_current_core=True):
    manifest = read(out/'benchmark_manifest.json')
    for name, expected in read(out/'SHA256SUMS.json').items():
        if hashlib.sha256((out/name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Frozen file changed: {name}')
    for name, expected in (manifest['core_sha256'].items() if check_current_core else []):
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Accepted core changed: {name}. Keep this historical run frozen; use fork-runtime with a new --output for the device-placement revision.')
    return manifest


def fork_runtime(source, target):
    """Reuse immutable data, but start a distinct device-runtime experiment."""
    source, target = Path(source).resolve(), Path(target).resolve()
    parent = verify(source, check_current_core=False)
    if target.exists(): raise ValueError('Runtime variant output must be a new directory')
    current = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in parent['core_sha256']}
    changed = [name for name in current if current[name] != parent['core_sha256'][name]]
    if any(name.replace('\\', '/') != 'faithful/python/recognition.py' for name in changed):
        raise ValueError('Unexpected symbolic/core changes; runtime fork is limited to recognition device placement')
    target.mkdir(parents=True)
    for name in parent['sha256']:
        shutil.copyfile(source/name, target/name)
    manifest = dict(parent, core_sha256=current,
        runtime_parent_manifest_sha256=hashlib.sha256((source/'benchmark_manifest.json').read_bytes()).hexdigest(),
        runtime_variant={'purpose': 'Automatic CUDA/CPU device placement; identical frozen benchmark data',
            'changed_core_files': changed, 'torch_version': str(torch.__version__),
            'cuda_available': torch.cuda.is_available()})
    save(target/'benchmark_manifest.json', manifest)
    save(target/'SHA256SUMS.json', {**manifest['sha256'], 'benchmark_manifest.json': hashlib.sha256((target/'benchmark_manifest.json').read_bytes()).hexdigest()})
    verify(target)
    print(f'Prepared runtime variant with identical benchmark hashes: {target}', flush=True)


def calibration(out):
    if (out/'benchmark_manifest.json').exists(): raise ValueError('Already frozen')
    ts = load_io(out/'train.json') + load_io(out/'test.json')
    meta = read(out/'evaluation_private.json')['tasks']
    with Kernel() as k:
        rows, seconds = search(k, ts, grammar(), grammar(), dict(SEARCH, limit=10000))
    rates = []
    for split in ['train', 'test']:
        for d in range(2, 9):
            rr = [r for r in rows if meta[r['name']]['split'] == split and meta[r['name']]['depth'] == d]
            rates.append({'split': split, 'depth': d, 'count': len(rr), 'rates': {str(n): sum(r['first_solution_nodes'] is not None and r['first_solution_nodes'] <= n for r in rr)/len(rr) if rr else None for n in BUDGETS}})
    save(out/'calibration.json', {'configuration': 'A only', 'seconds': seconds, 'options': SEARCH,
        'rows': rows, 'depth_budget_rates': rates,
        'decision': 'Freeze this candidate independent of nonbase outcomes. Deep unsolved strata retained as hard controls.'})
    print(json.dumps(rates, indent=2), flush=True)


def train_job(args):
    out, regime, seed, label, names = args
    tasks = [t for t in load_io(out/'train.json') if t.name in names]
    train_condition(tasks, label, seed, out/'runs'/regime/str(seed)/label)


def training(out, workers):
    verify(out)
    meta = read(out/'evaluation_private.json')['tasks']
    jobs = [(out, regime, seed, label, {n for n, m in meta.items() if m['split'] == 'train' and m['regime'] == regime})
        for label in ['B', 'C', 'D', 'E'] for regime in REGIMES for seed in SEEDS]
    # Categorical regime selects an independent training cohort. The learner
    # receives only names and Task I/O, never this metadata or latent definitions.
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for _ in pool.map(train_job, jobs): pass


def evaluation(out, workers, controls_only=False, available_only=False):
    verify(out)
    torch.set_num_threads(1)
    meta = read(out/'evaluation_private.json')['tasks']
    latent = read(out/'latent_library.json')  # Evaluation-only Oracle access.
    tasks = load_io(out/'test.json')
    jobs = {}
    index = []
    for regime in REGIMES:
        ts = [t for t in tasks if meta[t.name]['regime'] == regime]
        used = {u['latent'] for n, m in meta.items() if m['regime'] == regime for u in m['latent_uses']}
        oracle = grammar()
        oracle['productions'] += [{'program': f['program'], 'type': f['type'], 'log_weight': 0.} for f in latent if f['id'] in used]
        for seed in SEEDS:
            order = derangement(len(ts), seed+2000)
            save(out/'runs'/regime/str(seed)/'shuffle.json', {'seed': seed+2000, 'target_names': [t.name for t in ts], 'source_names': [ts[j].name for j in order]})
            for iteration in ROUNDS:
                for label in ['A', 'B', 'C', 'D', 'E', 'C_shuffle', 'D_shuffle', 'O']:
                    if controls_only and label not in ['A', 'O']: continue
                    model = None
                    g = oracle if label == 'O' else grammar()
                    if iteration and label not in ['A', 'O']:
                        source = label.split('_')[0]
                        folder = out/'runs'/regime/str(seed)/source/f'round_{iteration}'
                        if available_only and not (folder/'round.json').exists(): continue
                        g = read(folder/'round.json')['grammar']
                        if source in ['C', 'D']:
                            model = Recognition(g)
                            model.load_state_dict(torch.load(folder/'recognition.pt', map_location=model.device, weights_only=True)['state_dict'])
                    if model is None:
                        grouped = [(ts, g)]
                    else:
                        grouped = [([t], model.search_grammar(features(ts[order[i]] if label.endswith('shuffle') else t))) for i, t in enumerate(ts)]
                    requests = {}
                    for batch, sg in grouped:
                        rows = [wire(t) for t in batch]
                        group_key = sha({'grammar': g, 'sg': sg, 'budgets': BUDGETS, 'search': SEARCH})
                        requests.setdefault(group_key, []).extend(t['name'] for t in rows)
                        if group_key not in jobs: jobs[group_key] = {'tasks': {}, 'grammar': g, 'sg': sg}
                        jobs[group_key]['tasks'].update({t['name']: t for t in rows})
                    index.append({'regime': regime, 'seed': seed, 'iteration': iteration, 'configuration': label, 'grammar': g, 'requests': requests})
    # Normal and deranged recognition use exactly the same set of grammars.
    # Search each grammar once against the union of its assigned task I/O.
    # Retain explicit selections so a task is never scored under its own
    # guidance in the shuffle condition by accidentally merging results.
    grouped_jobs = {}
    paths = {}
    for group_key, job in jobs.items():
        rows = [job['tasks'][name] for name in sorted(job['tasks'])]
        cache_key = sha({'tasks': rows, 'grammar': job['grammar'], 'sg': job['sg'], 'budgets': BUDGETS, 'search': SEARCH})
        path = out/'search_cache'/f'{cache_key}.json'
        paths[group_key] = str(path.relative_to(out))
        grouped_jobs[cache_key] = (path, rows, job['grammar'], job['sg'], BUDGETS)
    jobs = grouped_jobs
    for entry in index:
        entry['selections'] = {paths[group_key]: names for group_key, names in entry.pop('requests').items()}
        entry['paths'] = list(entry['selections'])
    save(out/('control_index.json' if controls_only else 'partial_evaluation_index.json' if available_only else 'evaluation_index.json'), index)
    pending = [j for j in jobs.values() if not j[0].exists()]
    print(f'{len(jobs)} distinct searches; {len(pending)} pending; {workers} workers', flush=True)
    start = time.perf_counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for i, path in enumerate(pool.map(evaluate_job, pending), 1):
            if i % 25 == 0: print(f'evaluated {i}/{len(pending)} in {time.perf_counter()-start:.1f}s', flush=True)
    verify(out)
    save(out/('controls_complete.json' if controls_only else 'partial_evaluation_complete.json' if available_only else 'evaluation_complete.json'), {'distinct_searches': len(jobs), 'seconds_this_invocation': time.perf_counter()-start})


def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['calibrate', 'freeze', 'train', 'controls', 'evaluate', 'available', 'fork-runtime', 'all'])
    p.add_argument('--output', type=Path, default=OUT)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--source', type=Path, default=OUT)
    a = p.parse_args()
    if a.command == 'fork-runtime':
        fork_runtime(a.source, a.output)
        return
    if a.command in ['calibrate', 'all'] and not (a.output/'benchmark_manifest.json').exists(): calibration(a.output)
    if a.command in ['freeze', 'all'] and not (a.output/'benchmark_manifest.json').exists():
        from .controlled_data import freeze
        freeze(a.output)
    if a.command in ['train', 'all']: training(a.output, a.workers)
    if a.command in ['evaluate', 'all']: evaluation(a.output, a.workers)
    if a.command == 'controls': evaluation(a.output, a.workers, controls_only=True)
    if a.command == 'available': evaluation(a.output, a.workers, available_only=True)


if __name__ == '__main__': main()
