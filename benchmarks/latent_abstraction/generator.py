"""Latent-abstraction benchmark generator (evaluation-private; never imported by a learner).

Every benchmark instance is generated from a hidden library of latent abstractions
F = {F_1, ..., F_n}.  Tasks are programs that compose latent abstractions with base
DSL operators.  Learners receive only ``train.json`` / ``test.json`` containing task
names and (input, output) examples.  ``latent_library.json`` and ``private.json``
hold the latent definitions, generator programs and labels; they exist only for
evaluation.

Three independent variables are controlled:

* program complexity: requested operator-tree depth d in 2..8 (training) and
  3..8 (held-out); AST depth/size, primitive counts and effective complexity
  under the true latent library are measured and stored;
* abstraction reuse: cohorts ``zero`` (independently generated base programs),
  ``low`` (2/8 of training tasks per depth draw from a 12-latent pool),
  ``medium`` (4/8 from a 6-latent pool) and ``high`` (8/8 from a 4-latent pool);
* compositional generalization: held-out programs never coincide with training
  programs (canonical program, behaviour fingerprint and complete I/O sets are
  disjoint) but share latent sub-structure.  Held-out transfer types are
  I ``g(F_i(.))`` with an outer operator never applied to F_i in training,
  II ``F_i(h(.))`` with an inner operator never feeding F_i in training and
  III ``F_i(F_j(.))`` with an ordered latent pair never nested in training
  (nested tasks keep at least one further base stage, so III starts at depth 5).

The symbolic core (``faithful/haskell``, ``faithful/python``) is used unchanged
through its JSON protocol.  Canonicalization, deletion witnesses and AST
statistics are imported from the earlier controlled generator so that the
recovery metrics of the two benchmarks share one canonical form.
"""
import argparse
import collections
import hashlib
import json
import random
import time
from pathlib import Path

from faithful.python.kernel import Kernel, ROOT, abstraction, application, primitive, index, invented
from faithful.python.grid import grammar, REQUEST
from faithful.python.controlled_data import (canonical, deletions, depth, node, X, P, substitute, term,
                                             program, expression, ast_stats, key, digest, tupleize)

DATA = ROOT / 'benchmarks' / 'latent_abstraction' / 'data'
REGIMES = ['zero', 'low', 'medium', 'high']
TRAIN_DEPTHS = list(range(2, 9))
TEST_DEPTHS = list(range(3, 9))
TRAIN_PER_DEPTH = 8
TEST_PER_CELL = 2
TRANSFERS = ['I', 'II', 'III']
MIN_NESTED_DEPTH = 5          # nested transfer III keeps at least one base stage besides the two latents
MAX_ATTEMPTS = 4000           # per task; a cell that cannot be populated is recorded, not silently dropped
SHARE = {'zero': 0, 'low': 2, 'medium': 4, 'high': 8}          # latent-using tasks among 8 per training depth
POOL_SIZE = {'zero': 0, 'low': 12, 'medium': 6, 'high': 4}      # nested pools: high < medium < low
NEST_PROBABILITY = {'zero': 0., 'low': 0., 'medium': .3, 'high': .4}
LATENT_PLAN = {'grid': [2, 2, 2, 3], 'color': [2, 2, 2, 3], 'int': [2, 2, 2, 3]}
UNARY = ['rotate90', 'rotate180', 'flipH', 'flipV', 'transpose', 'invert', 'border', 'trim']
COLORS = ['red', 'blue', 'green']
INTS = ['zero', 'one', 'minus_one']
PARAMETER_VALUES = {'grid': [None], 'color': COLORS, 'int': INTS}
EXAMPLES_PER_TASK = 6
SPLIT_PROBES = 32
RECOVERY_PROBES = 40
DEFAULT_SEEDS = [101, 202, 303]
BUDGETS = [100, 300, 1000, 3000, 10000, 30000]
CALIBRATION_SEARCH = dict(max_states=3000000, max_size=33, maximum_depth=14, upper_bound=100, top_k=3)


def save(path, value, compact=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, sort_keys=False, separators=(',', ':')) if compact else json.dumps(value, indent=1)
    path.write_text(text, encoding='utf8')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def random_grid(rng):
    h, w = rng.randint(3, 7), rng.randint(3, 8)
    density = rng.choice([.18, .4, .7, 1.])
    g = [[rng.randint(1, 3) if rng.random() < density else 0 for _ in range(w)] for _ in range(h)]
    if rng.random() < .35:
        g = [[0] * (w + 2)] + [[0] + row + [0] for row in g] + [[0] * (w + 2)]
    return g


