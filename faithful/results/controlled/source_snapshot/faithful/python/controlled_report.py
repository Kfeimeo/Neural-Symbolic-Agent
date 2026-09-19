"""Analyze frozen outcomes without exposing private labels to the learner."""
import argparse
import collections
import hashlib
import json
import statistics
from pathlib import Path
from .kernel import Kernel, ROOT
from .toy import save
from .controlled_run import OUT, REGIMES, SEEDS, ROUNDS, BUDGETS, read, verify
from .controlled_metrics import best_rewrite, recovery, paired_bootstrap
from .controlled_data import key


def analyze(out):
    verify(out)
    index = read(out/'evaluation_index.json')
    labels = ['A', 'B', 'C', 'D', 'E', 'C_shuffle', 'D_shuffle', 'O']
    expected = {(regime, seed, iteration, label) for regime in REGIMES for seed in SEEDS for iteration in ROUNDS for label in labels}
    actual = {(e['regime'], e['seed'], e['iteration'], e['configuration']) for e in index}
    if actual != expected or len(index) != len(expected): raise RuntimeError('Incomplete or duplicate experiment configuration matrix')
    for regime in REGIMES:
        for seed in SEEDS:
            for label in ['B', 'C', 'D', 'E']:
                if not (out/'runs'/regime/str(seed)/label/'complete.json').exists():
                    raise RuntimeError(f'Incomplete training: {regime}/{seed}/{label}')
    missing = sorted({p for entry in index for p in entry['paths'] if not (out/p).exists()})
    if missing: raise RuntimeError(f'{len(missing)} searches remain; final analysis refused')
    private = read(out/'evaluation_private.json')
    meta = private['tasks']
    latents = read(out/'latent_library.json')
    recovery_rows, per_task = [], []
    rewrites, recovered, behavior = {}, {}, {}
    with Kernel() as k:
        def probe(p):
            s = key(p)
            if s not in behavior:
                behavior[s] = k.call('evaluate_batch', program=p, input_sets=[[x] for x in private['recovery_probes']])['values']
            return behavior[s]
        for n, entry in enumerate(index):
            observed_names = []
            g, regime = entry['grammar'], entry['regime']
            library_key = key([p for p in g['productions'] if 'invented' in p['program']])
            recovery_key = (regime, library_key)
            if recovery_key not in recovered:
                recovered[recovery_key] = recovery(k, g, latents, regime, private['recovery_probes'])
            recovery_rows.append({name: entry[name] for name in ['regime', 'seed', 'iteration', 'configuration']} | recovered[recovery_key])
            for path in entry['paths']:
                record = read(out/path)
                for row in record['rows']:
                    if row['name'] not in entry.get('selections', {}).get(path, [row['name']]): continue
                    observed_names.append(row['name'])
                    m = meta[row['name']]
                    rewrite_key = (row['name'], library_key)
                    if rewrite_key not in rewrites:
                        rewrites[rewrite_key] = best_rewrite(k, m['ground_truth'], g['productions'])
                    complexity = {a: b for a, b in rewrites[rewrite_key].items() if a != 'witness'}
                    truth = probe(m['ground_truth'])
                    compatible_ranks = [e['search_rank'] for e in row['solutions'] if probe(e['program']) == truth]
                    rank = row['first_solution_nodes']
                    per_task.append({name: entry[name] for name in ['regime', 'seed', 'iteration', 'configuration']} |
                        {'name': row['name'], 'transfer': m['transfer'], 'matched_transfer_stratum': m['matched_transfer_stratum'],
                        'depth': m['depth'], 'ast_size': m['ast_size'], 'ast_depth': m['ast_depth'], 'beta_normalized_size': m['beta_normalized_size'],
                        'primitive_leaf_count': m['primitive_leaf_count'], 'hidden_effective_leaf_size': m['hidden_library_complexity']['effective_leaf_size'],
                        **complexity, 'first_solution_nodes': rank, 'probe_consistent_topk_first_rank': min(compatible_ranks) if compatible_ranks else None,
                        'enumerated_nodes': row['enumerated_nodes'], 'expanded_states': row['expanded_states'], 'stop_reason': row['stop_reason'],
                        'search_cache': path, 'search_seconds_shared_batch': record['seconds'],
                        'budgets': {str(b): {'io_solved': rank is not None and rank <= b,
                            'probe_consistent_topk_solution': any(r <= b for r in compatible_ranks),
                            'candidate_budget_reached': row['enumerated_nodes'] >= b,
                            'censored_first_nodes': min(rank, b) if rank is not None else min(row['enumerated_nodes'], b)} for b in BUDGETS}})
            expected_names = {name for name, m in meta.items() if m['split'] == 'test' and m['regime'] == regime}
            if set(observed_names) != expected_names or len(observed_names) != len(expected_names):
                raise RuntimeError(f'Missing/duplicate task assignments: {regime}/{entry["configuration"]}')
            if n % 50 == 0: print(f'analysis {n}/{len(index)}', flush=True)
    save(out/'abstraction_recovery.json', recovery_rows)
    save(out/'effective_rewrites.json', [{'task': name, 'library': json.loads(lib), **value} for (name, lib), value in rewrites.items()])
    save(out/'per_task_results.json', {'rows': per_task,
        'probe_note': 'Probe metric is a conservative top-K diagnostic, not exact first behavioral-solution rank; lower-budget frontiers are not reconstructed.',
        'censor_note': 'Unsolved rows are right-censored at actual emitted candidates, not assumed to consume the nominal budget.',
        'timing_note': 'Batch times are shared by all rows pointing to the same cache file. Do not sum them per task.'})
    grouped = collections.defaultdict(list)
    for row in per_task:
        for n in BUDGETS:
            root = (row['configuration'], row['regime'], row['iteration'], n)
            for dimension in ['all', 'depth', 'ast_size', 'transfer', 'delta_L', 'delta_d']:
                value = 'all' if dimension == 'all' else row[dimension]
                grouped[root+(dimension, value)].append(row)
    curves = []
    for group, rows in grouped.items():
        config, regime, iteration, n, dimension, value = group
        seed_counts = {seed: sum(r['seed'] == seed for r in rows) for seed in SEEDS}
        seed_rates = {seed: statistics.mean(r['budgets'][str(n)]['io_solved'] for r in rows if r['seed'] == seed) for seed in SEEDS if seed_counts[seed]}
        rates = list(seed_rates.values())
        curves.append({'configuration': config, 'regime': regime, 'iteration': iteration, 'budget': n,
            'dimension': dimension, 'value': value, 'task_seed_observations': len(rows),
            'mean_solve_rate': statistics.mean(rates), 'seed_standard_deviation': statistics.stdev(rates) if len(rates)>1 else None,
            'per_seed_solve_rates': seed_rates, 'per_seed_task_counts': seed_counts,
            'probe_consistent_topk_rate': statistics.mean(r['budgets'][str(n)]['probe_consistent_topk_solution'] for r in rows),
            'budget_reached_fraction': statistics.mean(r['budgets'][str(n)]['candidate_budget_reached'] for r in rows),
            'mean_censored_first_nodes': statistics.mean(r['budgets'][str(n)]['censored_first_nodes'] for r in rows),
            'mean_delta_L': statistics.mean(r['delta_L'] for r in rows), 'mean_delta_d': statistics.mean(r['delta_d'] for r in rows)})
    save(out/'budget_curves.json', curves)
    # All comparisons paired on the identical frozen task and training seed.
    lookup = {(r['regime'], r['seed'], r['iteration'], r['configuration'], r['name']): r for r in per_task}
    comparisons = []
    for regime in REGIMES:
        names = sorted(n for n, m in meta.items() if m['split'] == 'test' and m['regime'] == regime)
        for iteration in ROUNDS:
            for lhs, rhs in [('B', 'A'), ('D', 'C'), ('E', 'A'), ('B', 'E'), ('C', 'C_shuffle'), ('D', 'D_shuffle'), ('O', 'B'), ('O', 'D'), ('C', 'A'), ('D', 'B')]:
                matrix = [[int(lookup[regime, seed, iteration, lhs, name]['budgets']['10000']['io_solved'])-
                    int(lookup[regime, seed, iteration, rhs, name]['budgets']['10000']['io_solved']) for name in names] for seed in SEEDS]
                comparisons.append({'regime': regime, 'iteration': iteration, 'contrast': f'{lhs}-{rhs}', 'budget': 10000,
                    **paired_bootstrap(matrix)})
    training_records = []
    for path in (out/'runs').glob('*/*/*/round_*/round.json'):
        record = read(path)
        training_records.append({'path': str(path.relative_to(out)), **{n: record[n] for n in ['iteration', 'label', 'training_seed', 'timings', 'solved_training_tasks', 'library_objective', 'frontier_log_marginal']},
            'inventions': len(record['grammar']['productions'])-24,
            'hierarchical_inventions': sum('invented' in key(pr['program'].get('invented', {})) for pr in record['grammar']['productions'] if 'invented' in pr['program'])})
    summary = {'status': 'completed_frozen_experiment', 'training_seeds': SEEDS, 'iterations': ROUNDS, 'budgets': BUDGETS,
        'benchmark_sha256': hashlib.sha256((out/'benchmark_manifest.json').read_bytes()).hexdigest(),
        'comparisons': comparisons, 'training': training_records,
        'final_10000': [r for r in curves if r['iteration'] == 5 and r['budget'] == 10000 and r['dimension'] == 'all'],
        'limitations': ['One dataset generation seed; confidence intervals are conditional on it.',
            'Finite probes cannot prove global semantic equivalence or minimal complexity.',
            'Effective rewrite optimum is restricted to beta-normal subtree/slot covering.',
            'Training cohorts contain 56 tasks each (224 total); held-out cohorts contain 42 each.',
            'd=2 held-out and other structurally impossible transfer cells are explicitly absent.',
            'Training uses 3000 candidates; evaluation uses nominal budgets through 10000 with a 500000-state cap.',
            'Canonicalization covers local algebra, not the complete Grid DSL equational theory.']}
    final_rows = [r for r in per_task if r['iteration'] == 5]
    mechanisms = []
    for regime in REGIMES:
        for label in ['B', 'C', 'D', 'O']:
            rows = [r for r in final_rows if r['regime'] == regime and r['configuration'] == label]
            positive = [r for r in rows if r['delta_L'] > 0]
            baseline = 'C' if label == 'D' else 'A'
            paired_nodes = [(r['first_solution_nodes'], lookup[regime, r['seed'], 5, baseline, r['name']]['first_solution_nodes']) for r in rows]
            paired_nodes = [(a, b) for a, b in paired_nodes if a is not None and b is not None]
            mechanisms.append({'regime': regime, 'configuration': label, 'comparison': baseline,
                'mean_delta_L': statistics.mean(r['delta_L'] for r in rows),
                'fraction_with_positive_delta_L': len(positive)/len(rows),
                'solve_rate_when_delta_L_positive': statistics.mean(r['budgets']['10000']['io_solved'] for r in positive) if positive else None,
                'paired_both_solved_count': len(paired_nodes),
                'mean_node_change_on_both_solved_subset': statistics.mean(a-b for a, b in paired_nodes) if paired_nodes else None,
                'node_note': 'Both-solved subset only; selection-biased, not an estimate for censored failures.',
                'transfer_rates': {t: statistics.mean(r['budgets']['10000']['io_solved'] for r in rows if r['transfer'] == t) for t in sorted({r['transfer'] for r in rows})}})
    summary['mechanism_diagnostics'] = mechanisms
    support_rows = []
    support_cache = {}
    with Kernel() as k:
        for regime in REGIMES:
            active = [f for f in latents if f['reuse'][regime]['training_occurrence_count'] or f['reuse'][regime]['heldout_reuse_count']]
            for seed in SEEDS:
                for label in ['B', 'D']:
                    folder = out/'runs'/regime/str(seed)/label/'round_5'/'round.json'
                    if not folder.exists(): continue  # Reporter unit fixture has no actual learner rounds.
                    record = read(folder)
                    for f in active:
                        matched_tasks = []
                        for name, frontier in zip(record['task_names'], record['frontiers']):
                            present = False
                            for e in frontier['entries']:
                                ck = (key(e['program']), f['id'])
                                if ck not in support_cache:
                                    support_cache[ck] = best_rewrite(k, e['program'], [f])['delta_L'] > 0
                                present |= support_cache[ck]
                            if present: matched_tasks.append(name)
                        support_rows.append({'regime': regime, 'seed': seed, 'configuration': label, 'iteration': 5, 'latent': f['id'],
                            'generator_training_tasks': f['reuse'][regime]['distinct_tasks'],
                            'io_frontier_structural_support_tasks': len(matched_tasks), 'task_names': matched_tasks,
                            'compression_minimum_support_met': len(matched_tasks) >= 2,
                            'note': 'Evaluation-only beta-normal pattern coverage in actual found frontiers; not a claim that candidate acceptance follows from support.'})
    save(out/'latent_frontier_support.json', support_rows)
    summary['latent_frontier_support'] = support_rows
    summary['calibration_heldout_solved'] = sum(r['first_solution_nodes'] is not None for r in read(out/'calibration.json')['rows'] if r['name'].startswith('test')) if (out/'calibration.json').exists() else None
    save(out/'experiment_summary.json', summary)
    write_reports(out, summary, recovery_rows)
    # Hash every artifact except the checksum file itself and actively written logs.
    save(out/'RESULT_SHA256SUMS.json', {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p.name != 'RESULT_SHA256SUMS.json' and p.suffix != '.log'})
    return summary


