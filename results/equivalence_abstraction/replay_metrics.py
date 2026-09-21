"""Reproducible evaluation-only analysis of the paired FINAL-frontier diagnostic.

Run from the repository root with `python -m results.equivalence_abstraction.replay_metrics`.
This does not train, alter the frozen Phase 3 protocol, or claim held-out results.
"""
from pathlib import Path
from collections import defaultdict
import statistics
from faithful.compression.interface import BridgeKernel
from experiments.full_dreamcoder import run as phase2
from experiments.abstraction_learning.learner import read_json, save_json
from experiments.equivalence_abstraction.metrics import exposure_and_parameters


def main():
    root = Path(__file__).parent
    rows = []
    with BridgeKernel() as k:
        for p in sorted((root / 'replay').glob('*.json.gz')):
            r = read_json(p)
            seed, ts, arm = r['seed'], r['training_seed'], r['arm']
            out = root / 'replay_metrics' / p.name
            if out.exists():
                rows.append(read_json(out))
                continue
            data = phase2.instance_dir(seed)
            private = phase2.bench.read(data / 'private.json')
            latents = phase2.bench.read(data / 'latent_library.json')
            before = read_json(r['source'])
            result = r['result']
            m = exposure_and_parameters(k, result['rewritten_programs'], before['task_names'],
                                       result['grammar_updates'], latents, r['regime'], private['recovery_probes'])
            row = {'seed': seed, 'training_seed': ts, 'arm': arm, 'regime': r['regime'], 'diagnostic_only': True,
                   'source_sha256': r['source_sha256'], 'metrics': m,
                   'extra_inventions': len(result['invented_abstractions']),
                   'extra_delta_mdl': result['mdl_accounting']['delta_mdl'],
                   'training_solve_rate': before['wake']['solved']/len(before['task_names']),
                   'held_out': None}
            save_json(out, row)
            rows.append(row)
            print(seed, ts, arm, 'recall', m['recovery']['metrics']['behavioral']['recall'],
                  'param', m['parameterised_latent_recall'], flush=True)
    groups = defaultdict(list)
    for row in rows:
        groups[row['arm']].append(row)
    summary = {}
    def mean(values):
        xs = [x for x in values if x is not None]
        return statistics.mean(xs) if xs else None
    for arm, rs in sorted(groups.items()):
        ms = [r['metrics'] for r in rs]
        numerator = sum(m['conditional_parametric_recovery']['numerator'] for m in ms)
        denominator = sum(m['conditional_parametric_recovery']['denominator'] for m in ms)
        summary[arm] = {'cells': len(rs), 'new_inventions_total': sum(r['extra_inventions'] for r in rs),
                        'extra_delta_mdl_mean': mean(r['extra_delta_mdl'] for r in rs),
                        'er': {kind: {f'ER@{n}': mean(m['er'][kind][f'ER@{n}'] for m in ms) for n in (1, 2)}
                               for kind in ('syntactic', 'behavioural', 'equivalence_usable')},
                        'behavioural_recovery': {key: mean(m['recovery']['metrics']['behavioral'][key] for m in ms)
                                                 for key in ('precision', 'recall', 'f1')},
                        'parameterised_latent_recall': mean(m['parameterised_latent_recall'] for m in ms),
                        'conditional_parametric_recovery': {'numerator': numerator, 'denominator': denominator,
                                                           'probability': numerator/denominator if denominator else None}}
    save_json(root / 'replay_summary.json', {'diagnostic_only': True, 'complete': len(rows) == 36,
                                            'independent_benchmark_instances': 3, 'training_seeds_per_instance': 3,
                                            'arms': summary, 'held_out': 'not evaluated for this extra-compression diagnostic'}, compact=False)


if __name__ == '__main__':
    main()