def stage(rng, e, parameter=None, ops=None):
    """Apply one random base operator stage to expression ``e``.

    ``parameter=P`` places the latent parameter slot into the chosen stage.
    """
    op = rng.choice(ops or UNARY + ['translate', 'recolor', 'solid'])
    if op == 'translate':
        if parameter is P:
            other = node(rng.choice(INTS))
            return node(op, e, P, other) if rng.random() < .5 else node(op, e, other, P)
        while True:
            a, b = rng.choice(INTS), rng.choice(INTS)
            if not (a == 'zero' and b == 'zero'):
                return node(op, e, node(a), node(b))
    if op == 'recolor':
        if parameter is P:
            other = node(rng.choice(COLORS))
            return node(op, e, other, P) if rng.random() < .5 else node(op, e, P, other)
        a, b = rng.sample(COLORS, 2)
        return node(op, e, node(a), node(b))
    if op == 'solid':
        return node(op, e, P if parameter is P else node(rng.choice(COLORS)))
    return node(op, e)


def head(e):
    return e[0]


def subtrees(e, path=()):
    """Yield (path, subtree) for every node of a tuple expression, root first."""
    yield path, e
    for i, a in enumerate(e[1:], 1):
        if isinstance(a, tuple):
            yield from subtrees(a, path + (i,))


def match_pattern(pattern, target, path=()):
    """Match a latent expression (X = wildcard) against ``target``.

    Returns ``(bound_argument, bound_path)`` or ``None``.  All wildcard positions
    must bind the same argument.
    """
    if pattern == X:
        return target, path
    if not isinstance(target, tuple) or len(pattern) != len(target) or pattern[0] != target[0]:
        return None
    bound = None
    for i, (a, b) in enumerate(zip(pattern[1:], target[1:]), 1):
        if not isinstance(a, tuple):
            return None
        if X in _leaves(a):
            r = match_pattern(a, b, path + (i,))
            if r is None or (bound is not None and bound[0] != r[0]):
                return None
            bound = r
        elif a != b:
            return None
    return bound


def _leaves(e):
    if len(e) == 1:
        return [e]
    return [l for a in e[1:] for l in _leaves(a)]


def latent_patterns(latent):
    """Concrete (parameter instantiated) patterns of one latent, valid parameter values only."""
    e = tupleize(latent['expression'])
    for v in latent['parameter_values'] or [None]:
        yield v, (e if v is None else substitute(e, X, node(v)))


def find_uses(e, latents):
    """Detect every syntactic occurrence of a latent in canonical expression ``e``.

    Each use records the latent id, parameter value, outer operator (parent operator
    or 'root'), inner head operator ('$x' for the raw input) and, when the argument
    is itself a latent occurrence, that latent id.  Detection is purely syntactic on
    the canonical expression, so incidental occurrences are found as well.
    """
    parents = {}
    for path, s in subtrees(e):
        for i, a in enumerate(s[1:], 1):
            if isinstance(a, tuple):
                parents[path + (i,)] = s[0]
    roots = collections.defaultdict(list)
    for path, s in subtrees(e):
        for f in latents:
            for v, pattern in latent_patterns(f):
                r = match_pattern(pattern, s, path)
                if r is not None:
                    roots[path].append((f['id'], v, r[0], r[1]))
    uses = []
    for path, s in subtrees(e):
        for fid, v, arg, arg_path in roots.get(path, []):
            inner = sorted({g for g, _, _, _ in roots.get(arg_path, [])})
            uses.append({'latent': fid, 'parameter': v, 'outer': parents.get(path, 'root'),
                         'inner': head(arg), 'inner_latent': inner[0] if inner else None, 'path': list(path)})
    return uses


def instantiate(latent, e, rng):
    v = None if latent['kind'] == 'grid' else rng.choice(latent['parameter_values'])
    return substitute(tupleize(latent['expression']), e, node(v) if v is not None else None), v


def latent_body(e, kind):
    body = abstraction(term(e, kind != 'grid'))
    return abstraction(body) if kind != 'grid' else body


