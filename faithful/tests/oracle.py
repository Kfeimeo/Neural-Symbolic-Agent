"""Run unmodified upstream modules in an isolated process (never our dreamcoder/).

Only bypass upstream __init__'s eager imports of unrelated legacy domains.
No probability, type, frontier or estimation function is patched.
"""
import sys
import types
from pathlib import Path
import json
import math

REFERENCE = Path(__file__).resolve().parents[1] / "reference/ec/dreamcoder"
package = types.ModuleType("dreamcoder")
package.__path__ = [str(REFERENCE)]
sys.modules["dreamcoder"] = package
from dreamcoder.type import TypeVariable, TypeConstructor, Context, UnificationFailure
from dreamcoder.program import Primitive, Index, Application, Abstraction, Invented
from dreamcoder.grammar import Grammar, ContextualGrammar
from dreamcoder.frontier import Frontier, FrontierEntry
from dreamcoder.task import Task

def tp(j):
    return TypeVariable(j["var"]) if "var" in j else TypeConstructor(j["constructor"], list(map(tp, j["arguments"])))
def tj(t):
    if isinstance(t, TypeVariable): return {"var": t.v}
    return {"constructor": t.name, "arguments": list(map(tj,t.arguments))}
def p(j):
    if "primitive" in j: return Primitive.GLOBALS[j["primitive"]]
    if "index" in j: return Index(j["index"])
    if "application" in j: return Application(*map(p,j["application"]))
    if "abstraction" in j: return Abstraction(p(j["abstraction"]))
    if "invented" in j: return Invented(p(j["invented"]))
    raise ValueError(j)
def pj(e):
    if isinstance(e, Primitive): return {"primitive":e.name}
    if isinstance(e, Index): return {"index":e.i}
    if isinstance(e, Application): return {"application":[pj(e.f),pj(e.x)]}
    if isinstance(e, Abstraction): return {"abstraction":pj(e.body)}
    if isinstance(e, Invented): return {"invented":pj(e.body)}
    raise ValueError(e)
def grammar(j):
    values={"zero":0,"succ":lambda x:x+1,"identity":lambda x:x,"truth":True,
            "choose":lambda c:lambda a:lambda b:a if c else b,
            "rotate90":lambda x:[list(r) for r in zip(*x[::-1])],
            "flipH":lambda x:[r[::-1] for r in x],"flipV":lambda x:x[::-1],
            "transpose":lambda x:[list(r) for r in zip(*x)],
            "invert":lambda x:[[0 if c==0 else 4-c for c in r] for r in x]}
    for pr in j["productions"]:
        if "primitive" in pr["program"]:
            name=pr["program"]["primitive"]
            Primitive(name,tp(pr["type"]),values.get(name))
    ps=[(pr["log_weight"],tp(pr["type"]),p(pr["program"])) for pr in j["productions"]]
    g=Grammar(j["log_variable"],ps)
    if j.get("contexts"):
        def at(key):
            ws=j["contexts"].get(key,[g.logVariable]+[w for w,_,_ in ps])
            return Grammar(ws[0],[(w,t,e) for w,(_,t,e) in zip(ws[1:],ps)])
        return ContextualGrammar(at("root"),at("variable"),{e:[at(f"{i}:{a}") for a in range(len(t.functionArguments()))] for i,(_,t,e) in enumerate(ps,1)})
    return g
def fj(j,g):
    task=Task("golden",tp(j["request"]),[])
    return Frontier([FrontierEntry(p(e["program"]),logPrior=0,logLikelihood=e["log_likelihood"]) for e in j["entries"]],task)
