import copy
import json
import random
import pytest
from faithful.python.kernel import Kernel, abstraction, application, primitive, index, invented
from faithful.python.grid import grammar, REQUEST, Task
from faithful.python.controlled_data import canonical, node, X, program, OUT, tupleize, validate
from faithful.python.controlled_learner import derangement, load_io, SEARCH
from faithful.python.controlled_metrics import best_rewrite, match, paired_bootstrap
from faithful.python.toy import search


def test_canonical_algebra():
    assert canonical(node('rotate90', node('rotate90', node('rotate90', node('rotate90', X))))) == X
    assert canonical(node('flipH', node('flipH', X))) == X
    assert canonical(node('trim', node('border', node('trim', X)))) == node('trim', X)
    with Kernel() as k:
        x = [[0, 1, 2], [3, 1, 0]]
        for a in ['rotate90', 'rotate180', 'flipH', 'flipV', 'transpose']:
            for b in ['rotate90', 'rotate180', 'flipH', 'flipV', 'transpose']:
                e = node(a, node(b, X))
                assert k.call('evaluate', program=program(e), inputs=[x]) == k.call('evaluate', program=program(canonical(e)), inputs=[x])


def test_rewrite_nested_and_multiple_parameters():
    with Kernel() as k:
        body = abstraction(abstraction(application(primitive('recolor'), application(primitive('border'), index(1)), primitive('red'), index(0))))
        inv = invented(body)
        pr = {'program': inv, 'type': k.call('infer', grammar=grammar(), program=inv)['type']}
        target = abstraction(application(inv, application(inv, index(0), primitive('blue')), primitive('green')))
        base = k.call('beta', program=target)['program']
        r = best_rewrite(k, base, [pr])
        assert r['delta_L'] > 0
        assert k.call('beta', program=r['witness'])['program'] == base
        assert r['effective_leaf_size'] == 5
        assert best_rewrite(k, base, [])['delta_L'] == 0
        # A free slot under a binder may not capture that local variable.
        with pytest.raises(ValueError):
            match(abstraction(index(1)), abstraction(index(0)), 1)


def test_budget_prefix_equivalence_and_state_censoring():
    g = grammar()
    x = [[0, 1, 2], [3, 0, 2]]
    with Kernel() as k:
        p = program(node('border', node('invert', X)))
        y = k.call('evaluate', program=p, inputs=[x])['value']
        ts = [Task('p', [([x], y)])]
        maximum, _ = search(k, ts, g, g, dict(SEARCH, limit=600))
        for n in [100, 300]:
            direct, _ = search(k, ts, g, g, dict(SEARCH, limit=n))
            rank = maximum[0]['first_solution_nodes']
            assert bool(direct[0]['solutions']) == (rank is not None and rank <= n)
        censored, _ = search(k, ts, g, g, dict(SEARCH, limit=10000, max_states=10))
        assert censored[0]['stop_reason'] == 'state_budget'


def test_contextual_budget_prefix_and_rewrite_optimum():
    import torch
    from faithful.python.grid import features
    from faithful.python.recognition import Recognition
    g = grammar()
    x = [[1, 0], [2, 3]]
    with Kernel() as k:
        p = program(node('invert', X))
        t = Task('invert', [([x], k.call('evaluate', program=p, inputs=[x])['value'])])
        torch.manual_seed(91)
        model = Recognition(g)
        sg = model.search_grammar(features(t))
        full, _ = search(k, [t], g, sg, dict(SEARCH, limit=300))
        short, _ = search(k, [t], g, sg, dict(SEARCH, limit=100))
        rank = full[0]['first_solution_nodes']
        assert bool(short[0]['solutions']) == (rank is not None and rank <= 100)
        other = Task('other', [([x], x)])
        combined, _ = search(k, [t, other], g, sg, dict(SEARCH, limit=300))
        separate, _ = search(k, [other], g, sg, dict(SEARCH, limit=300))
        assert combined == full + separate
        # Exhaustive alternatives in this small covering space: either two
        # short inventions or one larger invention; choose the true leaf minimum.
        short_inv = invented(program(node('border', node('invert', X))))
        long_inv = invented(program(node('border', node('invert', node('border', node('invert', X))))))
        base = k.call('beta', program=long_inv)['program']
        r = best_rewrite(k, base, [{'program': short_inv}, {'program': long_inv}])
        assert r['effective_leaf_size'] == 2


def test_derangements_and_paired_bootstrap():
    for seed in [2011, 2023, 2047]:
        order = derangement(42, seed)
        assert sorted(order) == list(range(42))
        assert all(i != j for i, j in enumerate(order))
    r = paired_bootstrap([[0]*12 for _ in range(3)], draws=100)
    assert r['paired_bootstrap_95_ci'] == [0, 0]
    r = paired_bootstrap([[1]*12 for _ in range(3)], draws=100)
    assert r['mean'] == 1 and r['paired_bootstrap_95_ci'] == [1, 1]


