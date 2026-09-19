"""Aggregate evaluation records into the reported result files.

Outputs
-------
``results/solve_curves.json``
    Experiments 1, 2, 5: solve curves per regime/arm/iteration (overall, by depth,
    by transfer type), probe-consistent rates, first-solution ranks and paired
    contrasts with two-way (instance x task) bootstrap intervals.
``results/abstraction_recovery.json``
    Experiment 3: recovery precision/recall/F1/weighted recall under every
    criterion, Recall(iteration) curves and a per-latent recovery/exposure table.
``results/compression_results.json``
    Experiment 4: MDL improvements, effective complexity (ΔL) of held-out
    programs, ΔMDL/ΔL versus solve-rate correlations, the identical-input
    round-1 compressor comparison and the perfect-Wake diagnostic.
``results/abstraction_learning/tables.md``
    Markdown tables consumed by PHASE1_REPORT.md.

All aggregate numbers are means and sample standard deviations over benchmark
instances; contrasts use the two-way paired bootstrap of the earlier controlled
study (instances and task positions resampled together; task positions align
by generation stratum across instances).
"""
import collections
import math
import statistics
from pathlib import Path

from faithful.python.controlled_metrics import paired_bootstrap
from benchmarks.latent_abstraction import generator as bench
from .learner import read_json, save_json, ROUNDS
from .evaluation import BUDGETS, CRITERIA
from .compressors import DESCRIPTIONS

ROOT = bench.ROOT
RESULTS = ROOT / 'results' / 'abstraction_learning'
REGIMES = bench.REGIMES
MAIN_ARMS = ['A0', 'A', 'B', 'C', 'D', 'E', 'O', 'O_uniform']
EXPOSURE_ARMS = ['B', 'B_wake10000', 'B_wake30000', 'D', 'D_wake10000', 'D_wake30000']
PW_ARMS = ['PW_B', 'PW_C', 'PW_D', 'PW_E']
CONTRASTS = [('B', 'A'), ('C', 'A'), ('D', 'A'), ('E', 'A'), ('A', 'A0'), ('D', 'B'), ('C', 'B'), ('E', 'B'), ('D', 'C'),
             ('O', 'A'), ('O', 'B'), ('O', 'D'), ('O', 'O_uniform'), ('O_uniform', 'A0'),
             ('B_wake10000', 'B'), ('B_wake30000', 'B'), ('D_wake10000', 'D'), ('D_wake30000', 'D'),
             ('PW_B', 'B'), ('PW_D', 'D'), ('PW_C', 'C'), ('PW_E', 'E'), ('O', 'PW_B'), ('O', 'PW_D')]
MAX_BUDGET = str(max(BUDGETS))


def final_iteration(arm):
    if arm in ('A0', 'O_uniform'):
        return 0
    if arm.startswith('PW_'):
        return 1
    return ROUNDS


def mstd(values):
    vals = [v for v in values if v is not None]
    return {'mean': statistics.mean(vals) if vals else None,
            'std': (statistics.stdev(vals) if len(vals) > 1 else 0.) if vals else None, 'n': len(vals)}


def fmt(x, digits=3):
    if x is None:
        return 'n/a'
    if isinstance(x, dict):
        return 'n/a' if x['mean'] is None else f"{x['mean']:.{digits}f} ± {x['std']:.{digits}f}"
    return f'{x:.{digits}f}'


def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    result = [0.] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            result[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return result


def pearson(xs, ys):
    if len(xs) < 3:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def spearman(xs, ys):
    return pearson(ranks(xs), ranks(ys)) if len(xs) >= 3 else None


def load_records(seeds):
    records = []
    for seed in seeds:
        folder = RESULTS / 'evaluation' / f'seed_{seed}'
        for path in sorted(folder.glob('*/*.json.gz')):
            records.append(read_json(path))
    return records


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '|' + '|'.join(['---'] * len(headers)) + '|'] +
                     ['| ' + ' | '.join(str(c) for c in row) + ' |' for row in rows])


