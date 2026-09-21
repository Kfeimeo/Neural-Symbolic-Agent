"""Snapshot completed evidence without resuming training or changing frozen bounds."""
import datetime
import gzip
import hashlib
import json
import statistics
from pathlib import Path

from faithful.compression.interface import BridgeKernel
from experiments.full_dreamcoder import run as phase2
from experiments.abstraction_learning.learner import read_json, save_json
from experiments.abstraction_learning.evaluation import recovery
from experiments.equivalence_abstraction.metrics import exposure_and_parameters

OUT = Path(__file__).parent
ROOT = OUT.parents[1]
ARMS = ('B0', 'B1', 'B2', 'B3')


def total_delta(mdl):
    # Same before/after boundary in all arms: raw input -> final compressed output.
    return mdl.get('total_delta_mdl', mdl['delta_mdl'])


def paired_diagnostics():
    rows = {}
    for p in (OUT/'replay_metrics').glob('*.json.gz'):
        r = read_json(p)
        rows[r['seed'], r['training_seed'], r['arm']] = r['metrics']
    counts = dict(behavioural_not_syntactic=0, equivalence_bridges_gap=0,
                  behavioural_unrecovered=0, equivalence_usable_unrecovered=0)
    original_counts = dict(behavioural_unrecovered=0, equivalence_usable_unrecovered=0, recovered_by_extra_B0=0)
    changes = {arm: [] for arm in ARMS[1:]}
    classification = {arm: dict(new=0, behavioural_matches=0, generalised_matches=0, specialised_matches=0) for arm in ARMS}
    original_checks = []
    for (seed, ts, arm), m in sorted(rows.items()):
        recovered = set(m['recovery']['metrics']['behavioral']['recovered_latents'])
        if arm == 'B0':
            sy = {i for i, s in m['syntactic'].items() if s['count'] >= 2}
            be = {i for i, s in m['behavioural'].items() if s['count'] >= 2}
            eq = {i for i, s in m['equivalence_usable'].items() if s['count'] >= 2}
            counts['behavioural_not_syntactic'] += len(be-sy)
            counts['equivalence_bridges_gap'] += len((be-sy)&eq)
            counts['behavioural_unrecovered'] += len(be-recovered)
            counts['equivalence_usable_unrecovered'] += len((be-recovered)&eq)
            for other in changes:
                hits = set(rows[seed, ts, other]['recovery']['metrics']['behavioral']['recovered_latents'])
                changes[other].append({'seed': seed, 'training_seed': ts, 'gained': sorted(hits-recovered), 'lost': sorted(recovered-hits)})
            src = phase2.evaluation_path(seed, 'medium', ts, 'library', 6)
            old = set(read_json(src)['recovery']['metrics']['behavioral']['recovered_latents'])
            original_counts['behavioural_unrecovered'] += len(be-old)
            original_counts['equivalence_usable_unrecovered'] += len((be-old)&eq)
            original_counts['recovered_by_extra_B0'] += len(recovered-old)
            original_checks.append({'seed': seed, 'training_seed': ts, 'phase2_recovered': sorted(old),
                                    'extra_B0_recovered': sorted(recovered), 'new': sorted(recovered-old),
                                    'source': str(src.relative_to(ROOT))})
        result = read_json(OUT/'replay'/f'{seed}_medium_{ts}_{arm}.json.gz')['result']
        new = {json.dumps(p['program'], sort_keys=True) for p in result['invented_abstractions']}
        indices = {i for i, p in enumerate(m['recovery']['learned_inventions']) if json.dumps(p['program'], sort_keys=True) in new}
        pairs = m['recovery']['metrics']['behavioral']['pairs']
        matched = {j for _, j in pairs}
        params = {p['latent'] for p in m['parameters']}
        general = {j for i, j in pairs if m['recovery']['active_latents'][i] in params}
        special = {s['invention_index'] for p in m['parameters'] for s in p['specialised_matches']}
        c = classification[arm]
        c['new'] += len(indices)
        c['behavioural_matches'] += len(indices&matched)
        c['generalised_matches'] += len(indices&general)
        c['specialised_matches'] += len(indices&special)
    d = {'baseline_gap_counts': counts, 'paired_recovery_changes': changes,
         'new_invention_classification': classification, 'phase2_original_gap_counts': original_counts,
         'phase2_to_extra_B0': original_checks}
    save_json(OUT/'report_diagnostics.json', d, compact=False)
    return d


