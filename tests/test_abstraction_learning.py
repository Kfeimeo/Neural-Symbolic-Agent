"""Regression tests for the latent-abstraction benchmark and the abstraction-learning study."""
import collections
import copy
import json
from pathlib import Path

import pytest

from faithful.compression.interface import BridgeKernel, digest
from faithful.python.kernel import Kernel, primitive as P, abstraction as L, application as A, index as I, invented, arrow, base
from faithful.python.grid import grammar, REQUEST, Task
from faithful.python.controlled_data import canonical, node, X, P as PARAM
from benchmarks.latent_abstraction import generator as bench
from experiments.abstraction_learning import compressors, learner, evaluation, analysis

ROOT = Path(__file__).resolve().parents[1]


def frontier(p):
    return {'request': REQUEST, 'entries': [{'program': p, 'log_likelihood': 0.}]}


def fixture_frontiers():
    fs = [frontier(L(A(P('flipH'), A(P('rotate90'), A(P('trim'), I(0)))))) for _ in range(4)]
    fs += [frontier(L(A(P('recolor'), A(P('border'), I(0)), P('red'), P(c)))) for c in ['blue', 'green', 'blue']]
    fs += [frontier(L(A(P('invert'), A(P('recolor'), A(P('border'), A(P('flipV'), I(0))), P('red'), P('green')))))]
    return fs


# ----------------------------------------------------------------------------- benchmark generator

def test_latent_detection_records_contexts_and_nesting():
    f = {'id': 'F00', 'kind': 'grid', 'depth': 2, 'expression': node('rotate90', node('trim', X)), 'parameter_values': None}
    g = {'id': 'F01', 'kind': 'color', 'depth': 2, 'expression': node('recolor', node('border', X), node('red'), PARAM), 'parameter_values': ['blue', 'green']}
    e = node('flipH', node('rotate90', node('trim', node('recolor', node('border', node('invert', X)), node('red'), node('blue')))))
    uses = {u['latent']: u for u in bench.find_uses(e, [f, g])}
    assert uses['F00']['outer'] == 'flipH' and uses['F00']['inner'] == 'recolor' and uses['F00']['inner_latent'] == 'F01'
    assert uses['F01']['outer'] == 'trim' and uses['F01']['inner'] == 'invert' and uses['F01']['parameter'] == 'blue'
    # an invalid parameter value is not a latent occurrence
    assert bench.find_uses(node('recolor', node('border', X), node('red'), node('red')), [f, g]) == []
    root = bench.find_uses(node('rotate90', node('trim', X)), [f, g])
    assert root[0]['outer'] == 'root' and root[0]['inner'] == '$x'
    # novelty: outer operator seen in training rejects transfer I, unseen accepts
    ctx = {'outer': collections.defaultdict(set), 'inner': collections.defaultdict(set), 'nested': set(), 'nested_triples': set()}
    plan = {'latents': [('F00', None)], 'novelty': 'x'}
    ctx['outer']['F00'].add('flipH')
    assert not bench.plan_satisfied(bench.find_uses(e, [f, g]), plan, 'I', ctx)
    ctx['outer']['F00'].clear()
    assert bench.plan_satisfied(bench.find_uses(e, [f, g]), plan, 'I', ctx)


def test_match_pattern_binds_one_argument_consistently():
    pattern = node('recolor', X, node('red'), node('blue'))
    assert bench.match_pattern(pattern, node('recolor', node('trim', X), node('red'), node('blue')))[0] == node('trim', X)
    assert bench.match_pattern(pattern, node('recolor', node('trim', X), node('red'), node('green'))) is None
    assert bench.match_pattern(node('translate', X, node('one'), node('zero')), node('translate', X, node('one'), node('zero')))[0] == X


def test_screening_rejects_identity_and_single_deletions():
    with Kernel() as k:
        probes = [bench.random_grid(bench.random.Random(i)) for i in range(8)]
        screen = bench.Screen(k, probes)
        shallow = {screen.identity: 0}
        assert screen.degenerate(canonical(node('invert', node('invert', X))), 2, shallow) == 'identity_or_constant'
        assert screen.degenerate(node('solid', node('solid', X, node('red')), node('blue')), 2, shallow) == 'single_deletion_equivalent'
        assert screen.degenerate(node('rotate90', node('trim', X)), 2, shallow) is None


