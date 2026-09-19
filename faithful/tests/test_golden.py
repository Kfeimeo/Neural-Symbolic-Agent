import json
import math
from pathlib import Path
import subprocess
import sys
import os
import pytest
from faithful.python.kernel import *

I,B=base("int"),base("bool")
V=variable(0)
def make_g():
    specs=[("zero",I,-.4),("succ",arrow(I,I),-.8),("truth",B,-.2),
           ("choose",arrow(B,arrow(V,arrow(V,V))),-1.7),
           ("identity",arrow(V,V),-1.3)]
    g={"log_variable":-.3,"productions":[{"program":primitive(n),"type":t,"log_weight":w} for n,t,w in specs]}
    body=abstraction(application(primitive("succ"),application(primitive("succ"),index(0))))
    g["productions"].append({"program":invented(body),"type":arrow(I,I),"log_weight":-1.1})
    return g

@pytest.fixture(scope="module")
def kernel():
    build()
    with Kernel() as k: yield k

@pytest.fixture(scope="module")
def oracle():
    def call(op,**kw):
        result=subprocess.run([sys.executable,str(Path(__file__).with_name("oracle.py"))],input=json.dumps(dict(operation=op,**kw))+"\n",capture_output=True,text=True,check=True)
        line=result.stdout
        assert line, "Official oracle exited"
        r=json.loads(line)
        if os.environ.get("FAITHFUL_TRACE"):
            with open(os.environ["FAITHFUL_TRACE"],"a",encoding="utf8") as f:
                f.write(json.dumps({"implementation":"official","request":dict(operation=op,**kw),"response":r})+"\n")
        if not r["ok"]: raise ValueError(r["error"])
        return r["result"]
    yield call

@pytest.mark.parametrize("a,b",[(V,V),(variable(1),V),(arrow(V,variable(1)),arrow(V,variable(1))),(I,I),(V,I),(arrow(V,V),arrow(I,I)),(arrow(V,variable(1)),arrow(B,I)),(I,B),(V,arrow(V,I)),(arrow(V,V),arrow(I,B))])
def test_type_unification(kernel,oracle,a,b):
    try: official=oracle("unify",left=a,right=b)
    except ValueError as exc:
        assert str(exc).startswith(("UnificationFailure:","Occurs:")), str(exc)
        with pytest.raises(ValueError): kernel.call("unify",left=a,right=b)
    else: assert kernel.call("unify",left=a,right=b)==official

def cases():
    g=make_g(); inv=g["productions"][-1]["program"]
    return [(I,[],primitive("zero")),(I,[],application(primitive("succ"),primitive("zero"))),
            (arrow(I,I),[],abstraction(index(0))),
            (arrow(I,arrow(I,I)),[],abstraction(abstraction(index(1)))),
            (I,[I,I,B],index(1)),(B,[I,I,B],index(2)),
            (I,[],application(primitive("choose"),primitive("truth"),primitive("zero"),application(inv,primitive("zero")))),
            (arrow(I,I),[],abstraction(application(inv,index(0)))),
            (arrow(arrow(I,I),arrow(I,I)),[],abstraction(abstraction(application(index(1),index(0)))))]

@pytest.mark.parametrize("req,env,p",cases())
def test_probabilities(kernel,oracle,req,env,p):
    kw=dict(grammar=make_g(),request=req,environment=env,program=p)
    assert kernel.call("score",**kw)["log_probability"]==pytest.approx(oracle("score",**kw)["log_probability"],abs=1e-12)

@pytest.mark.parametrize("req,env,p",[x for x in cases() if not x[1]])
def test_inference_roundtrip(kernel,oracle,req,env,p):
    kw=dict(grammar=make_g(),program=p)
    assert kernel.call("infer",**kw)==oracle("infer",**kw)

@pytest.mark.parametrize("req",[I,arrow(I,I),arrow(I,arrow(I,I)),arrow(arrow(I,I),arrow(I,I))])
def test_enumeration(kernel,oracle,req):
    kw=dict(grammar=make_g(),request=req,upper_bound=6.0,maximum_depth=7,limit=100000)
    a=kernel.call("enumerate",**kw)["programs"];b=oracle("enumerate",**kw)["programs"]
    key=lambda e:json.dumps(e["program"],sort_keys=True)
    assert len(a)>0
    assert {key(e) for e in a}=={key(e) for e in b}
    bm={key(e):e for e in b}
    assert [e["search_log_score"] for e in a]==pytest.approx(sorted([e["search_log_score"] for e in a],reverse=True))
    for e in a:
        assert e["type"]==bm[key(e)]["type"]
        assert e["search_log_score"]==pytest.approx(bm[key(e)]["search_log_score"],abs=1e-12)
        assert e["log_prior"]==pytest.approx(bm[key(e)]["log_prior"],abs=1e-12)

def frontiers():
    g=make_g(); inv=g["productions"][-1]["program"]
    req=arrow(I,I)
    ps=[abstraction(index(0)),abstraction(application(primitive("identity"),index(0))),
        abstraction(application(inv,index(0))),abstraction(application(primitive("succ"),application(primitive("succ"),index(0))))]
    return [{"request":req,"entries":[{"program":p,"log_likelihood":ll} for p,ll in zip(ps,[0,-.7,0,0])]},
            {"request":I,"entries":[{"program":primitive("zero"),"log_likelihood":0},{"program":application(primitive("identity"),primitive("zero")),"log_likelihood":-1.2}]}]

