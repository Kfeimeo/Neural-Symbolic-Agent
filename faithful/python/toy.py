"""Full-DSL toy A/B/C/D experiment; only dataset generation uses the old package."""
import argparse
import copy
import hashlib
import json
import random
import statistics
import time
from pathlib import Path
import torch
from .kernel import Kernel,ROOT,build,abstraction,application,primitive,index
from .grid import grammar,Task,features,REQUEST
from .recognition import Recognition

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf8')
def wire(task):
    return {'name':task.name,'examples':[{'inputs':xs,'output':y} for xs,y in task.examples]}
def decode_gt(p):
    return index(0) if p['name']=='$input' else application(primitive(p['name']),*[decode_gt(x) for x in p['arguments']])
def encode_old(p):return {'name':p.name,'arguments':[encode_old(c) for c in p.arguments]}
def dataset(which,seed):
    if which=='calibration':
        path=ROOT/'results/calibration/benchmark_private.json'
        source=json.loads(path.read_text(encoding='utf8'))
        train=[Task(t['name'],[([e['input']],e['output']) for e in t['examples']]) for t in source['training']]
        test=[Task(t['name'],[([e['input']],e['output']) for e in t['examples']]) for t in source['testing']]
        truth={t['name']:abstraction(decode_gt(t['ground_truth'])) for t in source['testing']}
        return train,test,truth,source['evaluation_probes'],hashlib.sha256(path.read_bytes()).hexdigest()
    from dreamcoder.domains.grid import make_language,synthetic_tasks,sample_grid
    language=make_language()
    old_train=synthetic_tasks(language,random.Random(seed),36,'train')
    old_test=synthetic_tasks(language,random.Random(seed+1),24,'heldout')
    def convert(ts):return [Task(t.name,[([e.input],e.output) for e in t.examples]) for t in ts]
    truth={t.name:abstraction(decode_gt(encode_old(t.ground_truth))) for t in old_test}
    return convert(old_train),convert(old_test),truth,[sample_grid(random.Random(seed+1000+i)) for i in range(20)],None

def search(k,tasks,g,sg,options):
    start=time.perf_counter()
    r=k.call('search_tasks',grammar=g,search_grammar=sg,request=REQUEST,tasks=[wire(t) for t in tasks],**options)
    elapsed=time.perf_counter()-start
    for row in r['tasks']:
        row.update(enumerated_nodes=r['enumerated_nodes'],expanded_states=r['expanded_states'],stop_reason=r['stop_reason'])
    return r['tasks'],elapsed
def learning_frontier(row):return {'request':REQUEST,'entries':[{'program':e['program'],'log_likelihood':e['log_likelihood']} for e in row['solutions']]}

def train(k,train_tasks,args,output):
    from dreamcoder.domains.grid import sample_grid
    base=grammar()
    options=dict(limit=args.max_nodes,max_states=args.max_states,max_size=args.max_size,maximum_depth=args.maximum_depth,upper_bound=100,top_k=args.top_k)
    print('Wake: 24-production grammar on training I/O',flush=True)
    initial,wake_seconds=search(k,train_tasks,base,base,options)
    save(output/'training_wake.json',{'tasks':initial,'seconds':wake_seconds})
    fs=[learning_frontier(r) for r in initial if r['solutions']]
    print(f'Compression: {len(fs)}/{len(train_tasks)} solved training frontiers',flush=True)
    start=time.perf_counter()
    compressed=k.call('compress',grammar=base,frontiers=fs,arity=args.compression_arity,iterations=args.compression_iterations)
    compressed['seconds']=time.perf_counter()-start
    save(output/'compression.json',compressed)
    learned=compressed['grammar']
    print(f"Library: {len(base['productions'])} -> {len(learned['productions'])}",flush=True)
    rewritten=iter(compressed['frontiers']); data=[]
    for task,row in zip(train_tasks,initial):
        if row['solutions']: data.append((features(task),next(rewritten)))
    replay_count=len(data);rng=random.Random(args.seed+100);rejected=0;dream_records=[]
    print(f'Dream: {args.dreams} ancestral draws',flush=True)
    for i in range(args.dreams):
        try:
            sampled=k.call('sample',grammar=learned,request=REQUEST,uniforms=[rng.random() for _ in range(args.dream_fuel)])
            xs=[sample_grid(rng) for _ in range(4)]
            ys=k.call('evaluate_batch',program=sampled['program'],input_sets=[[x] for x in xs])['values']
            if any(y is None for y in ys):raise ValueError('Failed domain evaluation')
        except ValueError:rejected+=1;continue
        task=Task(f'dream-{i}',[([x],y) for x,y in zip(xs,ys)])
        f={'request':REQUEST,'entries':[{'program':sampled['program'],'log_likelihood':0.}]}
        data.append((features(task),f));dream_records.append({'task':wire(task),'frontier':f})
    save(output/'dreams.json',{'draws':args.dreams,'accepted':len(dream_records),'rejected':rejected,'records':dream_records})
    expanded=[]
    for x,f in data:
        expanded.append((x,{'request':f['request'],'entries':[{'program':k.call('beta',program=e['program'])['program'],'log_likelihood':e['log_likelihood']} for e in f['entries']]}))
    models=[];losses={}
    for label,g,pairs in [('C',base,expanded),('D',learned,data)]:
        print(f'Recognition {label}: {len(pairs)} frontiers, {args.steps} steps',flush=True)
        torch.manual_seed(args.seed);model=Recognition(g)
        history=model.fit_frontiers(k,pairs,steps=args.steps,seed=args.seed)
        models.append(model);losses[label]=history
        torch.save({'grammar':g,'state_dict':model.state_dict()},output/f'model_{label}.pt')
    save(output/'recognition_losses.json',losses)
    return base,learned,models,fs,{'solved_training_tasks':len(fs),'training_tasks':len(train_tasks),'replay_frontiers':replay_count,'dreams_accepted':len(dream_records),'dreams_rejected':rejected,'compression':compressed,'wake_seconds':wake_seconds}

