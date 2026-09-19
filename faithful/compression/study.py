"""Evaluation-only orchestration. Private metadata never enters compressors."""
import argparse
import concurrent.futures
import copy
import hashlib
import json
import time
import types
from pathlib import Path
import torch
from .interface import ROOT, BridgeKernel, digest
from .original import OriginalCompressor
from .stitch import StitchCompressor
from ..python import controlled_learner as learner
from ..python.grid import grammar, features, REQUEST
from ..python.toy import save, search, learning_frontier
from ..python.controlled_metrics import recovery, best_rewrite
from ..python.controlled_data import ast_stats
from ..python.recognition import Recognition, arity

SOURCE=ROOT/'faithful/results/controlled'
OUT=ROOT/'results/stitch'
REGIMES=['zero','low','medium','high']
BUDGETS=[100,300,600,1000,3000,10000]
BACKENDS={'original':OriginalCompressor,'stitch':StitchCompressor}
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))

def verify():
    for name,value in read(SOURCE/'SHA256SUMS.json').items():
        assert hashlib.sha256((SOURCE/name).read_bytes()).hexdigest()==value,name
    paths=list((ROOT/'faithful/haskell').glob('*.hs'))+list((ROOT/'faithful/python').glob('*.py'))
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    path=OUT/'core_sha256.json'
    if path.exists():assert read(path)==hashes,'Core modified during study'
    else:save(path,hashes)

def inspect(k,result,frontiers,names,regime,private,latents):
    g=result.grammar_updates
    rec=recovery(k,g,latents,regime,private['recovery_probes'])
    active={f['id']:f for f in latents if f['id'] in rec['active_latents']}
    exposure=[]
    for name,f in active.items():
        pr={'program':{'invented':f['body']},'type':f['type']}
        supported=[n for n,fr in zip(names,frontiers) if any(best_rewrite(k,e['program'],[pr])['delta_L']>0 for e in fr['entries'])]
        exposure.append(dict(latent=name,frontier_support_tasks=supported,supported=bool(supported),minimum_two_task_support=len(supported)>=2))
    for metric in ['beta','behavioral']:
        matched={rec['active_latents'][i] for i,j in rec['metrics'][metric]['pairs']}
        rec[metric+'_by_exposure']={label:dict(total=len(ids),recovered=len(ids&matched),recall=len(ids&matched)/len(ids) if ids else None)
            for label,ids in [('supported',{r['latent'] for r in exposure if r['supported']}),('unsupported',{r['latent'] for r in exposure if not r['supported']}),
                              ('minimum_two_tasks',{r['latent'] for r in exposure if r['minimum_two_task_support']})]}
    rewrites=[]
    for name,a,b in zip(names,frontiers,result.rewritten_programs):
        for before,after in zip(a['entries'],b['entries']):
            x,y=ast_stats(before['program']),ast_stats(after['program'])
            rewrites.append(dict(task=name,before=before['program'],after=after['program'],ast_size_reduction=x[0]-y[0],depth_reduction=x[1]-y[1],leaf_reduction=x[3]-y[3]))
    return dict(recovery=rec,exposure=exposure,rewrites=rewrites,tasks_affected=len({r['task'] for r in rewrites if r['before']!=r['after']}),
        ast_size_reduction=sum(r['ast_size_reduction'] for r in rewrites),depth_reduction=sum(r['depth_reduction'] for r in rewrites),
        inventions=[dict(p,parameter_count=arity(p['type'])) for p in result.invented_abstractions])

def frozen():
    verify();private=read(SOURCE/'evaluation_private.json');latents=read(SOURCE/'latent_library.json')
    tasks=learner.load_io(SOURCE/'train.json');g=grammar()
    frozen_path=OUT/'frozen_input.json'
    with BridgeKernel() as k:
        if not frozen_path.exists():
            rows,seconds=search(k,tasks,g,g,dict(learner.SEARCH,limit=learner.TRAIN_NODES))
            save(frozen_path,dict(grammar=g,names=[t.name for t in tasks],frontiers=[learning_frontier(r) for r in rows],wake_rows=rows,wake_seconds=seconds))
        frozen=read(frozen_path)
        all_results=[];oracle=[]
        for regime in REGIMES:
            names=[n for n in frozen['names'] if private['tasks'][n]['regime']==regime]
            fs=[f for n,f in zip(frozen['names'],frozen['frontiers']) if n in names]
            latent_by_id={f['id']:f for f in latents}
            occurrences=[(n,u['latent']) for n in names for u in private['tasks'][n]['latent_uses']]
            # One frontier per distinct training-task/latent pair, not duplicated
            # support for multiple calls inside one task. No invented symbol input.
            occurrences=list(dict.fromkeys(occurrences))
            oracle_names=[n+':'+fid for n,fid in occurrences]
            gt=[dict(request=latent_by_id[fid]['type'],entries=[dict(program=latent_by_id[fid]['body'],log_likelihood=0.)]) for n,fid in occurrences]
            for mode,frontiers,target,input_names in [('frozen',fs,all_results,names),('oracle',gt,oracle,oracle_names)]:
                selected_names=[n for n,f in zip(input_names,frontiers) if f['entries']]
                frontiers=[f for f in frontiers if f['entries']]
                for label,cls in BACKENDS.items():
                    path=OUT/'compression'/f'{mode}_{regime}_{label}.json'
                    if path.exists():target.append(read(path));continue
                    print(mode,regime,label,flush=True);start=time.perf_counter()
                    result=cls(k).compress(frontiers,g)
                    metrics=inspect(k,result,frontiers,selected_names,regime,private,latents)
                    row=dict(mode=mode,regime=regime,backend=label,seconds=time.perf_counter()-start,**result.to_dict(),**metrics)
                    save(path,row);target.append(row)
                    print('accepted',len(result.invented_abstractions),'MDL',result.mdl_accounting['delta_mdl'],flush=True)
        save(OUT/'frozen_frontier_results.json',all_results)
        save(OUT/'oracle_results.json',dict(diagnostic_only=True,input='True base-DSL latent fragments, one frontier per distinct training-task/latent pair; same fragment repeated only when used in distinct training tasks; zero-reuse cohort has empty oracle corpus; no held-out fragments',results=oracle))
        save(OUT/'abstraction_recovery.json',[{key:r[key] for key in ['mode','regime','backend','recovery','exposure']} for r in all_results+oracle])
        save(OUT/'mdl_comparison.json',[{key:r[key] for key in ['mode','regime','backend','mdl_accounting']} for r in all_results+oracle])
        save(OUT/'historical_exposure_reference.json',dict(source_sha256=hashlib.sha256((SOURCE/'latent_frontier_support.json').read_bytes()).hexdigest(),
            note='Historical file describes iteration 5 frontiers; current exposure is recomputed on these frozen round-zero frontiers, not copied across different corpora.',rows=read(SOURCE/'latent_frontier_support.json')))

