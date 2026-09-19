"""Post-freeze evaluator audits. Never repairs or regenerates frozen tasks."""
import argparse
import collections
from .kernel import Kernel
from .controlled_run import OUT, read, verify
from .controlled_data import digest, key
from .toy import save


def audit(out):
    verify(out)
    private = read(out/'evaluation_private.json')
    latent = read(out/'latent_library.json')
    probes = private['recovery_probes']
    groups = collections.defaultdict(list)
    fingerprints = {'train': set(), 'test': set()}
    with Kernel() as k:
        for f in latent:
            params = [None] if f['kind'] == 'grid' else [1, 2, 3] if f['kind'] == 'color' else [-1, 0, 1]
            sets = [[x] if p is None else [x, p] for p in params for x in probes]
            values = k.call('evaluate_batch', program=f['body'], input_sets=sets)['values']
            groups[(f['kind'], digest(values))].append(f['id'])
        for name, m in private['tasks'].items():
            values = k.call('evaluate_batch', program=m['ground_truth'], input_sets=[[x] for x in probes])['values']
            fingerprints[m['split']].add(digest(values))
    result = {'scope': 'post-freeze evaluation-only audit, no dataset changes',
        'latent_behavioral_equivalence_classes': list(groups.values()),
        'latent_duplicate_classes': [g for g in groups.values() if len(g)>1],
        'additional_recovery_probe_train_test_overlap': len(fingerprints['train'] & fingerprints['test']),
        'probe_count': len(probes), 'note': 'Finite-probe equivalence classes, not a formal semantic quotient.'}
    io_key = lambda task: key(sorted(key(e) for e in task['examples']))
    result['complete_io_order_invariant_overlap'] = len({io_key(t) for t in read(out/'train.json')} & {io_key(t) for t in read(out/'test.json')})
    save(out/'postfreeze_audit.json', result)
    print(result, flush=True)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=type(OUT), default=OUT)
    audit(p.parse_args().output)
