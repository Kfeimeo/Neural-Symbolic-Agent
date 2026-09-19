"""Shared scoring and protocol; no generator, latent or held-out imports."""
import copy
import hashlib
import json
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from ..python.kernel import Kernel, ROOT

def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True).encode()).hexdigest()

def leaves(p):
    if 'application' in p: return sum(map(leaves, p['application']))
    if 'abstraction' in p: return leaves(p['abstraction'])
    return 1

class BridgeKernel(Kernel):
    def __init__(self):
        exe = ROOT/'faithful/build/compression_bridge.exe'
        self.process = subprocess.Popen([str(exe)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding='utf8')

def build_bridge():
    folder = ROOT/'faithful/build/bridge'
    folder.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ghc', '-O1', '-i'+str(ROOT/'faithful/haskell'), '-i'+str(ROOT/'faithful/compression'),
        '-outputdir', str(folder), '-main-is', 'Bridge.main', str(ROOT/'faithful/compression/Bridge.hs'),
        '-o', str(ROOT/'faithful/build/compression_bridge.exe')], check=True)

def accounting(k, grammar, frontiers):
    values = [k.call('frontier', grammar=grammar, frontier=f)['log_marginal'] for f in frontiers if f['entries']]
    library = len(grammar['productions']) + .001*sum(leaves(p['program'].get('invented', p['program'])) for p in grammar['productions'])
    return dict(mdl=library-sum(values), library_cost=library, corpus_cost=-sum(values))

@dataclass
class CompressionResult:
    invented_abstractions: list
    rewritten_programs: list
    mdl_accounting: dict
    grammar_updates: dict
    statistics: dict
    history: list
    def to_dict(self): return asdict(self)
    def protocol(self):
        return dict(grammar=self.grammar_updates, frontiers=self.rewritten_programs, history=self.history)

class Compressor:
    def __init__(self, kernel, iterations=3):
        self.kernel, self.iterations = kernel, iterations
    def compress(self, frontier, grammar):
        """Accept persistent frontier lists, including unsolved tasks."""
        solved=[f for f in frontier if f['entries']]
        result=self._compress(solved,grammar)
        rewritten=iter(result.rewritten_programs)
        result.rewritten_programs=[next(rewritten) if f['entries'] else copy.deepcopy(f) for f in frontier]
        result.statistics['input_sha256']=digest(dict(frontiers=frontier,grammar=grammar))
        return result
    def _compress(self, frontier, grammar): raise NotImplementedError
    def result(self, frontier, grammar, g, fs, history, stats):
        k=self.kernel
        fitted=k.call('compression_objective', grammar=grammar, frontiers=frontier)['grammar']
        before, after=accounting(k, fitted, frontier), accounting(k, g, fs)
        old={digest(p['program']) for p in grammar['productions']}
        inventions=[p for p in g['productions'] if digest(p['program']) not in old]
        for a,b in zip(frontier,fs):
            assert len(a['entries'])==len(b['entries']) and a['request']==b['request']
            for x,y in zip(a['entries'],b['entries']):
                assert x['log_likelihood']==y['log_likelihood']
                assert k.call('beta',program=x['program'])==k.call('beta',program=y['program'])
                k.call('score',grammar=g,request=a['request'],program=y['program'])
        return CompressionResult(inventions, fs, dict(before=before, after=after,
            delta_mdl=before['mdl']-after['mdl'], corpus_savings=before['corpus_cost']-after['corpus_cost'],
            library_cost_increase=after['library_cost']-before['library_cost']),g,
            dict(stats,input_sha256=digest(dict(frontiers=frontier,grammar=grammar))),history)
