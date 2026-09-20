"""Aggregate Phase 2 evaluation records (and the Phase 1 comparison arms) into the reported files.

Outputs (``results/full_dreamcoder/``)
--------------------------------------
``cells.json``        per (regime, arm, iteration): training solve rate, latent frontier
                      support (mean / median / distribution), ER@1, ER@2, behavioural
                      precision / recall / F1, held-out solve curve S(B) at every budget,
                      first-solution rank statistics, cost.  Means ± SD over instances.
``contrasts.json``    paired contrasts (two-way instance x task bootstrap) at every budget.
``per_latent.json``   one row per (instance, regime, active latent): perfect support,
                      support under every arm and iteration, recovery flags.
``gap_closure.json``  exposure / recovery / oracle gaps of B and how much of each
                      Full-DC closes, per regime.
``chain.json``        per-cohort deltas along recognition -> ER@2 -> recovery -> held-out
                      solve rate, with rank correlations.
``tables.md``         markdown tables consumed by PHASE2_REPORT.md.

Arm labels: ``B``, ``A``, ``A0``, ``O``, ``O_uniform``, ``B_wake10000``, ``PWS_B``, ``PW_D`` ...
are the Phase 1 records read unchanged; ``FullDC`` is the primary-seed Full-DC library
evaluated alone (Phase 1 protocol), ``FullDC_rec`` the same library searched with its
recognition model, ``FullDC_shuffle`` the derangement control; ``FullDC_t2`` /
``FullDC_t3`` are replication training seeds and ``FullDC_pool`` their per-instance
mean together with the primary seed (medium reuse only).
"""
import collections
import statistics

from benchmarks.latent_abstraction import generator as bench
from experiments.abstraction_learning.learner import read_json, save_json, ROUNDS, round_path
from experiments.abstraction_learning.evaluation import BUDGETS
from experiments.abstraction_learning.analysis import mstd, fmt, paired_bootstrap, spearman, pearson, table, final_iteration as phase1_final
from .run import RESULTS, PHASE1, SEEDS, REGIMES, TRAINING_SEEDS, PRIMARY_SEED, COMPARISON_ARMS, ARM, run_dir

MAX = str(max(BUDGETS))
TRAIN_TASKS = bench.TRAIN_PER_DEPTH * len(bench.TRAIN_DEPTHS)
MODE_SUFFIX = {'library': '', 'recognition': '_rec', 'shuffle': '_shuffle'}
POOL = f'{ARM}_pool'
FOCUS_ARMS = ['B', ARM, f'{ARM}_rec']
CONTRASTS = [(ARM, 'B'), (f'{ARM}_rec', 'B'), (f'{ARM}_rec', ARM), (f'{ARM}_rec', f'{ARM}_shuffle'), (f'{ARM}_shuffle', 'B'),
             (ARM, 'A'), (ARM, 'B_wake10000'), ('O', ARM), ('O', f'{ARM}_rec'), ('PWS_B', ARM), (ARM, 'PWS_B'), ('O', 'B'), ('PWS_B', 'B'),
             (f'{ARM}_t2', 'B'), (f'{ARM}_t3', 'B'), (POOL, 'B'), (f'{ARM}_t2_rec', 'B'), (f'{ARM}_t3_rec', 'B'), (f'{POOL}_rec', 'B'),
             ('O', POOL), ('PWS_B', POOL)]
EXPOSURE_ARMS = ['B', ARM, f'{ARM}_t2', f'{ARM}_t3', POOL, 'B_wake10000', 'PWS_B', 'PWS_D', 'PW_D', 'O']


def label_of(record):
    if record.get('base_arm') != ARM:
        return record['arm']
    base = ARM if record['training_seed'] == PRIMARY_SEED else f"{ARM}_t{record['training_seed']}"
    return base + MODE_SUFFIX[record['mode']]


def final_iteration(label):
    return ROUNDS if label.startswith(ARM) else phase1_final(label)


def load_records():
    records = []
    for seed in SEEDS:
        for path in sorted((RESULTS / 'evaluation' / f'seed_{seed}').glob('*/*.json.gz')):
            r = read_json(path)
            r['label'] = label_of(r)
            records.append(r)
        for path in sorted((PHASE1 / 'evaluation' / f'seed_{seed}').glob('*/*.json.gz')):
            r = read_json(path)
            if r['arm'] in COMPARISON_ARMS:
                r['label'] = r['arm']
                r['mode'] = 'library'
                records.append(r)
    return records


# ----------------------------------------------------------------------------- per-record metrics
def support_counts(r):
    return {k: v['count'] for k, v in (r.get('exposure') or {}).items()}


def exposure_recall(r, k):
    s = support_counts(r)
    return sum(c >= k for c in s.values()) / len(s) if s else None


def training_solve_rate(r):
    tr = r.get('training')
    if not tr or 'solved' not in tr or r['arm'].startswith('PW'):
        return None
    return tr['solved'] / TRAIN_TASKS


def solved_ranks(r):
    return [t['first_solution_nodes'] for t in r['per_task'] if t['first_solution_nodes'] is not None]


def wake_ranks(r):
    tr = r.get('training') or {}
    return [v for v in (tr.get('wake_first_solution_nodes') or {}).values() if v is not None]


