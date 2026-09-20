"""Abstraction-discovery methods behind one interface.

::

    Frontiers + Grammar (+ task ids)  ->  Compressor  ->  new library + updated grammar

Every method runs on the frozen Haskell machinery (typing, inverse-beta rewriting,
inside-outside fitting, DreamCoder MDL objective) exposed by the compression bridge.
Methods differ only in how candidate abstractions are *proposed* and by which
*objective* they are *selected*:

======  ==================  ==============================================
method  proposals           selection objective
======  ==================  ==============================================
A       none                prior fitting only (no library learning)
B       DreamCoder          DreamCoder MDL (frozen Haskell ``compress``)
C       Stitch              Stitch leaf-cost utility (structure penalty 1)
D       Stitch              DreamCoder MDL (hybrid)
E       DreamCoder          Stitch leaf-cost utility
======  ==================  ==============================================

B is the unchanged DreamCoder compressor.  C, D and E share one greedy loop
(propose, score every admissible candidate with the frozen typed rewrite, accept
the best strictly improving candidate, repeat up to ``iterations`` times) so that
the proposal source and the objective are the only factors.  The Stitch utility
is Stitch's leaf-cost objective (primitive/variable cost 100, application and
lambda cost 0, structure penalty 1.0) evaluated on the frozen typed rewrite:
total leaf savings over all frontier entries minus the non-variable leaves of
the body.  Stitch's own native utility of each proposal is recorded alongside.

No compressor module reads latent definitions or held-out data; the learner
passes only frontiers and the current grammar.
"""
import copy

import stitch_core

from faithful.compression.interface import Compressor, digest, leaves
from faithful.compression.original import OriginalCompressor
from faithful.compression.stitch import encode, decode

STITCH_COSTS = dict(cost_app=0, cost_lam=0, cost_var=100, cost_ivar=100, cost_prim_default=100)
# stitch_core forwards keyword arguments as command-line flags and accepts str/int/bool only.
STITCH_CONFIGS = [dict(max_arity=a, structure_penalty=s) for a in (1, 2, 3) for s in ('0.5', '1.0', '2.0')]
STITCH_ITERATIONS = 4
EPS = 1e-10


def primitive_leaves(p):
    """Leaves that are not bound variables: primitives and invented references."""
    if 'application' in p:
        return sum(map(primitive_leaves, p['application']))
    if 'abstraction' in p:
        return primitive_leaves(p['abstraction'])
    return 0 if 'index' in p else 1


def strip_lambdas(p):
    while 'abstraction' in p:
        p = p['abstraction']
    return p


def nontrivial(inv):
    """DreamCoder's candidate filter: more than one primitive/invented leaf, or one leaf with a repeated variable.

    Stitch otherwise proposes eta-wrappers such as ``λx. #f x`` (a single atom applied
    to its variables) whose leaf-cost utility is an artefact of counting variables.
    """
    def all_leaves(q):
        if 'application' in q:
            return [l for x in q['application'] for l in all_leaves(x)]
        if 'abstraction' in q:
            return all_leaves(q['abstraction'])
        return [q]
    ls = all_leaves(strip_lambdas(inv['invented']))
    atoms = [l for l in ls if 'index' not in l]
    indices = [l['index'] for l in ls if 'index' in l]
    return len(atoms) > 1 or (len(atoms) == 1 and len(indices) > len(set(indices)))


def admissible(kernel, inv, grammar):
    """Reject trivial proposals and duplicates (beta-equal to an existing production) before scoring."""
    if not nontrivial(inv):
        return 'trivial: single atom applied to variables'
    normal = kernel.call('beta', program=inv)['program']
    for pr in grammar['productions']:
        if pr['program'] == inv or ('invented' in pr['program'] and kernel.call('beta', program=pr['program'])['program'] == normal):
            return 'duplicate of an existing production'
    return None


def encode_corpus(frontiers):
    atoms, programs, tasks = {}, [], []
    for i, f in enumerate(frontiers):
        for e in f['entries']:
            programs.append(encode(e['program'], atoms))
            tasks.append(str(i))
    names = {name: p for name, p in atoms.values()}
    return programs, tasks, names


def changed_entries(before, after):
    return sum(x['program'] != y['program'] for a, b in zip(before, after) for x, y in zip(a['entries'], b['entries']))


