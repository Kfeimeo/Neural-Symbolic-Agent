"""Read-only audit of measured compression outputs and frozen boundaries."""
from .study import read,OUT,SOURCE,verify
from .interface import BridgeKernel,digest
from .stitch import StitchCompressor
from ..python.toy import save

def run():
    verify();frozen=read(OUT/'frozen_input.json');private=read(SOURCE/'evaluation_private.json')
    results=read(OUT/'frozen_frontier_results.json');checks=[]
    with BridgeKernel() as k:
        for regime in ['zero','low','medium','high']:
            pair={r['backend']:r for r in results if r['regime']==regime}
            assert pair['original']['statistics']['input_sha256']==pair['stitch']['statistics']['input_sha256']
            assert pair['original']['mdl_accounting']['before']==pair['stitch']['mdl_accounting']['before']
            fs=[f for n,f in zip(frozen['names'],frozen['frontiers']) if private['tasks'][n]['regime']==regime and f['entries']]
            for label,r in pair.items():
                assert digest(dict(frontiers=fs,grammar=frozen['grammar']))==r['statistics']['input_sha256']
                for a,b in zip(fs,r['rewritten_programs']):
                    for x,y in zip(a['entries'],b['entries']):
                        assert k.call('beta',program=x['program'])==k.call('beta',program=y['program'])
            # Independent fresh replay verifies deterministic Stitch result and
            # native rewrites even for an early artifact created before logging
            # those per-proposal validation witnesses was added.
            fresh=StitchCompressor(k).compress(fs,frozen['grammar'])
            assert fresh.grammar_updates==pair['stitch']['grammar_updates']
            assert fresh.rewritten_programs==pair['stitch']['rewritten_programs']
            save(OUT/'audit_native'/f'{regime}.json',fresh.to_dict())
            checks.append(dict(regime=regime,paired_input_equal=True,paired_baseline_equal=True,
                all_accepted_rewrites_beta_equal=True,native_stitch_replay_identical=True))
    save(OUT/'audit.json',dict(core_and_benchmark_unchanged=True,checks=checks))
if __name__=='__main__':run()
