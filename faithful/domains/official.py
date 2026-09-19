"""Official tutorial/list task semantics with deterministic I/O-only boundaries."""
import copy
import json
import random
import subprocess
import types
import torch
from ..python.kernel import ROOT, Kernel, base, arrow, variable, primitive
from ..python.grid import Task
from ..python import ec
from ..python.toy import save
from ..compression.interface import accounting

INT=base('int')
def lst(t): return {'constructor':'list','arguments':[t]}
def grammar(specs):
    return {'log_variable':0.,'productions':[dict(program=primitive(n),type=t,log_weight=0.) for n,t in specs]}

class DomainKernel(Kernel):
    def __init__(self):
        self.process=subprocess.Popen([str(ROOT/'faithful/build/official_domain.exe')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,encoding='utf8')

def build():
    folder=ROOT/'faithful/build/domain';folder.mkdir(parents=True,exist_ok=True)
    subprocess.run(['ghc','-O1','-i'+str(ROOT/'faithful/haskell'),'-i'+str(ROOT/'faithful/compression'),
        '-outputdir',str(folder),'-main-is','DomainMain.main',str(ROOT/'faithful/domains/DomainMain.hs'),
        '-o',str(ROOT/'faithful/build/official_domain.exe')],check=True)

def features(task):
    # Domain encoder only: same 40-dimensional recognition network and loss.
    vectors=[]
    for xs,y in task.examples:
        row=[]
        for value in [xs[0],y]:
            v=value if isinstance(value,list) else [value]
            row += [len(v)/10, sum(v)/max(1,len(v))/10]+[float(x)/10 for x in v[:18]]+[0.]*(18-len(v[:18]))
        vectors.append(row)
    return torch.tensor(vectors,dtype=torch.float32).mean(0)

def dataset(domain):
    if domain=='arithmetic':
        request=arrow(INT,INT)
        g=grammar([(n,request) for n in ['incr','incr2']])
        ts=[Task('add'+str(n),[([x],x+n) for x in [-7,-1,0,2,9]],request) for n in range(1,5)]
        return g,ts[:3],ts[3:]
    a,b=variable(0),variable(1)
    request=arrow(lst(INT),lst(INT))
    g=grammar([('map',arrow(arrow(a,b),arrow(lst(a),lst(b)))),('+',arrow(INT,arrow(INT,INT))),
        ('-',arrow(INT,arrow(INT,INT))),('0',INT),('1',INT)])
    xs=[[],[-2,0,3],[1],[5,-3,2,0],[2,2,-1]]
    funcs=[('map double',lambda n:n*2),('map increment',lambda n:n+1),('map negation',lambda n:-n),
        ('map quadruple',lambda n:n*4),('map add 3',lambda n:n+3)]
    ts=[Task(n,[([x],[f(y) for y in x]) for x in xs],request) for n,f in funcs]
    return g,ts[:3],ts[3:]

def run(domain,output):
    g,train,test=dataset(domain); traces=[]
    def wake(k,t,g,sg,**ignored):
        r=k.call('enumerate_budget',grammar=g,search_grammar=sg,request=t.request,upper_bound=100,
            maximum_depth=14,max_size=33,limit=3000,max_states=500000)
        entries=[];first=None
        for rank,e in enumerate(r['programs'],1):
            ys=k.call('evaluate_batch',program=e['program'],input_sets=[xs for xs,y in t.examples])['values']
            if ys==[y for xs,y in t.examples]:
                if first is None:first=rank
                entries.append(dict(program=e['program'],log_likelihood=0.,log_prior=e['log_prior']))
        entries.sort(key=lambda e:e['log_prior'],reverse=True)
        traces.append(dict(task=t.name,first_solution_nodes=first,enumerated_nodes=len(r['programs']),expanded_states=r['expanded_states'],stop_reason=r['stop_reason'],frontier_size=min(5,len(entries))))
        return dict(request=t.request,entries=entries[:5])
    # Bind domain-specific evaluator and encoder into the EXACT existing EC code.
    globals_=dict(ec.__dict__,features=features,Kernel=DomainKernel,wake=wake)
    globals_['dream']=types.FunctionType(ec.dream.__code__,globals_,argdefs=ec.dream.__defaults__)
    driver=types.FunctionType(ec.explore_compress.__code__,globals_,argdefs=ec.explore_compress.__defaults__)
    history=driver(train,rounds=3,seed=11,output=output,base_grammar=g)
    from ..python.recognition import Recognition
    last=history[-1];model=Recognition(last['grammar'])
    model.load_state_dict(torch.load(output/'recognition_2.pt',map_location=model.device,weights_only=True)['state'])
    held=[]
    with DomainKernel() as k:
        for t in test:
            for label,sg in [('generative',last['grammar']),('recognition',model.search_grammar(features(t)))]:
                f=wake(k,t,last['grammar'],sg)
                held.append(dict(label=label,frontier=f,**traces[-1]))
        for record in history:
            record['mdl']=accounting(k,record['grammar'],record['frontiers'])
    summary=dict(domain=domain,source='ellisk42/ec',training_names=[t.name for t in train],heldout=held,history=history,traces=traces,
        recipe='Unmodified ec.explore_compress code, 3 rounds, 20 Dream draws, 30 recognition steps; domain evaluator/encoder/wake boundary supplied',
        examples='Deterministic compact examples; official task functions, not original random draws',device=str(model.device))
    save(output/'validation.json',summary)
    return summary

if __name__=='__main__':
    torch.set_num_threads(1);build()
    for d in ['arithmetic','list']:
        r=run(d,ROOT/'results/stitch/domains'/d)
        print(d,[x['solved'] for x in r['history']],[(x['task'],x['label'],x['first_solution_nodes']) for x in r['heldout']],flush=True)
