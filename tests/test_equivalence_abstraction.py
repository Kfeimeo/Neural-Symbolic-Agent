"""Equations are justified algebraically; these tests catch implementation mistakes."""
import itertools
import pytest
from faithful.compression.interface import BridgeKernel
from faithful.python.grid import grammar, REQUEST
from experiments.equivalence_abstraction.equations import *
from experiments.equivalence_abstraction.egraph import EGraph, anti_unify, close_pattern
from experiments.equivalence_abstraction.compressor import EquivalenceCompressor

X = ('var', 0)


@pytest.fixture(scope='module')
def kernel():
    with BridgeKernel() as k:
        yield k


def test_reduction_overlaps_join():
    # Exhaust all unary words through length four, checking every one-step peak.
    ops = ['identity', 'flipH', 'flipV', 'transpose', 'rotate180', 'invert', 'trim', 'rotate90']
    for n in range(5):
        for word in itertools.product(ops, repeat=n):
            t = X
            for op in word:
                t = call(op, t)
            nf = normal(t)
            assert normal(nf) == nf
            for q in steps(t, root_reductions):
                assert size(q) < size(t)
                assert normal(q) == nf
    for n in (5, 6, 7):
        t = X
        for _ in range(n):
            t = call('rotate90', t)
        assert all(normal(q) == normal(t) for q in steps(t, root_reductions))


def test_rules_match_haskell_on_rectangles_and_parameters(kernel):
    grids = [[[0]], [[1, 0, 3]], [[1], [0], [2]], [[0, 1, 2], [3, 0, 1]], [[0, 0], [0, 0]]]
    terms = []
    for g in sorted(GEOMETRY):
        for op, args in [('invert', []), ('border', []), ('trim', []),
                         ('recolor', [('prim', 'red'), ('prim', 'blue')]), ('solid', [('prim', 'green')])]:
            terms.extend([call(g, call(op, X, *args)), call(op, call(g, X), *args)])
        for dr, dc in itertools.product(['zero', 'one', 'minus_one'], repeat=2):
            terms.extend([call(g, call('translate', X, ('prim', dr), ('prim', dc))),
                          call('translate', call(g, X), ('prim', dr), ('prim', dc))])
    for t in terms:
        expected = kernel.call('evaluate_batch', program=wire(('lam', t)), input_sets=[[g] for g in grids])['values']
        for q in root_equations(t):
            actual = kernel.call('evaluate_batch', program=wire(('lam', q)), input_sets=[[g] for g in grids])['values']
            assert actual == expected, (t, q)
            assert t in set(root_equations(q)), (t, q)


def test_saturation_normalizes_every_generated_term():
    t = call('flipH', call('invert', call('flipH', X)))
    qs, proof = saturate(t)
    assert call('invert', X) in qs and proof
    assert all(normal(q) == q for q in qs)
    with pytest.raises(RuntimeError):
        saturate(t, limit=1)


def test_parametric_eclass_antiunification(kernel):
    graph = EGraph()
    a, _, _ = graph.space(call('rotate90', call('translate', X, ('prim', 'one'), ZERO)))
    b, _, _ = graph.space(call('rotate90', call('translate', X, ('prim', 'minus_one'), ZERO)))
    invs = [close_pattern(p) for p in anti_unify(graph, a, b)]
    body = call('rotate90', call('translate', ('var', 0), ('var', 1), ZERO))
    expected = {'invented': wire(('lam', ('lam', body)))}
    assert expected in invs


def test_normalized_adapter_and_baseline_parity(kernel):
    from faithful.compression.original import OriginalCompressor
    p = wire(('lam', call('identity', call('flipH', X))))
    fs = [{'request': REQUEST, 'entries': [{'program': p, 'log_likelihood': 0.}]}]
    a = EquivalenceCompressor(kernel, arm='B0').compress(fs, grammar())
    b = OriginalCompressor(kernel).compress(fs, grammar())
    assert a.to_dict() == b.to_dict()
    c = EquivalenceCompressor(kernel, arm='B1').compress(fs, grammar())
    assert c.rewritten_programs[0]['entries'][0]['program'] == wire(('lam', call('flipH', X)))


def test_frozen_learner_code_is_reused():
    from experiments.equivalence_abstraction import learner
    from experiments.full_dreamcoder import learner as frozen
    assert learner.run_condition.__code__ is frozen.run_condition.__code__
    assert learner.run_condition.__defaults__ == frozen.run_condition.__defaults__
    assert frozen.METHODS != learner.ARMS


def test_b3_compression_preserves_semantics_and_mdl_gate(kernel):
    programs = [wire(('lam', call('border', call('invert', call('flipH', X))))),
                wire(('lam', call('flipH', call('invert', call('border', X)))))]
    fs = [{'request': REQUEST, 'entries': [{'program': p, 'log_likelihood': 0.}]} for p in programs]
    fs.append({'request': REQUEST, 'entries': []})
    result = EquivalenceCompressor(kernel, iterations=1, arm='B3').compress(fs, grammar())
    inputs = [[[[1, 0, 2], [0, 3, 1]]], [[[0]]]]
    for old, new in zip(fs, result.rewritten_programs):
        if not old['entries']:
            assert new == old
            continue
        assert kernel.call('evaluate_batch', program=old['entries'][0]['program'], input_sets=inputs) == kernel.call(
            'evaluate_batch', program=new['entries'][0]['program'], input_sets=inputs)
    assert all(h['after'] > h['before'] + 1e-10 for h in result.history)
    assert result.statistics['steps'][0]['candidate_count'] > 0


def test_parameter_metric_counts_all_exposed_values(kernel):
    from faithful.python.grid import GRID, INT
    from faithful.python.kernel import arrow
    from experiments.equivalence_abstraction.metrics import exposure_and_parameters
    body = ('lam', ('lam', call('border', call('translate', ('var', 1), ('var', 0), ZERO))))
    tp = arrow(GRID, arrow(INT, GRID))
    latent = {'id': 'fixture', 'body': wire(body), 'program': {'invented': wire(body)}, 'type': tp,
              'parameter_values': ['one', 'minus_one'],
              'reuse': {'medium': {'deliberate_active': True, 'test_deliberate_count': 2}}}
    fs = [{'request': REQUEST, 'entries': [{'program': wire(('lam', call('border', call('translate', X, ('prim', v), ZERO)))),
                                           'log_likelihood': 0.}]} for v in ('one', 'minus_one')]
    g = grammar()
    g['productions'].append({'program': latent['program'], 'type': tp, 'log_weight': 0.})
    m = exposure_and_parameters(kernel, fs, ['a', 'b'], g, [latent], 'medium',
                               [[[1, 0], [2, 3], [0, 1]], [[3], [1], [2]]])
    assert m['conditional_parametric_recovery'] == {'numerator': 1, 'denominator': 1, 'probability': 1.}
    assert m['parameterised_latent_recall'] == 1.
    assert m['parameters'][0]['exposed_parameter_tasks'] == {'one': ['a'], 'minus_one': ['b']}
