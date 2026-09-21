"""Evaluation-only diagnostics. Private latents never reach compression/training."""
import copy
from faithful.python.controlled_metrics import best_rewrite
from experiments.abstraction_learning.evaluation import frontier_support, recovery, arg_types, outputs, VALUE
from experiments.full_dreamcoder.exposure import behavioural_support
from .equations import term, wire, saturate


def er(support, k):
    return sum(v['count'] >= k for v in support.values()) / len(support) if support else None


def exposure_and_parameters(k, frontiers, names, grammar, latents, regime, probes):
    active = [f for f in latents if f['reuse'][regime]['deliberate_active']]
    syntactic = frontier_support(k, frontiers, names, active)
    cache = {}
    behavioural = behavioural_support(k, frontiers, names, active, probes, cache)
    variants = [[saturate(term(k.call('beta', program=e['program'])['program']))[0]
                 for e in f['entries']] for f in frontiers]
    usable = {}
    for f in active:
        latent_variants, _ = saturate(term(k.call('beta', program=f['body'])['program']))
        productions = [{'program': {'invented': wire(p)}, 'type': f['type']} for p in latent_variants]
        tasks = []
        for name, spaces in zip(names, variants):
            if any(best_rewrite(k, wire(q), productions)['delta_L'] > 0 for space in spaces for q in space):
                tasks.append(name)
        usable[f['id']] = {'tasks': tasks, 'count': len(tasks)}
    recovered = recovery(k, grammar, latents, regime, probes)
    hit_ids = set(recovered['metrics']['behavioral']['recovered_latents'])
    learned = recovered['learned_inventions']
    parameters = []
    for f in active:
        if not f['parameter_values']:
            continue
        exposed = {}
        for name in f['parameter_values']:
            single = copy.deepcopy(f)
            single['parameter_values'] = [name]
            # Cache keys include numerical value, so all parameter values are measured.
            support = behavioural_support(k, frontiers, names, [single], probes, cache)[f['id']]
            exposed[name] = support['tasks']
        specialized = []
        for j, inv in enumerate(learned):
            args, result = arg_types(inv['type'])
            fargs, fres = arg_types(f['type'])
            if len(args) != 1 or args[0].get('constructor') != 'grid' or result != fres:
                continue
            actual = outputs(k, inv['program'], args, probes, [None])
            if actual is None:
                continue
            for name in f['parameter_values']:
                if outputs(k, f['body'], fargs, probes, [VALUE[name]]) == actual:
                    specialized.append({'invention_index': j, 'parameter': name})
        parameters.append({'latent': f['id'], 'exposed_parameter_tasks': exposed,
                           'multiple_parameter_values_exposed': sum(bool(t) for t in exposed.values()) >= 2,
                           'generalised_recovered': f['id'] in hit_ids, 'specialised_matches': specialized})
    eligible = [p for p in parameters if p['multiple_parameter_values_exposed']]
    return {'syntactic': syntactic, 'behavioural': behavioural, 'equivalence_usable': usable,
            'er': {name: {f'ER@{n}': er(s, n) for n in (1, 2)}
                   for name, s in [('syntactic', syntactic), ('behavioural', behavioural), ('equivalence_usable', usable)]},
            'recovery': recovered, 'parameters': parameters,
            'parameterised_latent_recall': sum(p['generalised_recovered'] for p in parameters)/len(parameters) if parameters else None,
            'conditional_parametric_recovery': {'numerator': sum(p['generalised_recovered'] for p in eligible),
                                               'denominator': len(eligible),
                                               'probability': sum(p['generalised_recovered'] for p in eligible)/len(eligible) if eligible else None},
            'notes': ['Behavioural equality and parameter recovery are finite-probe witnesses, not equations.',
                      'Usable exposure = a shortening typed latent rewrite in the explicitly saturated E/R space.',
                      'Syntactic/behavioural/usable exposure use distinct training tasks; frontier ranks are not ER denominators.']}