class Screen:
    """Behavioural screening shared by latents and tasks (finite witnesses, not proofs)."""

    def __init__(self, k, probes):
        self.k, self.probes, self.cache = k, probes, {}
        self.identity = digest(probes)

    def behavior(self, e):
        s = key(e)
        if s not in self.cache:
            ys = self.k.call('evaluate_batch', program=program(e), input_sets=[[x] for x in self.probes])['values']
            self.cache[s] = (None if any(y is None for y in ys) else digest(ys), ys)
        return self.cache[s]

    def reference_bank(self, seed, size=600, limit=10000):
        shallow = {self.identity: 0}
        for i in range(size):
            e = canonical(stage(random.Random(seed + i), X))
            fp, _ = self.behavior(e)
            if fp is not None:
                shallow[fp] = min(shallow.get(fp, 999), depth(e))
        rows = self.k.call('enumerate_budget', grammar=grammar(), request=REQUEST, limit=limit,
                           max_states=500000, max_size=33, maximum_depth=14, upper_bound=100)
        for row in rows['programs']:
            try:
                e = canonical(expression(row['program']))
            except (ValueError, KeyError):
                continue
            fp, _ = self.behavior(e)
            if fp is not None:
                shallow[fp] = min(shallow.get(fp, 999), depth(e))
        return shallow, {'candidates': len(rows['programs']), 'stop_reason': rows['stop_reason'], 'fingerprints': len(shallow)}

    def degenerate(self, e, d, shallow, minimum_distinct=8):
        fp, ys = self.behavior(e)
        if fp is None:
            return 'evaluation_failure'
        if fp == self.identity or len({key(y) for y in ys}) < minimum_distinct:
            return 'identity_or_constant'
        if shallow.get(fp, 999) < d:
            return 'shallower_reference_equivalent'
        for q in deletions(e):
            qfp, _ = self.behavior(canonical(q))
            if qfp == fp:
                return 'single_deletion_equivalent'
        return None


def latent_library(k, rng, screen, shallow):
    """Automatically generate the hidden latent library of one benchmark instance.

    Each latent is a canonical composition of ``depth`` base operator stages with an
    optional colour/integer parameter slot.  A latent is accepted only when, for at
    least two parameter values (all values for grid latents), its instantiation is
    non-degenerate: not identity/near-constant on the split probes, not behaviourally
    equal to a shallower reference program, not equal to any single-stage deletion,
    and behaviourally distinct from every previously accepted latent instantiation.
    Degenerate parameter values are dropped from the latent's value set.
    """
    found, seen, fingerprints = [], set(), set()
    for kind, depths in LATENT_PLAN.items():
        for d_target in depths:
            for attempt in range(20000):
                e = X
                slot = rng.randrange(d_target)
                for i in range(d_target):
                    if kind != 'grid' and i == slot:
                        e = stage(rng, e, parameter=P, ops=['recolor', 'solid'] if kind == 'color' else ['translate'])
                    else:
                        e = stage(rng, e)
                e = canonical(e)
                if depth(e) != d_target or key(e) in seen:
                    continue
                values, signatures = [], []
                for v in PARAMETER_VALUES[kind]:
                    concrete = e if v is None else canonical(substitute(e, X, node(v)))
                    if depth(concrete) != d_target or screen.degenerate(concrete, d_target, shallow):
                        continue
                    values.append(v)
                    signatures.append(screen.behavior(concrete)[0])
                needed = 1 if kind == 'grid' else 2
                if len(values) < needed or len(set(signatures)) < needed or fingerprints & set(signatures):
                    continue
                seen.add(key(e))
                fingerprints |= set(signatures)
                body = latent_body(e, kind)
                tp = k.call('infer', grammar=grammar(), program=body)['type']
                found.append({'id': f'F{len(found):02d}', 'kind': kind, 'depth': d_target, 'expression': e,
                              'body': body, 'type': tp, 'program': invented(body),
                              'parameter_values': values if kind != 'grid' else None,
                              'leaf_size': ast_stats(body)[3], 'attempts': attempt + 1})
                break
            else:
                raise RuntimeError(f'Could not generate a {kind} latent of depth {d_target}')
    return found


def contexts_of(private, split, regime):
    """Training contexts of every latent in one cohort: outer operators, inner heads, nested pairs/triples."""
    ctx = {'outer': collections.defaultdict(set), 'inner': collections.defaultdict(set), 'nested': set(), 'nested_triples': set()}
    for meta in private.values():
        if meta['split'] != split or meta['regime'] != regime:
            continue
        for u in meta['latent_uses']:
            ctx['outer'][u['latent']].add(u['outer'])
            ctx['inner'][u['latent']].add(u['inner'])
            if u['inner_latent']:
                ctx['nested'].add((u['latent'], u['inner_latent']))
                ctx['nested_triples'].add((u['latent'], u['inner_latent'], u['outer']))
    return ctx


