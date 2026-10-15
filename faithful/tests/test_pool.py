"""KernelPool (parent-side kernel processes) and the persistent task-parallel WakePool.

Both must leave every result identical to the serial path; they only change
which process answers a request and when."""
from dataclasses import replace
import threading
import time

import pytest
import torch

from faithful.lib import (ast, Kernel, KernelPool, KernelError, ExploreCompress, ECConfig, SearchConfig, DreamConfig,
                          RecognitionConfig, NoCompression, OriginalCompressor, StitchCompressor, accounting)
from faithful.lib.recognition import Recognition as PooledRecognition
from faithful.python.recognition import Recognition as FrozenRecognition
from faithful.lib.domains import ArithmeticDomain, ListDomain, arithmetic_tasks, list_tasks, smoke_domain
from faithful.lib.ast import primitive as P, abstraction as L, application as A, index as I


def cfg(workers=1, **kw):
    return ECConfig(rounds=2, workers=workers, search=SearchConfig(limit=40, max_states=2000, top_k=3),
                    dream=DreamConfig(draws=4), recognition=RecognitionConfig(steps=5), **kw)


def arith(n=4):
    d = ArithmeticDomain(); a, b = arithmetic_tasks(d)
    return d, (a + b)[:n]


def grid_tasks(d):
    xs = [[[0, 1, 2], [2, 3, 0]], [[1, 0], [3, 2], [0, 3]]]
    return [d.unary_task("color-complement", [(x, [[0 if c == 0 else 4 - c for c in row] for row in x]) for x in xs]),
            d.unary_task("horizontal-reflection", [(x, [list(reversed(row)) for row in x]) for x in xs])]

# ---- KernelPool ---------------------------------------------------------------------------------

def test_kernel_pool_map_preserves_order_and_spreads_over_processes():
    with KernelPool(3) as pool:
        assert len(set(pool.pids)) == 3 and pool.alive and pool.supports("vs_compress")
        seen = set()
        def job(k, n):
            seen.add(k._local.kernel.pid); time.sleep(0.05)   # hold the borrowed process long enough to overlap
            return k.beta(A(L(I(0)), P(f"p{n}")))
        out = pool.map(job, range(9))
        assert out == [P(f"p{n}") for n in range(9)]
        assert len(seen) == 3                                 # every process did work
        assert pool.beta(P("x")) == P("x") and pool.calls == 10
        # A nested map runs on the borrowed process rather than waiting for the pool.
        nested = pool.map(lambda k, xs: k.map(lambda k2, x: k2.beta(P(x)), xs), [["a", "b"], ["c"], []])
        assert nested == [[P("a"), P("b")], [P("c")], []]
        # Exceptions propagate; the pool stays usable.
        def bad(k, n):
            if n == 2: raise KernelError("boom")
            return k.beta(P(str(n)))
        with pytest.raises(KernelError, match="boom"): pool.map(bad, range(5))
        assert pool.map(lambda k, n: k.beta(P(str(n))), range(2)) == [P("0"), P("1")]
    assert not pool.alive
    with pytest.raises(ValueError): KernelPool(0)
    with pytest.raises(ValueError): KernelPool(1.5)


def test_kernel_pool_trace_files_are_per_process(tmp_path):
    with KernelPool(2, trace=tmp_path / "t.jsonl") as pool:
        pool.map(lambda k, p: k.beta(p), [P("a"), P("b"), P("c")])
        assert pool.trace == tmp_path / "t.jsonl"
    assert sorted(f.name for f in tmp_path.iterdir()) == ["t.kernel-0.jsonl", "t.kernel-1.jsonl"]


def test_kernel_pool_single_kernel_equivalence():
    """rescore_all, recognition summaries and MDL accounting through a pool equal the serial Kernel."""
    d = ListDomain(); a, b = list_tasks(d); tasks = a + b
    with Kernel() as k, KernelPool(3) as pool:
        serial = ExploreCompress(d, k, OriginalCompressor(), cfg())
        pooled = ExploreCompress(d, pool, OriginalCompressor(), cfg())
        hs, hp = serial.run(tasks), pooled.run(tasks)
        for a, b in zip(hs, hp):
            assert a.frontiers == b.frontiers and a.grammar == b.grammar
            assert a.dream == b.dream and a.recognition_losses == b.recognition_losses and a.solved == b.solved
        fs = hs[-1].frontiers
        assert serial.rescore_all(fs, serial.grammar) == pooled.rescore_all(fs, pooled.grammar)
        assert accounting(k, serial.grammar, fs) == accounting(pool, pooled.grammar, fs)
        assert pool.calls > 0 and all(kk.calls > 0 for kk in pool.kernels)