def train_job(job):
    regime,label,seed=job
    private=read(SOURCE/'evaluation_private.json')
    tasks=[t for t in learner.load_io(SOURCE/'train.json') if private['tasks'][t.name]['regime']==regime]
    output=OUT/'ec'/regime/str(seed)/label
    class CompressionKernel(BridgeKernel):
        def call(self,operation,**payload):
            if operation!='compress' or getattr(self,'compressing',False):return super().call(operation,**payload)
            self.compressing=True
            try:result=BACKENDS[label](self,iterations=payload['iterations']).compress(payload['frontiers'],payload['grammar'])
            finally:self.compressing=False
            folder=output/'compression_calls';folder.mkdir(parents=True,exist_ok=True)
            save(folder/f'{digest(payload)}.json',dict(input=payload,result=result.to_dict()))
            return result.protocol()
    # Run the unchanged controlled EC bytecode with ONLY compression dispatch changed.
    globals_=dict(learner.__dict__,Kernel=CompressionKernel)
    driver=types.FunctionType(learner.train_condition.__code__,globals_,argdefs=learner.train_condition.__defaults__)
    driver(tasks,'D',seed,output,rounds=5)
    return job

def evaluate_job(job):
    regime,label,seed=job;torch.set_num_threads(1)
    private=read(SOURCE/'evaluation_private.json');latents=read(SOURCE/'latent_library.json')
    tasks=[t for t in learner.load_io(SOURCE/'test.json') if private['tasks'][t.name]['regime']==regime]
    folder=OUT/'ec'/regime/str(seed)/label;result=[]
    with BridgeKernel() as k:
        for iteration in [0,5]:
            path=folder/f'evaluation_{iteration}.json'
            if path.exists():result.append(read(path));continue
            if iteration:
                r=read(folder/f'round_{iteration}/round.json');g=r['grammar']
                model=Recognition(g)
                model.load_state_dict(torch.load(folder/f'round_{iteration}/recognition.pt',map_location=model.device,weights_only=True)['state_dict'])
            else:g=grammar();model=None;r=None
            if model is None:
                rows,_=search(k,tasks,g,g,dict(learner.SEARCH,limit=max(BUDGETS)))
            else:
                rows=[]
                for t in tasks:
                    sg=model.search_grammar(features(t))
                    rr,_=search(k,[t],g,sg,dict(learner.SEARCH,limit=max(BUDGETS)))
                    rows.extend(rr)
            for row in rows:row['transfer']=private['tasks'][row['name']]['transfer']
            record=dict(regime=regime,backend=label,seed=seed,iteration=iteration,rows=rows,
                curves=[dict(budget=n,solve_rate=sum(x['first_solution_nodes'] is not None and x['first_solution_nodes']<=n for x in rows)/len(rows),
                    fraction_reaching_budget=sum(x['enumerated_nodes']>=n for x in rows)/len(rows)) for n in BUDGETS],
                recovery=recovery(k,g,latents,regime,private['recovery_probes']),library_size=len(g['productions']),
                library_objective=r['library_objective'] if r else None,
                transfer={s:sum(x['first_solution_nodes'] is not None for x in rows if x['transfer']==s)/sum(x['transfer']==s for x in rows) for s in {x['transfer'] for x in rows}})
            save(path,record);result.append(record)
    return result

def full_ec(workers=4):
    assert (OUT/'frozen_frontier_results.json').exists() and (OUT/'oracle_results.json').exists()
    jobs=[(regime,label,11) for regime in REGIMES for label in BACKENDS]
    save(OUT/'full_ec_protocol.json',dict(jobs=jobs,rounds=5,heldout_iterations=[0,5],search=learner.SEARCH,training_nodes=learner.TRAIN_NODES,
        recognition_steps=learner.STEPS,dream_draws=learner.DREAM_DRAWS,budgets=BUDGETS,
        scope='All frozen cohorts, paired seed 11; no claim of multi-seed significance. Scope fixed before full EC outcomes.'))
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for job in pool.map(train_job,jobs):print('trained',job,flush=True)
        records=[]
        for rows in pool.map(evaluate_job,jobs):records.extend(rows)
    save(OUT/'full_ec_results.json',records);verify()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['frozen','ec']);parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    if args.mode=='frozen':frozen()
    else:full_ec(args.workers)
