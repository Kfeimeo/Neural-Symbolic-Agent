"""Evaluation-only recovery, finite exact rewriting and paired statistics."""
import collections
import functools
import json
import random
import statistics
from .kernel import Kernel, application
from .controlled_data import ast_stats, canonical, key, digest


def canonical_ast(p):
    def unpack(q):
        if 'abstraction' in q: return ('lambda', unpack(q['abstraction']))
        if 'index' in q: return (f'${q["index"]}',)
        args = []
        while 'application' in q:
            q, x = q['application']; args.insert(0, unpack(x))
        if 'primitive' in q: return (q['primitive'], *args)
        return ('opaque', key(q), *args)
    try: return key(canonical(unpack(p)))
    except (TypeError, IndexError): return key(p)


def lower(p, n, local=0):
    if 'index' in p:
        i = p['index']
        if i < local: return p
        if i < local+n: raise ValueError('Captured binder')
        return {'index': i-n}
    if 'abstraction' in p: return {'abstraction': lower(p['abstraction'], n, local+1)}
    if 'application' in p: return {'application': [lower(x, n, local) for x in p['application']]}
    return p


def match(pattern, target, slots, local=0, bindings=None):
    bs = {} if bindings is None else bindings
    if 'index' in pattern and local <= pattern['index'] < local+slots:
        i = pattern['index']-local
        q = lower(target, local)
        if i in bs and bs[i] != q: raise ValueError('Inconsistent slot')
        bs[i] = q
    elif 'abstraction' in pattern and 'abstraction' in target:
        match(pattern['abstraction'], target['abstraction'], slots, local+1, bs)
    elif 'application' in pattern and 'application' in target:
        for a, b in zip(pattern['application'], target['application']): match(a, b, slots, local, bs)
    elif pattern != target: raise ValueError('Mismatch')
    return bs


def best_rewrite(k, p, productions):
    """Dynamic program over normalized subtrees and closed invention patterns.

    Exact optimum in this stated finite rewrite space, retaining the request's
    lambda structure, not arbitrary semantic equivalence or inverse-beta
    rewrites. Slots must bind strict subtrees; thus recursion terminates and
    binder captures are rejected.
    """
    p = k.call('beta', program=p)['program']
    patterns = []
    for production in productions:
        inv = production['program']
        if 'invented' not in inv: continue
        body = k.call('beta', program=inv)['program']
        n = 0
        while 'abstraction' in body:
            n += 1; body = body['abstraction']
        patterns.append((inv, n, body))
    def cost(q):
        a = ast_stats(q)
        return (a[3], a[1], a[0], key(q))
    @functools.lru_cache(None)
    def solve(serialized):
        q = json.loads(serialized)
        normal = q
        if 'abstraction' in q: normal = {'abstraction': solve(key(q['abstraction']))}
        if 'application' in q: normal = {'application': [solve(key(x)) for x in q['application']]}
        choices = [normal]
        for inv, n, pattern in patterns:
            try:
                bs = match(pattern, q, n)
                if set(bs) != set(range(n)): continue
                if any(ast_stats(x)[0] >= ast_stats(q)[0] for x in bs.values()): continue
                args = [solve(key(bs[i])) for i in reversed(range(n))]
                choices.append(application(inv, *args))
            except ValueError: pass
        return min(choices, key=cost)
    result = solve(key(p))
    if k.call('beta', program=result)['program'] != p: raise AssertionError('Unsound evaluation rewrite')
    a, b = ast_stats(p), ast_stats(result)
    return {'base_leaf_size': a[3], 'effective_leaf_size': b[3], 'delta_L': a[3]-b[3],
            'base_ast_depth': a[1], 'effective_ast_depth': b[1], 'delta_d': a[1]-b[1],
            'effective_ast_size': b[0], 'witness': result,
            'rewrite_space': 'exact beta-normal subtree/slot covering with request lambdas retained, not global beta-equivalent or semantic minimization'}


def recovery(k, g, latents, regime, probes):
    learned = [pr for pr in g['productions'] if 'invented' in pr['program']]
    active = [f for f in latents if f['reuse'][regime]['training_occurrence_count'] or f['reuse'][regime]['heldout_reuse_count']]
    matrices = {name: [] for name in ['syntactic', 'canonical', 'beta', 'type', 'behavioral']}
    normalized = [k.call('beta', program=p['program'])['program'] for p in learned]
    def output(p, kind):
        values = []
        params = [None] if kind == 'grid' else ([1, 2, 3] if kind == 'color' else [-1, 0, 1])
        for param in params:
            sets = [[x] if param is None else [x, param] for x in probes]
            values.extend(k.call('evaluate_batch', program=p, input_sets=sets)['values'])
        return values if all(v is not None for v in values) else None
    for i, f in enumerate(active):
        normal = k.call('beta', program=f['body'])['program']
        expected = output(f['body'], f['kind'])
        for j, (pr, actual) in enumerate(zip(learned, normalized)):
            same_type = pr['type'] == f['type']
            matches = {'syntactic': pr['program']['invented'] == f['body'],
                'canonical': canonical_ast(actual) == canonical_ast(normal), 'beta': actual == normal,
                'type': same_type, 'behavioral': same_type and expected is not None and output(pr['program'], f['kind']) == expected}
            for name, yes in matches.items():
                if yes: matrices[name].append([i, j])
    metrics = {}
    for name, pairs in matrices.items():
        recovered = {i for i, j in pairs}; matched = {j for i, j in pairs}
        precision = len(matched)/len(learned) if learned else 0.
        recall = len(recovered)/len(active) if active else None
        total_weight = sum(f['reuse'][regime]['heldout_reuse_count'] for f in active)
        metrics[name] = {'precision': precision, 'recall': recall,
            'f1': 2*precision*recall/(precision+recall) if recall is not None and precision+recall else 0. if active else None,
            'weighted_recall': sum(active[i]['reuse'][regime]['heldout_reuse_count'] for i in recovered)/total_weight if total_weight else None,
            'pairs': pairs}
    return {'learned_count': len(learned), 'active_latents': [f['id'] for f in active], 'metrics': metrics,
        'type_note': 'Type matching alone is not evidence of abstraction recovery.',
        'behavior_note': 'Finite independent probes and all configured parameter values; not a universal equivalence proof.'}


def paired_bootstrap(differences, seed=917, draws=2000):
    """Two-way paired bootstrap: resample seeds and shared task IDs together.

    Input matrix has identical task columns for every training seed. This does
    not pretend repeated measurements on one frozen dataset are new datasets.
    """
    if not differences or not differences[0]: return None
    rng = random.Random(seed)
    n, m = len(differences), len(differences[0])
    values = []
    for _ in range(draws):
        si = [rng.randrange(n) for _ in range(n)]
        ti = [rng.randrange(m) for _ in range(m)]
        values.append(sum(differences[i][j] for i in si for j in ti)/(n*m))
    values.sort()
    means = [statistics.mean(row) for row in differences]
    return {'mean': statistics.mean(means), 'seed_standard_deviation': statistics.stdev(means) if n > 1 else 0.,
        'paired_bootstrap_95_ci': [values[int(.025*draws)], values[int(.975*draws)]],
        'training_seeds': n, 'tasks': m, 'draws': draws,
        'scope': 'conditional on one generated dataset; two-way paired resampling of seed and task'}
