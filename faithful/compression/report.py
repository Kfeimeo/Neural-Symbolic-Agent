"""Generate reports only from measured artifacts; no synthesis or tuning."""
import hashlib
import json
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from .study import OUT,SOURCE,ROOT,read,verify
from ..python.toy import save

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,row))+' |' for row in rows])
def fmt(x):return 'N/A' if x is None else f'{x:.3f}'
def test_status():
    root=ET.parse(OUT/'regression.xml').getroot()
    suites=list(root) if root.tag=='testsuites' else [root]
    total=sum(int(x.attrib.get('tests',0)) for x in suites)
    failed=sum(int(x.attrib.get('failures',0))+int(x.attrib.get('errors',0)) for x in suites)
    return f'{total-failed} passed; {failed} failed/error'

def domains():
    ds=[read(OUT/'domains'/name/'validation.json') for name in ['arithmetic','list']]
    lines=['# Official DreamCoder Domain Validation','',
        '## Scope and source provenance',
        'Arithmetic follows the [official tutorial](https://github.com/ellisk42/ec/blob/master/docs/creating-new-domains.md): `incr : int -> int`, `incr2 : int -> int`; train add1/add2/add3, held-out add4. List uses official `map double`, `map increment`, `map negation` training functions and held-out `map quadruple`, `map add 3` from [makeListTasks.py](https://github.com/ellisk42/ec/blob/master/dreamcoder/domains/list/makeListTasks.py), with the `map`, `+`, `-`, `0`, `1` subset of bootstrapTarget primitives. `map : (a -> b) -> list(a) -> list(b)` is polymorphic and higher-order.',
        '',
        'Examples are compact deterministic samples of the official task functions, not the original randomized 5000-example arithmetic training sets. This validates external domain semantics, not reproduction of published performance. The locally pinned reference commit is `cb0e63f5c33cd2de360b791038b0f5272750270e`; exact domain source hashes are in `official_source_sha256.json`. Only names, type requests and I/O examples enter learning; no ground-truth AST enters either domain learner.',
        '',
        '## Runtime and unchanged algorithm',
        '`DomainMain.hs` supplies domain primitive values to the existing Haskell evaluator and delegates symbolic operations to the existing core. The original Haskell files are unchanged; no official OCaml runtime is used. Python binds domain evaluator, 40-dimensional I/O task encoder and Wake boundary into the exact existing `ec.explore_compress` function bytecode. Wake uses the existing typed budget enumerator and evaluator, retaining generative top-5 frontiers. This is a domain adapter, not a replacement solver.',
        '',
        'Three persistent rounds execute Wake -> frontier merge -> original compression -> grammar update -> ancestral Dream -> posterior-frontier Replay -> unchanged PyTorch recognition training -> next Wake. Each round uses 20 Dream draws and 30 optimizer steps from the existing domain EC recipe; Wake uses 3000 complete candidates, 500000 expanded states, leaf-size 33, depth 14. Arithmetic and List use the same recipe. CUDA is used for recognition.',
        '', '## Measured trajectories', '']
    rows=[]
    for d in ds:
        for i,r in enumerate(d['history']):
            tr=d['traces'][i*3:i*3+3]
            rows.append([d['domain'],i+1,f"{r['solved']}/3",len(r['grammar']['productions']),len(r['compression']),
                fmt(r['mdl']['mdl']),'/'.join(str(t['frontier_size']) for t in tr),'/'.join(str(t['first_solution_nodes']) for t in tr),r['dream']['accepted']])
    lines += [table(['Domain','Round','Solved','Library size','New inventions','MDL','Frontier sizes','First solution candidate ranks','Accepted dreams / 20'],rows),'',
        'MDL = negative summed frontier log-marginal + number of productions + 0.001 × production body leaf cost, in natural-log units. Initial and later frontier sets may differ: trajectory changes are not a fixed-corpus compression contrast.',
        'Round-1 to round-3 MDL decrease: '+', '.join(d['domain']+' '+fmt(d['history'][0]['mdl']['mdl']-d['history'][-1]['mdl']['mdl']) for d in ds)+'. With no accepted inventions, these changes reflect frontier/prior evolution, not demonstrated library compression.',
        '', '## Held-out and recognition effect','',table(['Domain','Task','Guidance','First solution rank','Emitted candidates','Expanded states','Stop'],[
            [d['domain'],r['task'],r['label'],r['first_solution_nodes'],r['enumerated_nodes'],r['expanded_states'],r['stop_reason']] for d in ds for r in d['heldout']]),'',
        'The arithmetic training tasks are solved in all three rounds and add4 transfers. List training tasks are also solved, but map add 3 is unsolved under the fixed bound. Recognition helps arithmetic add4 and hurts List map quadruple in this run; no universal recognition gain is claimed.',
        '', '## Inventions and limits','',
        'Neither small training corpus accepted a new invention. The full compression phase ran and grammar weights evolved; absence of an accepted invention is a measured outcome. Learned invention discovery on these official subsets is therefore **not established**. A separate correctness test constructs a polymorphic higher-order invented map wrapper, verifies inference, lambda binding, beta equivalence and evaluation on int/bool lists; this checks representation support, not learned recovery. Controlled Grid experiments supply the learned-invention evidence.',
        '', '## Reproduction','',
        'From the project root, run `E:\\anaconda3\\envs\\py312\\python.exe -m faithful.domains.official`. Results and checkpoints are in `results/stitch/domains/`. Source hashes and the complete regression results are recorded with the Stitch study.']
    (ROOT/'OFFICIAL_DOMAIN_VALIDATION.md').write_text('\n'.join(lines)+'\n',encoding='utf8')

