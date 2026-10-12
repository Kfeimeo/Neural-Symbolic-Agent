# Minimal grid DSL smoke check

The `63613498.json` result is a development diagnostic, not a controlled
generalization comparison. This task's test answer was already inspected.

Command:

```powershell
python -m arc_tsl.experiments.run_grid --task data/arc/training/63613498.json --out results/arc_tsl/grid_shapes_v1/63613498.json --max-cost 12 --max-states 300000 --time-limit 30
```

Outcome: no training-consistent program at maximum cost 12; 21,363 expanded
states, 12,259 evaluated programs, about 1.007 seconds fit wall time. The search
ended on cost, not state/time limits. No program was selected and no test
prediction was produced. This does not establish that the rule is inexpressible
or that the extension improves generalization. The JSON includes source hashes.

Validation: 80 ARC-TSL tests passed, including 12 new tests covering extraction
views, nonzero backgrounds, transparent holes vs opaque black, clipping,
geometry equivalences, invalid dimensions, typed composition, bounded search,
and synthesized paint / variable-size canvas programs on unseen synthetic
inputs. Restricted-grammar integration tests establish composability, not real
ARC search coverage. Full-language canvas search is also tested.