@pytest.mark.parametrize('seed', bench.DEFAULT_SEEDS)
def test_frozen_instances_are_isolated_and_compositional(seed):
    out = bench.DATA / f'seed_{seed}'
    if not (out / 'manifest.json').exists():
        pytest.skip('benchmark instance not generated')
    bench.verify(out)
    train, test = bench.read(out / 'train.json'), bench.read(out / 'test.json')
    assert all(set(t) == {'name', 'examples'} for t in train + test)
    private = bench.read(out / 'private.json')['tasks']
    latents = bench.read(out / 'latent_library.json')
    assert bench.validate(train, test, private)['passed']
    for task in bench.load_tasks(out / 'train.json'):
        assert set(vars(task)) == {'name', 'examples', 'request'}
    for regime in ['low', 'medium', 'high']:
        ctx = bench.contexts_of(private, 'train', regime)
        for name, m in private.items():
            if m['split'] != 'test' or m['regime'] != regime:
                continue
            uses = [u for u in m['latent_uses'] if u['deliberate']]
            assert uses and m['depth'] >= 3
            assert m['effective_complexity']['delta_L'] > 0
            redetected = bench.find_uses(bench.tupleize(m['expression']), latents)
            assert redetected == [{k: v for k, v in u.items() if k != 'deliberate'} for u in m['latent_uses']]
            if m['transfer'] == 'I':
                assert any(u['outer'] != 'root' and u['outer'] not in ctx['outer'][u['latent']] for u in uses)
            elif m['transfer'] == 'II':
                assert any(u['inner'] != '$x' and u['inner'] not in ctx['inner'][u['latent']] for u in uses)
            else:
                assert m['depth'] >= bench.MIN_NESTED_DEPTH
                nested = [u for u in uses if u['inner_latent']]
                assert nested and (m['novelty'].startswith('ordered') is ((nested[0]['latent'], nested[0]['inner_latent']) not in ctx['nested']))
    assert all(not any(u['deliberate'] for u in m['latent_uses']) for m in private.values() if m['regime'] == 'zero')


# ----------------------------------------------------------------------------- compressors

@pytest.fixture(scope='module')
def kernel():
    with BridgeKernel() as k:
        yield k


@pytest.mark.parametrize('method', list(compressors.METHODS))
def test_compressor_interface_soundness(kernel, method):
    fs = fixture_frontiers() + [{'request': REQUEST, 'entries': []}]
    g = grammar()
    before = digest([fs, g])
    r = compressors.make_compressor(method, kernel).compress(fs, g)
    assert digest([fs, g]) == before, 'inputs mutated'
    assert len(r.rewritten_programs) == len(fs) and r.rewritten_programs[-1]['entries'] == []
    xs = [[[0, 1, 2], [3, 0, 1]], [[1]], [[1, 0], [2, 3], [0, 1]]]
    for a, b in zip(fs, r.rewritten_programs):
        for x, y in zip(a['entries'], b['entries']):
            assert kernel.call('beta', program=x['program']) == kernel.call('beta', program=y['program'])
            assert kernel.call('evaluate_batch', program=x['program'], input_sets=[[v] for v in xs]) == kernel.call('evaluate_batch', program=y['program'], input_sets=[[v] for v in xs])
    for p in r.invented_abstractions:
        assert kernel.call('infer', grammar=r.grammar_updates, program=p['program'])['type'] == p['type']
    if method == 'A':
        assert not r.invented_abstractions and abs(r.mdl_accounting['delta_mdl']) < 1e-9
    else:
        assert r.invented_abstractions and r.mdl_accounting['delta_mdl'] > 0


def test_shared_loop_reproduces_frozen_dreamcoder_compressor(kernel):
    fs, g = fixture_frontiers(), grammar()
    direct = kernel.call('compress', grammar=g, frontiers=fs, arity=1, iterations=3)
    loop = compressors.DreamCoderReimplemented(kernel).compress(fs, g)
    assert loop.grammar_updates == direct['grammar'] and loop.rewritten_programs == direct['frontiers']


def test_trivial_and_duplicate_proposals_are_filtered(kernel):
    wrapper = invented(L(A(invented(L(A(P('flipH'), I(0)))), I(0))))
    assert not compressors.nontrivial(wrapper)
    assert compressors.nontrivial(invented(L(A(P('flipH'), A(P('trim'), I(0))))))
    assert compressors.nontrivial(invented(L(A(P('recolor'), I(0), I(0), I(0)))))
    g = grammar()
    inv = invented(L(A(P('flipH'), A(P('trim'), I(0)))))
    g['productions'].append({'program': inv, 'type': REQUEST, 'log_weight': 0.})
    eta = invented(L(A(inv, I(0))))
    assert compressors.admissible(kernel, eta, g) is not None
    assert compressors.admissible(kernel, invented(L(A(P('trim'), A(P('flipH'), I(0))))), g) is None