def collect():
    snapshot = {'written': datetime.datetime.now().isoformat(), 'full_study_complete': False,
                'replay': read_json(OUT/'replay_summary.json'),
                'diagnostics': paired_diagnostics(),
                'coverage': {}, 'final_runs': [], 'evaluation': []}
    runs = list((OUT/'runs').rglob('complete.json'))
    rounds = list((OUT/'runs').rglob('round_*.json.gz'))
    evals = list((OUT/'evaluation').rglob('*.json.gz'))
    snapshot['coverage'] = {'completed_runs': len(runs), 'planned_runs': 72,
                            'training_round_records': len(rounds), 'planned_training_round_records': 432,
                            'held_out_records': len(evals), 'planned_held_out_records': 936,
                            'replay_records': len(list((OUT/'replay').glob('*.json.gz'))), 'planned_replay_records': 36}
    snapshot['full_study_complete'] = len(runs) == 72 and len(rounds) == 432 and len(evals) == 936
    with BridgeKernel() as k:
        for seed in phase2.SEEDS:
            phase2.bench.verify(phase2.instance_dir(seed))
        for completed in sorted(runs):
            folder = completed.parent
            records = [read_json(folder/f'round_{i}.json.gz') for i in range(1, 7)]
            r = records[-1]
            arm = r['method']
            seed = int(folder.parent.parent.name.split('_')[1])
            regime = folder.parent.name
            ts = r['training_seed']
            data = phase2.instance_dir(seed)
            latents = phase2.bench.read(data/'latent_library.json')
            probes = phase2.bench.read(data/'private.json')['recovery_probes']
            rec = recovery(k, r['grammar'], latents, regime, probes)
            param = {f['id'] for f in latents if f['reuse'][regime]['deliberate_active'] and f['parameter_values']}
            hits = set(rec['metrics']['behavioral']['recovered_latents'])
            metric_path = OUT/'metrics'/f'{seed}_{regime}_{ts}_{arm}_6.json.gz'
            try:
                if metric_path.exists():
                    metrics = read_json(metric_path)
                else:
                    metrics = exposure_and_parameters(k, r['frontiers'], r['task_names'], r['grammar'], latents, regime, probes)
                    save_json(metric_path, metrics)
                metric_failure = None
            except RuntimeError as exc:
                if 'closure exceeds' not in str(exc):
                    raise
                metrics, metric_failure = None, str(exc)
            row = {'arm': arm, 'seed': seed, 'regime': regime, 'training_seed': ts,
                   'solved': r['wake']['solved'], 'tasks': len(r['task_names']), 'invention_count': r['invention_count'],
                   'recovery': rec, 'parameterised_recall': len(hits & param)/len(param) if param else None,
                   'cumulative_recorded_compression_delta_mdl': sum(x['compression']['mdl']['delta_mdl'] for x in records),
                   'cumulative_raw_to_final_delta_mdl': sum(total_delta(x['compression']['mdl']) for x in records),
                   'metrics': metrics, 'metrics_failure': metric_failure}
            snapshot['final_runs'].append(row)
            print('final', arm, 'recall', rec['metrics']['behavioral']['recall'], 'parameter', row['parameterised_recall'], 'failure', metric_failure, flush=True)
    for arm in ARMS:
        rs = [read_json(p)['result'] for p in (OUT/'replay').glob(f'*_{arm}.json.gz')]
        summary = snapshot['replay']['arms'][arm]
        summary['raw_to_final_delta_mdl_mean'] = statistics.mean(total_delta(r['mdl_accounting']) for r in rs)
        summary['final_invention_count_mean'] = statistics.mean(sum('invented' in p['program'] for p in r['grammar_updates']['productions']) for r in rs)
        metric_rows = [read_json(p)['metrics'] for p in (OUT/'replay_metrics').glob(f'*_{arm}.json.gz')]
        summary['exact_syntactic_recall'] = statistics.mean(m['recovery']['metrics']['syntactic']['recall'] for m in metric_rows)
        summary['beta_recall'] = statistics.mean(m['recovery']['metrics']['beta']['recall'] for m in metric_rows)
    for p in sorted(evals):
        r = read_json(p)
        snapshot['evaluation'].append({'file': str(p.relative_to(ROOT)), 'arm': r['base_arm'],
                                       'seed': r['seed'], 'regime': r['regime'], 'training_seed': r['training_seed'],
                                       'iteration': r['iteration'], 'mode': r['mode'], 'summary': r['summary'],
                                       'first_solution_ranks': {t['name']: t['first_solution_nodes'] for t in r['per_task']}})
    snapshot['source_receipts'] = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in [OUT/'protocol.json', OUT/'replay_summary.json', OUT/'report_diagnostics.json', Path(__file__)]}
    save_json(OUT/'completed_evidence.json', snapshot, compact=False)
    return snapshot


if __name__ == '__main__':
    collect()