def metrics(k,rows,g,truth,probes):
    first=[r['first_solution_nodes'] for r in rows if r['first_solution_nodes'] is not None]
    exact=behavior=0;cache={}
    def outputs(p):
        key=json.dumps(p,sort_keys=True)
        if key not in cache:cache[key]=k.call('evaluate_batch',program=p,input_sets=[[x] for x in probes])['values']
        return cache[key]
    for row in rows:
        target=truth[row['name']]
        exact+=any(k.call('beta',program=e['program'])['program']==target for e in row['solutions'])
        behavior+=any(outputs(e['program'])==outputs(target) for e in row['solutions'])
    return {'task_count':len(rows),'solved':sum(bool(r['solutions']) for r in rows),'solve_rate':sum(bool(r['solutions']) for r in rows)/len(rows),
            'mean_first_solution_nodes':statistics.mean(first) if first else None,'first_solution_sample_count':len(first),
            'mean_censored_first_solution_nodes':statistics.mean(r['first_solution_nodes'] or r['enumerated_nodes'] for r in rows),
            'mean_enumerated_nodes':statistics.mean(r['enumerated_nodes'] for r in rows),'mean_expanded_states':statistics.mean(r['expanded_states'] for r in rows),
            'expanded_ast_recovery_rate':exact/len(rows),'probe_behavioral_recovery_rate':behavior/len(rows)}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--benchmark',choices=['original','calibration'],default='original')
    parser.add_argument('--seed',type=int,default=7)
    parser.add_argument('--dreams',type=int,default=600)
    parser.add_argument('--dream-fuel',type=int,default=128)
    parser.add_argument('--steps',type=int,default=1000)
    parser.add_argument('--max-nodes',type=int,default=1500)
    parser.add_argument('--max-states',type=int,default=60000)
    parser.add_argument('--max-size',type=int,default=7)
    parser.add_argument('--maximum-depth',type=int,default=10)
    parser.add_argument('--top-k',type=int,default=3)
    parser.add_argument('--compression-arity',type=int,default=1)
    parser.add_argument('--compression-iterations',type=int,default=3)
    parser.add_argument('--output',type=Path,default=ROOT/'faithful/results/toy_original')
    args=parser.parse_args();torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    build();out=args.output;out.mkdir(parents=True,exist_ok=True)
    train_tasks,test_tasks,truth,probes,source_hash=dataset(args.benchmark,args.seed)
    io={'training':[wire(t) for t in train_tasks],'testing':[wire(t) for t in test_tasks]}
    save(out/'benchmark_io.json',io)
    save(out/'evaluation_private.json',{'truth':truth,'probes':probes})
    manifest={'arguments':{**vars(args),'output':str(out)},'source_benchmark_sha256':source_hash,'io_sha256':hashlib.sha256((out/'benchmark_io.json').read_bytes()).hexdigest(),
              'budget_note':'Complete-candidate and expanded-state caps; DSL node size includes variables/constants, excludes lambda/application syntax. All candidates within budget are checked, then generative top-K is retained. Not a matched wall-time comparison with Lite.'}
    save(out/'manifest.json',manifest)
    with Kernel() as k:
        base,learned,models,fs,training=train(k,train_tasks,args,out)
        fitted=k.call('update',grammar=base,frontiers=fs)
        uniform=copy.deepcopy(learned);uniform['log_variable']=0.
        for pr in uniform['productions']:pr['log_weight']=0.
        specs=[('A',base,None),('B',learned,None),('C',base,models[0]),('D',learned,models[1]),('base_fitted',fitted,None),('library_uniform',uniform,None),('C_shuffle',base,models[0]),('D_shuffle',learned,models[1])]
        order=list(range(len(test_tasks)));rng=random.Random(args.seed+555)
        while True:
            rng.shuffle(order)
            if all(i!=v for i,v in enumerate(order)):break
        save(out/'shuffle.json',order)
        summary={'manifest':manifest,'training':training,'configurations':{}}
        options=dict(limit=args.max_nodes,max_states=args.max_states,max_size=args.max_size,maximum_depth=args.maximum_depth,upper_bound=100,top_k=args.top_k)
        for label,g,model in specs:
            print(f'Held-out {label}: {len(test_tasks)} tasks',flush=True)
            guidance_seconds=0.
            if model is None:rows,elapsed=search(k,test_tasks,g,g,options)
            else:
                rows=[];elapsed=0.
                for i,t in enumerate(test_tasks):
                    start=time.perf_counter();sg=model.search_grammar(features(test_tasks[order[i]] if label.endswith('shuffle') else t));guidance_seconds+=time.perf_counter()-start
                    rr,seconds=search(k,[t],g,sg,options);rows.extend(rr);elapsed+=seconds
            save(out/f'{label}_frontiers.json',rows)
            m=metrics(k,rows,g,truth,probes);m.update(search_batch_seconds=elapsed,recognition_seconds=guidance_seconds)
            summary['configurations'][label]=m;save(out/'summary.json',summary)
            print(f"{label}: {m['solved']}/{len(test_tasks)}, first-solution mean={m['mean_first_solution_nodes']}",flush=True)
    print(f'Saved {out.resolve()}',flush=True)
if __name__=='__main__':main()