def pick(rng, candidates, usage, keyfn=lambda f: f['id']):
    """Least-used candidate (ties broken at random) so that reuse counts stay balanced inside a pool."""
    return min(candidates, key=lambda c: (usage[keyfn(c)], rng.random()))


def build(rng, d, regime, split, transfer, pool, exposed, contexts, usage):
    """Construct one uncanonicalized expression and the deliberate latent plan.

    ``usage`` counts deliberate uses per latent in the current split/cohort; the
    least-used eligible latent is chosen so that every pool member receives about
    the same number of deliberate occurrences (the reuse manipulation is then the
    pool size and the share of latent-using tasks, not sampling noise).
    """
    plan = {'latents': [], 'novelty': None}
    if split == 'train':
        if not pool:
            e = X
            for _ in range(d):
                e = stage(rng, e)
            return e, plan
        eligible = [f for f in pool if f['depth'] <= d]
        if not eligible:
            return None, plan
        f = pick(rng, eligible, usage)
        partners = [g for g in pool if g['id'] != f['id'] and f['depth'] + g['depth'] <= d]
        if partners and rng.random() < NEST_PROBABILITY[regime]:
            g = pick(rng, partners, usage)
            e = X
            for _ in range(rng.randint(0, d - f['depth'] - g['depth'])):
                e = stage(rng, e)
            e, vg = instantiate(g, e, rng)
            e, vf = instantiate(f, e, rng)
            plan['latents'] = [(f['id'], vf), (g['id'], vg)]
        else:
            e = X
            for _ in range(rng.randint(0, d - f['depth'])):
                e = stage(rng, e)
            e, vf = instantiate(f, e, rng)
            plan['latents'] = [(f['id'], vf)]
        while depth(e) < d:
            e = stage(rng, e)
        return e, plan
    if transfer == 'control':
        e = X
        for _ in range(d):
            e = stage(rng, e)
        return e, plan
    outer_ctx, inner_ctx, nested_ctx = contexts['outer'], contexts['inner'], contexts['nested']
    ops = UNARY + ['translate', 'recolor', 'solid']
    if transfer == 'I':
        eligible = [f for f in exposed if f['depth'] + 1 <= d and set(ops) - outer_ctx[f['id']]]
        if not eligible:
            return None, plan
        f = pick(rng, eligible, usage)
        e = X
        for _ in range(rng.randint(0, d - f['depth'] - 1)):
            e = stage(rng, e)
        e, vf = instantiate(f, e, rng)
        e = stage(rng, e, ops=sorted(set(ops) - outer_ctx[f['id']]))
        while depth(e) < d:
            e = stage(rng, e)
        plan['latents'] = [(f['id'], vf)]
        plan['novelty'] = 'outer operator unseen with this latent in training'
        return e, plan
    if transfer == 'II':
        eligible = [f for f in exposed if f['depth'] + 1 <= d and set(ops) - inner_ctx[f['id']]]
        if not eligible:
            return None, plan
        f = pick(rng, eligible, usage)
        e = X
        for _ in range(rng.randint(0, d - f['depth'] - 1)):
            e = stage(rng, e)
        e = stage(rng, e, ops=sorted(set(ops) - inner_ctx[f['id']]))
        e, vf = instantiate(f, e, rng)
        while depth(e) < d:
            e = stage(rng, e)
        plan['latents'] = [(f['id'], vf)]
        plan['novelty'] = 'inner operator unseen feeding this latent in training'
        return e, plan
    if transfer == 'III':
        pairs = [(f, g) for f in exposed for g in exposed if f['id'] != g['id'] and f['depth'] + g['depth'] < d]
        novel = [(f, g) for f, g in pairs if (f['id'], g['id']) not in nested_ctx]
        chosen = novel or pairs
        if not chosen:
            return None, plan
        f, g = min(chosen, key=lambda pair: (usage[pair[0]['id']] + usage[pair[1]['id']], rng.random()))
        e = X
        for _ in range(rng.randint(0, d - f['depth'] - g['depth'])):
            e = stage(rng, e)
        e, vg = instantiate(g, e, rng)
        e, vf = instantiate(f, e, rng)
        while depth(e) < d:
            e = stage(rng, e)
        plan['latents'] = [(f['id'], vf), (g['id'], vg)]
        plan['novelty'] = 'ordered latent pair never nested in training' if novel else 'pair nested in training; (pair, outer operator) triple unseen'
        return e, plan
    raise ValueError(transfer)


