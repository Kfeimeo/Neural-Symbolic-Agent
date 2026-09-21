"""Phase 3 adapters; all acceptance scores come from the frozen Haskell MDL."""
import copy
from itertools import combinations

from faithful.compression.interface import CompressionResult, accounting, digest
from faithful.compression.original import OriginalCompressor
from experiments.abstraction_learning.compressors import admissible
from .equations import term, wire, normal, saturate, cost, children
from .egraph import EGraph, anti_unify, close_pattern


def deduplicate(fs):
    for f in fs:
        es = {}
        for e in f['entries']:
            key = digest(e['program'])
            if key in es and es[key]['log_likelihood'] != e['log_likelihood']:
                raise ValueError('equivalent entries have different likelihoods')
            es[key] = e
        f['entries'] = list(es.values())
    return fs


def pattern_body(inv):
    t = term(inv['invented'])
    while t[0] == 'lam':
        t = t[1]
    return t


def matches(p, t, slots=None):
    slots = {} if slots is None else slots
    if p[0] == 'var':
        i = p[1]
        if i in slots:
            return slots[i] == t
        slots[i] = t
        return True
    if p[0] != t[0] or len(p) != len(t):
        return False
    if not children(p):
        return p == t
    return all(matches(a, b, slots) for a, b in zip(children(p), children(t)))


def rewrite_cost(t, p):
    """Representation selection only. Haskell performs/checks actual typed rewriting."""
    slots = {}
    original = 1 + sum(rewrite_cost(c, p) for c in children(t))
    if t[0] != 'lam' and matches(p, t, slots):
        from .equations import size
        return min(original, 1 + 2 * len(slots) + sum(size(v) - 1 for v in slots.values()))
    return original


class EquivalenceCompressor:
    def __init__(self, kernel, iterations=3, arm='B1'):
        self.kernel, self.iterations, self.arm = kernel, iterations, arm

    def compress(self, frontier, grammar):
        if self.arm == 'B0':
            return OriginalCompressor(self.kernel, self.iterations).compress(frontier, grammar)
        original = frontier
        frontier = [f for f in original if f['entries']]
        k = self.kernel
        fs, audit = copy.deepcopy(frontier), []
        for f in fs:
            for e in f['entries']:
                p = term(e['program'])
                qs, proof = ((normal(p),), []) if self.arm == 'B1' else saturate(p)
                e['program'] = wire(min(qs, key=cost))
                audit.append({'input': wire(p), 'normal': wire(normal(p)), 'representatives': len(qs),
                              'equation_edges': len(proof), 'output': e['program']})
        fs = deduplicate(fs)
        if self.arm in ('B1', 'B2'):
            result = OriginalCompressor(k, self.iterations).compress(fs, grammar)
        else:
            result = self.egraph_compress(frontier, grammar)
        result.statistics.update(arm=self.arm, representation_audit=audit, raw_frontiers=frontier,
                                 representation='RR' if self.arm == 'B1' else 'E/R', saturation_complete=True)
        # Keep normalization/extraction changes separate from invention gains.
        fitted = k.call('compression_objective', grammar=grammar, frontiers=frontier)['grammar']
        raw = accounting(k, fitted, frontier)
        result.mdl_accounting['raw_input'] = raw
        result.mdl_accounting['total_delta_mdl'] = raw['mdl'] - result.mdl_accounting['after']['mdl']
        rewritten = iter(result.rewritten_programs)
        result.rewritten_programs = [next(rewritten) if f['entries'] else copy.deepcopy(f) for f in original]
        return result

    def egraph_compress(self, frontier, grammar):
        k, g, fs = self.kernel, copy.deepcopy(grammar), copy.deepcopy(frontier)
        history, diagnostics = [], []
        initial = None
        for step in range(self.iterations):
            graph, spaces, task_classes = EGraph(), [], []
            for f in fs:
                entry_spaces, classes = [], set()
                for e in f['entries']:
                    _, qs, _ = graph.space(term(e['program']))
                    entry_spaces.append(qs)
                    classes.update(graph.first_order_classes(qs))
                spaces.append(entry_spaces)
                task_classes.append(classes)
            graph.rebuild()
            task_classes = [{graph.find(c) for c in cs} for cs in task_classes]
            canonical = copy.deepcopy(fs)
            for f, qs in zip(canonical, spaces):
                for e, variants in zip(f['entries'], qs):
                    e['program'] = wire(min(variants, key=cost))
            canonical = deduplicate(canonical)
            base = k.call('compression_objective', grammar=g, frontiers=canonical)
            if initial is None:
                initial = accounting(k, base['grammar'], canonical)
            proposals, visited = {}, set()
            for left, right in combinations(task_classes, 2):
                for a in sorted(left):
                    for b in sorted(right):
                        key = tuple(sorted((a, b)))
                        if key in visited:
                            continue
                        visited.add(key)
                        for p in anti_unify(graph, *key):
                            inv = close_pattern(p)
                            proposals[digest(inv)] = inv
            proposals = {key: inv for key, inv in proposals.items() if not admissible(k, inv, g)}
            best, scored = None, []
            for key, inv in sorted(proposals.items()):
                # No extraction until the e-class AU candidate is known.
                selected = copy.deepcopy(fs)
                pattern = pattern_body(inv)
                for f, qs in zip(selected, spaces):
                    for e, variants in zip(f['entries'], qs):
                        e['program'] = wire(min(variants, key=lambda q: (rewrite_cost(q, pattern), cost(q))))
                selected = deduplicate(selected)
                try:
                    trial = k.call('compression_trial', grammar=g, frontiers=selected, invention=inv)
                except ValueError as exc:
                    scored.append({'candidate': key, 'rejected_type': str(exc)})
                    continue
                scored.append({'candidate': key, 'objective': trial['objective']})
                if best is None or trial['objective'] > best[0]['objective']:
                    best = trial, inv
            diagnostics.append({'step': step, 'classes': len(graph.classes), 'enodes': len(graph.nodes),
                                'candidate_count': len(proposals), 'scores': scored})
            if best is None or best[0]['objective'] <= base['objective'] + 1e-10:
                g, fs = base['grammar'], canonical
                break
            trial, inv = best
            history.append({'before': base['objective'], 'after': trial['objective'], 'invented': inv})
            g, fs = trial['grammar'], trial['frontiers']
        if initial is None:
            fitted = k.call('compression_objective', grammar=g, frontiers=fs)
            g = fitted['grammar']
            initial = accounting(k, g, fs)
        after = accounting(k, g, fs)
        old = {digest(p['program']) for p in grammar['productions']}
        return CompressionResult([p for p in g['productions'] if digest(p['program']) not in old], fs,
                                 {'before': initial, 'after': after, 'delta_mdl': sum(h['after']-h['before'] for h in history),
                                  'corpus_savings': initial['corpus_cost']-after['corpus_cost'],
                                  'library_cost_increase': after['library_cost']-initial['library_cost']}, g,
                                 {'backend': 'e-class AU + frozen compression_trial', 'steps': diagnostics}, history)


def make_compressor(arm, kernel, iterations=3):
    return EquivalenceCompressor(kernel, iterations, arm)