def stitch_proposals(frontiers, configs=STITCH_CONFIGS, iterations=STITCH_ITERATIONS):
    """Distinct closed abstractions proposed by Stitch under several utility settings.

    Multi-iteration runs contribute every abstraction whose body does not reference
    an earlier, not yet accepted proposal of the same run (``fn_`` tokens); accepted
    library inventions are opaque atoms for Stitch and decode back to references.
    """
    programs, tasks, names = encode_corpus(frontiers)
    proposals, seen, errors = [], {}, []
    if not programs:
        return proposals, errors
    for cfg in configs:
        try:
            r = stitch_core.compress(programs, iterations=iterations, tasks=tasks, silent=True, **STITCH_COSTS, **cfg)
        except Exception as exc:  # Rust backend panic or parse failure; recorded, never hidden
            errors.append({'config': cfg, 'error': f'{type(exc).__name__}: {exc}'})
            continue
        for rank, (a, meta) in enumerate(zip(r.abstractions, r.json['abstractions'])):
            if 'fn_' in a.body:
                continue
            inv = {'invented': decode(a.body, names, a.arity)}
            d = digest(inv)
            if d in seen:
                seen[d]['configs'].append(cfg)
                continue
            seen[d] = {'invention': inv, 'source': 'stitch', 'native_body': a.body, 'arity': a.arity, 'native_utility': meta['utility'],
                       'native_uses': meta['num_uses'], 'rank': rank, 'config': cfg, 'configs': [cfg]}
            proposals.append(seen[d])
    return proposals, errors


def dreamcoder_proposals(kernel, grammar, frontiers):
    """DreamCoder's own candidate set: closed inverse-beta fragments with support in at least two tasks."""
    candidates = kernel.call('compression_candidates', grammar=grammar, frontiers=frontiers, arity=1)['programs']
    return [{'invention': inv, 'source': 'dreamcoder', 'rank': i} for i, inv in enumerate(candidates)], []


class NoCompression(Compressor):
    """Method A: the frozen prior fit without any invention."""
    label = 'A'

    def _compress(self, frontier, grammar):
        fitted = self.kernel.call('compression_objective', grammar=grammar, frontiers=frontier)['grammar']
        return self.result(frontier, grammar, fitted, copy.deepcopy(frontier), [], {'backend': 'none', 'protocol': 'inside-outside prior fit only'})


class DreamCoderCompressor(OriginalCompressor):
    """Method B: the unchanged Haskell DreamCoder compressor (arity 1, up to 3 inventions)."""
    label = 'B'


