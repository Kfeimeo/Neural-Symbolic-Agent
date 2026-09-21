"""Per-cell Phase 3 metrics, explicit completeness, and paired medium contrasts."""
from pathlib import Path
from faithful.compression.interface import BridgeKernel
from experiments.full_dreamcoder import run as phase2
from experiments.abstraction_learning.learner import ROUNDS, read_json, save_json, round_path
from .metrics import exposure_and_parameters
from .learner import ARMS


def analyze(root):
    root = Path(root)
    rows, missing = [], []
    with BridgeKernel() as k:
        for regime in phase2.REGIMES:
            for seed in phase2.SEEDS:
                data = phase2.instance_dir(seed)
                private = phase2.bench.read(data / 'private.json')
                latents = phase2.bench.read(data / 'latent_library.json')
                for ts in phase2.TRAINING_SEEDS[regime]:
                    for arm in ARMS:
                        folder = root / 'runs' / f'seed_{seed}' / regime / f'{arm}_t{ts}'
                        cumulative = 0.
                        for iteration in range(1, ROUNDS + 1):
                            p = round_path(folder, iteration)
                            if not p.exists():
                                missing.append([seed, regime, ts, arm, iteration, 'training'])
                                continue
                            r = read_json(p)
                            metric_path = root / 'metrics' / f'{seed}_{regime}_{ts}_{arm}_{iteration}.json.gz'
                            if metric_path.exists():
                                m = read_json(metric_path)
                            else:
                                m = exposure_and_parameters(k, r['frontiers'], r['task_names'], r['grammar'],
                                                            latents, regime, private['recovery_probes'])
                                save_json(metric_path, m)
                            cumulative += r['compression']['mdl']['delta_mdl']
                            row = {'seed': seed, 'regime': regime, 'training_seed': ts, 'arm': arm, 'iteration': iteration,
                                   'exposure_stage': 'post-compression persistent frontier', 'er': m['er'],
                                   'behavioural_recovery': m['recovery']['metrics']['behavioral'],
                                   'parameterised_latent_recall': m['parameterised_latent_recall'],
                                   'conditional_parametric_recovery': m['conditional_parametric_recovery'],
                                   'invention_count': r['invention_count'], 'cumulative_delta_mdl': cumulative,
                                   'training_solve_rate': r['wake']['solved']/len(r['task_names']), 'held_out': {}}
                            for mode in phase2.MODES:
                                if mode in phase2.FINAL_ONLY_MODES and iteration != ROUNDS:
                                    continue
                                epath = root / 'evaluation' / f'seed_{seed}' / regime / f'{arm}_t{ts}_{mode}_{iteration}.json.gz'
                                if not epath.exists():
                                    missing.append([seed, regime, ts, arm, iteration, mode])
                                    continue
                                e = read_json(epath)
                                row['held_out'][mode] = {'curve': e['summary']['curve'],
                                                        'first_solution_rank': {t['name']: t['first_solution_nodes'] for t in e['per_task']}}
                            rows.append(row)
    paired = []
    index = {(r['seed'], r['regime'], r['training_seed'], r['arm']): r for r in rows if r['iteration'] == ROUNDS}
    for seed in phase2.SEEDS:
        for ts in phase2.TRAINING_SEEDS['medium']:
            cells = {arm: index.get((seed, 'medium', ts, arm)) for arm in ARMS}
            if any(r is None for r in cells.values()):
                continue
            b = cells['B0']
            for arm in ARMS[1:]:
                r = cells[arm]
                rec0, rec = b['behavioural_recovery']['recall'], r['behavioural_recovery']['recall']
                gap = b['er']['behavioural']['ER@2'] - rec0
                paired.append({'seed': seed, 'training_seed': ts, 'arm': arm,
                               'recall_delta_vs_B0': rec-rec0,
                               'remaining_behavioural_ER2_gap_fraction': (rec-rec0)/gap if gap > 0 else None,
                               'interpretation': 'descriptive paired gap closure, not causal attribution; EC feedback changes later frontiers'})
    report = {'complete': not missing, 'expected_training_cells': 18*4*ROUNDS, 'observed_training_cells': len(rows),
              'missing': missing, 'cells': rows, 'medium_paired': paired,
              'answers': {str(i): 'Pending complete paired B0-B3 results; no empirical conclusion asserted.' for i in range(1, 6)}}
    save_json(root / 'analysis.json', report, compact=False)
    print(f'Phase 3 complete={report["complete"]}; {len(rows)} training cells; {len(missing)} missing records', flush=True)
    return report