def analyze(seeds):
    records = load_records(seeds)
    if not records:
        raise RuntimeError('No evaluation records found')
    by_cell = collections.defaultdict(dict)   # (regime, arm, iteration) -> seed -> record
    for r in records:
        by_cell[(r['regime'], r['arm'], r['iteration'])][r['seed']] = r
    arms = sorted({r['arm'] for r in records}, key=lambda a: (a not in MAIN_ARMS, MAIN_ARMS.index(a) if a in MAIN_ARMS else 0, a))
    iterations = sorted({r['iteration'] for r in records})

    # ------------------------------------------------------------------ solve curves
    cells = []
    for (regime, arm, iteration), per_seed in sorted(by_cell.items(), key=lambda kv: (REGIMES.index(kv[0][0]), arms.index(kv[0][1]), kv[0][2])):
        recs = list(per_seed.values())
        depths = sorted({d for r in recs for d in r['summary']['by_depth']}, key=int)
        transfers = sorted({t for r in recs for t in r['summary']['by_transfer']})
        cells.append({'regime': regime, 'arm': arm, 'iteration': iteration, 'seeds': sorted(per_seed), 'n_seeds': len(recs),
                      'solve_rate': {n: mstd([r['summary']['curve'].get(n) for r in recs]) for n in map(str, BUDGETS)},
                      'limit': recs[0]['summary'].get('limit'),
                      'per_seed_solve_rate_max': {str(s): r['summary']['curve'].get(MAX_BUDGET) for s, r in per_seed.items()},
                      'probe_consistent_rate': mstd([r['summary']['probe_consistent_rate'] for r in recs]),
                      'mean_first_solution_nodes_solved': mstd([r['summary']['mean_first_solution_nodes_solved'] for r in recs]),
                      'median_first_solution_nodes_solved': mstd([r['summary']['median_first_solution_nodes_solved'] for r in recs]),
                      'expanded_states': mstd([r['batch']['expanded_states'] for r in recs]),
                      'by_depth': {d: {n: mstd([r['summary']['by_depth'].get(d, {}).get(n) for r in recs]) for n in map(str, BUDGETS)} for d in depths},
                      'by_transfer': {t: {n: mstd([r['summary']['by_transfer'].get(t, {}).get(n) for r in recs]) for n in map(str, BUDGETS)} for t in transfers},
                      'library_size': mstd([r['library_size'] for r in recs]),
                      'invention_count': mstd([len(r['inventions']) for r in recs])})
    contrasts = []
    for regime in REGIMES:
        for x, y in CONTRASTS:
            kx, ky = (regime, x, final_iteration(x)), (regime, y, final_iteration(y))
            if kx not in by_cell or ky not in by_cell:
                continue
            common = sorted(set(by_cell[kx]) & set(by_cell[ky]))
            if not common:
                continue
            for budget in ['10000', MAX_BUDGET]:
                matrix = []
                for seed in common:
                    a = {t['name']: t for t in by_cell[kx][seed]['per_task']}
                    b = {t['name']: t for t in by_cell[ky][seed]['per_task']}
                    names = sorted(a)
                    assert names == sorted(b), 'task sets differ'
                    solved = lambda t: t['first_solution_nodes'] is not None and t['first_solution_nodes'] <= int(budget)
                    matrix.append([float(solved(a[n])) - float(solved(b[n])) for n in names])
                stats = paired_bootstrap(matrix)
                contrasts.append({'regime': regime, 'contrast': f'{x}-{y}', 'budget': int(budget), 'iteration_x': final_iteration(x),
                                  'iteration_y': final_iteration(y), 'seeds': common, **(stats or {})})
    save_json(ROOT / 'results' / 'solve_curves.json',
              {'budgets': BUDGETS, 'rounds': ROUNDS, 'arms': {a: DESCRIPTIONS.get(a.split('_wake')[0] if '_wake' in a else a.replace('PW_', ''), a) for a in arms},
               'arm_notes': {'B_wake10000': 'B with Wake budget 10000', 'D_wake10000': 'D with Wake budget 10000', 'B_wake30000': 'B with Wake budget 30000',
                             'D_wake30000': 'D with Wake budget 30000', 'PW_*': 'compressor applied to the ground-truth training programs (perfect exposure)'},
               'cells': cells, 'contrasts': contrasts,
               'notes': ['Solve rate at budget N = fraction of held-out tasks whose first enumerated solution has rank <= N under the arm grammar (prefix-exact).',
                         'Means/std over benchmark instances; contrasts use a two-way paired bootstrap over instances and task positions.',
                         'probe_consistent_rate counts tasks with a top-K solution matching the generator program on 40 independent probes.']},
              compact=False)

    # ------------------------------------------------------------------ recovery
    rcells = []
    for (regime, arm, iteration), per_seed in sorted(by_cell.items(), key=lambda kv: (REGIMES.index(kv[0][0]), arms.index(kv[0][1]), kv[0][2])):
        recs = list(per_seed.values())
        rcells.append({'regime': regime, 'arm': arm, 'iteration': iteration, 'n_seeds': len(recs),
                       'learned_count': mstd([r['recovery']['learned_count'] for r in recs]),
                       'active_latents': mstd([len(r['recovery']['active_latents']) for r in recs]),
                       'metrics': {c: {m: mstd([r['recovery']['metrics'][c][m] for r in recs]) for m in ['precision', 'recall', 'f1', 'weighted_recall']} for c in CRITERIA},
                       'per_seed_behavioral_recall': {str(s): r['recovery']['metrics']['behavioral']['recall'] for s, r in per_seed.items()}})
    recall_curves = {}
    for regime in REGIMES:
        recall_curves[regime] = {}
        for arm in arms:
            if arm in ('A0', 'O_uniform') or arm.startswith('PW_'):
                continue
            curve = []
            for it in range(1, ROUNDS + 1):
                recs = list(by_cell.get((regime, arm, it), {}).values())
                curve.append({'iteration': it, 'behavioral_recall': mstd([r['recovery']['metrics']['behavioral']['recall'] for r in recs]),
                              'canonical_recall': mstd([r['recovery']['metrics']['canonical']['recall'] for r in recs]),
                              'behavioral_weighted_recall': mstd([r['recovery']['metrics']['behavioral']['weighted_recall'] for r in recs]),
                              'behavioral_precision': mstd([r['recovery']['metrics']['behavioral']['precision'] for r in recs]),
                              'learned_count': mstd([r['recovery']['learned_count'] for r in recs]),
                              'training_solved': mstd([r['training']['solved'] for r in recs if r.get('training')])})
            if any(c['behavioral_recall']['n'] for c in curve):
                recall_curves[regime][arm] = curve
    per_latent = []
    for seed in seeds:
        latents = bench.read(RESULTS.parent.parent / 'benchmarks' / 'latent_abstraction' / 'data' / f'seed_{seed}' / 'latent_library.json')
        for regime in REGIMES:
            for f in latents:
                if not f['reuse'][regime]['deliberate_active']:
                    continue
                row = {'seed': seed, 'regime': regime, 'latent': f['id'], 'kind': f['kind'], 'depth': f['depth'],
                       'expression': f['expression'], 'training_deliberate': f['reuse'][regime]['training_deliberate_count'],
                       'training_occurrences': f['reuse'][regime]['training_occurrence_count'],
                       'training_distinct_contexts': f['reuse'][regime]['training_distinct_contexts'],
                       'test_deliberate': f['reuse'][regime]['test_deliberate_count'], 'exposure': {}, 'recovered_by': {}}
                for arm in arms:
                    r = by_cell.get((regime, arm, final_iteration(arm)), {}).get(seed)
                    if r is None:
                        continue
                    if r.get('exposure') and f['id'] in r['exposure']:
                        row['exposure'][arm] = r['exposure'][f['id']]['count']
                    matched = [c for c in CRITERIA if f['id'] in r['recovery']['metrics'][c]['recovered_latents']]
                    if matched:
                        row['recovered_by'][arm] = matched
                per_latent.append(row)
    save_json(ROOT / 'results' / 'abstraction_recovery.json',
              {'criteria': CRITERIA, 'rounds': ROUNDS, 'cells': rcells, 'recall_by_iteration': recall_curves, 'per_latent': per_latent,
               'notes': ['Active latents are those deliberately used by the generator in the cohort (training or held-out).',
                         'Zero-reuse cohorts have no active latents: recall is undefined there, precision is 0 for any invention.',
                         'behavioral = type-compatible up to argument order and identical outputs on 40 independent probes for every valid parameter value.',
                         'exposure = number of training tasks whose persistent frontier structurally contains the latent (evaluation-only diagnostic).']},
              compact=False)

    # ------------------------------------------------------------------ compression / complexity
    ccells = []
    cumulative = {}
    for (regime, arm, iteration), per_seed in sorted(by_cell.items(), key=lambda kv: (REGIMES.index(kv[0][0]), arms.index(kv[0][1]), kv[0][2])):
        recs = list(per_seed.values())
        for seed, r in per_seed.items():
            prev = cumulative.get((regime, arm, iteration - 1, seed), 0.)
            cumulative[(regime, arm, iteration, seed)] = prev + (r['training']['mdl']['delta_mdl'] if r.get('training') else 0.)
        ccells.append({'regime': regime, 'arm': arm, 'iteration': iteration, 'n_seeds': len(recs),
                       'delta_mdl_round': mstd([r['training']['mdl']['delta_mdl'] if r.get('training') else None for r in recs]),
                       'cumulative_delta_mdl': mstd([cumulative[(regime, arm, iteration, s)] for s in per_seed]),
                       'corpus_savings_round': mstd([r['training']['mdl']['corpus_savings'] if r.get('training') else None for r in recs]),
                       'library_cost_increase_round': mstd([r['training']['mdl']['library_cost_increase'] if r.get('training') else None for r in recs]),
                       'training_solved': mstd([r['training']['solved'] if r.get('training') else None for r in recs]),
                       'library_size': mstd([r['library_size'] for r in recs]), 'invention_count': mstd([len(r['inventions']) for r in recs]),
                       'mean_delta_L': mstd([r['summary']['mean_delta_L'] for r in recs]),
                       'fraction_shortened': mstd([r['summary']['fraction_shortened'] for r in recs]),
                       'mean_true_delta_L': mstd([r['summary']['mean_true_delta_L'] for r in recs]),
                       'solve_rate_when_shortened': mstd([r['summary']['solve_rate_when_shortened'] for r in recs]),
                       'solve_rate_when_not_shortened': mstd([r['summary']['solve_rate_when_not_shortened'] for r in recs]),
                       'solve_rate_max': mstd([r['summary']['curve'].get(MAX_BUDGET) for r in recs]),
                       'solve_rate_10000': mstd([r['summary']['curve']['10000'] for r in recs])})
    learned_arms = [a for a in arms if a not in ('A0', 'A', 'O', 'O_uniform') and not a.startswith('PW_')]
    correlations = {}
    for scope in REGIMES + ['all']:
        xs_mdl, xs_L, ys = [], [], []
        for (regime, arm, iteration), per_seed in by_cell.items():
            if arm not in learned_arms or (scope != 'all' and regime != scope):
                continue
            for seed, r in per_seed.items():
                xs_mdl.append(cumulative[(regime, arm, iteration, seed)])
                xs_L.append(r['summary']['mean_delta_L'])
                ys.append(r['summary']['curve']['10000'])
        correlations[scope] = {'cells': len(ys), 'budget': 10000, 'cumulative_delta_mdl_vs_solve_rate': {'pearson': pearson(xs_mdl, ys), 'spearman': spearman(xs_mdl, ys)},
                               'mean_delta_L_vs_solve_rate': {'pearson': pearson(xs_L, ys), 'spearman': spearman(xs_L, ys)}}
    task_level = {}
    for regime in REGIMES:
        task_level[regime] = {}
        for arm in learned_arms:
            counts = collections.Counter()
            for it in range(1, ROUNDS + 1):
                for r in by_cell.get((regime, arm, it), {}).values():
                    for t in r['per_task']:
                        counts[('shortened' if t['delta_L'] > 0 else 'unshortened', 'solved' if t['solved'] else 'unsolved')] += 1
            task_level[regime][arm] = {f'{a}_{b}': counts[(a, b)] for a in ['shortened', 'unshortened'] for b in ['solved', 'unsolved']}
    round1 = []
    for regime in REGIMES:
        for arm in ['B', 'C', 'D', 'E']:
            recs = list(by_cell.get((regime, arm, 1), {}).values())
            if not recs:
                continue
            inputs = {r['seed']: r['training']['solved'] for r in recs}
            round1.append({'regime': regime, 'arm': arm, 'n_seeds': len(recs), 'input_solved_frontiers': inputs,
                           'inventions': mstd([r['training']['invention_count'] for r in recs]),
                           'delta_mdl': mstd([r['training']['mdl']['delta_mdl'] for r in recs]),
                           'behavioral_recall': mstd([r['recovery']['metrics']['behavioral']['recall'] for r in recs]),
                           'behavioral_precision': mstd([r['recovery']['metrics']['behavioral']['precision'] for r in recs]),
                           'canonical_recall': mstd([r['recovery']['metrics']['canonical']['recall'] for r in recs]),
                           'solve_rate_10000': mstd([r['summary']['curve']['10000'] for r in recs]),
                           'mean_delta_L': mstd([r['summary']['mean_delta_L'] for r in recs])})
    perfect = []
    for regime in REGIMES:
        for arm in PW_ARMS:
            recs = list(by_cell.get((regime, arm, 1), {}).values())
            if not recs:
                continue
            perfect.append({'regime': regime, 'arm': arm, 'n_seeds': len(recs),
                            'inventions': mstd([r['training']['invention_count'] for r in recs]),
                            'delta_mdl': mstd([r['training']['mdl']['delta_mdl'] for r in recs]),
                            'behavioral_recall': mstd([r['recovery']['metrics']['behavioral']['recall'] for r in recs]),
                            'behavioral_weighted_recall': mstd([r['recovery']['metrics']['behavioral']['weighted_recall'] for r in recs]),
                            'behavioral_precision': mstd([r['recovery']['metrics']['behavioral']['precision'] for r in recs]),
                            'canonical_recall': mstd([r['recovery']['metrics']['canonical']['recall'] for r in recs]),
                            'solve_rate_max': mstd([r['summary']['curve'][MAX_BUDGET] for r in recs]),
                            'mean_delta_L': mstd([r['summary']['mean_delta_L'] for r in recs])})
    save_json(ROOT / 'results' / 'compression_results.json',
              {'cells': ccells, 'correlations': correlations, 'task_level_shortening_vs_solving': task_level,
               'round1_identical_input': round1, 'perfect_wake': perfect,
               'notes': ['delta_mdl_round: improvement of the frozen DreamCoder objective by that round\'s compression over the fitted baseline on the same corpus.',
                         'cumulative_delta_mdl: sum of per-round improvements (corpora grow across rounds, so this is a rough total-compression measure).',
                         'mean_delta_L: mean reduction in leaf size of held-out generator programs under the arm library (exact DP in the beta-normal subtree/slot rewrite space).',
                         'mean_true_delta_L: the same reduction under the true active latent library (oracle upper bound of shortening).',
                         'Correlations pool learned arms (B, C, D, E and Wake-budget variants) x instances x iterations; they are associations, not causal estimates.']},
              compact=False)
    write_tables(seeds, by_cell, arms, cells, contrasts, rcells, recall_curves, per_latent, ccells, correlations, round1, perfect, task_level)
    return {'records': len(records), 'cells': len(cells), 'contrasts': len(contrasts)}