def run(j):
    op=j["operation"]
    if op=="unify":
        a,b=tp(j["left"]),tp(j["right"])
        return {"type":tj(a.apply(Context(1000,[]).unify(a,b)).canonical())}
    g=grammar(j["grammar"])
    if op=="task_frontier":
        req=tp(j["request"]);sg=grammar(j.get("search_grammar",j["grammar"]))
        task=Task("fixed-io",req,[(tuple(xs),y) for xs,y in j["examples"]])
        entries=[]
        for l,_,e in sg.enumeration(Context(1000,[]),[],req,j["upper_bound"],maximumDepth=j["maximum_depth"]):
            # Official interpreter + Task.predict. Task.check's POSIX signal
            # wrapper is unavailable on Windows; no solver math is substituted.
            try: valid=all(task.predict(e.evaluate([]),xs)==y for xs,y in task.examples)
            except Exception: valid=False
            if valid: entries.append(FrontierEntry(e,logPrior=g.logLikelihood(req,e),logLikelihood=0))
        f=Frontier(entries,task).topK(j["top_k"])
        return {"log_marginal":f.marginalLikelihood(),"entries":[{"program":pj(e.program),"log_prior":e.logPrior,"log_posterior":e.logPosterior} for e in f.normalize()]}
    if op=="parse_programs":
        from dreamcoder.program import Program
        return {"programs":[pj(Program.parse(s)) for s in j["programs"]]}
    if op=="decode_compression":
        from dreamcoder.program import Program
        o=j["official"]
        productions=[]
        for pr in o["DSL"]["productions"]:
            e=Program.parse(pr["expression"])
            productions.append({"program":pj(e),"type":tj(e.infer().canonical()),"log_weight":pr["logProbability"]})
        fs=[{"request":f["request"],"entries":[{"program":pj(Program.parse(e["program"])),"log_likelihood":e["logLikelihood"]} for e in f["programs"]]} for f in o["frontiers"]]
        return {"grammar":{"log_variable":o["DSL"]["logVariable"],"productions":productions},"frontiers":fs}
    if op=="sample":
        import random
        uniforms=iter(j["uniforms"])
        random.random=lambda:next(uniforms)
        _,e=g._sample(tp(j["request"]),Context(1000,[]),[],maximumDepth=10000)
        return {"program":pj(e),"log_probability":g.logLikelihood(tp(j["request"]),e)}
    if op=="recognition_loss":
        import torch
        from dreamcoder.recognition import RecognitionModel
        gs=[g.noParent,g.variableParent]+[x for xs in g.library.values() for x in xs] if isinstance(g,ContextualGrammar) else [g]
        for sub in gs:
            sub.logVariable=torch.tensor([sub.logVariable],dtype=torch.float64,requires_grad=True)
            sub.productions=[(torch.tensor([w],dtype=torch.float64,requires_grad=True),t,e) for w,t,e in sub.productions]
            sub.expression2likelihood={e:w for w,t,e in sub.productions}
            sub.expression2likelihood[Index(0)]=sub.logVariable
        f=fj(j["frontier"],g)
        f=Frontier([FrontierEntry(g.closedLikelihoodSummary(f.task.request,e.program),logPrior=0,logLikelihood=e.logLikelihood) for e in f],f.task)
        class Harness:
            featureExtractor=types.SimpleNamespace(featuresOfTask=lambda t:torch.zeros(1))
            def auxiliaryLoss(self,*args): return None
            def __call__(self,features): return g
        loss,_=RecognitionModel.frontierBiasOptimal(Harness(),f,vectorized=False)
        return {"loss":float(loss.detach())}
    if op=="infer": return {"type":tj(p(j["program"]).infer().canonical()),"program":j["program"]}
    if op=="beta": return {"program":pj(p(j["program"]).betaNormalForm())}
    if op=="score":
        req=tp(j["request"]); env=list(map(tp,j.get("environment",[])))
        if isinstance(g,ContextualGrammar): s=g.likelihoodSummary(None,None,Context(1000,[]),env,req,p(j["program"]))[1]
        else: s=g.likelihoodSummary(Context(1000,[]),env,req,p(j["program"]))[1]
        return {"log_probability":s.logLikelihood(g)}
    if op=="enumerate":
        sg=grammar(j.get("search_grammar",j["grammar"]))
        req=tp(j["request"])
        xs=list(sg.enumeration(Context(1000,[]),list(map(tp,j.get("environment",[]))),req,j.get("upper_bound",8),maximumDepth=j.get("maximum_depth",12)))
        xs.sort(key=lambda x:-x[0])
        return {"programs":[{"program":pj(e),"type":tj(req),"search_log_score":l,"log_prior":g.logLikelihood(req,e)} for l,_,e in xs[:j.get("limit",100)]]}
    if op=="frontier":
        f=g.rescoreFrontier(fj(j["frontier"],g)); z=f.marginalLikelihood()
        return {"log_marginal":z,"entries":[{"program":pj(e.program),"log_prior":e.logPrior,"log_likelihood":e.logLikelihood,"log_posterior":e.logPosterior,"posterior":math.exp(e.logPosterior)} for e in f.normalize()]}
    if op=="update":
        u=g.insideOutside([fj(f,g) for f in j["frontiers"]],j.get("pseudo_counts",1),iterations=j.get("iterations",1))
        return {"log_variable":u.logVariable,"productions":[{"program":pj(e),"type":tj(t),"log_weight":w} for w,t,e in u.productions],"contexts":{}}
    raise ValueError(op)
if __name__=="__main__":
    for line in sys.stdin:
        try: out={"ok":True,"result":run(json.loads(line))}
        except Exception as exc: out={"ok":False,"error":type(exc).__name__+": "+str(exc)}
        print(json.dumps(out),flush=True)
