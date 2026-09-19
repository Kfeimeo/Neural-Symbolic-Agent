"""Cost pilot using I/O-only smoke tasks; never selects benchmark by B/C/D wins."""
import json
import random
import time
import torch
from .kernel import Kernel, ROOT, abstraction, application, primitive, index
from .grid import grammar, Task, features, REQUEST
from .toy import search, learning_frontier, save
from .ec import dream
from .recognition import Recognition


def profile():
    torch.set_num_threads(1)
    g = grammar()
    xs = [[[0, 1, 2], [3, 0, 1]], [[1, 0], [2, 3], [0, 2]]]
    result = {'scope': 'independent smoke cost pilot, not benchmark calibration', 'timings': {}}
    with Kernel() as k:
        t = time.perf_counter()
        for _ in range(100):
            k.call('infer', grammar=g, program=abstraction(index(0)))
        result['timings']['ipc_infer_100_seconds'] = time.perf_counter() - t
        tasks = []
        for n, ops in enumerate([['border'], ['invert'], ['border', 'invert'], ['border', 'flipH']]):
            p = index(0)
            for op in ops:
                p = application(primitive(op), p)
            ys = k.call('evaluate_batch', program=abstraction(p), input_sets=[[x] for x in xs])['values']
            tasks.append(Task(str(n), [([x], y) for x, y in zip(xs, ys)]))
        for budget in [100, 1000, 10000]:
            rows, seconds = search(k, tasks, g, g, dict(limit=budget, max_states=500000,
                max_size=33, maximum_depth=14, upper_bound=100, top_k=3))
            result['timings'][f'search_{budget}_seconds'] = seconds
            result[f'search_{budget}'] = [{key: r[key] for key in ('enumerated_nodes', 'expanded_states', 'stop_reason', 'first_solution_nodes')} for r in rows]
        fs = [learning_frontier(r) for r in rows if r['solutions']]
        t = time.perf_counter()
        c = k.call('compress', grammar=g, frontiers=fs, arity=1, iterations=1)
        result['timings']['compression_4_frontiers_seconds'] = time.perf_counter() - t
        result['compression'] = c['history']
        t = time.perf_counter()
        pairs, stats = dream(k, g, REQUEST, xs, random.Random(71), draws=64)
        result['timings']['dream_64_seconds'] = time.perf_counter() - t
        result['dream'] = stats
        t = time.perf_counter()
        torch.manual_seed(71)
        model = Recognition(g)
        model.fit_frontiers(k, pairs + [(features(t), f) for t, f in zip(tasks, fs)], steps=100, seed=71)
        result['timings']['recognition_100_steps_seconds'] = time.perf_counter() - t
    save(ROOT / 'faithful/results/controlled/profile.json', result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    profile()