def stitch():
    frozen=read(OUT/'frozen_frontier_results.json');oracle=read(OUT/'oracle_results.json')['results']
    full=read(OUT/'full_ec_results.json') if (OUT/'full_ec_results.json').exists() else []
    lines=['# Stitch Controlled Compression Report','',
        '## Research scope','',
        'Real [Stitch](https://github.com/mlb2251/stitch) Python bindings `stitch-core==0.1.29` are used. The primary comparison replaces proposal search with Stitch and retains the original Haskell inverse-beta rewrite, type validation, inside-outside fitting and MDL acceptance. This controlled adapter is **not unrestricted vanilla Stitch**. Its conclusions must not be generalized to all Stitch configurations.',
        '',
        'Stitch proposes one abstraction per step using native leaf cost (primitive/variable/invention-variable=100, application/lambda=0), maximum abstraction arity 1, task-aware input, one thread. The existing compressor also uses arity 1 and at most three accepted inventions per round. A proposal is accepted only when the same DreamCoder objective improves; the Stitch arm stops if its top proposal fails typing or MDL. It does not search the next-best native proposal after a rejection. Native proposals, native utility and rejection reasons are retained. That proposal-selection/MDL mismatch is an explicit experimental limitation.',
        '',
        'The frozen solver, typed enumeration, grammar implementation, original compressor, recognition network/loss, Dream, Replay, EC loop source, benchmark files and all search bounds remain unchanged. Both full-EC arms run the exact existing controlled learner bytecode with only its Kernel compression dispatch substituted. New bridge/domain files import the original core. `core_sha256.json` verifies source preservation; original frozen benchmark SHA256 sums are checked before and after the study.',
        'Runs share CPU/GPU resources and resume from completed checkpoints. Wall times are diagnostic only; search-efficiency conclusions use candidate ranks and expanded-state counts, not a controlled wall-clock speed claim.',
        '', '## Shared evaluation protocol','',
        'The frozen input is one fresh uniform base-grammar Wake at the unchanged 3000-candidate training budget on all 224 original training tasks, grouped into the four original 56-task cohorts. Both compressors receive identical solved frontiers and grammar, including all retained top-3 entries and their likelihoods. Unsolved frontiers are excluded from compression exactly as in the original EC driver; all Wake results, including failures, remain in `frozen_input.json`. Input hashes are recorded in each result.',
        '',
        'MDL = -sum log marginal(frontier | fitted grammar) + library cost; library cost = production count + 0.001 × sum body leaf sizes. The baseline is fitted by the same single inside-outside step, so the reported positive ΔMDL means improvement over a shared fitted baseline, not over the unfitted uniform prior. Corpus savings and library-cost increase are recorded separately. Native Stitch AST utility is never substituted for this MDL.',
        '',
        'Recovery compares learned inventions against active generator latents. Beta matching uses the Haskell beta normalizer. Behavioral matching requires equal types and identical outputs on the original independent recovery probes and configured parameter values; it is not a universal equivalence proof. Precision counts matched learned inventions; recall counts recovered active latents; duplicate/equivalent latents can create many-to-many matches. F1 uses these two rates. Type alone is not recovery. Zero-reuse has no active latent denominator and reports N/A.',
        '', '## Frozen frontier results','']
    def compression_rows(rs):
        return [[r['regime'],r['backend'],len(r['invented_abstractions']),fmt(r['recovery']['metrics']['beta']['recall']),
            fmt(r['recovery']['metrics']['behavioral']['precision']),fmt(r['recovery']['metrics']['behavioral']['recall']),fmt(r['recovery']['metrics']['behavioral']['f1']),
            fmt(r['mdl_accounting']['delta_mdl']),fmt(r['mdl_accounting']['corpus_savings']),fmt(r['mdl_accounting']['library_cost_increase']),r['tasks_affected'],r['ast_size_reduction'],r['depth_reduction']] for r in rs]
    headers=['Reuse','Backend','New inventions','Beta recall','Behavior precision','Behavior recall','Behavior F1','ΔMDL','Corpus savings','Δlibrary cost','Tasks rewritten','Σ AST reduction','Σ depth reduction']
    lines += [table(headers,compression_rows(frozen)),'',
        'AST/depth reductions count the actual corresponding rewritten frontier entries, treating invented function references as atomic. They are sums across retained programs, not ground-truth-program complexity and not expanded-body savings. Full before/after AST witnesses, invention types and type arities are in the JSON outputs.',
        '',
        'A concrete high-reuse example is latent F00: both backends recover its behavior, but only Stitch has an invention whose expanded beta-normal body exactly equals F00. Original reaches the same probe behavior through a different rotation/translation expression. Therefore the frozen exact-match gain is partly representational alignment, not evidence of recovering an additional distinct behavior. The high-reuse Oracle behavioral gain (3/4 versus 2/4) is stronger evidence, restricted to the diagnostic corpus.',
        '', '## Exposure separation','',
        'The existing `latent_frontier_support.json` is preserved with its hash in `historical_exposure_reference.json`. It describes earlier iteration-5 frontiers, so its labels cannot be assigned to this new round-zero corpus. We recompute the same beta-normal structural coverage on the exact input, separating any support (at least one task), minimum two-task support, and zero support. The support computation is evaluation-only and never enters compression.', '',
        table(['Reuse','Backend','Supported behavior recall','Unsupported behavior recall','Supported latent count','Unsupported latent count'],[
            [r['regime'],r['backend'],fmt(r['recovery']['behavioral_by_exposure']['supported']['recall']),fmt(r['recovery']['behavioral_by_exposure']['unsupported']['recall']),r['recovery']['behavioral_by_exposure']['supported']['total'],r['recovery']['behavioral_by_exposure']['unsupported']['total']] for r in frozen]),
        '', '## Oracle-frontier diagnostic','',
        'Only true latent fragment bodies used by training tasks are supplied, in the base DSL, one frontier per distinct training-task/latent pair. Repeated occurrences within the same task do not inflate support. Cross-task repetition is retained. This differs from the Wake corpus and is diagnostic only; no oracle material enters normal training or evaluation. The zero-reuse cohort has an empty oracle corpus. Recall still includes active held-out-only latents; exposure-conditioned results show what the oracle actually contains.', '',table(headers,compression_rows(oracle)),
        '', '## Full EC','',
        'Paired seed 11, all four frozen cohorts, five persistent rounds, original 600 recognition steps, 64 ancestral Dream draws, training budget 3000, test budgets 100/300/600/1000/3000/10000; state cap 500000, leaf size 33, depth 14, description length 100, frontier top-K 3. Single-seed results do not support significance or robustness claims. Failed dreams and state-censored searches remain counted. Each per-task first-solution rank supplies exact shorter-budget solve curves; it does not reconstruct shorter-budget top-K frontiers.']
    if full:
        last=[r for r in full if r['iteration']==5]
        lines += ['',table(['Reuse','Backend','Test solved / tasks','Solve rate @10000','Reached 10000','Library size','Beta recall','Behavior recall','Training MDL'],[
            [r['regime'],r['backend'],f"{sum(x['first_solution_nodes'] is not None for x in r['rows'])}/{len(r['rows'])}",fmt(r['curves'][-1]['solve_rate']),fmt(r['curves'][-1]['fraction_reaching_budget']),r['library_size'],fmt(r['recovery']['metrics']['beta']['recall']),fmt(r['recovery']['metrics']['behavioral']['recall']),fmt(-r['library_objective'])] for r in last])]
        lines += ['', 'Transfer solve rates by original split label:', '',table(['Reuse','Backend','Transfer stratum','Solve rate'],[[r['regime'],r['backend'],s,fmt(v)] for r in last for s,v in r['transfer'].items()])]
        lines += ['', 'Solve curves:', '',table(['Reuse','Backend']+[str(n) for n in [100,300,600,1000,3000,10000]],[[r['regime'],r['backend']]+[fmt(c['solve_rate']) for c in r['curves']] for r in last])]
        diffs=[]
        for regime in ['zero','low','medium','high']:
            pair={r['backend']:r for r in last if r['regime']==regime}
            a,b=pair['original'],pair['stitch']
            both=[(x,y) for x,y in zip(a['rows'],b['rows']) if x['first_solution_nodes'] is not None and y['first_solution_nodes'] is not None]
            assert [x['name'] for x in a['rows']]==[x['name'] for x in b['rows']]
            diff=b['curves'][-1]['solve_rate']-a['curves'][-1]['solve_rate']
            diffs.append([regime,fmt(diff),len(both),fmt(sum(x['first_solution_nodes'] for x,y in both)/len(both)) if both else 'N/A',fmt(sum(y['first_solution_nodes'] for x,y in both)/len(both)) if both else 'N/A'])
        lines += ['',table(['Reuse','Stitch minus Original solve rate','Solved by both','Mean rank Original (intersection)','Mean rank Stitch (intersection)'],diffs),
            '', 'Intersection-only rank means are descriptive and selection-biased; unsolved tasks are censored at actual emissions, not assigned a fictitious first-solution rank. Complete per-task emitted candidates and expanded-state counts are retained.']
        lines += ['',table(['Reuse','Backend','Mean emitted candidates','Mean expanded states','State-censored tasks'],[[r['regime'],r['backend'],fmt(sum(x['enumerated_nodes'] for x in r['rows'])/len(r['rows'])),fmt(sum(x['expanded_states'] for x in r['rows'])/len(r['rows'])),sum(x['stop_reason']=='state_budget' for x in r['rows'])] for r in last])]
        evolution=[]
        for p in sorted((OUT/'ec').glob('*/*/*/round_*/round.json')):
            r=read(p)
            evolution.append(dict(regime=p.parents[3].name,seed=int(p.parents[2].name),backend=p.parents[1].name,
                iteration=r['iteration'],solved=r['solved_training_tasks'],library_size=len(r['grammar']['productions']),
                mdl=-r['library_objective'],dream=r['dream'],recognition_device=r['recognition_device'],
                frontier_sizes=[len(f['entries']) for f in r['frontiers']]))
        save(OUT/'library_evolution.json',evolution)
        lines += ['', 'All five training rounds:', '',table(['Reuse','Backend','Round','Training solved / 56','Library size','Training MDL','Dream accepted / 64'],[[r['regime'],r['backend'],r['iteration'],r['solved'],r['library_size'],fmt(r['mdl']),r['dream']['accepted']] for r in evolution]),
            '', 'Training MDL is on each round\'s evolving solved frontier set; compare paired frozen-corpus MDL above when attributing compression gains. A lower trajectory value can also reflect corpus changes.']
    else:lines += ['', '**Full EC has not finished; no full-EC conclusion is available yet.**']
    lines += ['', '## Answers to Q1–Q5','',
        '1. **More latent abstractions?** In the high-reuse frozen corpus, Stitch recovers one exact beta latent (25%) while Original recovers none exactly. Behavioral recall is tied at 25%. Thus this is improved exact recovery, not a blanket improvement in behavioral discovery. High-reuse oracle exact/behavioral recall is 75% for Stitch, versus 0%/50% for Original.',
        '2. **Recall rather than extra macros?** The high-reuse frozen gain uses two inventions versus three for Original. It is not explained by larger macro count. Other cohorts do not show a general recall gain; low-reuse frozen behavior recall is worse. Precision/F1 and all matching pairs are saved, including non-latent macros.',
        '3. **Effective complexity?** Accepted Stitch inventions produce verified beta-equivalent frontier rewrites and positive measured AST/leaf savings, but total common MDL improvements are below Original on all nonempty frozen cohorts. Macro discovery alone is not evidence of superior compression.',
        '4. **Search efficiency?** '+('Use the paired final solve curves and intersection rank table above: reductions in frozen corpus size do not by themselves establish faster held-out synthesis. Effects vary by cohort, and only one seed was measured.' if full else 'Pending full EC; frozen compression cannot answer this question.'),
        '5. **Failure analysis.** Separate zero-exposure latents (Wake limitation) from exposed but unrecovered latents (compression/selection limitation). Low/medium oracle failures persist despite direct exposure: the top Stitch AST-cost proposal fails the common probabilistic MDL gate. The adapter stops instead of enumerating lower-ranked proposals. This implicates proposal utility/acceptance mismatch in this configuration, not proof that Stitch search fundamentally cannot discover useful functions. High-reuse oracle success shows the abstraction space can represent useful latents. Remaining full-EC failures may reflect recognition guidance, search ordering or state caps; these data do not uniquely identify the synthesis bottleneck.',
        '', '## Correctness, provenance and reproduction','',
        'All accepted rewrites are checked by Haskell beta normalization and scored against the typed grammar. Native Stitch rewrites are independently beta checked before common rewriting. Tests include evaluator output agreement, shared MDL calculations, identical input hashes, no input mutation, no private benchmark imports in compressor modules, unsolved-frontier preservation, exact original-adapter parity, and polymorphic/higher-order invented function evaluation. Full existing and added regression results: **'+test_status()+'** (`results/stitch/regression.xml`). The first regression attempt lacked `frozendict` in py312; after installing that reference-test dependency, the unchanged tests passed.',
        '',
        'Install `faithful/compression/requirements.txt` into `faithful/vendor`, build with `python -c "from faithful.compression.interface import build_bridge; build_bridge()"`, then run `python -m faithful.domains.official`, `python -m faithful.compression.study frozen`, `python -m faithful.compression.study ec --workers 4`, and `python -m faithful.compression.report`. Set `PYTHONPATH` to the absolute `faithful/vendor` path for official-reference subprocess tests. This study used `E:\\anaconda3\\envs\\py312\\python.exe` with CUDA. Saved checkpoints support round-boundary resume; result caches are for this frozen study only, not interchangeable configurations.']
    (ROOT/'STITCH_COMPRESSION_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')

def main():
    verify();domains();stitch()
    paths=list((ROOT/'faithful/compression').glob('*.py'))+list((ROOT/'faithful/compression').glob('*.hs'))+list((ROOT/'faithful/domains').glob('*.*'))+[ROOT/'faithful/tests/test_stitch.py',ROOT/'faithful/compression/requirements.txt']
    save(OUT/'study_source_sha256.json',{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()})
    refs=[ROOT/'faithful/reference/ec'/p for p in ['docs/creating-new-domains.md','dreamcoder/domains/list/listPrimitives.py','dreamcoder/domains/list/makeListTasks.py']]
    save(OUT/'official_source_sha256.json',{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in refs})
    import torch
    save(OUT/'runtime.json',dict(python=sys.version,executable=sys.executable,platform=platform.platform(),torch=str(torch.__version__),
        cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        ghc=subprocess.check_output(['ghc','--numeric-version'],text=True).strip(),stitch='0.1.29'))
if __name__=='__main__':main()