class GreedyCompressor(Compressor):
    """Shared propose -> score -> accept loop for C, D and E.

    ``proposer`` is ``'stitch'`` or ``'dreamcoder'``; ``objective`` is ``'mdl'``
    (frozen DreamCoder objective, accept if strictly improved) or ``'stitch'``
    (leaf-cost utility, accept if positive).
    """
    proposer = 'stitch'
    objective = 'mdl'
    label = '?'

    def propose(self, grammar, frontiers):
        if self.proposer == 'stitch':
            return stitch_proposals(frontiers)
        return dreamcoder_proposals(self.kernel, grammar, frontiers)

    def score(self, grammar, frontiers, base, proposal):
        row = {k: v for k, v in proposal.items() if k != 'invention'}
        row['invention'] = proposal['invention']
        reason = admissible(self.kernel, proposal['invention'], grammar)
        if reason:
            row['outcome'] = 'rejected: ' + reason
            return row
        try:
            trial = self.kernel.call('compression_trial', grammar=grammar, frontiers=frontiers, invention=proposal['invention'])
        except ValueError as exc:
            row['outcome'] = f'ill-typed under the fixed type system: {exc}'
            return row
        saved = sum(leaves(x['program']) - leaves(y['program']) for a, b in zip(frontiers, trial['frontiers']) for x, y in zip(a['entries'], b['entries']))
        row.update(objective=trial['objective'], delta_mdl=trial['objective'] - base['objective'], saved_leaves=saved,
                   utility=saved - primitive_leaves(proposal['invention']['invented']),
                   rewritten_entries=changed_entries(frontiers, trial['frontiers']), type=trial['type'])
        row['_trial'] = trial
        return row

    def best_of(self, scored):
        candidates = [r for r in scored if '_trial' in r and r['rewritten_entries'] > 0]
        if self.objective == 'mdl':
            return max(candidates, key=lambda r: (r['objective'], r['utility'], -r['rank']), default=None)
        return max(candidates, key=lambda r: (r['utility'], r['objective'], -r['rank']), default=None)

    def accepts(self, best, base):
        if best is None:
            return False
        return best['objective'] > base['objective'] + EPS if self.objective == 'mdl' else best['utility'] > 0

    def _compress(self, frontier, grammar):
        g, fs = copy.deepcopy(grammar), copy.deepcopy(frontier)
        history, steps = [], []
        for step in range(self.iterations):
            base = self.kernel.call('compression_objective', grammar=g, frontiers=fs)
            proposals, errors = self.propose(g, fs)
            scored = [self.score(g, fs, base, p) for p in proposals]
            best = self.best_of(scored)
            record = {'step': step, 'objective_before': base['objective'], 'proposal_count': len(proposals), 'proposal_errors': errors,
                      'proposals': [{k: v for k, v in r.items() if k != '_trial'} for r in scored]}
            steps.append(record)
            if not self.accepts(best, base):
                record['outcome'] = ('no admissible proposal' if best is None else
                                     'no proposal improves the DreamCoder objective' if self.objective == 'mdl' else
                                     'no proposal has positive leaf-cost utility')
                break
            record['outcome'] = 'accepted ' + best.get('native_body', digest(best['invention'])[:12])
            history.append({'before': base['objective'], 'after': best['objective'], 'invented': best['invention'],
                            'utility': best['utility'], 'saved_leaves': best['saved_leaves'], 'native_utility': best.get('native_utility'),
                            'source': best['source'], 'rank': best['rank'], 'config': best.get('config'),
                            'mdl_gate_would_accept': best['objective'] > base['objective'] + EPS})
            g, fs = best['_trial']['grammar'], best['_trial']['frontiers']
        if not history:
            g = self.kernel.call('compression_objective', grammar=grammar, frontiers=frontier)['grammar']
        return self.result(frontier, grammar, g, fs, history,
                           {'backend': f'{self.proposer} proposals + {self.objective} objective', 'steps': steps,
                            'stitch_version': '0.1.29' if self.proposer == 'stitch' else None,
                            'protocol': f'greedy; up to {self.iterations} accepted inventions; admissibility = DreamCoder triviality filter and no beta-duplicates; '
                                        'all candidates rewritten by the frozen typed inverse-beta rewrite'})


class StitchCompressor(GreedyCompressor):
    """Method C: Stitch proposals selected by Stitch's leaf-cost utility."""
    proposer, objective, label = 'stitch', 'stitch', 'C'


class HybridCompressor(GreedyCompressor):
    """Method D: Stitch proposals selected by the DreamCoder MDL objective."""
    proposer, objective, label = 'stitch', 'mdl', 'D'


class DreamCoderProposalStitchObjective(GreedyCompressor):
    """Method E: DreamCoder's inverse-beta candidates selected by Stitch's leaf-cost utility."""
    proposer, objective, label = 'dreamcoder', 'stitch', 'E'


class DreamCoderReimplemented(GreedyCompressor):
    """DreamCoder proposals + DreamCoder MDL through the shared loop; a parity check against B, not an arm."""
    proposer, objective, label = 'dreamcoder', 'mdl', 'B_loop'


METHODS = {'A': NoCompression, 'B': DreamCoderCompressor, 'C': StitchCompressor,
           'D': HybridCompressor, 'E': DreamCoderProposalStitchObjective}
DESCRIPTIONS = {'A': 'no compression (prior fit only)', 'B': 'DreamCoder compression (frozen Haskell compressor)',
                'C': 'Stitch compression: Stitch proposals + Stitch leaf-cost utility',
                'D': 'hybrid: Stitch proposals + DreamCoder MDL selection',
                'E': 'DreamCoder proposals + Stitch leaf-cost utility',
                'O': 'oracle library (true active latents) + prior fit, no compression',
                'O_uniform': 'oracle library, uniform weights, no learning',
                'A0': 'uniform base grammar, no learning'}


def make_compressor(method, kernel, iterations=3):
    return METHODS[method](kernel, iterations=iterations)