def plan_satisfied(uses, plan, transfer, contexts):
    """Check that deliberate latent uses survived canonicalization and satisfy the novelty condition."""
    by_latent = collections.defaultdict(list)
    for u in uses:
        by_latent[u['latent']].append(u)
    for fid, v in plan['latents']:
        if not any(u['parameter'] == v for u in by_latent[fid]):
            return False
    if transfer in ('train', 'control'):
        return True
    fid, v = plan['latents'][0]
    if transfer == 'I':
        return any(u['parameter'] == v and u['outer'] != 'root' and u['outer'] not in contexts['outer'][fid] for u in by_latent[fid])
    if transfer == 'II':
        return any(u['parameter'] == v and u['inner'] != '$x' and u['inner'] not in contexts['inner'][fid] for u in by_latent[fid])
    gid, vg = plan['latents'][1]
    if plan['novelty'].startswith('ordered'):
        return any(u['parameter'] == v and u['inner_latent'] == gid for u in by_latent[fid])
    return any(u['parameter'] == v and u['inner_latent'] == gid and (fid, gid, u['outer']) not in contexts['nested_triples'] for u in by_latent[fid])


def generate_instance(seed, out, train_per_depth=TRAIN_PER_DEPTH, test_per_cell=TEST_PER_CELL):
    out = Path(out)
    if (out / 'manifest.json').exists():
        raise RuntimeError(f'{out} is frozen; refusing to regenerate a benchmark instance')
    started = time.perf_counter()
    rng = random.Random(seed)
    probes = [random_grid(random.Random(seed * 1000 + 10000 + n)) for n in range(SPLIT_PROBES)]
    recovery_probes = [random_grid(random.Random(seed * 1000 + 20000 + n)) for n in range(RECOVERY_PROBES)]
    rejected = collections.Counter()
    train, test, private = [], [], {}
    with Kernel() as k:
        screen = Screen(k, probes)
        shallow, bank = screen.reference_bank(seed * 1000 + 30000)
        print(f'seed {seed}: reference bank {bank}', flush=True)
        latents = latent_library(k, rng, screen, shallow)
        pools = {'zero': []}
        pools['low'] = latents[:POOL_SIZE['low']]
        by_kind = {kind: [f for f in latents if f['kind'] == kind] for kind in LATENT_PLAN}
        pools['medium'] = [f for kind in LATENT_PLAN for f in by_kind[kind][:2]]
        pools['high'] = [by_kind['grid'][0], by_kind['grid'][1], by_kind['color'][0], by_kind['int'][0]]
        assert len(pools['medium']) == POOL_SIZE['medium'] and len(pools['high']) == POOL_SIZE['high']
        train_fp, test_fp, train_programs, test_programs = set(), set(), set(), set()
        for split in ['train', 'test']:
            for regime in REGIMES:
                contexts = contexts_of(private, 'train', regime)
                exposed_ids = {u['latent'] for m in private.values() if m['split'] == 'train' and m['regime'] == regime for u in m['latent_uses']}
                exposed = [f for f in pools[regime] if f['id'] in exposed_ids]
                depths = TRAIN_DEPTHS if split == 'train' else TEST_DEPTHS
                usage = collections.Counter()
                for d in depths:
                    if split == 'train':
                        cells = [('train', train_per_depth)]
                    elif regime == 'zero':
                        cells = [('control', test_per_cell * (2 + (d >= MIN_NESTED_DEPTH)))]
                    else:
                        cells = [(t, test_per_cell) for t in TRANSFERS if t != 'III' or d >= MIN_NESTED_DEPTH]
                    for transfer, count in cells:
                        for j in range(count):
                            share = split == 'test' and regime != 'zero' or (split == 'train' and j < SHARE[regime])
                            for attempt in range(MAX_ATTEMPTS):
                                e, plan = build(rng, d, regime, split, transfer if split == 'test' else 'train',
                                                pools[regime] if share else [], exposed, contexts, usage)
                                if e is None:
                                    rejected['unpopulated_cell_no_eligible_latent'] += 1
                                    break
                                e = canonical(e)
                                if depth(e) != d:
                                    rejected['algebraic_depth_reduction'] += 1
                                    continue
                                uses = find_uses(e, latents)
                                if not plan_satisfied(uses, plan, transfer if split == 'test' else 'train', contexts):
                                    rejected['latent_not_intact_or_context_seen'] += 1
                                    continue
                                reason = screen.degenerate(e, d, shallow)
                                if reason:
                                    rejected[reason] += 1
                                    continue
                                fp, ys = screen.behavior(e)
                                if split == 'test' and (fp in train_fp or fp in test_fp or key(e) in train_programs or key(e) in test_programs):
                                    rejected['split_or_test_duplicate'] += 1
                                    continue
                                xs = [random_grid(rng) for _ in range(EXAMPLES_PER_TASK)]
                                yy = k.call('evaluate_batch', program=program(e), input_sets=[[x] for x in xs])['values']
                                if any(y is None for y in yy) or len({key(y) for y in yy}) < 3:
                                    rejected['degenerate_examples'] += 1
                                    continue
                                break
                            else:
                                rejected[f'unpopulated_cell_{split}/{regime}/{d}/{transfer}'] += 1
                                print(f'seed {seed}: could not populate {split}/{regime}/{d}/{transfer}/{j} within {MAX_ATTEMPTS} attempts', flush=True)
                                continue
                            if e is None:
                                continue
                            name = f'{split}-{regime}-{len(train) if split == "train" else len(test):04d}'
                            (train if split == 'train' else test).append({'name': name, 'examples': [{'inputs': [x], 'output': y} for x, y in zip(xs, yy)]})
                            (train_fp if split == 'train' else test_fp).add(fp)
                            (train_programs if split == 'train' else test_programs).add(key(e))
                            p = program(e)
                            assert k.call('infer', grammar=grammar(), program=p)['type'] == REQUEST
                            a = ast_stats(p)
                            deliberate = {(fid, v) for fid, v in plan['latents']}
                            for fid, _ in plan['latents']:
                                usage[fid] += 1
                            for u in uses:
                                u['deliberate'] = (u['latent'], u['parameter']) in deliberate
                            private[name] = {'split': split, 'regime': regime, 'depth': d,
                                             'transfer': transfer if split == 'test' else 'train',
                                             'novelty': plan['novelty'], 'ground_truth': p, 'expression': e,
                                             'fingerprint': fp, 'latent_uses': uses,
                                             'deliberate_latent_use': bool(plan['latents']),
                                             'ast_size': a[0], 'ast_depth': a[1], 'primitive_leaf_count': a[2], 'base_leaf_size': a[3],
                                             'beta_normalized_size': ast_stats(k.call('beta', program=p)['program'])[0]}
                    print(f'seed {seed}: {split} {regime} d={d} done ({len(train)} train, {len(test)} test)', flush=True)
        for f in latents:
            f['reuse'] = {}
            f['contexts'] = {}
            for regime in REGIMES:
                rows = {}
                for split in ['train', 'test']:
                    ms = [m for m in private.values() if m['regime'] == regime and m['split'] == split]
                    uses = [(name, u) for name, m in private.items() if m['regime'] == regime and m['split'] == split for u in m['latent_uses'] if u['latent'] == f['id']]
                    rows[split] = {'occurrence_count': len(uses), 'deliberate_occurrence_count': sum(u['deliberate'] for _, u in uses),
                                   'distinct_tasks': len({n for n, _ in uses}),
                                   'distinct_contexts': len({(u['outer'], u['inner']) for _, u in uses}),
                                   'task_count': len(ms)}
                f['reuse'][regime] = {'training_occurrence_count': rows['train']['occurrence_count'],
                                      'training_deliberate_count': rows['train']['deliberate_occurrence_count'],
                                      'training_distinct_tasks': rows['train']['distinct_tasks'],
                                      'training_distinct_contexts': rows['train']['distinct_contexts'],
                                      'test_occurrence_count': rows['test']['occurrence_count'],
                                      'test_distinct_tasks': rows['test']['distinct_tasks'],
                                      'active': rows['train']['occurrence_count'] + rows['test']['occurrence_count'] > 0,
                                      'deliberate_active': rows['train']['deliberate_occurrence_count'] + rows['test']['deliberate_occurrence_count'] > 0,
                                      'test_deliberate_count': rows['test']['deliberate_occurrence_count'],
                                      'in_pool': any(g['id'] == f['id'] for g in pools[regime])}
                f['contexts'][regime] = [{'task': name, 'split': m['split'], 'depth': m['depth'], 'transfer': m['transfer'],
                                          'outer': u['outer'], 'inner': u['inner'], 'inner_latent': u['inner_latent'],
                                          'parameter': u['parameter'], 'deliberate': u['deliberate']}
                                         for name, m in private.items() if m['regime'] == regime for u in m['latent_uses'] if u['latent'] == f['id']]
        validation = validate(train, test, private)
        stats = {'seed': seed, 'train_count': len(train), 'test_count': len(test),
                 'counts': dict(collections.Counter(f"{m['split']}/{m['regime']}/{m['depth']}/{m['transfer']}" for m in private.values())),
                 'rejections': dict(rejected), 'reference_bank': bank,
                 'latent_depths': {f['id']: f['depth'] for f in latents},
                 'pools': {r: [f['id'] for f in pools[r]] for r in REGIMES},
                 'incidental_uses': {r: sum(1 for m in private.values() if m['regime'] == r for u in m['latent_uses'] if not u['deliberate']) for r in REGIMES},
                 'nested_training_pairs': {r: sorted({f"{u['latent']}>{u['inner_latent']}" for m in private.values() if m['regime'] == r and m['split'] == 'train' for u in m['latent_uses'] if u['inner_latent']}) for r in REGIMES},
                 'novelty_levels': dict(collections.Counter(f"{m['regime']}/{m['transfer']}/{m['novelty']}" for m in private.values() if m['split'] == 'test' and m['regime'] != 'zero')),
                 'generation_seconds': time.perf_counter() - started,
                 'notes': ['d is operator-tree depth of the expanded base program; AST statistics are stored separately.',
                           'Screening uses finite probes and single-deletion witnesses; it is not a proof of minimality.',
                           'Latent occurrence counts include incidental (non-deliberate) syntactic occurrences.',
                           'The zero cohort has no pool; any detected occurrence there is incidental.']}
    save(out / 'train.json', train)
    save(out / 'test.json', test)
    save(out / 'latent_library.json', latents)
    save(out / 'private.json', {'seed': seed, 'tasks': private, 'split_probes': probes, 'recovery_probes': recovery_probes})
    save(out / 'split_validation.json', validation)
    save(out / 'structural_statistics.json', stats)
    return stats