def test_compressor_modules_do_not_read_private_data():
    for name in ['compressors.py', 'learner.py']:
        text = (ROOT / 'experiments' / 'abstraction_learning' / name).read_text(encoding='utf8')
        assert 'private.json' not in text and 'latent_library' not in text
        assert 'from benchmarks' not in text and 'import benchmarks' not in text


# ----------------------------------------------------------------------------- learner and evaluation

def test_learner_caches_rounds_and_uses_io_only(tmp_path):
    x = [[0, 1, 2], [3, 0, 1]]
    with Kernel() as k:
        y = k.call('evaluate', program=L(A(P('invert'), I(0))), inputs=[x])['value']
    tasks = [Task('t0', [([x], y)]), Task('t1', [([x], x)])]
    out = learner.run_condition(tasks, 'A', tmp_path / 'A', rounds=1, wake_limit=200, verbose=False)
    record = learner.read_json(learner.round_path(out, 1))
    assert record['wake']['solved'] == 2 and record['invention_count'] == 0 and record['options']['recognition'] == 'off'
    assert (out / 'complete.json').exists()
    learner.run_condition(tasks, 'A', tmp_path / 'A', rounds=1, wake_limit=200, verbose=False)


def test_recovery_handles_permuted_arguments_and_unrelated_inventions(kernel):
    body = L(L(A(P('recolor'), A(P('border'), I(1)), P('red'), I(0))))          # λx.λc. recolor (border x) red c
    latent = {'id': 'F00', 'kind': 'color', 'depth': 2, 'body': body, 'type': kernel.call('infer', grammar=grammar(), program=body)['type'],
              'parameter_values': ['blue', 'green'], 'reuse': {'high': {'deliberate_active': True, 'test_deliberate_count': 3}}}
    swapped = invented(L(L(A(P('recolor'), A(P('border'), I(0)), P('red'), I(1)))))   # λc.λx. ...
    other = invented(L(A(P('flipH'), A(P('trim'), I(0)))))
    g = grammar()
    for inv in [swapped, other]:
        g['productions'].append({'program': inv, 'type': kernel.call('infer', grammar=g, program=inv)['type'], 'log_weight': 0.})
    probes = [bench.random_grid(bench.random.Random(i)) for i in range(6)]
    r = evaluation.recovery(kernel, g, [latent], 'high', probes)
    m = r['metrics']
    assert m['type']['recall'] == 0 and m['type_permuted']['recall'] == 1
    assert m['behavioral']['recall'] == 1 and m['behavioral']['precision'] == 0.5 and m['behavioral']['weighted_recall'] == 1
    assert m['syntactic']['recall'] == 0 and m['beta']['recall'] == 0
    empty = evaluation.recovery(kernel, grammar(), [latent], 'high', probes)
    assert empty['metrics']['behavioral']['precision'] is None and empty['metrics']['behavioral']['recall'] == 0


def test_ragged_paired_bootstrap():
    r = analysis.paired_bootstrap([[1., 1.], [1., 1., 1.], [1.]], draws=200)
    assert r['mean'] == 1 and r['paired_bootstrap_95_ci'] == [1, 1] and r['tasks'] == [2, 3, 1]
    r = analysis.paired_bootstrap([[0., 1.], [1., 0., 1.]], draws=500)
    assert 0 < r['mean'] < 1 and r['paired_bootstrap_95_ci'][0] <= r['mean'] <= r['paired_bootstrap_95_ci'][1]
    assert analysis.paired_bootstrap([[], []]) is None


def test_analysis_statistics_helpers():
    assert analysis.ranks([3, 1, 2, 2]) == [4, 1, 2.5, 2.5]
    assert abs(analysis.pearson([1, 2, 3], [2, 4, 6]) - 1) < 1e-12
    assert abs(analysis.spearman([1, 2, 3, 4], [10, 20, 15, 40]) - 0.8) < 1e-12
    assert analysis.pearson([1, 1, 1], [1, 2, 3]) is None
    assert analysis.mstd([None, 1., 3.]) == {'mean': 2., 'std': pytest.approx(1.4142135623730951), 'n': 2}