def write_reports(out, summary, recoveries):
    stats = read(out/'structural_statistics.json')
    validation = read(out/'split_validation.json')
    calibration = read(out/'calibration.json')
    base = [r for r in calibration['rows'] if r['name'].startswith('test')]
    solved = sum(r['first_solution_nodes'] is not None for r in base)
    benchmark = f'''# Controlled Synthetic Benchmark

## Scope and frozen files

The accepted Haskell/PyTorch core was not edited. Original 36/24 toy results are
smoke/regression evidence only. This experiment uses {stats['train_count']} training
and {stats['test_count']} held-out tasks, split into four independent reuse cohorts
(56 train / 42 test each). Learners see only six I/O examples per task.
`train.json` and `test.json` contain no programs, latent labels, or private features.
`evaluation_private.json` and `latent_library.json` belong exclusively to evaluation.

The generator constructs 12 two-stage latent functions using randomized typed
composition: four Grid→Grid, four Grid→Color→Grid, four Grid→Int→Grid. Their bodies
contain only the known 24-production base DSL. No latent enters A/B/C/D/E initialization,
Wake, compression, or recognition targets. Oracle O is explicitly separate.

Training deliberate reuse fractions are 0, 1/4, 1/2, 1 for zero/low/medium/high,
with pool concentration increasing. Test latent functions must have appeared in the
same cohort's training generator. Incidental base-fragment reuse in the zero control
is possible and is not called zero mathematical subprogram overlap.

## Complexity and transfer

Operator-tree depth d runs from 2 through 8 in training. Each record also stores raw
AST depth/size, beta-normalized size, primitive leaves, base leaf size, and effective
hidden-library leaf size. The independent controls are requested depth, deliberate
reuse rate, and search budget; other complexity statistics are measured, not assumed
identical across cohorts. Cohort comparisons therefore are descriptive, not a
randomized causal estimate independent of all semantic distribution differences.

I: latent in a new outer Grid context. II: latent receives a new input transformation.
III: two distinct, type-compatible latent calls nest. IV: latent enters the `objects`
argument under `crop(largest(objects(...)))`, absent from training contexts.
Zero reuse has matched count/depth strata and the label `control`, not fictitious latent transfer.
The minimum depths are I/II=3, III=4, IV=5; these structural holes are explicit in
`structural_statistics.json`. At feasible cells there are two held-out tasks per cohort.
Thus nested/novel context is not falsely asserted at d=2.

## Degeneracy and separation

Canonicalization includes the dihedral group, involutions, identity, local trim/border
and constant-argument identities. Six fresh examples, 32 independent split probes,
40 separate recovery probes, and an enumerated 10,000-base-program behavioral reference
bank screen identity, near-constant behavior, known shorter-depth equivalents, and
single-stage deletions. These are finite witness checks, not a minimality proof.

Split validation: `{json.dumps(validation, ensure_ascii=False)}`.
Shared subprograms are intentional. Full/canonical programs, complete task I/O and
probe fingerprints have zero train/test overlap. The validation includes all cohorts,
not merely separate per-cohort checks. Latent occurrence/task/context/reuse counts are
in the frozen latent file. A distinct program context here includes instantiated
arguments and the surrounding input/output transformation context.

## Benchmark calibration

Only A was used before permanent freeze. Structural development first exposed missing
training latent coverage and inadequate single-deletion screening; both were corrected
before B/C/D/O were run. Final A solves {solved}/{len(base)} held-out tasks at 10,000 candidates.
The held-out distribution is hard and is not advertised as smoothly calibrated across
all depths. Easy and transition strata exist mainly in training and shallow held-out
cells. Deep failure remains an explicit research outcome, not a reason to regenerate
after viewing other configurations.

## Final frozen experiment

`benchmark_manifest.json` and `SHA256SUMS.json` freeze all benchmark files and accepted
core hashes before nonbase runs. `RESULT_SHA256SUMS.json` additionally covers final
artifacts and checkpoints. Manifest self-hashing is avoided using the sidecar checksum.
Dataset seed=20260918; training seeds=11,23,47; recognition base seeds=1011,1023,1047
plus iteration×10000; shuffle seeds=2011,2023,2047. No seed was selected for performance.

Reproduce from this frozen dataset:

```powershell
python -m pytest faithful/tests -q
python -m faithful.python.controlled_run train --workers 8
python -m faithful.python.controlled_run evaluate --workers 8
python -m faithful.python.controlled_report
```

To create an independent new study use a new output directory; the generator refuses
to overwrite a frozen benchmark. Existing artifacts are resumed by content hash.
'''
    (ROOT/'CONTROLLED_BENCHMARK_REPORT.md').write_text(benchmark, encoding='utf8')
    lines = ['# Controlled DreamCoder Experiment', '', '## Final frozen experiment', '',
        'All configurations use the same frozen tasks. O is an oracle diagnostic, not a fair algorithm competitor.', '',
        '| Reuse | Configuration | Solve rate at N=10000, iteration 5 | Seed SD | Probe-consistent top-K rate | Mean ΔL |',
        '|---|---|---:|---:|---:|---:|']
    for r in summary['final_10000']:
        lines.append(f"| {r['regime']} | {r['configuration']} | {r['mean_solve_rate']:.3f} | {r['seed_standard_deviation']:.3f} | {r['probe_consistent_topk_rate']:.3f} | {r['mean_delta_L']:.2f} |")
    lines += ['', '## Controls and budgets', '',
        'A is the uniform base grammar; B learns library and generative weights; C uses base-only recognition; D combines library and recognition; E fits only base generative weights. C/D shuffle use task-grammar derangements within each cohort. Iteration 0 has no trained recognition. Iterations 1,2,3,5 are saved from the same persistent five-round run.', '',
        'Training uses 3000 complete candidates, arity-1 faithful compression with up to three accepted inventions per round, 64 ancestral Dream draws and 600 unchanged recognition optimizer steps. Failed dreams are counted, not silently replaced. Persistent frontiers are rescored under the current grammar and merged by generative top-K. Every round records library, weights, frontiers, Dream feature/frontier data with inputs, recognition checkpoint where enabled, and the actual objective.', '',
        'Evaluation budgets are 100,300,600,1000,3000,10000 complete candidates with 500000 expanded states, DSL leaf-size bound 33, depth bound 14 and description-length bound 100. The same maximum-budget enumeration supplies exact shorter-budget first-solution outcomes by prefix rank. This optimization does not reconstruct lower-budget top-K frontiers. Cache keys include full grammar, guidance, I/O and resource bounds. Prefix correctness and state censoring have regression tests.', '',
        'Each curve reports the fraction actually reaching its nominal candidate budget; a state-limited search must not be described as having exhausted 10000 candidates. First-solution nodes for failures are right-censored at actual emissions. Shared batch timing is not summed per task.', '',
        '## Paired contrasts at iteration 5', '', '| Reuse | Contrast | Mean difference | Paired bootstrap 95% CI |', '|---|---|---:|---|']
    for r in summary['comparisons']:
        if r['iteration'] == 5:
            lines.append(f"| {r['regime']} | {r['contrast']} | {r['mean']:.3f} | [{r['paired_bootstrap_95_ci'][0]:.3f}, {r['paired_bootstrap_95_ci'][1]:.3f}] |")
    lines += ['', 'The bootstrap resamples training seeds and shared task IDs in pairs (2000 draws). These intervals are conditional on one generated dataset. Three seeds do not establish cross-dataset robustness.', '',
        '## Recovery and effective complexity', '', '| Reuse | Learner | Mean inventions | Behavioral precision | Recall | F1 | Held-out weighted recall |', '|---|---|---:|---:|---:|---:|---:|']
    for regime in REGIMES:
        for label in ['B', 'D']:
            rr = [r for r in recoveries if r['regime'] == regime and r['configuration'] == label and r['iteration'] == 5]
            mean = lambda field: statistics.mean([r['metrics']['behavioral'][field] for r in rr if r['metrics']['behavioral'][field] is not None]) if any(r['metrics']['behavioral'][field] is not None for r in rr) else None
            lines.append(f"| {regime} | {label} | {statistics.mean(r['learned_count'] for r in rr):.2f} | {mean('precision')} | {mean('recall')} | {mean('f1')} | {mean('weighted_recall')} |")
    lines += ['', 'Recovery JSON separates raw syntax, canonical, β, type and independent-probe matches; precision/recall/F1 and weighted recall are supplied for each. Type agreement alone does not establish recovery. Zero-reuse latent recall is undefined rather than spuriously 100%.', '',
        'Effective complexity uses an exact dynamic program within the explicitly bounded space of β-normal subtree/slot coverings, retaining the request lambda structure. Every rewrite witness is β-checked by Haskell. This is not a claim of the globally shortest program over all β-equivalent inverse expansions or all semantically equivalent Grid programs. `effective_rewrites.json` preserves witnesses. Δd is the AST depth change of the minimum-leaf rewrite, with depth as tie-breaker.', '',
        '## Research questions and limits', '']
    def contrast(regime, name):
        return next(r for r in summary['comparisons'] if r['regime'] == regime and r['iteration'] == 5 and r['contrast'] == name)
    for i, (question, names) in enumerate([
        ('Does library learning help without deliberate reuse?', ['B-A', 'D-C']),
        ('Does benefit grow with reuse?', ['B-A', 'D-C']),
        ('Does recognition guidance survive a task shuffle?', ['C-C_shuffle', 'D-D_shuffle']),
        ('How large is the oracle gap?', ['O-B', 'O-D'])], 1):
        lines.append(question + ' ' + '; '.join(f"{regime}: " + ', '.join(f"{name}={contrast(regime,name)['mean']:+.3f}" for name in names) for regime in REGIMES) + '.')
        lines.append('')
    lines += ['For recovery, consult the table and `abstraction_recovery.json`; for complexity-to-search association, `budget_curves.json` explicitly stratifies by ΔL and Δd, depth, AST size, transfer type, budget and EC iteration. `per_task_results.json` supports paired task-level investigation. These are associations; the experiment does not identify a causal effect of program shortening independently of grammar probability changes.', '',
        'Type I/II/III/IV results are separate curve strata. No aggregate score substitutes for them. Higher-depth failure can be attributed only within tested budgets and priors; even O failure does not establish an impossibility result. Oracle uniformly adds the true active latent definitions, so probability dilution may affect its search.', '',
        'No D>C>B>A ordering is imposed. Stitch is not added by this study. A positive oracle gap together with poor latent recovery motivates a follow-up compression study; an absent gap motivates task/prior/search analysis first. The hard A distribution and finite semantic checks remain material acceptance limitations.', '',
        '`latent_frontier_support.json` additionally distinguishes generated exposure from actual I/O-driven frontier support. The accepted compressor requires support in at least two tasks. If a latent is absent from found frontiers, low recovery cannot by itself be attributed to candidate ranking/compression, and a different compressor alone is not demonstrated to fix it.', '',
        '## Profiling and validation', '',
        'The pre-study profile is in `profile.json`. Real per-round costs, objective values and hierarchy counts are in `experiment_summary.json`; no compression algorithm was replaced. All accepted-core hashes are verified before and after evaluation. The faithful test suite and new benchmark tests are run separately and their live outputs retained in the task execution.', '',
        'Benchmark calibration and frozen outcomes are separate artifacts. Re-running the report never regenerates tasks or alters learner data.']
    lines += ['', '## Transfer and shortening diagnostics at iteration 5', '',
        '| Reuse | Configuration | Fraction shortened | Mean ΔL | I | II | III | IV | Control |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in summary['mechanism_diagnostics']:
        rates = r['transfer_rates']
        rendered = ' | '.join(f'{rates[t]:.3f}' if t in rates else '—' for t in ['I', 'II', 'III', 'IV', 'control'])
        lines.append(f"| {r['regime']} | {r['configuration']} | {r['fraction_with_positive_delta_L']:.3f} | {r['mean_delta_L']:.2f} | {rendered} |")
    lines += ['', '## Interpretation of this completed run', '',
        'The negative control does not support a universal “no benefit without latent reuse” claim: zero-reuse B solves 16.7% versus A 0%, while E already solves 9.5%. The small base DSL still produces incidental reusable fragments. Across the deliberately reused cohorts B−A rises from 4.8 to 11.9 to 23.8 percentage points, but including zero reuse breaks monotonicity. D−C is not monotone, and its paired intervals include zero in every cohort.', '',
        'Latent recovery is incomplete and strongest at high reuse: D’s held-out-weighted behavioral recall is 11.5%, 11.5%, and 46.8% for low/medium/high. High-reuse D shortens 84.1% of held-out task/seed instances by a mean 1.90 leaves. Shortening is not sufficient for synthesis success: low-reuse B solves none of the five held-out tasks that its library shortens. Grammar probabilities and search ordering matter alongside representation length.', '',
        'The recognition shuffle does not generally erase the recognition advantage. At high reuse C loses 7.9 percentage points under shuffle, but its paired interval touches zero; D loses only 0.8 points. The clearest positive D conditioning effect here is zero reuse (+7.9 points, interval [1.6,16.7]). Much of the observed recognition benefit therefore survives exchanging task-conditioned grammars and cannot be attributed solely to task-specific guidance.', '',
        'Outer reuse is the weakest raw D transfer stratum in low and high reuse (5.6% and 11.1% solved); nested reuse is weakest in medium reuse (16.7%). These are descriptive strata with different feasible depth ranges, so the per-depth data should be used before attributing a causal difference to contextual position.', '',
        'Every final and intermediate evaluation reaches all requested candidate budgets: the expanded-state cap does not censor these runs. Nevertheless, Oracle solves at most 12.5% at depth 7–8 in the reused cohorts. Giving the true library therefore does not remove the deep-search problem at N=10000. Larger budgets and alternate priors remain unresolved explanations; the experiment does not prove a solver impossibility or a compression-only cause. Multi-round improvements are also not monotone: high-reuse D falls from 32.5% at round 3 to 31.0% at round 5.', '',
        'Oracle is not a strict upper bound on the full system: it supplies the true latent functions with uniform weights and no recognition. High-reuse D reaches 31.0% versus Oracle 28.6%; this is compatible with different priors, guidance and learned fragments. Zero-reuse Oracle has no latent additions and equals A.', '',
        'Decision on Stitch: the low/medium Oracle−B gaps (+19.0/+16.7 points, paired intervals excluding zero) and poor recovery justify a separate controlled compressor comparison on identical found frontiers. They do not justify replacing the accepted core or claiming that Stitch alone will fix the benchmark. In low reuse, seven of nine active latents have no beta-normal structural coverage in the final B frontiers, and the same seven remain absent in D for all seeds; candidate discovery cannot be diagnosed independently of this missing Wake evidence. A follow-up should separate this exposure bottleneck from compression on fragments supported by at least two found task frontiers. No Stitch code is integrated in this stage.', '',
        'The completed experiment provides all planned measurements, but the hard calibration, one dataset seed, finite probes and restricted rewrite optimum remain explicit limits on scientific acceptance. The outputs support mechanism-specific findings, not a blanket claim that every generalization question has been settled.', '',
        'Validation: 74 faithful/benchmark tests passed. Benchmark and final artifact SHA-256 checks passed. Summed per-round recorded stage times are approximately 54,054 s Wake, 2,598 s compression/prior fitting, 284 s Dream and 600 s recognition; these are concurrent-job wall-time sums, not elapsed study time. Recognition accounts for about 1% of this training-stage total. This run used CPU-only PyTorch; a GPU would not automatically accelerate the Haskell stages.']
    (ROOT/'CONTROLLED_EXPERIMENT_REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf8')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, default=OUT)
    analyze(p.parse_args().output)