def validate(train, test, private):
    def values(split, field):
        return {key(m[field]) for m in private.values() if m['split'] == split}
    checks = {field + '_overlap': len(values('train', field) & values('test', field)) for field in ['ground_truth', 'expression', 'fingerprint']}
    io_key = lambda t: key(sorted(key(e) for e in t['examples']))
    checks['complete_io_overlap'] = len({io_key(t) for t in train} & {io_key(t) for t in test})

    def subterms(e):
        yield key(e)
        for a in e[1:]:
            if isinstance(a, tuple):
                yield from subterms(a)
    for regime in REGIMES:
        tr = {s for m in private.values() if m['split'] == 'train' and m['regime'] == regime for s in subterms(tupleize(m['expression'])) if len(s) > 15}
        te = {s for m in private.values() if m['split'] == 'test' and m['regime'] == regime for s in subterms(tupleize(m['expression'])) if len(s) > 15}
        checks[f'shared_nontrivial_subprograms_{regime}'] = len(tr & te)
        heldout = {u['latent'] for m in private.values() if m['split'] == 'test' and m['regime'] == regime for u in m['latent_uses'] if u['deliberate']}
        exposed = {u['latent'] for m in private.values() if m['split'] == 'train' and m['regime'] == regime for u in m['latent_uses']}
        checks[f'heldout_latents_exposed_in_training_{regime}'] = heldout <= exposed
    checks['passed'] = all(v == 0 for n, v in checks.items() if n.endswith('_overlap')) and all(checks[f'heldout_latents_exposed_in_training_{r}'] for r in REGIMES) \
        and all(checks[f'shared_nontrivial_subprograms_{r}'] > 0 for r in ['low', 'medium', 'high'])
    assert checks['passed'], checks
    return checks


