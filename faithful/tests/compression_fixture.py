"""Arithmetic names used ONLY as tiny symbolic compression fixtures, not a domain port."""
import json
from pathlib import Path
from faithful.python.kernel import *

def fixture():
    i=base("int")
    g={"log_variable":0,"productions":[{"program":primitive(n),"type":t,"log_weight":0} for n,t in [("+",arrow(i,arrow(i,i))),("1",i),("2",i),("3",i)]]}
    ps=[abstraction(application(primitive("+"),application(primitive("+"),index(0),primitive("1")),primitive(c))) for c in ["1","2","3"]]
    fs=[{"request":arrow(i,i),"entries":[{"program":p,"log_likelihood":0}]} for p in ps]*3
    return g,fs
def source(p):
    if "primitive" in p:return p["primitive"]
    if "index" in p:return "$"+str(p["index"])
    if "application" in p:return "("+" ".join(map(source,p["application"]))+")"
    if "abstraction" in p:return "(lambda "+source(p["abstraction"])+")"
    return "#"+source(p["invented"])
def official_input(g,fs):
    return dict(DSL={"logVariable":g["log_variable"],"productions":[{"expression":source(p["program"]),"logProbability":p["log_weight"]} for p in g["productions"]]},frontiers=[{"request":f["request"],"programs":[{"program":source(e["program"]),"logLikelihood":e["log_likelihood"]} for e in f["entries"]]} for f in fs],arity=1,topK=5,topI=300,bs=1000000,CPUs=1,iterations=1,aic=1,pseudoCounts=1,structurePenalty=.001,inline=True,verbose=True)
if __name__=="__main__":
    out=ROOT/"faithful/results";out.mkdir(exist_ok=True)
    g,fs=fixture()
    (out/"compression_input.json").write_text(json.dumps(official_input(g,fs)),encoding="utf8")
    with Kernel() as k:
        r=k.call("compress",grammar=g,frontiers=fs,arity=1,iterations=1)
    (out/"compression_ours.json").write_text(json.dumps(r,indent=2),encoding="utf8")
    print(json.dumps(r["history"],indent=2))