def test_frontier(kernel,oracle):
    kw=dict(grammar=make_g(),frontier=frontiers()[0])
    a=kernel.call("frontier",**kw);b=oracle("frontier",**kw)
    assert a["log_marginal"]==pytest.approx(b["log_marginal"],abs=1e-12)
    key=lambda e:json.dumps(e["program"],sort_keys=True)
    for e,f in zip(sorted(a["entries"],key=key),sorted(b["entries"],key=key)):
        for k in ("log_prior","log_likelihood","log_posterior","posterior"): assert e[k]==pytest.approx(f[k],abs=1e-12)

@pytest.mark.parametrize("iterations,pc",[(1,1),(1,.25)])
def test_update(kernel,oracle,iterations,pc):
    kw=dict(grammar=make_g(),frontiers=frontiers(),iterations=iterations,pseudo_counts=pc)
    a=kernel.call("update",**kw);b=oracle("update",**kw)
    assert a["log_variable"]==pytest.approx(b["log_variable"],abs=1e-12)
    for p,q in zip(a["productions"],b["productions"]):
        assert p["program"]==q["program"]
        assert p["log_weight"]==pytest.approx(q["log_weight"],abs=1e-12)

def test_repeated_update_with_fresh_reference_statistics(kernel,oracle):
    g=make_g()
    for _ in range(3):
        g=oracle("update",grammar=g,frontiers=frontiers(),iterations=1,pseudo_counts=1)
    a=kernel.call("update",grammar=make_g(),frontiers=frontiers(),iterations=3,pseudo_counts=1)
    assert a["log_variable"]==pytest.approx(g["log_variable"],abs=1e-12)
    for p,q in zip(a["productions"],g["productions"]):
        assert p["log_weight"]==pytest.approx(q["log_weight"],abs=1e-12)

def test_contextual_and_generative_separation(kernel,oracle):
    g=make_g(); sg=make_g()
    sg["contexts"]={"root":[-.4,.5,-2,-.2,-3,-2,-1],"2:0":[-.7,-1,.8,-.9,-2,-3,.4],"variable":[.2,-2,-.4,-.6,-1,-1,-2]}
    for req,env,p in cases():
        kw=dict(grammar=sg,request=req,environment=env,program=p)
        assert kernel.call("score",**kw)["log_probability"]==pytest.approx(oracle("score",**kw)["log_probability"],abs=1e-12)
    kw=dict(grammar=g,search_grammar=sg,request=arrow(I,I),upper_bound=5,maximum_depth=6,limit=100000)
    a=kernel.call("enumerate",**kw)["programs"];b=oracle("enumerate",**kw)["programs"]
    key=lambda e:json.dumps(e["program"],sort_keys=True)
    assert {key(e) for e in a}=={key(e) for e in b}
    assert any(abs(e["log_prior"]-e["search_log_score"])>.1 for e in a)
    for x,y in zip(sorted(a,key=key),sorted(b,key=key)):
        assert x["log_prior"]==pytest.approx(y["log_prior"],abs=1e-12)
        assert x["search_log_score"]==pytest.approx(y["search_log_score"],abs=1e-12)

def test_beta_capture(kernel,oracle):
    p=abstraction(application(abstraction(abstraction(index(1))),index(0)))
    kw=dict(grammar=make_g(),program=p)
    assert kernel.call("beta",**kw)==oracle("beta",**kw)

def test_recognition_loss(kernel,oracle):
    import torch
    from faithful.python.recognition import context_keys,frontier_bias_optimal
    g=make_g(); keys=context_keys(g)
    logits=torch.arange(len(keys)*7,dtype=torch.float64).reshape(len(keys),7)*.017-.4
    g["contexts"]=dict(zip(keys,logits.tolist()))
    f=frontiers()[0]
    summaries=[kernel.call("score",grammar=g,request=f["request"],program=e["program"])["events"] for e in f["entries"]]
    value=frontier_bias_optimal(logits,summaries,[e["log_likelihood"] for e in f["entries"]],keys)
    assert float(value)==pytest.approx(oracle("recognition_loss",grammar=g,frontier=f)["loss"],abs=1e-12)

def test_fixed_io_wake_frontier(kernel,oracle):
    from faithful.python.ec import wake
    from faithful.python.grid import Task,smoke_grammar as grammar,REQUEST
    g=grammar();sg=grammar();sg["log_variable"]=-.8
    sg["productions"][0]["log_weight"]=-1.7
    examples=[([[[0,1,2],[3,1,0]]],[[2,1,0],[0,1,3]])]
    task=Task("golden-io",examples)
    f=wake(kernel,task,g,sg,bound=7,depth=7,limit=100000,top_k=100000)
    a=kernel.call("frontier",grammar=g,frontier=f)
    b=oracle("task_frontier",grammar=g,search_grammar=sg,request=REQUEST,examples=examples,upper_bound=7,maximum_depth=7,top_k=100000)
    key=lambda e:json.dumps(e["program"],sort_keys=True)
    assert len(a["entries"])>1
    assert {key(e) for e in a["entries"]}=={key(e) for e in b["entries"]}
    assert a["log_marginal"]==pytest.approx(b["log_marginal"],abs=1e-12)
    for x,y in zip(sorted(a["entries"],key=key),sorted(b["entries"],key=key)):
        assert x["log_prior"]==pytest.approx(y["log_prior"],abs=1e-12)
        assert x["log_posterior"]==pytest.approx(y["log_posterior"],abs=1e-12)