def test_interrupted_cache_recovery_and_input_guard(tmp_path):
    from faithful.python.controlled_learner import evaluate_job
    path = tmp_path/'search.json'
    path.write_text('{interrupted')
    task = {'name': 'identity', 'examples': [{'inputs': [[[1, 2]]], 'output': [[1, 2]]}]}
    job = (path, [task], grammar(), grammar(), [100])
    evaluate_job(job)
    first = path.read_bytes()
    assert json.loads(first)['rows'][0]['first_solution_nodes'] is not None
    assert not path.with_suffix('.partial').exists()
    evaluate_job(job)
    assert first == path.read_bytes()
    with pytest.raises(ValueError, match='Stale'):
        evaluate_job((path, [task], grammar(), grammar(), [300]))


def test_actual_dataset_isolation_and_latent_exposure():
    if not (OUT/'train.json').exists(): pytest.skip('Generate dataset first')
    train = json.loads((OUT/'train.json').read_text())
    test = json.loads((OUT/'test.json').read_text())
    private = json.loads((OUT/'evaluation_private.json').read_text())['tasks']
    assert len(train) == 224 and len(test) == 168
    assert validate(train, test, private)['passed']
    for task in load_io(OUT/'train.json') + load_io(OUT/'test.json'):
        assert set(vars(task)) == {'name', 'examples', 'request'}
    for regime in ['low', 'medium', 'high']:
        exposed = {u['latent'] for m in private.values() if m['split'] == 'train' and m['regime'] == regime for u in m['latent_uses']}
        heldout = {u['latent'] for m in private.values() if m['split'] == 'test' and m['regime'] == regime for u in m['latent_uses']}
        assert heldout <= exposed
    assert all(not m['latent_uses'] for m in private.values() if m['regime'] == 'zero')
    assert all('invented' not in p['program'] for p in grammar()['productions'])


def test_io_overlap_is_example_order_invariant():
    examples = [{'inputs': [[[1]]], 'output': [[2]]}, {'inputs': [[[2]]], 'output': [[3]]}]
    a, b = node('border', node('invert', X)), node('trim', node('invert', X))
    private = {name: {'split': split, 'ground_truth': program(e), 'canonical_program': program(e),
        'expression': e, 'fingerprint': name} for name, split, e in [('a', 'train', a), ('b', 'test', b)]}
    with pytest.raises(AssertionError, match="complete_io_overlap.*1"):
        validate([{'examples': examples}], [{'examples': list(reversed(examples))}], private)


def test_report_matrix_and_shuffle_assignment_guard(tmp_path, monkeypatch):
    """Synthetic reporter fixture, never written to experiment output paths."""
    from faithful.python import controlled_report as report
    from faithful.python.toy import save
    monkeypatch.setattr(report, 'verify', lambda out: {})
    monkeypatch.setattr(report, 'write_reports', lambda *args: None)
    save(tmp_path/'benchmark_manifest.json', {'unit_test_fixture': True})
    save(tmp_path/'latent_library.json', [])
    g = grammar()
    p = program(node('border', node('invert', X)))
    private = {'tasks': {}, 'recovery_probes': [[[1, 0], [2, 3]]]}
    entries = []
    for regime in report.REGIMES:
        name = f'test-{regime}'
        private['tasks'][name] = {'split': 'test', 'regime': regime, 'transfer': 'control', 'matched_transfer_stratum': 'I',
            'depth': 2, 'ast_size': 6, 'ast_depth': 4, 'beta_normalized_size': 6, 'primitive_leaf_count': 2,
            'ground_truth': p, 'hidden_library_complexity': {'effective_leaf_size': 3}}
        cache = f'{regime}.json'
        save(tmp_path/cache, {'seconds': .01, 'rows': [{'name': name, 'first_solution_nodes': 1,
            'solutions': [{'program': p, 'search_rank': 1}], 'enumerated_nodes': 10000, 'expanded_states': 20000, 'stop_reason': 'candidate_budget'}]})
        for seed in report.SEEDS:
            for label in ['B', 'C', 'D', 'E']:
                save(tmp_path/'runs'/regime/str(seed)/label/'complete.json', {'rounds': 5})
            for iteration in report.ROUNDS:
                for label in ['A', 'B', 'C', 'D', 'E', 'C_shuffle', 'D_shuffle', 'O']:
                    gg = copy.deepcopy(g)
                    if seed == 11 and label == 'D':
                        gg['productions'].append({'program': invented(p), 'type': REQUEST, 'log_weight': 0.})
                    entries.append({'regime': regime, 'seed': seed, 'iteration': iteration, 'configuration': label,
                        'grammar': gg, 'paths': [cache], 'selections': {cache: [name]}})
    save(tmp_path/'evaluation_private.json', private)
    save(tmp_path/'evaluation_index.json', entries[:-1])
    with pytest.raises(RuntimeError, match='matrix'): report.analyze(tmp_path)
    save(tmp_path/'evaluation_index.json', entries)
    result = report.analyze(tmp_path)
    assert result['status'] == 'completed_frozen_experiment'
    assert len(json.loads((tmp_path/'per_task_results.json').read_text())['rows']) == 480
    curves = json.loads((tmp_path/'budget_curves.json').read_text())
    assert any(r['dimension'] == 'delta_L' and r['value'] > 0 and r['seed_standard_deviation'] is None for r in curves)
    entries[0]['selections'][entries[0]['paths'][0]] = ['wrong-shuffled-target']
    save(tmp_path/'evaluation_index.json', entries)
    with pytest.raises(RuntimeError, match='assignments'): report.analyze(tmp_path)
