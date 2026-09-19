import json
from .compression_fixture import fixture,official_input
from faithful.python.kernel import *

def hierarchy_fixture(k):
    g,fs=fixture()
    first=k.call("compress",grammar=g,frontiers=fs,arity=1,iterations=1)
    g=first["grammar"];inv=g["productions"][-1]["program"]
    # Two explicit bound parameters, internal expression parameterization,
    # and a previously learned production, entirely within fidelity fixtures.
    ps=[abstraction(abstraction(application(inv,application(inv,index(1),index(0)),primitive(c)))) for c in ["1","2","3"]]
    fs=[{"request":arrow(base("int"),arrow(base("int"),base("int"))),"entries":[{"program":p,"log_likelihood":0}]} for p in ps]*3
    return g,fs
if __name__=="__main__":
    out=ROOT/"faithful/results"
    with Kernel() as k:
        g,fs=hierarchy_fixture(k)
        r=k.call("compress",grammar=g,frontiers=fs,arity=1,iterations=1)
    j=official_input(g,fs);j["inline"]=True
    (out/"hierarchy_input.json").write_text(json.dumps(j),encoding="utf8")
    (out/"hierarchy_fixture.json").write_text(json.dumps({"grammar":g,"frontiers":fs}),encoding="utf8")
    (out/"hierarchy_ours.json").write_text(json.dumps(r,indent=2),encoding="utf8")
    print(json.dumps(r["history"]))
