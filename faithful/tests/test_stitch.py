import copy
import json
import pytest
from faithful.compression.interface import BridgeKernel, accounting, digest
from faithful.compression.original import OriginalCompressor
from faithful.compression.stitch import StitchCompressor, encode, decode
from faithful.domains.official import DomainKernel, dataset
from faithful.python.kernel import primitive as P, abstraction as L, application as A, index as I, invented, arrow, base, variable
from faithful.python.grid import grammar, REQUEST

@pytest.fixture
def kernel():
    with BridgeKernel() as k:yield k

def fixture():
    p=L(A(P('flipH'),A(P('rotate90'),A(P('flipH'),I(0)))))
    return [dict(request=REQUEST,entries=[dict(program=copy.deepcopy(p),log_likelihood=0.)]) for _ in range(8)]

def test_roundtrip_binders_and_opaque():
    p=L(A(invented(L(A(P('flipH'),I(0)))),I(0)))
    atoms={};s=encode(p,atoms)
    assert decode(s,{name:q for name,q in atoms.values()})==p
    assert decode('(lam (#0 $0))',{},1)==L(L(A(I(1),I(0))))

@pytest.mark.parametrize('cls',[OriginalCompressor,StitchCompressor])
def test_common_objective_sound_rewrites_and_no_mutation(kernel,cls):
    fs=fixture();g=grammar();before=digest([fs,g])
    r=cls(kernel).compress(fs,g)
    assert digest([fs,g])==before
    assert r.invented_abstractions
    fit=kernel.call('compression_objective',grammar=g,frontiers=fs)
    assert r.mdl_accounting['before']['mdl']==pytest.approx(-fit['objective'])
    assert r.mdl_accounting['after']==accounting(kernel,r.grammar_updates,r.rewritten_programs)
    xs=[[[0,1,2],[3,0,1]],[[1]],[[1,0],[2,3],[0,1]]]
    for a,b in zip(fs,r.rewritten_programs):
        p,q=a['entries'][0]['program'],b['entries'][0]['program']
        assert kernel.call('beta',program=p)==kernel.call('beta',program=q)
        assert kernel.call('evaluate_batch',program=p,input_sets=[[x] for x in xs])==kernel.call('evaluate_batch',program=q,input_sets=[[x] for x in xs])
    for p in r.invented_abstractions:
        assert kernel.call('infer',grammar=r.grammar_updates,program=p['program'])['type']==p['type']

def test_identical_input_and_protocol(kernel):
    fs=fixture();g=grammar()
    a,b=[cls(kernel).compress(fs,g) for cls in [OriginalCompressor,StitchCompressor]]
    assert a.statistics['input_sha256']==b.statistics['input_sha256']
    assert a.mdl_accounting['before']==b.mdl_accounting['before']
    # Compressor source cannot read evaluation-only metadata.
    from pathlib import Path
    for name in ['interface','original','stitch']:
        text=(Path(__file__).parents[1]/'compression'/f'{name}.py').read_text()
        assert 'evaluation_private.json' not in text and 'latent_library.json' not in text

def test_official_polymorphic_higher_order_invention():
    g,_,_=dataset('list')
    inv=invented(L(L(A(P('map'),I(1),I(0)))))
    with DomainKernel() as k:
        tp=k.call('infer',grammar=g,program=inv)['type']
        assert 'var' in json.dumps(tp)
        p=L(A(inv,L(I(0)),I(0)))
        for xs in [[True,False],[-3,0,5],[]]:
            assert k.call('evaluate',program=p,inputs=[xs])['value']==xs
        assert k.call('beta',program=p)==k.call('beta',program=L(A(P('map'),L(I(0)),I(0))))

@pytest.mark.parametrize('cls',[OriginalCompressor,StitchCompressor])
def test_unsolved_frontiers_are_preserved(kernel,cls):
    empty=dict(request=REQUEST,entries=[])
    fs=[empty,*fixture(),empty]
    r=cls(kernel).compress(fs,grammar())
    assert r.rewritten_programs[0]==empty==r.rewritten_programs[-1]
    assert len(r.rewritten_programs)==len(fs)
    assert r.mdl_accounting['delta_mdl']>0
    no_solutions=cls(kernel).compress([empty],grammar())
    assert no_solutions.rewritten_programs==[empty]
    assert not no_solutions.invented_abstractions

def test_original_adapter_exactly_matches_frozen_core(kernel):
    fs,g=fixture(),grammar()
    direct=kernel.call('compress',grammar=g,frontiers=fs,arity=1,iterations=3)
    assert OriginalCompressor(kernel).compress(fs,g).protocol()==direct
