"""Shared version-space compressor: algebra, soundness and reference agreement.

Reference artifacts under faithful/results/versionspace were produced by the
unmodified OCaml binary (`python -m faithful.versionspace.differential official`).
Every test reruns our implementation; nothing is read back from our own output.
"""
import json
import os
import pytest
from faithful.python.kernel import ROOT
from faithful.compression.versionspace import VersionSpaceKernel, VersionSpaceCompressor, build_versionspace
from faithful.compression.interface import digest
from faithful.versionspace.differential import OUT, parse, show, compare, list_corpus, grammar, parse_log, reference

@pytest.fixture(scope='module')
def kernel():
    build_versionspace()
    with VersionSpaceKernel() as k: yield k

key = lambda p: json.dumps(p, sort_keys=True)
PROGRAMS = ['(lambda (+ (+ $0 1) 1))', '(lambda (map (lambda (+ $0 1)) $0))',
    '(lambda (lambda (if (gt? $0 0) (+ $1 1) (+ $0 1))))', '(lambda (fold $0 0 (lambda (lambda (+ $1 $0)))))',
    '(lambda (#(lambda (+ (+ $0 1))) $0 1))',
    '(lambda (#(lambda (lambda (+ (+ $0 1) $1))) 1 (#(lambda (lambda (+ (+ $0 1) $1))) $0 1)))']

@pytest.mark.parametrize('source', PROGRAMS)
def test_table_denotes_the_explicit_version_set(kernel, source):
    # One inversion step: the hash-consed table and the frozen explicit
    # enumeration must describe exactly the same set of refactorings.
    p = parse(source)
    shared = kernel.call('vs_versions', program=p, arity=1)['programs']
    explicit = kernel.call('versions', program=p, arity=1)['programs']
    # Union members may overlap, so the table is compared as a set.
    assert set(map(key, shared)) == set(map(key, explicit))

@pytest.mark.parametrize('source', PROGRAMS)
def test_every_refactoring_is_beta_equivalent(kernel, source):
    p = parse(source)
    expected = kernel.call('beta', program=p)
    refactorings = kernel.call('vs_versions', program=p, arity=2)
    if refactorings['log_version_size'] > 9: refactorings = kernel.call('vs_versions', program=p, arity=1)
    assert len(refactorings['programs']) > 5
    for q in refactorings['programs']:
        assert kernel.call('beta', program=q) == expected

def test_sharing_keeps_three_step_spaces_small(kernel):
    # About e^18 refactorings; an explicit set of that size cannot be built.
    r = kernel.call('vs_versions', program=parse(PROGRAMS[2]), arity=3, count_only=True)
    assert r['log_version_size'] > 18
    assert r['reachable_versions'] < 50000

@pytest.mark.parametrize('name', ['compression', 'hierarchy'])
def test_original_reference_fixtures(kernel, name):
    out = ROOT/'faithful/results'
    fixture = json.loads((out/f'{name}_fixture.json').read_text())
    official = json.loads((out/f'{name}_official.json').read_text())
    log = (out/f'{name}_official.log').read_text()
    ours = kernel.call('vs_compress', **fixture, arity=1, iterations=1, top_k=5, trace=True)
    assert compare(ours, official, log) == []
    # Monomorphic library: the kernel and reference likelihoods are the same function.
    assert kernel.call('vs_compress', **fixture, arity=1, iterations=1, top_k=5, trace=True, likelihood='ocaml') == ours

# The whole suite takes about half an hour; by default a spread of the quicker
# corpora runs. FAITHFUL_VS_FULL=1 (or `differential compare`) covers all of them.
QUICK = ['list_arity1', 'list_narrow_rescoring', 'list_narrow_beam', 'planted_inlining_1', 'planted_list_1', 'planted_arith_0']
def artifacts():
    names = sorted(p.name[:-len('.case.json')] for p in OUT.glob('*.case.json'))
    return names if os.environ.get('FAITHFUL_VS_FULL') else [n for n in names if n in QUICK]

@pytest.mark.parametrize('name', artifacts())
def test_reference_agreement_on_complex_corpora(kernel, name):
    case = json.loads((OUT/f'{name}.case.json').read_text(encoding='utf8'))
    official, log, status, _ = reference(name)
    assert status == 0
    # Polymorphic libraries: the reference normaliser is selected (see ReferenceLikelihood.hs).
    ours = kernel.call('vs_compress', grammar=case['grammar'], frontiers=case['frontiers'], trace=True, likelihood='ocaml', **case['options'])
    # Rank order, both scores and the rewritten frontiers of every rescored candidate,
    # then the final library, weights and frontiers of every iteration.
    assert compare(ours, official, log) == []
    # The comparison is not vacuous: candidates were proposed, rescored and adopted.
    steps = parse_log(log)
    assert steps and steps[0]['candidate_count'] > 0 and steps[0]['trials'] and ours['history']
    assert all(h['rewrite_fallbacks'] == 0 for h in ours['history'])

