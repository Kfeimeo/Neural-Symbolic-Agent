"""Congruence-closed e-classes and first-order e-class anti-unification.

The finite equation system allows explicit closure construction. Enodes share
children; AU walks pairs of e-classes, never a canonical extracted corpus.
Binders are boundaries: AU considers first-order bodies and closes every free
input/parameter. This avoids moving a term across a binder without a proof.
"""
from itertools import product
from .equations import children, normal, saturate, spine, call, wire, cost


class EGraph:
    def __init__(self):
        self.parent, self.nodes, self.terms, self.memo = [], [], {}, {}
        self.completed = set()

    def find(self, c):
        while c != self.parent[c]:
            self.parent[c] = self.parent[self.parent[c]]
            c = self.parent[c]
        return c

    def union(self, a, b):
        a, b = sorted((self.find(a), self.find(b)))
        if a != b:
            self.parent[b] = a
        return a

    def add(self, t):
        t = normal(t)
        if t in self.terms:
            return self.find(self.terms[t])
        name, args = spine(t)
        if name is not None and args:
            node = (('call', name), tuple(self.add(a) for a in args))
        elif children(t):
            node = ((t[0],), tuple(self.add(a) for a in children(t)))
        else:
            node = (t, ())
        if node not in self.memo:
            self.memo[node] = len(self.parent)
            self.parent.append(len(self.parent))
            self.nodes.append(node)
        c = self.memo[node]
        self.terms[t] = c
        return self.find(c)

    def space(self, t):
        terms, proof = saturate(t)
        root = self.add(terms[0])
        for q in terms:
            self.union(root, self.add(q))
        # Saturate subexpressions too, so equal children have the same class.
        pending = list(self.terms)
        for q in pending:
            if q not in self.completed:
                self.completed.add(q)
                qs, _ = saturate(q)
                for v in qs:
                    self.union(self.add(q), self.add(v))
        self.rebuild()
        return self.find(root), terms, proof

    def rebuild(self):
        while True:
            memo, changed = {}, False
            for i, (op, cs) in enumerate(self.nodes):
                node = op, tuple(self.find(c) for c in cs)
                if node in memo and self.find(i) != self.find(memo[node]):
                    self.union(i, memo[node])
                    changed = True
                memo[node] = self.find(i)
            if not changed:
                break
        self.classes = {}
        for i, (op, cs) in enumerate(self.nodes):
            self.classes.setdefault(self.find(i), set()).add((op, tuple(self.find(c) for c in cs)))

    def first_order_classes(self, terms):
        result = set()
        def walk(t):
            if t[0] == 'lam':
                walk(t[1])
                return
            if not has_lambda(t) and t[0] == 'app':
                result.add(self.find(self.terms[normal(t)]))
            name, args = spine(t)
            for c in (args if name is not None else children(t)):
                walk(c)
        for t in terms:
            walk(t)
        return result


def has_lambda(t):
    return t[0] == 'lam' or any(has_lambda(c) for c in children(t))


def holes(p):
    if p[0] == 'hole':
        return {p}
    return set().union(*(holes(c) for c in p[2])) if p[0] == 'node' else set()


def anti_unify(graph, a, b, max_parameters=2, limit=256):
    memo = {}
    def go(a, b, visiting):
        key = a, b
        h = ('hole', a, b)
        if key in visiting:
            return (h,)
        if key in memo:
            return memo[key]
        out = {h}
        for (op, cs), (other, ds) in product(sorted(graph.classes[a]), sorted(graph.classes[b])):
            if op != other or len(cs) != len(ds) or op[0] in ('lam', 'var'):
                continue
            for combo in product(*(go(c, d, visiting | {key}) for c, d in zip(cs, ds))):
                p = ('node', op, combo)
                if len(holes(p)) <= max_parameters:
                    out.add(p)
                if len(out) > limit:
                    raise RuntimeError('AU pair exceeds pattern cap; cell incomplete')
        memo[key] = tuple(sorted(out, key=repr))
        return memo[key]
    return go(graph.find(a), graph.find(b), set())


def close_pattern(p):
    slots = {}
    def build(q):
        if q[0] == 'hole':
            return ('var', slots.setdefault(q, len(slots)))
        _, op, cs = q
        args = [build(c) for c in cs]
        return call(op[1], *args) if op[0] == 'call' else (*op, *args)
    t = build(p)
    for _ in slots:
        t = ('lam', t)
    return {'invented': wire(t)}