def load_tasks(path):
    """Learner-facing loader: names and examples only."""
    from faithful.python.grid import Task
    data = read(path)
    assert all(set(t) == {'name', 'examples'} for t in data)
    return [Task(t['name'], [(e['inputs'], e['output']) for e in t['examples']]) for t in data]


def calibrate(out):
    """A-only calibration of the uniform base grammar; permitted before freezing."""
    from faithful.python.toy import search
    out = Path(out)
    if (out / 'manifest.json').exists():
        raise RuntimeError('Already frozen')
    tasks = load_tasks(out / 'train.json') + load_tasks(out / 'test.json')
    meta = read(out / 'private.json')['tasks']
    with Kernel() as k:
        rows, seconds = search(k, tasks, grammar(), grammar(), dict(CALIBRATION_SEARCH, limit=max(BUDGETS)))
    rates = []
    for split in ['train', 'test']:
        for regime in REGIMES:
            for d in range(2, 9):
                rr = [r for r in rows if meta[r['name']]['split'] == split and meta[r['name']]['regime'] == regime and meta[r['name']]['depth'] == d]
                if rr:
                    rates.append({'split': split, 'regime': regime, 'depth': d, 'count': len(rr),
                                  'rates': {str(n): sum(r['first_solution_nodes'] is not None and r['first_solution_nodes'] <= n for r in rr) / len(rr) for n in BUDGETS}})
    record = {'configuration': 'A0: uniform base grammar, no learning', 'seconds': seconds, 'options': CALIBRATION_SEARCH, 'budgets': BUDGETS,
              'rows': [{'name': r['name'], 'first_solution_nodes': r['first_solution_nodes'], 'enumerated_nodes': r['enumerated_nodes'],
                        'expanded_states': r['expanded_states'], 'stop_reason': r['stop_reason']} for r in rows],
              'depth_budget_rates': rates,
              'policy': 'Only the uniform base grammar is inspected before the freeze. The benchmark is frozen regardless of these rates and never regenerated after any learned-library run.'}
    save(out / 'calibration.json', record)
    return record


