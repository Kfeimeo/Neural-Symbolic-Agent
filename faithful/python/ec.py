"""Persistent multi-round Explore–Compress driver. Uses no reference code."""
import copy
import json
import random
from pathlib import Path
import torch
from .kernel import Kernel,ROOT,build
from .grid import Task,grammar,smoke_grammar,features
from .recognition import Recognition

def wake(kernel,task,g,sg,bound=6,depth=7,limit=1000,top_k=5):
    candidates=kernel.call("enumerate",grammar=g,search_grammar=sg,request=task.request,
                           upper_bound=bound,maximum_depth=depth,limit=limit)["programs"]
    entries=[]
    for e in candidates:
        try: valid=all(kernel.call("evaluate",program=e["program"],inputs=xs)["value"]==y for xs,y in task.examples)
        except ValueError: valid=False
        if valid: entries.append({"program":e["program"],"log_likelihood":0.,"search_log_score":e["search_log_score"],"log_prior":e["log_prior"]})
    entries.sort(key=lambda e:e["log_prior"],reverse=True)
    return {"request":task.request,"entries":entries[:top_k]}

def dream(kernel,g,request,inputs,rng,draws=20,fuel=128):
    data=[];rejected=0
    for n in range(draws):
        try:
            sample=kernel.call("sample",grammar=g,request=request,uniforms=[rng.random() for _ in range(fuel)])
            p=sample["program"]
            examples=[([x],kernel.call("evaluate",program=p,inputs=[x])["value"]) for x in inputs]
        except ValueError:
            rejected+=1;continue
        task=Task(f"dream-{n}",examples,request)
        data.append((features(task),{"request":request,"entries":[{"program":p,"log_likelihood":0.}]}))
    return data,{"draws":draws,"accepted":len(data),"resource_or_evaluation_rejections":rejected}

def explore_compress(tasks,rounds=3,seed=7,output=None,search_bound=6,compression_arity=1,base_grammar=None):
    rng=random.Random(seed);torch.manual_seed(seed)
    g=copy.deepcopy(base_grammar) if base_grammar is not None else grammar();model=None;history=[];persistent=[{"request":t.request,"entries":[]} for t in tasks]
    with Kernel() as kernel:
        for r in range(rounds):
            for i,t in enumerate(tasks):
                found=wake(kernel,t,g,model.search_grammar(features(t)) if model else g,bound=search_bound)
                unique={json.dumps(e["program"],sort_keys=True):e for e in persistent[i]["entries"]+found["entries"]}
                scored=[]
                for e in unique.values():
                    e=copy.deepcopy(e);e["log_prior"]=kernel.call("score",grammar=g,request=t.request,program=e["program"])["log_probability"];scored.append(e)
                persistent[i]={"request":t.request,"entries":sorted(scored,key=lambda e:e["log_prior"],reverse=True)[:5]}
            solved=[f for f in persistent if f["entries"]]
            compression=kernel.call("compress",grammar=g,frontiers=solved,arity=compression_arity,iterations=3) if solved else {"grammar":g,"frontiers":[],"history":[]}
            g=compression["grammar"]
            it=iter(compression["frontiers"])
            persistent=[next(it) if f["entries"] else f for f in persistent]
            dreamed,stats=dream(kernel,g,tasks[0].request,[e[0][0] for e in tasks[0].examples],rng)
            model=Recognition(g)
            replay=[(features(t),f) for t,f in zip(tasks,persistent) if f["entries"]]
            losses=model.fit_frontiers(kernel,replay+dreamed,steps=30,seed=seed+r)
            record={"round":r,"grammar":g,"frontiers":copy.deepcopy(persistent),"compression":compression["history"],"dream":stats,"recognition_losses":losses,"solved":len(solved)}
            history.append(record)
            if output:
                output=Path(output);output.mkdir(parents=True,exist_ok=True)
                (output/"history.json").write_text(json.dumps(history,indent=2),encoding="utf8")
                torch.save({"state":model.state_dict(),"grammar":g},output/f"recognition_{r}.pt")
    return history

def demo():
    # Only I/O examples enter the driver. No held-out benchmark selection.
    xs=[[[0,1,2],[2,3,0]],[[1,0],[3,2],[0,3]]]
    tasks=[Task("color-complement",[([x],[[0 if c==0 else 4-c for c in row] for row in x]) for x in xs]),
           Task("horizontal-reflection",[([x],[list(reversed(row)) for row in x]) for x in xs])]
    return explore_compress(tasks,rounds=3,output=ROOT/"faithful/results/ec",search_bound=4.5,compression_arity=0,base_grammar=smoke_grammar())

if __name__=="__main__":
    build(); h=demo();print(json.dumps({"rounds":len(h),"solved":[r["solved"] for r in h]}))
