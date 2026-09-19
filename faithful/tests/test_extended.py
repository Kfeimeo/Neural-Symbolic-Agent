import json
import random
from pathlib import Path
import pytest
from faithful.python.kernel import *
from faithful.tests.test_golden import kernel,oracle,make_g,I

@pytest.mark.parametrize("seed",range(12))
def test_ancestral_sampling(kernel,oracle,seed):
    rng=random.Random(seed)
    kw=dict(grammar=make_g(),request=arrow(I,I),uniforms=[rng.random() for _ in range(512)])
    a=kernel.call("sample",**kw);b=oracle("sample",**kw)
    assert a["program"]==b["program"]
    assert a["log_probability"]==pytest.approx(b["log_probability"],abs=1e-12)

def test_grid_evaluation_binding_and_invention(kernel):
    from faithful.python.grid import grammar,REQUEST
    x=[[0,1,2],[3,2,1]]
    f=invented(abstraction(application(primitive("rotate90"),application(primitive("invert"),index(0)))))
    p=abstraction(application(f,index(0)))
    assert kernel.call("evaluate",program=p,inputs=[x])["value"]==[[1,0],[2,3],[3,2]]
    with pytest.raises(ValueError): kernel.call("sample",grammar=grammar(),request=REQUEST,uniforms=[])

def test_grid_domain_semantics_preserved(kernel):
    from dreamcoder.domains.grid import make_language
    from dreamcoder.language import Program,INPUT
    from faithful.python.grid import smoke_grammar as grammar
    original=make_language()
    x=[[0,1,2],[3,2,1]]
    for pr in grammar()["productions"]:
        name=pr["program"]["primitive"]
        expected=original.evaluate(Program(name,(INPUT,)),tuple(map(tuple,x)))
        actual=kernel.call("evaluate",program=abstraction(application(primitive(name),index(0))),inputs=[x])["value"]
        assert actual==list(map(list,expected))

def test_inverse_beta_soundness_and_multiple_parameters(kernel):
    g=make_g()
    p=abstraction(abstraction(application(primitive("choose"),primitive("truth"),application(primitive("succ"),index(0)),application(primitive("succ"),index(1)))))
    vs=kernel.call("versions",program=p,arity=1)["programs"]
    assert len(vs)>5
    expected=kernel.call("beta",program=p)["program"]
    for v in vs:
        assert kernel.call("beta",program=v)["program"]==expected
        assert kernel.call("infer",grammar=g,program=v)["type"]==kernel.call("infer",grammar=g,program=p)["type"]

def test_replay_distribution_and_gradient(kernel):
    import torch
    from faithful.tests.test_golden import frontiers
    from faithful.python.recognition import context_keys,frontier_kl,replay_sample
    f=frontiers()[0];g=make_g()
    scored=kernel.call("frontier",grammar=g,frontier=f)
    rng=random.Random(8);counts={json.dumps(e["program"],sort_keys=True):0 for e in scored["entries"]}
    for _ in range(10000): counts[json.dumps(replay_sample(scored,rng)["program"],sort_keys=True)]+=1
    for e in scored["entries"]: assert abs(counts[json.dumps(e["program"],sort_keys=True)]/10000-e["posterior"])<.02
    summaries=[kernel.call("score",grammar=g,request=f["request"],program=e["program"])["events"] for e in scored["entries"]]
    keys=context_keys(g); logits=torch.zeros((len(keys),7),dtype=torch.float64,requires_grad=True)
    loss=frontier_kl(logits,summaries,[e["posterior"] for e in scored["entries"]],keys)
    loss.backward()
    assert torch.isfinite(logits.grad).all() and logits.grad.abs().sum()>0

@pytest.mark.parametrize("name",["compression","hierarchy"])
def test_live_compression_artifact(kernel,oracle,name):
    from faithful.tests.compression_fixture import fixture
    out=ROOT/"faithful/results"
    if name=="compression":g,fs=fixture()
    else:
        from faithful.tests.hierarchy_probe import hierarchy_fixture
        g,fs=hierarchy_fixture(kernel)
    a=kernel.call("compress",grammar=g,frontiers=fs,arity=1,iterations=1)
    o=json.loads((out/f"{name}_official.json").read_text())
    b=oracle("decode_compression",grammar=g,official=o)
    assert a["frontiers"]==b["frontiers"]
    key=lambda p:json.dumps(p["program"],sort_keys=True)
    aa=sorted(a["grammar"]["productions"],key=key);bb=sorted(b["grammar"]["productions"],key=key)
    assert len(aa)==len(bb)>len(g["productions"])
    for p,q in zip(aa,bb):
        assert p["program"]==q["program"]
        assert p["type"]==q["type"]
        assert p["log_weight"]==pytest.approx(q["log_weight"],abs=1e-12)
    assert a["grammar"]["log_variable"]==pytest.approx(b["grammar"]["log_variable"],abs=1e-12)
    assert a["history"][0]["after"]>a["history"][0]["before"]
    # Objective is recomputed from the actual official outputs, not copied constants.
    z=sum(kernel.call("frontier",grammar=b["grammar"],frontier=f)["log_marginal"] for f in b["frontiers"])
    def size(p):
        if "application" in p:return sum(map(size,p["application"]))
        if "abstraction" in p:return size(p["abstraction"])
        return 1
    cost=sum(size(p["program"].get("invented",p["program"])) for p in bb)
    assert a["history"][0]["after"]==pytest.approx(z-len(bb)-.001*cost,abs=1e-12)

def test_compression_candidate_beta_space():
    from faithful.tests.candidate_probe import probe
    report=probe()
    assert all(d["beta_classes_equal"] for d in report.values())

def test_three_round_grid_loop():
    from faithful.python.ec import demo
    h=demo()
    assert len(h)==3 and all(r["solved"]==2 for r in h)
    assert all(r["recognition_losses"] for r in h)
    assert all(r["dream"]["draws"]==r["dream"]["accepted"]+r["dream"]["resource_or_evaluation_rejections"] for r in h)