def write_tables(seeds, by_cell, arms, cells, contrasts, rcells, recall_curves, per_latent, ccells, correlations, round1, perfect, task_level):
    lines = ['# Generated tables (experiments/abstraction_learning/analysis.py)', '']
    cell = {(c['regime'], c['arm'], c['iteration']): c for c in cells}
    rcell = {(c['regime'], c['arm'], c['iteration']): c for c in rcells}
    ccell = {(c['regime'], c['arm'], c['iteration']): c for c in ccells}
    con = {(c['regime'], c['contrast'], c['budget']): c for c in contrasts}

    # benchmark structure
    lines += ['## Benchmark instances', '']
    rows = []
    for seed in seeds:
        data = bench.DATA / f'seed_{seed}'
        stats = bench.read(data / 'structural_statistics.json')
        latents = bench.read(data / 'latent_library.json')
        for regime in REGIMES:
            active = [f for f in latents if f['reuse'][regime]['deliberate_active']]
            counts = [f['reuse'][regime]['training_deliberate_count'] for f in active]
            tests = [f['reuse'][regime]['test_deliberate_count'] for f in active]
            rows.append([seed, regime, stats['counts'].get(f'train/{regime}/2/train', 0) and sum(v for k, v in stats['counts'].items() if k.startswith(f'train/{regime}/')),
                         sum(v for k, v in stats['counts'].items() if k.startswith(f'test/{regime}/')), len(stats['pools'][regime]), len(active),
                         fmt(statistics.mean(counts), 1) if counts else 'n/a', f'{min(counts)}-{max(counts)}' if counts else 'n/a',
                         fmt(statistics.mean(tests), 1) if tests else 'n/a', stats['incidental_uses'][regime], len(stats['nested_training_pairs'][regime])])
    lines += [table(['Instance', 'Reuse', 'Train tasks', 'Test tasks', 'Pool size', 'Active latents', 'Mean deliberate train uses / latent', 'Range', 'Mean test uses / latent', 'Incidental uses', 'Nested train pairs'], rows), '']
    rows = []
    for seed in seeds:
        cal = bench.read(bench.DATA / f'seed_{seed}' / 'calibration.json')
        for r in cal['depth_budget_rates']:
            if r['split'] == 'test':
                rows.append([seed, r['regime'], r['depth'], r['count']] + [fmt(r['rates'][str(n)], 2) for n in cal['budgets']])
    lines += ['A0 calibration (uniform base grammar, held-out tasks, solve rate by depth and candidate budget; inspected before freezing):', '',
              table(['Instance', 'Reuse', 'Depth', 'Tasks'] + [str(n) for n in BUDGETS], rows), '']

    # experiment 1
    lines += ['## Experiment 1: effect of reuse (final iteration, solve rate at 20000 candidates)', '']
    arms1 = [a for a in MAIN_ARMS if any((rg, a, final_iteration(a)) in cell for rg in REGIMES)]
    rows = [[regime] + [fmt(cell[(regime, a, final_iteration(a))]['solve_rate'][MAX_BUDGET]) if (regime, a, final_iteration(a)) in cell else 'n/a' for a in arms1] for regime in REGIMES]
    lines += [table(['Reuse'] + arms1, rows), '']
    rows = [[regime] + [fmt(cell[(regime, a, final_iteration(a))]['solve_rate']['10000']) if (regime, a, final_iteration(a)) in cell else 'n/a' for a in arms1] for regime in REGIMES]
    lines += ['Same at 10000 candidates:', '', table(['Reuse'] + arms1, rows), '']
    rows = [[regime] + [fmt(cell[(regime, a, final_iteration(a))]['probe_consistent_rate']) if (regime, a, final_iteration(a)) in cell else 'n/a' for a in arms1] for regime in REGIMES]
    lines += ['Probe-consistent solution rate (top-K solution reproduces the generator program on 40 independent probes):', '', table(['Reuse'] + arms1, rows), '']
    rows = []
    for regime in REGIMES:
        for x, y in CONTRASTS[:14]:
            c = con.get((regime, f'{x}-{y}', int(MAX_BUDGET)))
            if c and 'mean' in c:
                rows.append([regime, f'{x}-{y}', fmt(c['mean']), fmt(c['seed_standard_deviation']), f"[{c['paired_bootstrap_95_ci'][0]:.3f}, {c['paired_bootstrap_95_ci'][1]:.3f}]", c['training_seeds']])
    lines += ['Paired contrasts at 20000 candidates (mean difference in solve rate; two-way bootstrap over instances and task positions):', '',
              table(['Reuse', 'Contrast', 'Mean diff', 'Instance SD', '95% CI', 'Instances'], rows), '']

    # experiment 2
    lines += ['## Experiment 2: effect of complexity (solve rate at 20000 by depth, final iteration)', '']
    for regime in REGIMES:
        depths = sorted({d for a in arms1 if (regime, a, final_iteration(a)) in cell for d in cell[(regime, a, final_iteration(a))]['by_depth']}, key=int)
        rows = [[a] + [fmt(cell[(regime, a, final_iteration(a))]['by_depth'].get(d, {}).get(MAX_BUDGET), 2) for d in depths] for a in arms1 if (regime, a, final_iteration(a)) in cell]
        lines += [f'Reuse = {regime}:', '', table(['Arm'] + [f'd={d}' for d in depths], rows), '']
    lines += ['Solve rate at 20000 by held-out transfer type (final iteration):', '']
    for regime in REGIMES:
        transfers = sorted({t for a in arms1 if (regime, a, final_iteration(a)) in cell for t in cell[(regime, a, final_iteration(a))]['by_transfer']})
        rows = [[a] + [fmt(cell[(regime, a, final_iteration(a))]['by_transfer'].get(t, {}).get(MAX_BUDGET), 2) for t in transfers] for a in arms1 if (regime, a, final_iteration(a)) in cell]
        lines += [f'Reuse = {regime}:', '', table(['Arm'] + transfers, rows), '']

    # experiment 3
    lines += ['## Experiment 3: abstraction recovery', '']
    rows = []
    for regime in REGIMES:
        if regime == 'zero':
            continue
        for a in ['B', 'C', 'D', 'E'] + [x for x in EXPOSURE_ARMS if x not in ('B', 'D')]:
            c = rcell.get((regime, a, final_iteration(a)))
            if not c:
                continue
            m = c['metrics']
            rows.append([regime, a, fmt(c['learned_count'], 1), fmt(m['canonical']['recall']), fmt(m['beta']['recall']), fmt(m['type_permuted']['recall']),
                         fmt(m['behavioral']['precision']), fmt(m['behavioral']['recall']), fmt(m['behavioral']['f1']), fmt(m['behavioral']['weighted_recall'])])
    lines += [table(['Reuse', 'Arm', 'Inventions', 'Canonical recall', 'Beta recall', 'Type recall (perm.)', 'Behav. precision', 'Behav. recall', 'Behav. F1', 'Weighted behav. recall'], rows), '']
    lines += ['Behavioral recall by EC iteration (mean over instances):', '']
    for regime in REGIMES:
        if regime == 'zero' or regime not in recall_curves:
            continue
        rows = []
        for a, curve in recall_curves[regime].items():
            rows.append([a] + [fmt(pt['behavioral_recall'], 2) for pt in curve])
        lines += [f'Reuse = {regime}:', '', table(['Arm'] + [f'it {pt["iteration"]}' for pt in next(iter(recall_curves[regime].values()))], rows), '']
    lines += ['Training tasks solved by EC iteration (mean over instances, out of 56):', '']
    for regime in REGIMES:
        rows = []
        for a in arms:
            if a in ('A0', 'O_uniform') or a.startswith('PW_'):
                continue
            pts = [ccell.get((regime, a, it)) for it in range(1, ROUNDS + 1)]
            if all(p is None for p in pts):
                continue
            rows.append([a] + [fmt(p['training_solved'], 1) if p else 'n/a' for p in pts])
        lines += [f'Reuse = {regime}:', '', table(['Arm'] + [f'it {it}' for it in range(1, ROUNDS + 1)], rows), '']
    rows = []
    for regime in REGIMES:
        if regime == 'zero':
            continue
        entries = [p for p in per_latent if p['regime'] == regime]
        for a in ['B', 'C', 'D', 'E']:
            exposed = [p for p in entries if a in p['exposure']]
            if not exposed:
                continue
            two = [p for p in exposed if p['exposure'][a] >= 2]
            one = [p for p in exposed if p['exposure'][a] == 1]
            none = [p for p in exposed if p['exposure'][a] == 0]
            rec = lambda ps: f"{sum('behavioral' in p['recovered_by'].get(a, []) for p in ps)}/{len(ps)}"
            rows.append([regime, a, len(exposed), rec(two), rec(one), rec(none)])
    lines += ['Exposure and recovery per active latent (final iteration; latents pooled over instances): behaviorally recovered / latents with frontier support in >=2, 1, 0 training tasks:', '',
              table(['Reuse', 'Arm', 'Active latents', '>=2 tasks', '1 task', '0 tasks'], rows), '']

    # experiment 4
    lines += ['## Experiment 4: compression versus generalization', '']
    rows = []
    for regime in REGIMES:
        for a in ['B', 'C', 'D', 'E']:
            c = ccell.get((regime, a, ROUNDS))
            if c:
                rows.append([regime, a, fmt(c['cumulative_delta_mdl'], 2), fmt(c['invention_count'], 1), fmt(c['mean_delta_L'], 2), fmt(c['fraction_shortened'], 2),
                             fmt(c['mean_true_delta_L'], 2), fmt(c['solve_rate_when_shortened']), fmt(c['solve_rate_when_not_shortened']), fmt(c['solve_rate_max'])])
    lines += [table(['Reuse', 'Arm', 'Cumulative ΔMDL', 'Inventions', 'Mean ΔL (held-out)', 'Fraction shortened', 'Mean ΔL under true library', 'Solve rate | shortened', 'Solve rate | not shortened', 'Solve rate'], rows), '']
    rows = [[scope, c['cells'], fmt(c['cumulative_delta_mdl_vs_solve_rate']['pearson']), fmt(c['cumulative_delta_mdl_vs_solve_rate']['spearman']),
             fmt(c['mean_delta_L_vs_solve_rate']['pearson']), fmt(c['mean_delta_L_vs_solve_rate']['spearman'])] for scope, c in correlations.items()]
    lines += ['Correlations across (learned arm x instance x iteration) cells:', '', table(['Scope', 'Cells', 'ΔMDL vs solve: Pearson', 'Spearman', 'ΔL vs solve: Pearson', 'Spearman'], rows), '']
    rows = []
    for regime in REGIMES:
        for a, counts in task_level[regime].items():
            s = counts['shortened_solved'] + counts['shortened_unsolved']
            u = counts['unshortened_solved'] + counts['unshortened_unsolved']
            rows.append([regime, a, s, fmt(counts['shortened_solved'] / s) if s else 'n/a', u, fmt(counts['unshortened_solved'] / u) if u else 'n/a'])
    lines += ['Task-level association pooled over iterations and instances (a task counts once per arm x instance x iteration):', '',
              table(['Reuse', 'Arm', 'Shortened task-cells', 'Solve rate', 'Unshortened task-cells', 'Solve rate'], rows), '']

    # experiment 5
    lines += ['## Experiment 5: oracle gap', '']
    rows = []
    for regime in REGIMES:
        for a in ['A', 'B', 'D', 'C', 'E', 'PW_B', 'PW_D', 'PW_C', 'PW_E', 'O', 'O_uniform']:
            c = cell.get((regime, a, final_iteration(a)))
            r = rcell.get((regime, a, final_iteration(a)))
            k = ccell.get((regime, a, final_iteration(a)))
            if c:
                rows.append([regime, a, fmt(c['solve_rate'][MAX_BUDGET]), fmt(c['probe_consistent_rate']), fmt(r['metrics']['behavioral']['recall']) if r else 'n/a',
                             fmt(k['mean_delta_L'], 2) if k else 'n/a', fmt(c['mean_first_solution_nodes_solved'], 0)])
    lines += [table(['Reuse', 'Arm', 'Solve rate @20000', 'Probe-consistent', 'Behav. recall', 'Mean ΔL', 'Mean first-solution rank (solved)'], rows), '']
    rows = []
    for regime in REGIMES:
        for x, y in CONTRASTS:
            if x not in ('O', 'O_uniform', 'PW_B', 'PW_D', 'PW_C', 'PW_E'):
                continue
            c = con.get((regime, f'{x}-{y}', int(MAX_BUDGET)))
            if c and 'mean' in c:
                rows.append([regime, f'{x}-{y}', fmt(c['mean']), f"[{c['paired_bootstrap_95_ci'][0]:.3f}, {c['paired_bootstrap_95_ci'][1]:.3f}]"])
    lines += ['Oracle and perfect-Wake contrasts at 20000 candidates:', '', table(['Reuse', 'Contrast', 'Mean diff', '95% CI'], rows), '']
    rows = []
    for p in perfect:
        rows.append([p['regime'], p['arm'], fmt(p['inventions'], 1), fmt(p['delta_mdl'], 1), fmt(p['canonical_recall']), fmt(p['behavioral_precision']), fmt(p['behavioral_recall']), fmt(p['behavioral_weighted_recall']), fmt(p['mean_delta_L'], 2), fmt(p['solve_rate_max'])])
    lines += ['Perfect-Wake diagnostic (compressor applied to the ground-truth programs of all 56 training tasks, up to 12 inventions):', '',
              table(['Reuse', 'Arm', 'Inventions', 'ΔMDL', 'Canonical recall', 'Behav. precision', 'Behav. recall', 'Weighted recall', 'Mean ΔL', 'Solve rate @20000'], rows), '']

    # exposure arms
    lines += ['## Search exposure: Wake budget', '']
    rows = []
    for regime in REGIMES:
        for a in EXPOSURE_ARMS:
            c = cell.get((regime, a, ROUNDS))
            r = rcell.get((regime, a, ROUNDS))
            k = ccell.get((regime, a, ROUNDS))
            if c:
                rows.append([regime, a, fmt(k['training_solved'], 1), fmt(c['solve_rate'][MAX_BUDGET]), fmt(r['metrics']['behavioral']['recall']), fmt(r['metrics']['behavioral']['weighted_recall']), fmt(k['mean_delta_L'], 2), fmt(c['invention_count'], 1)])
    lines += [table(['Reuse', 'Arm', 'Training solved (final)', 'Solve rate @20000', 'Behav. recall', 'Weighted recall', 'Mean ΔL', 'Inventions'], rows), '']
    rows = []
    for regime in REGIMES:
        for x, y in [('B_wake10000', 'B'), ('B_wake30000', 'B'), ('D_wake10000', 'D'), ('D_wake30000', 'D')]:
            c = con.get((regime, f'{x}-{y}', int(MAX_BUDGET)))
            if c and 'mean' in c:
                rows.append([regime, f'{x}-{y}', fmt(c['mean']), f"[{c['paired_bootstrap_95_ci'][0]:.3f}, {c['paired_bootstrap_95_ci'][1]:.3f}]"])
    lines += [table(['Reuse', 'Contrast', 'Mean diff', '95% CI'], rows), '']

    # round 1 identical input
    lines += ['## Identical-input compressor comparison (round 1: same base-grammar Wake frontiers for every compressor)', '']
    rows = [[r['regime'], r['arm'], fmt(r['inventions'], 1), fmt(r['delta_mdl'], 2), fmt(r['canonical_recall']), fmt(r['behavioral_precision']), fmt(r['behavioral_recall']), fmt(r['mean_delta_L'], 2), fmt(r['solve_rate_10000'])] for r in round1]
    lines += [table(['Reuse', 'Arm', 'Inventions', 'ΔMDL', 'Canonical recall', 'Behav. precision', 'Behav. recall', 'Mean ΔL', 'Solve rate @10000 after round 1'], rows), '']

    # trajectories
    lines += ['## Held-out solve rate at 10000 candidates by EC iteration', '']
    for regime in REGIMES:
        rows = []
        for a in arms:
            if a in ('A0', 'O_uniform') or a.startswith('PW_'):
                continue
            pts = [cell.get((regime, a, it)) for it in range(1, ROUNDS + 1)]
            if all(p is None for p in pts):
                continue
            rows.append([a] + [fmt(p['solve_rate']['10000'], 2) if p else 'n/a' for p in pts])
        lines += [f'Reuse = {regime}:', '', table(['Arm'] + [f'it {it}' for it in range(1, ROUNDS + 1)], rows), '']
    (RESULTS / 'tables.md').write_text('\n'.join(lines) + '\n', encoding='utf8')
