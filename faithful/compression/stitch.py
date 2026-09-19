"""Real Stitch proposal search, with frozen DreamCoder rewriting/MDL acceptance.

Stitch's native AST utility is not mislabeled as DreamCoder marginal MDL.
Only its proposal search is substituted; both arms use the same acceptance rule.
"""
import copy
import re
import sys
from .interface import Compressor, ROOT, digest
sys.path.insert(0,str(ROOT/'faithful/vendor'))
import stitch_core

def encode(p, atoms):
    if 'application' in p: return '('+' '.join(encode(x,atoms) for x in p['application'])+')'
    if 'abstraction' in p: return '(lam '+encode(p['abstraction'],atoms)+')'
    if 'index' in p: return '$'+str(p['index'])
    key=digest(p)
    if key not in atoms: atoms[key]=('p'+str(len(atoms)),p)
    return atoms[key][0]

def decode(text, names, arity=0):
    tokens=iter(re.findall(r'\(|\)|[^\s()]+',text))
    def read(token, depth=0):
        if token=='(':
            first=next(tokens)
            if first=='lam':
                result={'abstraction':read(next(tokens),depth+1)}
                assert next(tokens)==')'
                return result
            result=read(first,depth)
            for t in tokens:
                if t==')': return result
                result={'application':[result,read(t,depth)]}
            raise ValueError('Unclosed application')
        if token.startswith('$'): return {'index':int(token[1:])}
        if token.startswith('#'): return {'index':depth+arity-1-int(token[1:])}
        return copy.deepcopy(names[token])
    result=read(next(tokens))
    if next(tokens,None) is not None: raise ValueError('Trailing tokens')
    for _ in range(arity): result={'abstraction':result}
    return result

class StitchCompressor(Compressor):
    def _compress(self, frontier, grammar):
        g,fs=copy.deepcopy(grammar),copy.deepcopy(frontier)
        history=[]; attempts=[]
        for _ in range(self.iterations):
            base=self.kernel.call('compression_objective',grammar=g,frontiers=fs)
            atoms={}; programs=[]; tasks=[]
            for i,f in enumerate(fs):
                for e in f['entries']:
                    programs.append(encode(e['program'],atoms));tasks.append(str(i))
            if not programs: g=base['grammar'];break
            proposal=stitch_core.compress(programs,iterations=1,max_arity=1,tasks=tasks,
                cost_app=0,cost_lam=0,cost_var=100,cost_ivar=100,cost_prim_default=100,
                silent=True)
            attempt={'native':proposal.json};attempts.append(attempt)
            if not proposal.abstractions: g=base['grammar'];break
            a=proposal.abstractions[0]
            names={name:p for name,p in atoms.values()}
            inv={'invented':decode(a.body,names,a.arity)}
            attempt['proposal']=inv
            names[a.name]=inv
            native_rewritten=[decode(s,names) for s in proposal.rewritten]
            original_programs=[e['program'] for f in fs for e in f['entries']]
            assert len(native_rewritten)==len(original_programs)
            for before,after in zip(original_programs,native_rewritten):
                assert self.kernel.call('beta',program=before)==self.kernel.call('beta',program=after),'Unsound native Stitch rewrite'
            attempt['native_rewritten_programs']=native_rewritten
            try:
                trial=self.kernel.call('compression_trial',grammar=g,frontiers=fs,invention=inv)
            except ValueError as e:
                attempt['rejection']='type/grammar: '+str(e);g=base['grammar'];break
            attempt['objective']=trial['objective']
            if trial['objective']<=base['objective']+1e-10:
                attempt['rejection']='No improvement in common DreamCoder MDL';g=base['grammar'];break
            history.append(dict(before=base['objective'],after=trial['objective'],invented=inv))
            g,fs=trial['grammar'],trial['frontiers']
        return self.result(frontier,grammar,g,fs,history,{'backend':'stitch_core','version':'0.1.29','attempts':attempts,
            'protocol':'Stitch top-1 leaf-cost proposal; shared inverse-beta rewrite and DreamCoder MDL gate; stop on rejected proposal'})
