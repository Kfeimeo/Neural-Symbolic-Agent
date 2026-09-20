"""Behavioural frontier exposure: does a solved training frontier *compute* a latent, in any syntactic form?

The Phase 1 exposure criterion (``frontier_support``) is syntactic modulo beta: a
latent counts as exposed in a task when the exact rewrite can shorten a frontier
program with it.  Latents are often found in an equivalent but different form
(commuting stages, permuted offsets, instantiated parameters), which the
inverse-beta candidate generator of the compressor cannot merge.  This module
measures the complementary notion: a frontier program *behaviourally exposes* a
latent ``F`` when it contains a subexpression ``s`` and a strict sub-subexpression
``t`` (possibly the task input itself) such that ``s(x) == F(t(x), v)`` on the 40
recovery probes for some valid parameter value ``v`` (grid latents have no
parameter).  This covers latents applied to the input and to an inner context.
The comparison is on finite probes, so it is a witness, not a proof.
Evaluation-only: reads the latent library and the probes.
"""
import json

from experiments.abstraction_learning.evaluation import arg_types, VALUE


def subtrees_with_input(p):
    """Application subtrees of a beta-normal request body that reference the task input (index 0)."""
    found = []
    body = p['abstraction'] if 'abstraction' in p else p   # strip the request lambda: index 0 is the task input

    def uses_input(q, depth=0):
        if 'index' in q:
            return q['index'] == depth
        if 'application' in q:
            return any(uses_input(x, depth) for x in q['application'])
        if 'abstraction' in q:
            return uses_input(q['abstraction'], depth + 1)
        return False

    def walk(q, depth=0):
        if 'application' in q:
            if depth == 0 and uses_input(q):
                found.append(q)
            for x in q['application']:
                walk(x, depth)
        elif 'abstraction' in q:
            walk(q['abstraction'], depth + 1)
    walk(body)
    return found


def signature(values):
    return None if any(v is None for v in values) else tuple(json.dumps(v) for v in values)


def behavioural_support(k, frontiers, task_names, active, probes, cache=None):
    """Per active latent: training tasks whose frontier holds s, t with s(x) == F(t(x), v) on the probes for some v."""
    cache = {} if cache is None else cache
    probe_sets = [[x] for x in probes]
    var_key = json.dumps({'index': 0}, sort_keys=True)
    latent_values = {}
    for f in active:
        f_args, _ = arg_types(f['type'])
        latent_values[f['id']] = ([VALUE[v] for v in f['parameter_values']] if f['parameter_values'] else [None], len(f_args))

    def outputs_of(key, program):
        if key not in cache:
            cache[key] = signature(k.call('evaluate_batch', program=program, input_sets=probe_sets)['values'])
        return cache[key]

    def latent_on(f, inner_key, inner_sig, v):
        """F(t(x), v) on the probes, cached per (latent, inner subtree, value)."""
        ck = ('latent', f['id'], inner_key, v)
        if ck not in cache:
            inputs = [[json.loads(g)] + ([] if v is None else [v]) for g in inner_sig]
            cache[ck] = signature(k.call('evaluate_batch', program=f['body'], input_sets=inputs)['values'])
        return cache[ck]

    result = {f['id']: {'tasks': [], 'witnesses': []} for f in active}
    for name, fr in zip(task_names, frontiers):
        subtrees = {}
        for e in fr['entries']:
            normal = k.call('beta', program=e['program'])['program']
            for s in subtrees_with_input(normal):
                subtrees.setdefault(json.dumps(s, sort_keys=True), s)
        if not subtrees:
            continue
        sigs = {key: outputs_of(key, {'abstraction': s}) for key, s in subtrees.items()}
        sigs[var_key] = outputs_of(var_key, {'abstraction': {'index': 0}})
        for f in active:
            values, arity = latent_values[f['id']]
            if arity > 2:
                continue
            hit = None
            for s_key, s_sig in sigs.items():
                if s_key == var_key or s_sig is None:
                    continue
                for t_key, t_sig in sigs.items():
                    if t_sig is None or t_key == s_key or (t_key != var_key and t_key not in s_key):
                        continue
                    for i, v in enumerate(values):
                        if latent_on(f, t_key, t_sig, v) == s_sig:
                            hit = (s_key, t_key, i)
                            break
                    if hit:
                        break
                if hit:
                    break
            if hit:
                result[f['id']]['tasks'].append(name)
                result[f['id']]['witnesses'].append({'task': name, 'subexpression': json.loads(hit[0]), 'inner': json.loads(hit[1]), 'parameter_index': hit[2]})
    for f in active:
        result[f['id']]['count'] = len(result[f['id']]['tasks'])
    return result
