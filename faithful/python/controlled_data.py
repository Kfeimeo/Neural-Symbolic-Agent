"""Private hierarchical generator. This module is never imported by the learner.

Algebra and probe screening are dataset checks, not modifications to synthesis.
"""
import collections
import hashlib
import itertools
import json
import random
from pathlib import Path
from .kernel import Kernel, ROOT, abstraction, application, primitive, index, invented
from .grid import grammar, REQUEST
from .toy import save

OUT = ROOT / 'faithful/results/controlled'
REGIMES = ['zero', 'low', 'medium', 'high']
DEPTHS = list(range(2, 9))
BUDGETS = [100, 300, 600, 1000, 3000, 10000]
SEED = 20260918


def key(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'))


def digest(x):
    return hashlib.sha256(key(x).encode()).hexdigest()


def node(op, *xs):
    return (op, *xs)


X = ('$x',)
P = ('$p',)


def term(e, parameters=False):
    if e[0] == '$x':
        return index(1 if parameters else 0)
    if e[0] == '$p':
        return index(0)
    return application(primitive(e[0]), *[term(x, parameters) for x in e[1:]])


def program(e):
    return abstraction(term(e))


def expression(p):
    if 'abstraction' in p: return expression(p['abstraction'])
    if 'index' in p:
        if p['index'] != 0: raise ValueError('Only unary grid functions in base reference bank')
        return X
    xs = []
    while 'application' in p:
        p, x = p['application']; xs.insert(0, expression(x))
    return node(p['primitive'], *xs)


def substitute(e, x, p):
    if e == X:
        return x
    if e == P:
        return p
    return tuple([e[0]] + [substitute(a, x, p) for a in e[1:]])


def depth(e):
    return 0 if len(e) == 1 else 1 + max(map(depth, e[1:]))


def ast_stats(p):
    if 'application' in p:
        a, b = map(ast_stats, p['application'])
        return (1 + a[0] + b[0], 1 + max(a[1], b[1]), a[2] + b[2], a[3] + b[3])
    if 'abstraction' in p:
        a = ast_stats(p['abstraction'])
        return (1 + a[0], 1 + a[1], a[2], a[3])
    return (1, 1, int('primitive' in p), 1)


def random_grid(rng):
    h, w = rng.randint(3, 7), rng.randint(3, 8)
    density = rng.choice([.18, .4, .7, 1.])
    g = [[rng.randint(1, 3) if rng.random() < density else 0 for _ in range(w)] for _ in range(h)]
    if rng.random() < .35:
        g = [[0] * (w + 2)] + [[0] + row + [0] for row in g] + [[0] * (w + 2)]
    return g


def stage(rng, e, parameter=None):
    op = rng.choice(['rotate90', 'flipH', 'transpose', 'invert', 'border', 'trim', 'translate', 'recolor'])
    if op == 'translate':
        return node(op, e, parameter if parameter == P else node(rng.choice(['one', 'minus_one'])), node(rng.choice(['zero', 'one', 'minus_one'])))
    if op == 'recolor':
        a, b = rng.sample(['red', 'blue', 'green'], 2)
        return node(op, e, node(a), node(b))
    return node(op, e)


def canonical(e):
    """Normalize local identities and the complete dihedral transform group."""
    e = tuple([e[0]] + [canonical(a) for a in e[1:]])
    if e[0] == 'identity':
        return e[1]
    if len(e) == 2 and e[0] in ['invert', 'flipH', 'flipV', 'transpose'] and e[1][0] == e[0]:
        return e[1][1]
    if e[0] == 'trim' and e[1][0] in ['trim', 'border']:
        return canonical(node('trim', e[1][1]))
    if e[0] == 'recolor' and e[2] == e[3]:
        return e[1]
    if e[0] == 'translate' and e[2:] == (('zero',), ('zero',)):
        return e[1]
    ops = {'rotate90', 'rotate180', 'flipH', 'flipV', 'transpose'}
    if e[0] in ops:
        chain = []
        q = e
        while q[0] in ops:
            chain.append(q[0]); q = q[1]
        def transform(a, op):
            if op == 'rotate90': return tuple(tuple(reversed(r)) for r in zip(*a))
            if op == 'rotate180': return tuple(tuple(reversed(r)) for r in reversed(a))
            if op == 'flipH': return tuple(tuple(reversed(r)) for r in a)
            if op == 'flipV': return tuple(reversed(a))
            return tuple(zip(*a))
        sample = ((0, 1), (2, 3))
        target = sample
        for op in reversed(chain): target = transform(target, op)
        for n in range(3):
            for cs in itertools.product(sorted(ops), repeat=n):
                a = sample
                for op in cs: a = transform(a, op)
                if a == target:
                    for op in cs: q = node(op, q)
                    return q
    return e


def deletions(e):
    """Type-preserving single-stage deletions (a lower-complexity witness test)."""
    if e[0] in ['rotate90', 'rotate180', 'flipH', 'flipV', 'transpose', 'invert', 'border', 'trim', 'translate', 'recolor', 'solid']:
        yield e[1]
    if e[0] == 'crop' and e[1][0] == 'largest' and e[1][1][0] == 'objects':
        yield e[1][1][1]
    for i, a in enumerate(e[1:], 1):
        for b in deletions(a):
            yield e[:i] + (b,) + e[i+1:]


def latent_library(k, rng):
    found = []
    seen = set()
    probes = [random_grid(random.Random(SEED + 30000 + i)) for i in range(20)]
    for kind in ['grid', 'color', 'int']:
        while sum(f['kind'] == kind for f in found) < 4:
            inner = stage(rng, X)
            if kind == 'color':
                e = node('recolor', inner, node(rng.choice(['red', 'blue', 'green'])), P)
            elif kind == 'int':
                e = node('translate', inner, P, node(rng.choice(['zero', 'one', 'minus_one'])))
            else:
                e = stage(rng, inner)
            if depth(canonical(e)) != 2 or key(e) in seen: continue
            # Latents must survive the novel object-valued context; e.g. border
            # immediately erased by crop is unsuitable, regardless of any learner.
            concrete = substitute(e, X, node('green' if kind == 'color' else 'one'))
            wrapped = node('crop', node('largest', node('objects', concrete)))
            def signature(q):
                return k.call('evaluate_batch', program=program(q), input_sets=[[x] for x in probes])['values']
            target = signature(wrapped)
            if any(signature(q) == target for q in deletions(wrapped)): continue
            p = abstraction(term(e, kind != 'grid'))
            if kind != 'grid': p = abstraction(p)
            tp = k.call('infer', grammar=grammar(), program=p)['type']
            seen.add(key(e))
            found.append({'id': f'F{len(found):02d}', 'kind': kind, 'expression': e,
                          'body': p, 'type': tp, 'program': invented(p)})
    return found


def generate(out=OUT, train_per_cell=8, test_per_cell=2):
    out = Path(out)
    if (out / 'benchmark_manifest.json').exists():
        raise RuntimeError('Refusing to overwrite a frozen benchmark. Use a new output directory.')
    rng = random.Random(SEED)
    probes = [random_grid(random.Random(SEED + 10000 + n)) for n in range(32)]
    # Independent probes for evaluating recovered libraries, not generator screening.
    recovery_probes = [random_grid(random.Random(SEED + 20000 + n)) for n in range(40)]
    train, test, private = [], [], {}
    rejected = collections.Counter()
    train_fp, test_fp, train_programs = set(), set(), set()
    inputs_identity = digest(probes)
    with Kernel() as k:
        latents = latent_library(k, rng)
        # Pools overlap across regimes; only frequency/concentration is manipulated.
        pools = {'low': latents, 'medium': [latents[i] for i in [0, 1, 4, 5, 6, 8, 9, 10]],
                 'high': [latents[i] for i in [0, 4, 5, 8]]}
        cache = {}
        def behavior(e):
            s = key(e)
            if s not in cache:
                ys = k.call('evaluate_batch', program=program(e), input_sets=[[x] for x in probes])['values']
                cache[s] = (digest(ys), ys)
            return cache[s]
        # Reference bank includes every well-typed generated single-stage transform.
        shallow = {}
        for i in range(600):
            e = canonical(stage(random.Random(SEED+i), X))
            fp, _ = behavior(e)
            shallow[fp] = depth(e)
        shallow[inputs_identity] = 0
        candidates = k.call('enumerate_budget', grammar=grammar(), request=REQUEST, limit=10000,
            max_states=500000, max_size=33, maximum_depth=14, upper_bound=100)
        for row in candidates['programs']:
            e = canonical(expression(row['program']))
            fp, _ = behavior(e)
            shallow[fp] = min(shallow.get(fp, 999), depth(e))
        print(f'behavior reference bank: {len(shallow)} fingerprints', flush=True)
        def use(f, x):
            p = node(rng.choice(['red', 'blue', 'green'])) if f['kind'] == 'color' else node(rng.choice(['one', 'minus_one']))
            return substitute(tupleize(f['expression']), x, p), {'latent': f['id'], 'parameter': p if f['kind'] != 'grid' else None}
        for split in ['train', 'test']:
            for regime in REGIMES:
                for d in DEPTHS:
                    kinds = ['train'] if split == 'train' else [t for t, minimum in [('I', 3), ('II', 3), ('III', 4), ('IV', 5)] if d >= minimum]
                    for transfer in kinds:
                        count = train_per_cell if split == 'train' else test_per_cell
                        for j in range(count):
                            for attempt in range(5000):
                                uses = []
                                share = regime != 'zero' and (split == 'test' or j < {'low': 2, 'medium': 4, 'high': train_per_cell}[regime])
                                e = X
                                if share:
                                    pool = pools[regime]
                                    if split == 'test':
                                        exposed = {u['latent'] for m in private.values() if m['split'] == 'train' and m['regime'] == regime for u in m['latent_uses']}
                                        pool = [f for f in pool if f['id'] in exposed]
                                    f = rng.choice(pool)
                                    if transfer == 'III':
                                        h = rng.choice([h for h in pool if h['id'] != f['id']])
                                        e, u = use(h, e); uses.append(u)
                                        e, u = use(f, e); uses.append(u)
                                    elif transfer == 'II':
                                        for _ in range(d - 2): e = stage(rng, e)
                                        e, u = use(f, e); uses.append(u)
                                    else:
                                        e, u = use(f, e); uses.append(u)
                                        if transfer == 'IV':
                                            e = node('crop', node('largest', node('objects', e)))
                                while depth(e) < d: e = stage(rng, e)
                                e = canonical(e)
                                if depth(e) != d:
                                    rejected['algebraic_depth_reduction'] += 1; continue
                                fp, ys = behavior(e)
                                if any(y is None for y in ys) or shallow.get(fp, 999) < d or len({key(y) for y in ys}) < 8:
                                    rejected['identity_constant_shallow'] += 1; continue
                                if any(behavior(canonical(q))[0] == fp for q in deletions(e)):
                                    rejected['single_deletion_equivalence'] += 1; continue
                                if split == 'test' and (fp in train_fp or fp in test_fp or key(e) in train_programs):
                                    rejected['split_or_test_duplicate'] += 1; continue
                                # Fresh examples independent of all screening and recovery probes.
                                xs = [random_grid(rng) for _ in range(6)]
                                yy = k.call('evaluate_batch', program=program(e), input_sets=[[x] for x in xs])['values']
                                if any(y is None for y in yy) or len({key(y) for y in yy}) < 3:
                                    rejected['degenerate_examples'] += 1; continue
                                break
                            else:
                                raise RuntimeError(f'Cannot populate {split}/{regime}/{d}/{transfer}/{j}; {rejected}')
                            name = f'{split}-{len(train) if split == "train" else len(test):04d}'
                            row = {'name': name, 'examples': [{'inputs': [x], 'output': y} for x, y in zip(xs, yy)]}
                            (train if split == 'train' else test).append(row)
                            (train_fp if split == 'train' else test_fp).add(fp)
                            if split == 'train': train_programs.add(key(e))
                            p = program(e)
                            assert k.call('infer', grammar=grammar(), program=p)['type'] == REQUEST
                            normal = k.call('beta', program=p)['program']
                            a = ast_stats(p)
                            private[name] = {'split': split, 'regime': regime, 'depth': d, 'transfer': transfer if regime != 'zero' else 'control',
                                'matched_transfer_stratum': transfer, 'ground_truth': p, 'expression': e,
                                'canonical_program': program(canonical(e)), 'fingerprint': fp, 'latent_uses': uses,
                                'ast_size': a[0], 'ast_depth': a[1], 'primitive_leaf_count': a[2], 'base_leaf_size': a[3],
                                'beta_normalized_size': ast_stats(normal)[0],
                                'behavioral_complexity': {'shorter_reference_bank_match': False, 'single_deletion_match': False,
                                    'interpretation': 'screened witnesses only; not a proof of global minimality'}}
                        print(f'generated {split} {regime} d={d} {transfer}', flush=True)
        for f in latents:
            f['reuse'] = {}
            for regime in REGIMES:
                tr = [m for m in private.values() if m['regime'] == regime and m['split'] == 'train']
                te = [m for m in private.values() if m['regime'] == regime and m['split'] == 'test']
                tr_use = [m for m in tr if any(u['latent'] == f['id'] for u in m['latent_uses'])]
                f['reuse'][regime] = {'training_occurrence_count': sum(sum(u['latent'] == f['id'] for u in m['latent_uses']) for m in tr),
                    'distinct_tasks': len(tr_use), 'distinct_program_contexts': len({key(m['ground_truth']) for m in tr_use}),
                    'heldout_reuse_count': sum(sum(u['latent'] == f['id'] for u in m['latent_uses']) for m in te)}
        payloads = {'train.json': train, 'test.json': test, 'latent_library.json': latents,
                    'evaluation_private.json': {'tasks': private, 'split_probes': probes, 'recovery_probes': recovery_probes}}
        for filename, value in payloads.items(): save(out / filename, value)
        validation = validate(train, test, private)
        save(out / 'split_validation.json', validation)
        stats = {'counts': dict(collections.Counter((m['split'] + '/' + m['regime'] + '/' + str(m['depth']) + '/' + m['transfer']) for m in private.values())),
            'rejections': dict(rejected), 'train_count': len(train), 'test_count': len(test),
            'infeasible_cells': {'I': [2], 'II': [2], 'III': [2, 3], 'IV': [2, 3, 4]},
            'infeasible_reason': 'Latents contain two operator stages; nested requires four; novel object-valued context adds objects/largest/crop.',
            'zero_regime': 'No deliberate latent use; matched depth/count strata, transfer labels are not asserted.',
            'behavior_reference_bank': {'candidates': len(candidates['programs']), 'fingerprints': len(shallow), 'stop_reason': candidates['stop_reason']},
            'complexity_caveat': 'd is operator-tree depth, AST depth is stored separately. Probe screening is finite, not semantic equivalence proof.'}
        save(out / 'structural_statistics.json', stats)
    return stats


def tupleize(e):
    return tuple(tupleize(x) if isinstance(x, (list, tuple)) else x for x in e)


def validate(train, test, private):
    def values(split, field): return {key(m[field]) for m in private.values() if m['split'] == split}
    checks = {field + '_overlap': len(values('train', field) & values('test', field)) for field in ['ground_truth', 'canonical_program', 'fingerprint']}
    # Example order is not task identity; reordering a complete I/O set cannot
    # turn leakage into a new task.
    io_key = lambda t: key(sorted(key(e) for e in t['examples']))
    checks['complete_io_overlap'] = len({io_key(t) for t in train} & {io_key(t) for t in test})
    def subterms(e):
        yield key(e)
        for a in e[1:]: yield from subterms(a)
    tr = {s for m in private.values() if m['split'] == 'train' for s in subterms(m['expression']) if len(s) > 15}
    te = {s for m in private.values() if m['split'] == 'test' for s in subterms(m['expression']) if len(s) > 15}
    checks['shared_nontrivial_subprograms'] = len(tr & te)
    checks['passed'] = all(v == 0 for name, v in checks.items() if name.endswith('_overlap')) and bool(tr & te)
    assert checks['passed'], checks
    return checks


def freeze(out=OUT):
    out = Path(out)
    path = out / 'benchmark_manifest.json'
    if path.exists(): raise RuntimeError('Already frozen')
    from .controlled_metrics import best_rewrite
    private = json.loads((out/'evaluation_private.json').read_text())
    latents = json.loads((out/'latent_library.json').read_text())
    with Kernel() as k:
        for m in private['tasks'].values():
            active = [f for f in latents if f['reuse'][m['regime']]['training_occurrence_count']]
            m['hidden_library_complexity'] = best_rewrite(k, m['ground_truth'], active)
    save(out/'evaluation_private.json', private)
    filenames = ['train.json', 'test.json', 'latent_library.json', 'evaluation_private.json', 'split_validation.json', 'structural_statistics.json', 'calibration.json']
    hashes = {name: hashlib.sha256((out/name).read_bytes()).hexdigest() for name in filenames}
    core = [* (ROOT/'faithful/haskell').glob('*.hs'), * (ROOT/'faithful/python').glob('*.py')]
    core = [p for p in core if not p.name.startswith('controlled')]
    manifest = {'status': 'permanently_frozen_before_nonbase_evaluation', 'dataset_seed': SEED,
        'training_seeds': [11, 23, 47], 'recognition_seeds': [1011, 1023, 1047], 'shuffle_seeds': [2011, 2023, 2047],
        'budgets': BUDGETS, 'ec_iterations': [0, 1, 2, 3, 5], 'sha256': hashes,
        'core_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in core},
        'self_hash': 'SHA256SUMS.json hashes this manifest; self-referential digests are not used.',
        'calibration_policy': 'Only A may be inspected before freeze. No regeneration after any B/C/D/control run.',
        'oracle_policy': 'O is an evaluation upper-bound diagnostic, not a fair learner comparison.'}
    save(path, manifest)
    save(out/'SHA256SUMS.json', {**hashes, 'benchmark_manifest.json': hashlib.sha256(path.read_bytes()).hexdigest()})


if __name__ == '__main__':
    print(generate())