def freeze(out, core_globs=('faithful/haskell/*.hs', 'faithful/python/*.py', 'faithful/compression/*.hs')):
    from faithful.python.controlled_metrics import best_rewrite
    out = Path(out)
    if (out / 'manifest.json').exists():
        raise RuntimeError('Already frozen')
    private = read(out / 'private.json')
    latents = read(out / 'latent_library.json')
    with Kernel() as k:
        for name, m in private['tasks'].items():
            active = [f for f in latents if f['reuse'][m['regime']]['deliberate_active']]
            r = best_rewrite(k, m['ground_truth'], active)
            m['effective_complexity'] = {'base_leaf_size': r['base_leaf_size'], 'effective_leaf_size': r['effective_leaf_size'],
                                         'delta_L': r['delta_L'], 'base_ast_depth': r['base_ast_depth'],
                                         'effective_ast_depth': r['effective_ast_depth'], 'delta_d': r['delta_d'],
                                         'witness': r['witness'], 'rewrite_space': r['rewrite_space']}
    save(out / 'private.json', private)
    files = ['train.json', 'test.json', 'latent_library.json', 'private.json', 'split_validation.json', 'structural_statistics.json', 'calibration.json']
    hashes = {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in files}
    core = sorted(p for g in core_globs for p in ROOT.glob(g) if not p.name.startswith('controlled'))
    manifest = {'status': 'frozen_before_any_learned_library_run', 'seed': private['seed'], 'sha256': hashes,
                'core_sha256': {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in core},
                'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'policy': ['Only the uniform base grammar (A0) was inspected before freezing.',
                           'No task, latent or split is regenerated or tuned after any learned-library method is run.',
                           'Learners read train.json/test.json only; latent_library.json and private.json are evaluation-only.']}
    save(out / 'manifest.json', manifest)
    save(out / 'SHA256SUMS.json', {**hashes, 'manifest.json': hashlib.sha256((out / 'manifest.json').read_bytes()).hexdigest()})
    return manifest


def verify(out):
    out = Path(out)
    manifest = read(out / 'manifest.json')
    for name, expected in read(out / 'SHA256SUMS.json').items():
        if hashlib.sha256((out / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Frozen benchmark file changed: {out / name}')
    for name, expected in manifest['core_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Fixed core changed after freeze: {name}')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['generate', 'calibrate', 'freeze', 'verify', 'all'])
    parser.add_argument('--seeds', type=int, nargs='+', default=DEFAULT_SEEDS)
    parser.add_argument('--data', type=Path, default=DATA)
    args = parser.parse_args()
    for seed in args.seeds:
        out = args.data / f'seed_{seed}'
        if args.command in ['generate', 'all'] and not (out / 'train.json').exists():
            print(json.dumps(generate_instance(seed, out), indent=1))
        if args.command in ['calibrate', 'all'] and not (out / 'calibration.json').exists():
            record = calibrate(out)
            print(json.dumps(record['depth_budget_rates'], indent=1))
        if args.command in ['freeze', 'all'] and not (out / 'manifest.json').exists():
            freeze(out)
            print(f'frozen {out}')
        if args.command == 'verify':
            verify(out)
            print(f'verified {out}')


if __name__ == '__main__':
    main()