def quantile(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    pos = (len(xs) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def scalar_metrics(r):
    s = support_counts(r)
    beh = r['recovery']['metrics']['behavioral']
    ranks = solved_ranks(r)
    wr = wake_ranks(r)
    m = {'training_solve_rate': training_solve_rate(r), 'er1': exposure_recall(r, 1), 'er2': exposure_recall(r, 2),
         'support_mean': statistics.mean(s.values()) if s else None, 'support_median': statistics.median(s.values()) if s else None,
         'recall': beh['recall'], 'precision': beh['precision'], 'f1': beh['f1'], 'weighted_recall': beh['weighted_recall'],
         'canonical_recall': r['recovery']['metrics']['canonical']['recall'], 'learned_count': r['recovery']['learned_count'],
         'library_size': r['library_size'], 'probe_consistent_rate': r['summary']['probe_consistent_rate'],
         'rank_mean_solved': statistics.mean(ranks) if ranks else None, 'rank_median_solved': statistics.median(ranks) if ranks else None,
         'rank_q1_solved': quantile(ranks, .25), 'rank_q3_solved': quantile(ranks, .75),
         'rank_log10_mean_solved': statistics.mean(__import__('math').log10(x) for x in ranks) if ranks else None,
         'solved_count': len(ranks), 'task_count': len(r['per_task']),
         'expanded_states': r['batch'].get('expanded_states'), 'max_expanded_states': r['batch'].get('max_expanded_states', r['batch'].get('expanded_states')),
         'state_limited_tasks': r['batch'].get('state_limited_tasks', 0 if r['batch'].get('stop_reason') == 'candidate_budget' else None),
         'eval_seconds': r['batch'].get('seconds'),
         'wake_rank_mean_solved': statistics.mean(wr) if wr else None, 'wake_solved_this_round': len(wr) if r.get('training') and 'wake_first_solution_nodes' in r['training'] else None,
         'delta_mdl_round': (r.get('training') or {}).get('mdl', {}).get('delta_mdl'),
         'mean_delta_L': r['summary']['mean_delta_L'], 'fraction_shortened': r['summary']['fraction_shortened']}
    for n in map(str, BUDGETS):
        m[f'solve_{n}'] = r['summary']['curve'].get(n)
    for d, row in r['summary']['by_depth'].items():
        m[f'depth_{d}'] = row.get(MAX)
    for t, row in r['summary']['by_transfer'].items():
        m[f'transfer_{t}'] = row.get(MAX)
    tr = r.get('training') or {}
    if r.get('base_arm') == ARM:
        m.update(wake_seconds=tr.get('wake_seconds'), guidance_seconds=tr.get('guidance_seconds'), compression_seconds=tr.get('compression_seconds'),
                 dream_seconds=(tr.get('dream') or {}).get('seconds'), recognition_seconds=(tr.get('recognition') or {}).get('seconds'),
                 dream_accepted=(tr.get('dream') or {}).get('accepted'), replay_frontiers=(tr.get('recognition') or {}).get('replay_frontiers'))
    else:
        m.update(wake_seconds=tr.get('wake_seconds'), compression_seconds=tr.get('compression_seconds'))
    return m


def mean_or_none(values):
    vals = [v for v in values if v is not None]
    return statistics.mean(vals) if vals else None


# ----------------------------------------------------------------------------- grouping
def group(records):
    """(regime, label, iteration) -> instance -> [records]; pooled labels add the per-instance seed lists."""
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in records:
        by[(r['regime'], r['label'], r['iteration'])][r['seed']].append(r)
    pooled = collections.defaultdict(lambda: collections.defaultdict(list))
    for (regime, label, it), per_seed in by.items():
        if not label.startswith(ARM) or '_pool' in label:
            continue
        stem = label[len(ARM):]
        parts = stem.split('_')
        ts = int(parts[1][1:]) if len(parts) > 1 and parts[1].startswith('t') else PRIMARY_SEED
        suffix = '_' + '_'.join(p for p in parts[1:] if not p.startswith('t')) if any(not p.startswith('t') for p in parts[1:]) else ''
        if len(TRAINING_SEEDS[regime]) > 1 and ts in TRAINING_SEEDS[regime]:
            for seed, recs in per_seed.items():
                pooled[(regime, POOL + suffix, it)][seed].extend(recs)
    for key, per_seed in pooled.items():
        if all(len(recs) == len(TRAINING_SEEDS[key[0]]) for recs in per_seed.values()):
            by[key] = per_seed
    return by


def cell_of(regime, label, iteration, per_seed):
    metrics = collections.defaultdict(list)
    per_instance = {}
    for seed, recs in sorted(per_seed.items()):
        ms = [scalar_metrics(r) for r in recs]
        per_instance[str(seed)] = {k: mean_or_none(m.get(k) for m in ms) for k in ms[0]}
        for k, v in per_instance[str(seed)].items():
            metrics[k].append(v)
    supports = [c for recs in per_seed.values() for r in recs for c in support_counts(r).values()]
    hist = collections.Counter(min(c, 6) for c in supports)
    ranks = [t['first_solution_nodes'] for recs in per_seed.values() for r in recs for t in r['per_task'] if t['first_solution_nodes'] is not None]
    return {'regime': regime, 'label': label, 'iteration': iteration, 'n_instances': len(per_seed), 'records_per_instance': {str(s): len(v) for s, v in per_seed.items()},
            'metrics': {k: mstd(v) for k, v in metrics.items()}, 'per_instance': per_instance,
            'ranks': sorted(ranks), 'rank_task_count': sum(len(r['per_task']) for recs in per_seed.values() for r in recs),
            'support_histogram': {str(k): hist.get(k, 0) for k in range(7)}, 'support_histogram_note': 'counts of active latents (pooled over instances and seeds) by frontier support; 6 = six or more',
            'curve': {n: mstd(metrics[f'solve_{n}']) for n in map(str, BUDGETS)}}


# ----------------------------------------------------------------------------- analysis
def analyze():
    records = load_records()
    if not any(r.get('base_arm') == ARM for r in records):
        raise RuntimeError('No Phase 2 evaluation records found')
    by = group(records)
    labels = sorted({k[1] for k in by})
    cells = [cell_of(regime, label, it, per_seed) for (regime, label, it), per_seed in sorted(by.items(), key=lambda kv: (REGIMES.index(kv[0][0]), kv[0][1], kv[0][2]))]
    cell = {(c['regime'], c['label'], c['iteration']): c for c in cells}

    # ---- paired contrasts at every budget (final iterations)
    contrasts = []
    for regime in REGIMES:
        for x, y in CONTRASTS:
            kx, ky = (regime, x, final_iteration(x)), (regime, y, final_iteration(y))
            if kx not in by or ky not in by:
                continue
            common = sorted(set(by[kx]) & set(by[ky]))
            if not common:
                continue
            for budget in BUDGETS:
                matrix = []
                for seed in common:
                    def solved_map(recs):
                        acc = collections.defaultdict(list)
                        for r in recs:
                            for t in r['per_task']:
                                acc[t['name']].append(float(t['first_solution_nodes'] is not None and t['first_solution_nodes'] <= budget))
                        return {n: statistics.mean(v) for n, v in acc.items()}
                    a, b = solved_map(by[kx][seed]), solved_map(by[ky][seed])
                    names = sorted(a)
                    assert names == sorted(b), 'task sets differ'
                    matrix.append([a[n] - b[n] for n in names])
                stats = paired_bootstrap(matrix)
                contrasts.append({'regime': regime, 'contrast': f'{x}-{y}', 'budget': budget, 'seeds': common, **(stats or {})})
    con = {(c['regime'], c['contrast'], c['budget']): c for c in contrasts}

    # ---- per-latent exposure and recovery
    per_latent = []
    for seed in SEEDS:
        latents = bench.read(bench.DATA / f'seed_{seed}' / 'latent_library.json')
        for regime in REGIMES:
            for f in latents:
                if not f['reuse'][regime]['deliberate_active']:
                    continue
                row = {'seed': seed, 'regime': regime, 'latent': f['id'], 'kind': f['kind'], 'depth': f['depth'], 'expression': f['expression'],
                       'training_deliberate': f['reuse'][regime]['training_deliberate_count'], 'training_occurrences': f['reuse'][regime]['training_occurrence_count'],
                       'perfect_support': f['reuse'][regime]['training_distinct_tasks'], 'test_deliberate': f['reuse'][regime]['test_deliberate_count'],
                       'support': {}, 'support_by_iteration': {}, 'recovered': {}, 'recovered_by_iteration': {}}
                for label in labels:
                    if label.endswith('_rec') or label.endswith('_shuffle') or '_pool' in label:
                        continue
                    fin = by.get((regime, label, final_iteration(label)), {}).get(seed)
                    if not fin:
                        continue
                    r = fin[0]
                    if r.get('exposure') and f['id'] in r['exposure']:
                        row['support'][label] = r['exposure'][f['id']]['count']
                    row['recovered'][label] = f['id'] in r['recovery']['metrics']['behavioral']['recovered_latents']
                    if final_iteration(label) == ROUNDS:
                        row['support_by_iteration'][label] = [by.get((regime, label, it), {}).get(seed, [{}])[0].get('exposure', {}).get(f['id'], {}).get('count') for it in range(1, ROUNDS + 1)]
                        row['recovered_by_iteration'][label] = [f['id'] in by.get((regime, label, it), {}).get(seed, [{'recovery': {'metrics': {'behavioral': {'recovered_latents': []}}}}])[0]['recovery']['metrics']['behavioral']['recovered_latents'] for it in range(1, ROUNDS + 1)]
                per_latent.append(row)

    recovery_by_support = []
    for regime in REGIMES:
        if regime == 'zero':
            continue
        rows = [p for p in per_latent if p['regime'] == regime]
        for label in EXPOSURE_ARMS:
            if '_pool' in label:
                continue
            have = [p for p in rows if label in p['support'] and label in p['recovered']]
            if not have:
                continue
            ge2 = [p for p in have if p['support'][label] >= 2]
            lt2 = [p for p in have if p['support'][label] < 2]
            one = [p for p in have if p['support'][label] == 1]
            zero = [p for p in have if p['support'][label] == 0]
            def rate(ps):
                return sum(p['recovered'][label] for p in ps) / len(ps) if ps else None
            recovery_by_support.append({'regime': regime, 'label': label, 'latents': len(have),
                                        'n_ge2': len(ge2), 'p_recovered_ge2': rate(ge2), 'n_lt2': len(lt2), 'p_recovered_lt2': rate(lt2),
                                        'n_1': len(one), 'p_recovered_1': rate(one), 'n_0': len(zero), 'p_recovered_0': rate(zero),
                                        'recovered_ge2': sum(p['recovered'][label] for p in ge2), 'recovered_lt2': sum(p['recovered'][label] for p in lt2)})
    transitions = []
    for regime in REGIMES:
        if regime == 'zero':
            continue
        for label in [ARM, f'{ARM}_t2', f'{ARM}_t3', 'B_wake10000']:
            rows = [p for p in per_latent if p['regime'] == regime and 'B' in p['support'] and label in p['support']]
            if not rows:
                continue
            cats = collections.OrderedDict((('B<2,X<2', []), ('B<2,X>=2', []), ('B>=2,X<2', []), ('B>=2,X>=2', [])))
            for p in rows:
                cats[f"{'B>=2' if p['support']['B'] >= 2 else 'B<2'},{'X>=2' if p['support'][label] >= 2 else 'X<2'}"].append(p)
            transitions.append({'regime': regime, 'X': label, 'latents': len(rows),
                                'cells': {c: {'n': len(ps), 'recovered_by_B': sum(p['recovered']['B'] for p in ps), 'recovered_by_X': sum(p['recovered'][label] for p in ps),
                                              'mean_support_B': mean_or_none(p['support']['B'] for p in ps), 'mean_support_X': mean_or_none(p['support'][label] for p in ps)} for c, ps in cats.items()},
                                'support_change': {'raised': sum(p['support'][label] > p['support']['B'] for p in rows), 'unchanged': sum(p['support'][label] == p['support']['B'] for p in rows),
                                                   'lowered': sum(p['support'][label] < p['support']['B'] for p in rows)}})

    # ---- gap closure
    def m(regime, label, key, it=None):
        c = cell.get((regime, label, final_iteration(label) if it is None else it))
        return None if c is None else c['metrics'].get(key, {}).get('mean')
    perfect_er2 = {}
    for regime in REGIMES:
        vals = []
        for seed in SEEDS:
            rows = [p for p in per_latent if p['regime'] == regime and p['seed'] == seed]
            if rows:
                vals.append(sum(p['perfect_support'] >= 2 for p in rows) / len(rows))
        perfect_er2[regime] = statistics.mean(vals) if vals else None

    def closure(x, base, ref):
        if x is None or base is None or ref is None or abs(ref - base) < 1e-9:
            return None
        return (x - base) / (ref - base)
    gaps = []
    for regime in REGIMES:
        arms_here = [ARM] + ([POOL] if (regime, POOL, ROUNDS) in cell else [])
        for a in arms_here:
            row = {'regime': regime, 'arm': a,
                   'exposure': {'B': m(regime, 'B', 'er2'), 'FullDC': m(regime, a, 'er2'), 'B_wake10000': m(regime, 'B_wake10000', 'er2'), 'PWS_B': m(regime, 'PWS_B', 'er2'),
                                'perfect': perfect_er2[regime], 'er1_B': m(regime, 'B', 'er1'), 'er1_FullDC': m(regime, a, 'er1')},
                   'recovery': {'B': m(regime, 'B', 'recall'), 'FullDC': m(regime, a, 'recall'), 'B_wake10000': m(regime, 'B_wake10000', 'recall'), 'PWS_B': m(regime, 'PWS_B', 'recall'),
                                'PW_D': m(regime, 'PW_D', 'recall'), 'PWS_D': m(regime, 'PWS_D', 'recall'), 'oracle': 1.0 if regime != 'zero' else None},
                   'solve': {'A': m(regime, 'A', f'solve_{MAX}'), 'B': m(regime, 'B', f'solve_{MAX}'), 'FullDC': m(regime, a, f'solve_{MAX}'), 'FullDC_rec': m(regime, a + '_rec', f'solve_{MAX}'),
                             'FullDC_shuffle': m(regime, a + '_shuffle', f'solve_{MAX}'), 'B_wake10000': m(regime, 'B_wake10000', f'solve_{MAX}'), 'PWS_B': m(regime, 'PWS_B', f'solve_{MAX}'),
                             'O': m(regime, 'O', f'solve_{MAX}'), 'O_uniform': m(regime, 'O_uniform', f'solve_{MAX}')},
                   'training_solve': {'B': m(regime, 'B', 'training_solve_rate'), 'FullDC': m(regime, a, 'training_solve_rate'), 'B_wake10000': m(regime, 'B_wake10000', 'training_solve_rate'), 'O': m(regime, 'O', 'training_solve_rate')}}
            row['closure'] = {'exposure_vs_perfect': closure(row['exposure']['FullDC'], row['exposure']['B'], row['exposure']['perfect']),
                              'exposure_vs_PWS': closure(row['exposure']['FullDC'], row['exposure']['B'], row['exposure']['PWS_B']),
                              'recovery_vs_PWS_B': closure(row['recovery']['FullDC'], row['recovery']['B'], row['recovery']['PWS_B']),
                              'recovery_vs_oracle': closure(row['recovery']['FullDC'], row['recovery']['B'], row['recovery']['oracle']),
                              'solve_library_vs_O': closure(row['solve']['FullDC'], row['solve']['B'], row['solve']['O']),
                              'solve_recognition_vs_O': closure(row['solve']['FullDC_rec'], row['solve']['B'], row['solve']['O']),
                              'solve_library_vs_PWS_B': closure(row['solve']['FullDC'], row['solve']['B'], row['solve']['PWS_B'])}
            row['remaining'] = {'exposure_gap_to_perfect': None if row['exposure']['FullDC'] is None or row['exposure']['perfect'] is None else row['exposure']['perfect'] - row['exposure']['FullDC'],
                                'recovery_gap_to_PWS_B': None if row['recovery']['FullDC'] is None or row['recovery']['PWS_B'] is None else row['recovery']['PWS_B'] - row['recovery']['FullDC'],
                                'recovery_gap_to_oracle': None if row['recovery']['FullDC'] is None or row['recovery']['oracle'] is None else row['recovery']['oracle'] - row['recovery']['FullDC'],
                                'oracle_gap_library': None if row['solve']['FullDC'] is None or row['solve']['O'] is None else row['solve']['O'] - row['solve']['FullDC'],
                                'oracle_gap_recognition': None if row['solve']['FullDC_rec'] is None or row['solve']['O'] is None else row['solve']['O'] - row['solve']['FullDC_rec']}
            gaps.append(row)

    # ---- causal chain per cohort
    chain_rows = []
    for regime in REGIMES:
        for seed in SEEDS:
            b = cell.get((regime, 'B', ROUNDS), {}).get('per_instance', {}).get(str(seed))
            f = cell.get((regime, ARM, ROUNDS), {}).get('per_instance', {}).get(str(seed))
            fr = cell.get((regime, f'{ARM}_rec', ROUNDS), {}).get('per_instance', {}).get(str(seed))
            if not b or not f:
                continue
            chain_rows.append({'regime': regime, 'seed': seed,
                               'd_training_solve': f['training_solve_rate'] - b['training_solve_rate'],
                               'd_er1': None if f['er1'] is None else f['er1'] - b['er1'], 'd_er2': None if f['er2'] is None else f['er2'] - b['er2'],
                               'd_recall': None if f['recall'] is None else f['recall'] - b['recall'],
                               'd_solve_library': f[f'solve_{MAX}'] - b[f'solve_{MAX}'],
                               'd_solve_recognition': None if not fr else fr[f'solve_{MAX}'] - b[f'solve_{MAX}'],
                               'B': {k: b[k] for k in ['training_solve_rate', 'er1', 'er2', 'recall', f'solve_{MAX}']},
                               'FullDC': {k: f[k] for k in ['training_solve_rate', 'er1', 'er2', 'recall', f'solve_{MAX}']},
                               'FullDC_rec_solve': None if not fr else fr[f'solve_{MAX}']})
    reuse_rows = [r for r in chain_rows if r['regime'] != 'zero' and r['d_er2'] is not None]
    def corr(a, b):
        xs = [r[a] for r in reuse_rows if r[a] is not None and r[b] is not None]
        ys = [r[b] for r in reuse_rows if r[a] is not None and r[b] is not None]
        return {'n': len(xs), 'spearman': spearman(xs, ys), 'pearson': pearson(xs, ys)}
    chain = {'cohorts': chain_rows,
             'correlations_over_reuse_cohorts': {'d_training_solve_vs_d_er2': corr('d_training_solve', 'd_er2'), 'd_er2_vs_d_recall': corr('d_er2', 'd_recall'),
                                                 'd_recall_vs_d_solve_library': corr('d_recall', 'd_solve_library'), 'd_er2_vs_d_solve_library': corr('d_er2', 'd_solve_library'),
                                                 'd_recall_vs_d_solve_recognition': corr('d_recall', 'd_solve_recognition')},
             'sign_counts': {k: {'positive': sum(r[k] > 1e-9 for r in reuse_rows if r[k] is not None), 'zero': sum(abs(r[k]) <= 1e-9 for r in reuse_rows if r[k] is not None),
                                 'negative': sum(r[k] < -1e-9 for r in reuse_rows if r[k] is not None)} for k in ['d_training_solve', 'd_er2', 'd_recall', 'd_solve_library', 'd_solve_recognition']},
             'note': 'deltas are FullDC (primary training seed) minus B per (instance, regime) cohort at the final iteration; correlations pool the nine reuse cohorts'}

    # ---- training-task detail from the round records (persistent solved sets by depth; wake ranks)
    training_detail = []
    for regime in REGIMES:
        for seed in SEEDS:
            meta = bench.read(bench.DATA / f'seed_{seed}' / 'private.json')['tasks']
            row = {'regime': regime, 'seed': seed, 'by_depth': {}, 'newly_solved_by_FullDC': [], 'lost_by_FullDC': []}
            paths = {'B': PHASE1 / 'runs' / f'seed_{seed}' / regime / 'B', ARM: run_dir(seed, regime, PRIMARY_SEED)}
            solved_sets = {}
            for label, folder in paths.items():
                p = round_path(folder, ROUNDS)
                if not p.exists():
                    continue
                rec = read_json(p)
                solved_sets[label] = {n for n, f in zip(rec['task_names'], rec['frontiers']) if f['entries']}
                row[f'{label}_per_round_wake_solved'] = []
                row[f'{label}_per_round_wake_rank_mean'] = []
                for it in range(1, ROUNDS + 1):
                    rr = read_json(round_path(folder, it))
                    ranks = [v for v in rr['wake']['first_solution_nodes'].values() if v is not None]
                    row[f'{label}_per_round_wake_solved'].append(len(ranks))
                    row[f'{label}_per_round_wake_rank_mean'].append(statistics.mean(ranks) if ranks else None)
            if len(solved_sets) < 2:
                continue
            for d in bench.TRAIN_DEPTHS:
                names = [n for n in solved_sets['B'] | solved_sets[ARM] | {n for n, mm in meta.items() if mm['split'] == 'train' and mm['regime'] == regime and mm['depth'] == d} if meta[n]['depth'] == d and meta[n]['regime'] == regime and meta[n]['split'] == 'train']
                row['by_depth'][str(d)] = {'tasks': len(names), 'B': sum(n in solved_sets['B'] for n in names), 'FullDC': sum(n in solved_sets[ARM] for n in names)}
            row['newly_solved_by_FullDC'] = sorted(solved_sets[ARM] - solved_sets['B'])
            row['lost_by_FullDC'] = sorted(solved_sets['B'] - solved_sets[ARM])
            row['newly_solved_depths'] = collections.Counter(meta[n]['depth'] for n in row['newly_solved_by_FullDC'])
            row['newly_solved_with_deliberate_latent'] = sum(bool(meta[n]['deliberate_latent_use']) for n in row['newly_solved_by_FullDC'])
            training_detail.append(row)

    parity = read_json(RESULTS / 'parity.json') if (RESULTS / 'parity.json').exists() else None
    save_json(RESULTS / 'cells.json', {'budgets': BUDGETS, 'rounds': ROUNDS, 'labels': labels, 'cells': cells,
                                       'notes': ['Means ± sample SD over benchmark instances; pooled labels first average the training seeds within an instance.',
                                                 'solve_N = held-out solve rate at N complete candidates (prefix-exact); rank statistics are over solved held-out tasks only.',
                                                 'er1/er2 = fraction of active latents with frontier support in >= 1 / >= 2 distinct training tasks (Phase 1 structural criterion).',
                                                 'training_solve_rate = solved persistent frontiers / 56 training tasks.']}, compact=False)
    save_json(RESULTS / 'contrasts.json', {'contrasts': contrasts, 'note': 'two-way paired bootstrap over instances and their held-out tasks; solved indicators averaged over training seeds for pooled labels'}, compact=False)
    save_json(RESULTS / 'per_latent.json', {'per_latent': per_latent, 'recovery_by_support': recovery_by_support, 'transitions': transitions,
                                            'notes': ['support = number of distinct training tasks whose persistent frontier structurally contains the latent (Phase 1 criterion; evaluation-only).',
                                                      'perfect_support = distinct training tasks whose generating program contains the latent (the support a perfect Wake would give).',
                                                      'recovered = behaviourally recovered by at least one invention of the final library (Phase 1 criterion).']}, compact=False)
    save_json(RESULTS / 'gap_closure.json', {'rows': gaps, 'perfect_er2': perfect_er2,
                                             'note': 'closure = (FullDC - B) / (reference - B) with the reference named in the key; undefined when the reference equals B'}, compact=False)
    save_json(RESULTS / 'chain.json', chain, compact=False)
    save_json(RESULTS / 'training_detail.json', {'rows': training_detail}, compact=False)
    write_tables(cells, cell, contrasts, con, per_latent, recovery_by_support, transitions, gaps, perfect_er2, chain, training_detail, parity, labels)
    return {'records': len(records), 'cells': len(cells), 'contrasts': len(contrasts)}


# ----------------------------------------------------------------------------- tables
def ci(c):
    return 'n/a' if not c or 'mean' not in c else f"{c['mean']:+.3f} [{c['paired_bootstrap_95_ci'][0]:.3f}, {c['paired_bootstrap_95_ci'][1]:.3f}]"


def write_tables(cells, cell, contrasts, con, per_latent, recovery_by_support, transitions, gaps, perfect_er2, chain, training_detail, parity, labels):
    L = ['# Generated tables (experiments/full_dreamcoder/analysis.py)', '']
    have = lambda regime, label, it=None: (regime, label, final_iteration(label) if it is None else it) in cell
    M = lambda regime, label, key, it=None, digits=3: fmt(cell[(regime, label, final_iteration(label) if it is None else it)]['metrics'].get(key), digits) if have(regime, label, it) else 'n/a'

    if parity:
        L += ['## Reproducibility: round-1 parity with B and re-evaluation of a Phase 1 grammar', '',
              table(['Instance', 'Reuse', 'Training seed', 'Same round-1 frontiers', 'Same round-1 grammar', 'Same Wake ranks', 'Solved (FullDC, B)'],
                    [[r['seed'], r['regime'], r['training_seed'], r['same_frontiers'], r['same_grammar'], r['same_wake_ranks'], r['solved']] for r in parity['round1']]), '',
              table(['Instance', 'Reuse', 'Phase 1 arm', 'Identical first-solution ranks', 'Differences'],
                    [[r['seed'], r['regime'], f"{r['arm']}@{r['iteration']}", r['identical_first_solution_ranks'], r['differences']] for r in parity['phase1_reevaluation']]), '']

    trained = [l for l in ['B', ARM, f'{ARM}_t2', f'{ARM}_t3', POOL, 'B_wake10000', 'A', 'O'] if l in labels or l == POOL]
    L += ['## Training solve rate by Explore-Compress iteration (solved persistent frontiers / 56)', '']
    for regime in REGIMES:
        rows = [[l] + [M(regime, l, 'training_solve_rate', it) for it in range(1, ROUNDS + 1)] for l in trained if have(regime, l, ROUNDS)]
        L += [f'Reuse = {regime}:', '', table(['Arm'] + [f'it {it}' for it in range(1, ROUNDS + 1)], rows), '']

    L += ['## Latent frontier support and exposure recall by iteration', '',
          'ER@1 / ER@2 = fraction of active latents with support in >= 1 / >= 2 distinct training tasks. Perfect = support of the generating programs; PWS_B = ground-truth programs of the depth <= 4 training tasks.', '']
    for regime in REGIMES:
        if regime == 'zero':
            continue
        rows = []
        for l in [x for x in ['B', ARM, f'{ARM}_t2', f'{ARM}_t3', POOL, 'B_wake10000'] if have(regime, x, ROUNDS)]:
            rows.append([l, 'ER@1'] + [M(regime, l, 'er1', it, 2) for it in range(1, ROUNDS + 1)])
            rows.append([l, 'ER@2'] + [M(regime, l, 'er2', it, 2) for it in range(1, ROUNDS + 1)])
        rows.append(['perfect Wake', 'ER@2'] + [fmt(perfect_er2[regime], 2)] * ROUNDS)
        if have(regime, 'PWS_B'):
            rows.append(['PWS_B (depth<=4 truth)', 'ER@2'] + [M(regime, 'PWS_B', 'er2', 1, 2)] * ROUNDS)
        L += [f'Reuse = {regime}:', '', table(['Arm', 'Metric'] + [f'it {it}' for it in range(1, ROUNDS + 1)], rows), '']
    rows = []
    for regime in REGIMES:
        if regime == 'zero':
            continue
        for l in [x for x in EXPOSURE_ARMS if have(regime, x)]:
            c = cell[(regime, l, final_iteration(l))]
            rows.append([regime, l, fmt(c['metrics']['support_mean'], 2), fmt(c['metrics']['support_median'], 1), fmt(c['metrics']['er1'], 2), fmt(c['metrics']['er2'], 2),
                         ' / '.join(str(c['support_histogram'][str(k)]) for k in range(7))])
    L += ['Final-iteration support distribution (histogram over active latents pooled over instances: support 0 / 1 / 2 / 3 / 4 / 5 / >=6):', '',
          table(['Reuse', 'Arm', 'Mean support', 'Median', 'ER@1', 'ER@2', 'Histogram 0/1/2/3/4/5/6+'], rows), '']

    L += ['## Behavioural abstraction recovery (final library)', '']
    rows = []
    for regime in REGIMES:
        if regime == 'zero':
            continue
        for l in [x for x in ['B', ARM, f'{ARM}_t2', f'{ARM}_t3', POOL, 'B_wake10000', 'PWS_B', 'PWS_D', 'PW_D'] if have(regime, x)]:
            rows.append([regime, l, M(regime, l, 'learned_count', None, 1), M(regime, l, 'canonical_recall'), M(regime, l, 'precision'), M(regime, l, 'recall'), M(regime, l, 'f1'), M(regime, l, 'weighted_recall')])
    L += [table(['Reuse', 'Arm', 'Inventions', 'Canonical recall', 'Behav. precision', 'Behav. recall', 'Behav. F1', 'Weighted recall'], rows), '']
    L += ['Behavioural recall by iteration:', '']
    for regime in REGIMES:
        if regime == 'zero':
            continue
        rows = [[l] + [M(regime, l, 'recall', it, 2) for it in range(1, ROUNDS + 1)] for l in ['B', ARM, f'{ARM}_t2', f'{ARM}_t3', POOL, 'B_wake10000'] if have(regime, l, ROUNDS)]
        L += [f'Reuse = {regime}:', '', table(['Arm'] + [f'it {it}' for it in range(1, ROUNDS + 1)], rows), '']
    rows = [[r['regime'], r['label'], r['latents'], f"{r['recovered_ge2']}/{r['n_ge2']}", fmt(r['p_recovered_ge2'], 2), f"{r['recovered_lt2']}/{r['n_lt2']}", fmt(r['p_recovered_lt2'], 2),
             r['n_1'], fmt(r['p_recovered_1'], 2), r['n_0'], fmt(r['p_recovered_0'], 2)] for r in recovery_by_support]
    L += ['Recovery conditional on frontier support (latents pooled over instances, final iteration):', '',
          table(['Reuse', 'Arm', 'Active latents', 'Recovered | support>=2', 'P', 'Recovered | support<2', 'P', 'n support=1', 'P(rec | 1)', 'n support=0', 'P(rec | 0)'], rows), '']
    rows = []
    for t in transitions:
        for c, v in t['cells'].items():
            rows.append([t['regime'], t['X'], c.replace('X', t['X']), v['n'], v['recovered_by_B'], v['recovered_by_X'], fmt(v['mean_support_B'], 1), fmt(v['mean_support_X'], 1)])
    L += ['Exposure transitions from B to the recognition-on arm (X) and recovery in each cell:', '',
          table(['Reuse', 'X', 'Cell', 'Latents', 'Recovered by B', 'Recovered by X', 'Mean support B', 'Mean support X'], rows), '']
    rows = [[t['regime'], t['X'], t['support_change']['raised'], t['support_change']['unchanged'], t['support_change']['lowered']] for t in transitions]
    L += [table(['Reuse', 'X', 'Support raised', 'Unchanged', 'Lowered'], rows), '']

    L += ['## Held-out solve rate S(B) at every candidate budget (final iteration; unsolved tasks have r > 10000)', '']
    eval_arms = [x for x in ['A0', 'A', 'B', ARM, f'{ARM}_rec', f'{ARM}_shuffle', f'{ARM}_t2', f'{ARM}_t2_rec', f'{ARM}_t3', f'{ARM}_t3_rec', POOL, f'{POOL}_rec', 'B_wake10000', 'PWS_B', 'O', 'O_uniform'] if x in labels or POOL in x]
    for regime in REGIMES:
        rows = [[l] + [fmt(cell[(regime, l, final_iteration(l))]['curve'][str(n)]) for n in BUDGETS] + [M(regime, l, 'probe_consistent_rate')] for l in eval_arms if have(regime, l)]
        L += [f'Reuse = {regime}:', '', table(['Arm'] + [f'S({n})' for n in BUDGETS] + ['Probe-consistent'], rows), '']
    L += ['Held-out solve rate at 10000 by iteration:', '']
    for regime in REGIMES:
        rows = [[l] + [M(regime, l, f'solve_{MAX}', it) for it in range(1, ROUNDS + 1)] for l in ['B', ARM, f'{ARM}_rec', POOL, f'{POOL}_rec', 'B_wake10000', 'A', 'O'] if have(regime, l, ROUNDS)]
        L += [f'Reuse = {regime}:', '', table(['Arm'] + [f'it {it}' for it in range(1, ROUNDS + 1)], rows), '']
    rows = []
    for regime in REGIMES:
        for x, y in CONTRASTS:
            c = con.get((regime, f'{x}-{y}', max(BUDGETS)))
            if c and 'mean' in c:
                rows.append([regime, f'{x}-{y}'] + [ci(con.get((regime, f'{x}-{y}', n))) for n in BUDGETS])
    L += ['Paired contrasts (mean difference in solve rate with two-way bootstrap 95% CI) at every budget:', '',
          table(['Reuse', 'Contrast'] + [f'B={n}' for n in BUDGETS], rows), '']
    L += ['Solve rate at 10000 by held-out depth (final iteration):', '']
    for regime in REGIMES:
        depths = sorted({k for l in eval_arms if have(regime, l) for k in cell[(regime, l, final_iteration(l))]['metrics'] if k.startswith('depth_')}, key=lambda k: int(k.split('_')[1]))
        rows = [[l] + [M(regime, l, d, None, 2) for d in depths] for l in eval_arms if have(regime, l)]
        L += [f'Reuse = {regime}:', '', table(['Arm'] + [d.replace('depth_', 'd=') for d in depths], rows), '']
    L += ['Solve rate at 10000 by transfer type (final iteration):', '']
    for regime in REGIMES:
        ts = sorted({k for l in eval_arms if have(regime, l) for k in cell[(regime, l, final_iteration(l))]['metrics'] if k.startswith('transfer_')})
        rows = [[l] + [M(regime, l, t, None, 2) for t in ts] for l in eval_arms if have(regime, l)]
        L += [f'Reuse = {regime}:', '', table(['Arm'] + [t.replace('transfer_', '') for t in ts], rows), '']

    L += ['## First-solution search cost (held-out, final iteration; statistics over solved tasks, mean over instances)', '']
    rows = []
    for regime in REGIMES:
        for l in eval_arms:
            if have(regime, l):
                c = cell[(regime, l, final_iteration(l))]['metrics']
                rows.append([regime, l, fmt(c['solved_count'], 1), fmt(c['rank_mean_solved'], 0), fmt(c['rank_median_solved'], 0), fmt(c['rank_q1_solved'], 0), fmt(c['rank_q3_solved'], 0),
                             fmt(c['rank_log10_mean_solved'], 2), fmt(c['max_expanded_states'], 0), fmt(c['state_limited_tasks'], 1)])
    L += [table(['Reuse', 'Arm', 'Solved tasks', 'Mean rank', 'Median', 'Q1', 'Q3', 'Mean log10 rank', 'Max expanded states', 'State-limited tasks'], rows), '']
    L += ['Training Wake search cost per round (tasks solved in that round\'s Wake within 3000 candidates; mean first-solution rank over them):', '']
    for regime in REGIMES:
        rows = []
        for l in ['B', ARM]:
            drows = [d for d in training_detail if d['regime'] == regime and f'{l}_per_round_wake_solved' in d]
            if not drows:
                continue
            rows.append([l, 'solved'] + [fmt(statistics.mean(d[f'{l}_per_round_wake_solved'][it - 1] for d in drows), 1) for it in range(1, ROUNDS + 1)])
            rows.append([l, 'mean rank'] + [fmt(mean_or_none(d[f'{l}_per_round_wake_rank_mean'][it - 1] for d in drows), 0) for it in range(1, ROUNDS + 1)])
        L += [f'Reuse = {regime}:', '', table(['Arm', 'Metric'] + [f'it {it}' for it in range(1, ROUNDS + 1)], rows), '']
    rows = []
    for regime in REGIMES:
        drows = [d for d in training_detail if d['regime'] == regime]
        if not drows:
            continue
        for l in ['B', 'FullDC']:
            rows.append([regime, l] + [fmt(statistics.mean(d['by_depth'][str(dd)][l] for d in drows), 1) for dd in bench.TRAIN_DEPTHS] + [fmt(statistics.mean(sum(d['by_depth'][str(dd)][l] for dd in bench.TRAIN_DEPTHS) for d in drows), 1)])
        rows.append([regime, 'newly solved by FullDC'] + [fmt(statistics.mean(d['newly_solved_depths'].get(dd, 0) for d in drows), 1) for dd in bench.TRAIN_DEPTHS] + [fmt(statistics.mean(len(d['newly_solved_by_FullDC']) for d in drows), 1)])
        rows.append([regime, 'lost by FullDC'] + ['' for _ in bench.TRAIN_DEPTHS] + [fmt(statistics.mean(len(d['lost_by_FullDC']) for d in drows), 1)])
    L += ['Training tasks with a solved persistent frontier after the final round, by requested depth (mean over instances; 8 tasks per depth):', '',
          table(['Reuse', 'Arm'] + [f'd={d}' for d in bench.TRAIN_DEPTHS] + ['total'], rows), '']

    L += ['## Gap closure (final iteration, means over instances)', '',
          'closure = (FullDC - B) / (reference - B). Exposure reference: perfect Wake (support of the generating programs) and PWS_B; recovery reference: PWS_B and the oracle (recall 1); solve reference: O.', '']
    rows = []
    for g in gaps:
        e, r, s, c, rem = g['exposure'], g['recovery'], g['solve'], g['closure'], g['remaining']
        rows.append([g['regime'], g['arm'], fmt(e['B'], 2), fmt(e['FullDC'], 2), fmt(e['PWS_B'], 2), fmt(e['perfect'], 2), fmt(c['exposure_vs_perfect'], 2),
                     fmt(r['B'], 2), fmt(r['FullDC'], 2), fmt(r['PWS_B'], 2), fmt(c['recovery_vs_PWS_B'], 2), fmt(c['recovery_vs_oracle'], 2),
                     fmt(s['B']), fmt(s['FullDC']), fmt(s['FullDC_rec']), fmt(s['PWS_B']), fmt(s['O']), fmt(c['solve_library_vs_O'], 2), fmt(c['solve_recognition_vs_O'], 2),
                     fmt(rem['exposure_gap_to_perfect'], 2), fmt(rem['recovery_gap_to_oracle'], 2), fmt(rem['oracle_gap_recognition'], 3)])
    L += [table(['Reuse', 'Arm', 'ER@2 B', 'ER@2 FullDC', 'ER@2 PWS_B', 'ER@2 perfect', 'Exposure closure (perfect)', 'Recall B', 'Recall FullDC', 'Recall PWS_B', 'Recovery closure (PWS_B)', 'Recovery closure (oracle)',
                 'Solve B', 'Solve FullDC', 'Solve FullDC_rec', 'Solve PWS_B', 'Solve O', 'Oracle closure (library)', 'Oracle closure (rec)', 'Remaining exposure gap', 'Remaining recovery gap', 'Remaining oracle gap (rec)'], rows), '']

    L += ['## Causal chain per cohort (FullDC minus B, final iteration)', '']
    rows = [[r['regime'], r['seed'], fmt(r['d_training_solve'], 3), fmt(r['d_er1'], 2), fmt(r['d_er2'], 2), fmt(r['d_recall'], 2), fmt(r['d_solve_library'], 3), fmt(r['d_solve_recognition'], 3)] for r in chain['cohorts']]
    L += [table(['Reuse', 'Instance', 'Δ training solve', 'Δ ER@1', 'Δ ER@2', 'Δ recall', 'Δ solve (library)', 'Δ solve (recognition)'], rows), '']
    rows = [[k, v['n'], fmt(v['spearman']), fmt(v['pearson'])] for k, v in chain['correlations_over_reuse_cohorts'].items()]
    L += ['Rank correlations over the reuse cohorts:', '', table(['Pair', 'n', 'Spearman', 'Pearson'], rows), '']
    rows = [[k, v['positive'], v['zero'], v['negative']] for k, v in chain['sign_counts'].items()]
    L += [table(['Delta', 'Positive', 'Zero', 'Negative'], rows), '']

    L += ['## Medium reuse: per-latent exposure and recovery', '']
    rows = []
    for p in per_latent:
        if p['regime'] != 'medium':
            continue
        def s(l):
            return p['support'].get(l, 'n/a')
        def rec(l):
            return {True: 'yes', False: 'no'}.get(p['recovered'].get(l), 'n/a')
        rows.append([p['seed'], p['latent'], p['kind'], p['expression'], p['training_deliberate'], p['perfect_support'],
                     s('B'), s(ARM), s(f'{ARM}_t2'), s(f'{ARM}_t3'), s('B_wake10000'), s('PWS_B'),
                     rec('B'), rec(ARM), rec(f'{ARM}_t2'), rec(f'{ARM}_t3'), rec('B_wake10000'), rec('PWS_B'),
                     ' '.join(str(x) for x in p['support_by_iteration'].get(ARM, []))])
    L += [table(['Instance', 'Latent', 'Kind', 'Expression', 'Deliberate uses', 'Perfect support', 'Supp B', 'Supp FullDC', 'Supp t2', 'Supp t3', 'Supp B_wake10000', 'Supp PWS_B',
                 'Rec B', 'Rec FullDC', 'Rec t2', 'Rec t3', 'Rec B_wake10000', 'Rec PWS_B', 'FullDC support by iteration'], rows), '']
    L += ['Low and high reuse: per-latent exposure and recovery (primary seed):', '']
    rows = []
    for p in per_latent:
        if p['regime'] not in ('low', 'high'):
            continue
        rows.append([p['regime'], p['seed'], p['latent'], p['expression'], p['training_deliberate'], p['perfect_support'], p['support'].get('B', 'n/a'), p['support'].get(ARM, 'n/a'), p['support'].get('PWS_B', 'n/a'),
                     {True: 'yes', False: 'no'}.get(p['recovered'].get('B'), 'n/a'), {True: 'yes', False: 'no'}.get(p['recovered'].get(ARM), 'n/a'), {True: 'yes', False: 'no'}.get(p['recovered'].get('PWS_B'), 'n/a')])
    L += [table(['Reuse', 'Instance', 'Latent', 'Expression', 'Deliberate uses', 'Perfect support', 'Supp B', 'Supp FullDC', 'Supp PWS_B', 'Rec B', 'Rec FullDC', 'Rec PWS_B'], rows), '']

    L += ['## Cost (Phase 2 runs, primary seed; seconds summed over rounds, mean over instances)', '']
    rows = []
    for regime in REGIMES:
        vals = collections.defaultdict(list)
        for it in range(1, ROUNDS + 1):
            c = cell.get((regime, ARM, it))
            if c:
                for k in ['wake_seconds', 'guidance_seconds', 'compression_seconds', 'dream_seconds', 'recognition_seconds']:
                    vals[k].append(c['metrics'][k]['mean'] if c['metrics'].get(k) and c['metrics'][k]['mean'] is not None else 0.)
        b = [cell[(regime, 'B', it)]['metrics']['wake_seconds']['mean'] for it in range(1, ROUNDS + 1) if (regime, 'B', it) in cell and cell[(regime, 'B', it)]['metrics'].get('wake_seconds', {}).get('mean') is not None]
        ev = {l: mean_or_none(cell[(regime, l, it)]['metrics']['eval_seconds']['mean'] for it in range(1, ROUNDS + 1) if (regime, l, it) in cell) for l in [ARM, f'{ARM}_rec']}
        rows.append([regime, fmt(sum(vals['wake_seconds']), 0), fmt(sum(vals['guidance_seconds']), 1), fmt(sum(vals['compression_seconds']), 0), fmt(sum(vals['dream_seconds']), 1), fmt(sum(vals['recognition_seconds']), 0),
                     fmt(sum(b), 0) if b else 'n/a', fmt(ev.get(ARM), 0), fmt(ev.get(f'{ARM}_rec'), 0)])
    L += [table(['Reuse', 'Wake (guided)', 'of which guidance', 'Compression', 'Dream', 'Recognition training', 'B Wake (Phase 1)', 'Held-out eval / round (library)', 'Held-out eval / round (recognition)'], rows), '']
    (RESULTS / 'tables.md').write_text('\n'.join(L) + '\n', encoding='utf8')