def test_rewrites_are_sound_and_scorable(kernel):
    g, fs = list_corpus()
    r = kernel.call('vs_compress', grammar=g, frontiers=fs, arity=2, iterations=3, top_k=2, pseudo_counts=30, structure_penalty=1.5)
    assert len(r['history']) >= 2
    assert len(r['grammar']['productions']) == len(g['productions'])+len(r['history'])
    for a, b in zip(fs, r['frontiers']):
        assert a['request'] == b['request'] and len(a['entries']) == len(b['entries'])
        for x, y in zip(a['entries'], b['entries']):
            assert x['log_likelihood'] == y['log_likelihood']
            assert kernel.call('beta', program=x['program']) == kernel.call('beta', program=y['program'])
            kernel.call('score', grammar=r['grammar'], request=a['request'], program=y['program'])
    for h in r['history']:
        assert h['after'] >= h['before'] and h['rewrite_fallbacks'] == 0
        tp = kernel.call('infer', grammar=r['grammar'], program=h['invented'])['type']
        assert any(p['program'] == h['invented'] and p['type'] == tp for p in r['grammar']['productions'])

def test_compressor_interface_preserves_unsolved_frontiers(kernel):
    g, fs = list_corpus()
    empty = dict(request=fs[0]['request'], entries=[])
    frontiers = [empty]+fs[:20]+[empty]
    before = digest([frontiers, g])
    r = VersionSpaceCompressor(kernel, iterations=2, arity=2, top_k=2).compress(frontiers, g)
    assert digest([frontiers, g]) == before
    assert r.rewritten_programs[0] == empty == r.rewritten_programs[-1] and len(r.rewritten_programs) == len(frontiers)
    assert r.invented_abstractions and r.mdl_accounting['delta_mdl'] > 0
    assert kernel.call('vs_compress', grammar=g, frontiers=[empty], arity=2)['history'] == []

def test_duplicate_and_trivial_candidates_are_not_invented(kernel):
    # A library that already holds the only useful abstraction: nothing to add.
    inv = parse('#(lambda (+ (+ $0 1)))')
    tp = kernel.call('infer', grammar=grammar(['+', '1', '0']), program=inv)['type']
    g = grammar(['+', '1', '0'], [(inv, tp)])
    request = {'constructor': '->', 'arguments': [{'constructor': 'int', 'arguments': []}]*2}
    fs = [dict(request=request, entries=[dict(program=parse('(lambda (%s $0 %s))' % (show(inv), c)), log_likelihood=0.)]) for c in '01']*3
    r = kernel.call('vs_compress', grammar=g, frontiers=fs, arity=1, iterations=2)
    assert inv not in [h['invented'] for h in r['history']]
    assert [p['program'] for p in r['grammar']['productions']].count(inv) == 1

def test_frozen_ec_driver_runs_on_the_shared_table(kernel):
    # The EC loop is the frozen one; only the class it instantiates is substituted.
    import types
    from faithful.python import ec
    from faithful.python.grid import Task, smoke_grammar
    seen = []
    class Recording(VersionSpaceKernel):
        def __init__(self): super().__init__(compress_options=dict(top_k=2))
        def call(self, operation, **payload):
            result = super().call(operation, **payload)
            if operation == 'compress': seen.append((payload, result))
            return result
    driver = types.FunctionType(ec.explore_compress.__code__, dict(ec.__dict__, Kernel=Recording), argdefs=ec.explore_compress.__defaults__)
    xs = [[[0, 1, 2], [2, 3, 0]], [[1, 0], [3, 2], [0, 3]]]
    turn = lambda x: [list(r) for r in zip(*x[::-1])]
    tasks = [Task('quarter', [([x], turn(x)) for x in xs]), Task('half', [([x], turn(turn(x))) for x in xs]),
             Task('three-quarters', [([x], turn(turn(turn(x)))) for x in xs])]
    history = driver(tasks, rounds=2, search_bound=7, compression_arity=1, base_grammar=smoke_grammar())
    assert [r['solved'] for r in history] == [3, 3] and len(seen) == 2
    for payload, result in seen:
        assert set(result) == {'grammar', 'frontiers', 'history'}
        for a, b in zip(payload['frontiers'], result['frontiers']):
            for x, y in zip(a['entries'], b['entries']):
                assert kernel.call('beta', program=x['program']) == kernel.call('beta', program=y['program'])
