"""Sound equations on the frozen DSL's nonempty rectangular Grid domain.

No evaluator calls, probes, latent definitions or learned equations enter here.
Terms are immutable binary application trees; inventions remain opaque atoms.
"""
import json
from functools import lru_cache


def term(p):
    if 'application' in p:
        return ('app', *(term(x) for x in p['application']))
    if 'abstraction' in p:
        return ('lam', term(p['abstraction']))
    if 'primitive' in p:
        return ('prim', p['primitive'])
    if 'index' in p:
        return ('var', p['index'])
    return ('opaque', json.dumps(p, sort_keys=True))


def wire(t):
    tag = t[0]
    if tag == 'app':
        return {'application': [wire(t[1]), wire(t[2])]}
    if tag == 'lam':
        return {'abstraction': wire(t[1])}
    if tag == 'prim':
        return {'primitive': t[1]}
    if tag == 'var':
        return {'index': t[1]}
    return json.loads(t[1])


def call(name, *args):
    t = ('prim', name)
    for a in args:
        t = ('app', t, a)
    return t


def spine(t):
    args = []
    while t[0] == 'app':
        args.append(t[2])
        t = t[1]
    return (t[1] if t[0] == 'prim' else None), list(reversed(args))


def children(t):
    return t[1:] if t[0] in ('app', 'lam') else ()


def size(t):
    return 1 + sum(size(c) for c in children(t))


def cost(t):
    """Fixed, grammar-independent canonical cost, including deterministic tie-break."""
    return size(t), repr(t)


INVOLUTIONS = {'flipH', 'flipV', 'transpose', 'rotate180', 'invert'}
GEOMETRY = {'flipH', 'flipV', 'transpose', 'rotate90', 'rotate180'}
ZERO = ('prim', 'zero')


def root_reductions(t):
    n, a = spine(t)
    if n == 'identity' and len(a) == 1:
        yield a[0]
    if n in INVOLUTIONS | {'trim'} and len(a) == 1:
        m, b = spine(a[0])
        if m == n and len(b) == 1:
            yield a[0] if n == 'trim' else b[0]
    if n == 'translate' and len(a) == 3 and a[1:] == [ZERO, ZERO]:
        yield a[0]
    if n == 'recolor' and len(a) == 3 and a[1] == a[2]:
        yield a[0]
    q = t
    for _ in range(4):
        m, b = spine(q)
        if m != 'rotate90' or len(b) != 1:
            break
        q = b[0]
    else:
        yield q


@lru_cache(maxsize=100000)
def normal(t):
    cs = children(t)
    if cs:
        t = (t[0], *(normal(c) for c in cs))
    reductions = list(root_reductions(t))
    if not reductions:
        return t
    q = min(reductions, key=cost)
    assert size(q) < size(t)
    return normal(q)


def negate(t):
    names = {'zero': 'zero', 'one': 'minus_one', 'minus_one': 'one'}
    return ('prim', names[t[1]]) if t[0] == 'prim' and t[1] in names else None


def offsets(g, dr, dc, inverse=False):
    if g == 'transpose':
        return dc, dr
    if g == 'flipH':
        return dr, negate(dc)
    if g == 'flipV':
        return negate(dr), dc
    if g == 'rotate180':
        return negate(dr), negate(dc)
    return (negate(dc), dr) if inverse else (dc, negate(dr))


def root_equations(t):
    n, a = spine(t)
    if not a:
        return
    m, b = spine(a[0])
    # Position permutations commute with pointwise maps and symmetric padding/crop.
    arities = {'invert': 1, 'border': 1, 'trim': 1, 'recolor': 3, 'solid': 2}
    if n in GEOMETRY and len(a) == 1 and m in arities and len(b) == arities[m]:
        yield call(m, call(n, b[0]), *b[1:])
    if n in arities and len(a) == arities[n] and m in GEOMETRY and len(b) == 1:
        yield call(m, call(n, b[0], *a[1:]))
    # Two commuting axis reflections.
    if n in {'flipH', 'flipV'} and m in {'flipH', 'flipV'} and n != m and len(a) == len(b) == 1:
        yield call(m, call(n, b[0]))
    # Coordinate covariance preserves the clipping rectangle. Only expressible offsets.
    if n in GEOMETRY and len(a) == 1 and m == 'translate' and len(b) == 3:
        dr, dc = offsets(n, *b[1:])
        if dr is not None and dc is not None:
            yield call('translate', call(n, b[0]), dr, dc)
    if n == 'translate' and len(a) == 3 and m in GEOMETRY and len(b) == 1:
        dr, dc = offsets(m, *a[1:], inverse=True)
        if dr is not None and dc is not None:
            yield call(m, call('translate', b[0], dr, dc))


def steps(t, root_rule):
    yield from root_rule(t)
    for i, c in enumerate(children(t), 1):
        for q in steps(c, root_rule):
            yield (*t[:i], q, *t[i+1:])


def saturate(t, limit=512):
    """Exact finite E/R closure or explicit failure; never silently truncated.

    E preserves node count, RR decreases it, and the atom alphabet is finite.
    The cap is a representation resource bound, never a Wake budget change.
    """
    t = normal(t)
    seen, queue, proof = {t}, [t], []
    for p in queue:
        for raw in steps(p, root_equations):
            q = normal(raw)
            if q in seen:
                continue
            if len(seen) >= limit:
                raise RuntimeError(f'E/R closure exceeds {limit} terms; cell incomplete')
            seen.add(q)
            queue.append(q)
            proof.append((p, q))
    return tuple(sorted(seen, key=cost)), proof