def test_pooled_recognition_matches_frozen_training():
    d = smoke_domain(); tasks = grid_tasks(d)
    with Kernel() as k, KernelPool(2) as pool:
        ec = ExploreCompress(d, k, NoCompression(), ECConfig(rounds=1, seed=7, dream=DreamConfig(draws=3), recognition=RecognitionConfig(steps=1),
                                                           search=SearchConfig(upper_bound=4.5, maximum_depth=7, limit=1000, max_size=1000, max_states=60000)))
        h = ec.run(tasks)[0]
        data = [(d.features(t), f) for t, f in zip(tasks, h.frontiers) if f["entries"]]
        assert data
        torch.manual_seed(0); frozen = FrozenRecognition(h.grammar, feature_dim=d.feature_dim)
        torch.manual_seed(0); pooled = PooledRecognition(h.grammar, feature_dim=d.feature_dim)
        assert frozen.fit_frontiers(k, data, steps=20, seed=3) == pooled.fit_frontiers(pool, data, steps=20, seed=3)
        assert pooled.fit_frontiers(pool, [], steps=5) == []

# ---- persistent WakePool -------------------------------------------------------------------------

def slow_wake(*args):
    from faithful.lib.ec import generic_wake
    time.sleep(0.3)
    return generic_wake(*args)


def test_wake_pool_persists_across_solves_and_rounds():
    d, tasks = arith(4)
    with Kernel() as k, ExploreCompress(d, k, NoCompression(), cfg(workers=2), wake=slow_wake) as ec:
        first = ec.solve(tasks); pool = ec._pool
        assert pool is not None and pool.alive
        second = ec.solve(tasks)
        assert ec._pool is pool                                       # reused, not rebuilt
        pids = {(t.worker_pid, t.kernel_pid) for _, t in first}
        assert len(pids) == 2 and pids == {(t.worker_pid, t.kernel_pid) for _, t in second}
        history = ec.run(tasks)                                       # rounds reuse the same pool too
        assert ec._pool is pool and len(history) == 2
        assert {t.worker_pid for r in history for t in r.traces} == {p for p, _ in pids}
        # Grammar and search budget are read from each job, not frozen at pool creation.
        ec.config = replace(ec.config, search=replace(ec.config.search, limit=7))
        small = ec.solve(tasks)
        assert all(t.enumerated == 7 for _, t in small) and ec._pool is pool
        ec.close(); assert ec._pool is None and not pool.alive
        again = ec.solve(tasks)                                       # a closed driver rebuilds on demand
        assert ec._pool is not pool and [f for f, _ in again] == [f for f, _ in small]
    assert ec._pool is None


def test_wake_pool_survives_job_failure_and_pool_kernel_parent():
    d, tasks = arith(3)
    def flaky(ec, task, grammar, search_grammar):
        from faithful.lib.ec import generic_wake
        if task.name.endswith("1") and ec.config.search.limit == 40:
            raise RuntimeError("intentional worker failure")
        return generic_wake(ec, task, grammar, search_grammar)
    with KernelPool(2) as pool, ExploreCompress(d, pool, NoCompression(), cfg(workers=2), wake=flaky) as ec:
        with pytest.raises(RuntimeError, match="intentional"): ec.solve(tasks)
        p = ec._pool; assert p is not None and p.alive                 # a raised job does not break the pool
        ec.config = replace(ec.config, search=replace(ec.config.search, limit=41))   # job config travels with each job
        out = ec.solve(tasks)
        assert ec._pool is p and len(out) == 3
        assert all(t.kernel_pid not in pool.pids for _, t in out)      # workers never share the parent's processes
        assert pool.beta(P("z")) == P("z")
