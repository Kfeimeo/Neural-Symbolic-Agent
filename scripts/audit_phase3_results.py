"""Read saved Phase 3 evidence without rerunning searches or semantic metrics."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from statistics import mean


def read(p):
    with (gzip.open(p, 'rt', encoding='utf-8') if p.suffix == '.gz' else p.open(encoding='utf-8')) as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root', type=Path)
    args = ap.parse_args()
    root = args.root
    rows, missing, errors = [], [], []
    for seed in (101, 202, 303):
        latents = read(Path(f'benchmarks/latent_abstraction/data/seed_{seed}/latent_library.json'))
        parameter_ids = {f['id'] for f in latents if f['parameter_values'] and f['reuse']['medium']['deliberate_active']}
        for ts in (1, 2, 3):
            for arm in ('B0', 'B1', 'B2', 'B3'):
                folder = root / 'runs' / f'seed_{seed}' / 'medium' / f'{arm}_t{ts}'
                paths = [folder / 'complete.json'] + [folder / f'round_{i}.json.gz' for i in range(1, 7)]
                ep = {(mode, i): root / 'evaluation' / f'seed_{seed}' / 'medium' / f'{arm}_t{ts}_{mode}_{i}.json.gz'
                      for mode in ('library', 'recognition', 'shuffle') for i in (range(1, 7) if mode != 'shuffle' else [6])}
                missing.extend(str(p) for p in paths + list(ep.values()) if not p.exists())
                if any(not p.exists() for p in paths + list(ep.values())):
                    continue
                rounds = [read(p) for p in paths[1:]]
                ev = {key: read(p) for key, p in ep.items()}
                final = rounds[-1]
                e = ev['library', 6]
                rec = e['recovery']['metrics']['behavioral']
                for (mode, i), record in ev.items():
                    if (record['seed'], record['regime'], record['arm'], record['training_seed'], record['iteration'], record['mode']) != (seed, 'medium', f'{arm}_t{ts}', ts, i, mode):
                        errors.append(str(ep[mode, i]))
                    for budget, rate in record['summary']['curve'].items():
                        actual = mean(t['first_solution_nodes'] is not None and t['first_solution_nodes'] <= int(budget) for t in record['per_task'])
                        if abs(actual-rate) > 1e-10:
                            errors.append(f'curve mismatch {ep[mode, i]} {budget}')
                rows.append(dict(seed=seed, training_seed=ts, arm=arm, recovery=rec,
                    parameter_recall=len(parameter_ids & set(rec['recovered_latents']))/len(parameter_ids),
                    inventions=final['invention_count'], train_solve=final['wake']['solved']/len(final['task_names']),
                    cumulative_raw_delta_mdl=sum(r['compression']['mdl'].get('total_delta_mdl', r['compression']['mdl']['delta_mdl']) for r in rounds),
                    syntactic_er={f'ER@{k}': mean(v['count'] >= k for v in e['exposure'].values()) for k in (1, 2)},
                    heldout={mode: ev[mode, 6]['summary'] for mode in ('library', 'recognition', 'shuffle')}))
    summary = {}
    for arm in ('B0', 'B1', 'B2', 'B3'):
        rr = [r for r in rows if r['arm'] == arm]
        if not rr:
            continue
        summary[arm] = {k: mean(r[k] for r in rr) for k in ('parameter_recall', 'inventions', 'train_solve', 'cumulative_raw_delta_mdl')}
        summary[arm]['n'] = len(rr)
        summary[arm]['recovery'] = {k: mean(r['recovery'][k] for r in rr) for k in ('precision', 'recall', 'f1')}
        summary[arm]['syntactic_er'] = {k: mean(r['syntactic_er'][k] for r in rr) for k in ('ER@1', 'ER@2')}
        summary[arm]['curves'] = {m: {b: mean(r['heldout'][m]['curve'][b] for r in rr) for b in ('100', '300', '1000', '3000', '10000')} for m in ('library', 'recognition', 'shuffle')}
    paired = []
    for r in rows:
        if r['arm'] == 'B0':
            continue
        b = next(x for x in rows if x['arm'] == 'B0' and (x['seed'], x['training_seed']) == (r['seed'], r['training_seed']))
        paired.append(dict(seed=r['seed'], training_seed=r['training_seed'], arm=r['arm'], gained=sorted(set(r['recovery']['recovered_latents'])-set(b['recovery']['recovered_latents'])), lost=sorted(set(b['recovery']['recovered_latents'])-set(r['recovery']['recovered_latents']))))
    result = dict(scope='medium only; saved metrics, no new semantic evaluation', counts={pattern: len(list(root.glob(pattern))) for pattern in ('runs/**/complete.json', 'runs/**/round_*.json.gz', 'evaluation/**/*.json.gz')}, missing=missing, errors=errors, summary=summary, paired=paired, rows=rows,
                  unavailable=['behavioural ER', 'equivalence-usable ER', 'conditional parameter recovery', 'specialised invention matches'])
    out = root / 'audit'
    out.mkdir(exist_ok=True)
    (out / 'saved_evidence.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('rows', 'paired', 'summary')}, indent=2))


if __name__ == '__main__':
    main()
