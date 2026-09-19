import random
import pytest
from faithful.python.kernel import *
from faithful.python.grid import grammar,REQUEST
from faithful.tests.test_golden import kernel,oracle,make_g,I
from dreamcoder.domains.grid import make_language,sample_grid,Object
from dreamcoder.language import INPUT,Program

def ast(p):
    return index(0) if p==INPUT else application(primitive(p.name),*[ast(c) for c in p.arguments])
def wire(v):
    if isinstance(v,Object):return [list(c) for c in v.cells]
    if isinstance(v,(list,tuple)):return [wire(x) for x in v]
    return v

def test_all_24_signatures_and_evaluators(kernel):
    old=make_language();new=grammar()
    assert [p['program']['primitive'] for p in new['productions']]==list(old.primitives)
    grids=[((0,),),((1,0,2),(0,0,0),(3,0,1)),((1,2),(3,0))]+[sample_grid(random.Random(n)) for n in range(12)]
    args={'Grid':INPUT,'Color':Program('red'),'Int':Program('minus_one'),'Bool':Program('is_empty',(Program('objects',(INPUT,)),)),
          'Objects':Program('objects',(INPUT,)),'Object':Program('largest',(Program('objects',(INPUT,)),))}
    for pr in new['productions']:
        name=pr['program']['primitive'];sig=old.primitives[name].signature
        tp=base(sig.result.name.lower())
        for t in reversed(sig.arguments):tp=arrow(base(t.name.lower()),tp)
        assert pr['type']==tp
        p=Program(name,tuple(args[t.name] for t in sig.arguments))
        actual=kernel.call('evaluate_batch',program=abstraction(ast(p)),input_sets=[[wire(x)] for x in grids])['values']
        assert actual==[wire(old.evaluate(p,x)) for x in grids],name

@pytest.mark.parametrize('req',[I,arrow(I,I),arrow(arrow(I,I),arrow(I,I))])
def test_agenda_matches_official_cost_bounded_set(kernel,oracle,req):
    kw=dict(grammar=make_g(),request=req,upper_bound=6,maximum_depth=7,limit=100000)
    ours=kernel.call('enumerate_budget',**kw,max_states=1000000,max_size=1000)
    official=oracle('enumerate',**kw)['programs']
    key=lambda p:__import__('json').dumps(p,sort_keys=True)
    a={key(p['program']):p['search_log_score'] for p in ours['programs']}
    b={key(p['program']):p['search_log_score'] for p in official}
    assert a==pytest.approx(b,abs=1e-12)
    scores=[p['search_log_score'] for p in ours['programs']]
    assert scores==sorted(scores,reverse=True)
    assert ours['stop_reason']=='exhausted_bounds'

def test_toy_budget_and_ground_truth_free_search(kernel):
    kw=dict(grammar=grammar(),request=REQUEST,upper_bound=100,maximum_depth=10,max_size=7,max_states=20000,limit=200)
    task={'name':'trim','examples':[{'inputs':[[[0,0,0],[0,1,0],[0,0,0]]],'output':[[1]]}]}
    r=kernel.call('search_tasks',**kw,tasks=[task],top_k=3)
    assert r['enumerated_nodes']<=200 and r['expanded_states']<=20000
    assert r['tasks'][0]['solutions'] and r['tasks'][0]['first_solution_nodes']<=200
    e=kernel.call('enumerate_budget',**{**kw,'max_states':1})
    assert e['expanded_states']==1 and e['stop_reason']=='state_budget'

def test_conditional_objects_and_boundary_compositions(kernel):
    old=make_language()
    objs=Program('objects',(INPUT,));empty=Program('is_empty',(objs,))
    ps=[Program('if_grid',(empty,Program('border',(INPUT,)),Program('invert',(INPUT,)))),
        Program('crop',(Program('largest',(objs,)),)),
        Program('translate',(INPUT,Program('count',(objs,)),Program('one'))),
        Program('recolor',(INPUT,Program('zero'),Program('green')))]
    # zero is Int, not Color: the typed kernel must reject this last expression.
    with pytest.raises(ValueError):kernel.call('infer',grammar=grammar(),program=abstraction(ast(ps[-1])))
    for p in ps[:-1]:
        for x in [((0,0),(0,0)),((1,0,2),(0,0,0),(3,0,1)),((1,2),(0,3))]:
            assert kernel.call('evaluate',program=abstraction(ast(p)),inputs=[wire(x)])['value']==wire(old.evaluate(p,x))

def test_frozen_dataset_adapter_does_not_expose_labels():
    from faithful.python.toy import dataset,wire
    train,test,truth,probes,digest=dataset('calibration',7)
    assert len(train)==96 and len(test)==60 and len(truth)==60 and probes
    assert digest=='342bde58c0018fb3fe224284b3bedc37823f5acc24595a1b19918d7b2aa97cbc'
    assert all(set(vars(t))=={'name','examples','request'} for t in train+test)
    assert all(set(wire(t))=={'name','examples'} for t in train+test)
