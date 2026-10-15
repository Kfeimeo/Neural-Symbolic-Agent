"""KernelPool (parent-side kernel processes) and the persistent task-parallel WakePool.

Both must leave every result identical to the serial path; they only change
which process answers a request and when."""
from dataclasses import replace
import threading
import time

import pytest
import torch

from faithful.lib import (ast, Kernel, KernelPool, KernelError, Progress, NullProgress, ExploreCompress, ECConfig, SearchConfig, DreamConfig,
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


# ---- independent dreams ----------------------------------------------------------------------------

def dcfg(workers=1, seeding="independent", draws=12):
    return ECConfig(rounds=1, seed=11, workers=workers, search=SearchConfig(limit=40, max_states=2000, top_k=3),
                    dream=DreamConfig(draws=draws, seeding=seeding), recognition=RecognitionConfig(steps=3))


def test_dream_seeding_validation_and_sequential_is_serial():
    with pytest.raises(ValueError): DreamConfig(seeding="random")
    d, tasks = arith(3)
    with Kernel() as k, ExploreCompress(d, k, NoCompression(), dcfg(workers=2, seeding="sequential"), wake=slow_wake) as ec:
        ec.solve(tasks); pool = ec._pool
        before = pool._pool._processes and set(pool._pool._processes)  # workers already started by Wake
        data, stats = ec.dream(ec.grammar, tasks, __import__("random").Random(0))
        assert stats["seeding"] == "sequential" and stats["draws"] == 12 and stats["accepted"] == len(data)
        assert set(pool._pool._processes) == before                     # no dream work went to the pool


def test_independent_dreams_equal_across_serial_pool_and_workers():
    """Serial Kernel, KernelPool threads and worker processes produce the same dreams and training."""
    import random
    d, tasks = arith(4)
    with Kernel() as k, KernelPool(2) as pool:
        serial = ExploreCompress(d, k, NoCompression(), dcfg())
        threaded = ExploreCompress(d, pool, NoCompression(), dcfg())
        with ExploreCompress(d, k, NoCompression(), dcfg(workers=2)) as procs:
            g = serial.grammar
            a = serial.dream(g, tasks, random.Random(5)); b = threaded.dream(g, tasks, random.Random(5)); c = procs.dream(g, tasks, random.Random(5))
            assert a[1] == b[1] == c[1] and a[1]["accepted"] > 1
            for (fa, xa), (fb, xb), (fc, xc) in zip(a[0], b[0], c[0]):
                assert torch.equal(fa, fb) and torch.equal(fa, fc) and xa == xb == xc
            assert all(kk.calls > 0 for kk in pool.kernels)             # the pool spread the draws
            hs, ht, hp = serial.run(tasks)[0], threaded.run(tasks)[0], procs.run(tasks)[0]
            assert hs.dream == ht.dream == hp.dream and hs.recognition_losses == ht.recognition_losses == hp.recognition_losses
            assert hs.frontiers == ht.frontiers == hp.frontiers
            # draws are independent of their batch: fewer draws keep the common prefix exactly
            short = ExploreCompress(d, k, NoCompression(), dcfg(draws=5)).dream(g, tasks, random.Random(5))
            assert len(short[0]) <= 5 and [x for _, x in short[0]] == [x for _, x in a[0]][:len(short[0])]


def test_independent_dreams_on_kernel_domain_through_workers():
    d = smoke_domain(); tasks = grid_tasks(d)
    cfg = ECConfig(rounds=1, seed=7, workers=2, dream=DreamConfig(draws=6, seeding="independent"), recognition=RecognitionConfig(steps=2),
                   search=SearchConfig(upper_bound=4.5, maximum_depth=7, limit=1000, max_size=1000, max_states=60000))
    with Kernel() as k:
        with ExploreCompress(d, k, OriginalCompressor(arity=0), replace(cfg, workers=1)) as one, \
             ExploreCompress(d, k, OriginalCompressor(arity=0), cfg) as two:
            h1, h2 = one.run(tasks)[0], two.run(tasks)[0]
            assert h1.dream == h2.dream and h1.dream["accepted"] > 0 and h1.recognition_losses == h2.recognition_losses


# ---- progress --------------------------------------------------------------------------------------

class Counting(NullProgress):
    """Records every phase with its final count, for assertions."""
    def __init__(self): self.phases = []; self.rounds = []; self.closed = False
    def phase_started(self, name, total=None, unit=""): self.phases.append([name, total, 0])
    def advance(self, n=1): self.phases[-1][2] += n
    def round_finished(self, index, note=""): self.rounds.append(index)
    def close(self): self.closed = True


def test_progress_counts_every_phase_and_leaves_results_unchanged():
    import io
    d = ListDomain(); a, b = list_tasks(d); tasks = a + b
    cfg = dcfg(workers=2, draws=7)
    with Kernel() as k, KernelPool(2) as pool:
        plain = ExploreCompress(d, k, OriginalCompressor(), replace(cfg, workers=1)).run(tasks)
        for kern, w in ((k, 1), (pool, 1), (k, 2)):          # serial, KernelPool threads, worker processes
            counting = Counting()
            with ExploreCompress(d, kern, OriginalCompressor(), replace(cfg, workers=w), progress=counting) as ec:
                h = ec.run(tasks); ec.solve(b)
            assert [(r.frontiers, r.grammar, r.dream, r.recognition_losses) for r in h] == [(r.frontiers, r.grammar, r.dream, r.recognition_losses) for r in plain]
            names = [n for n, _, _ in counting.phases]
            assert names == ["wake", "rescore", "compress", "dream", "summaries", "recognition", "solve"]
            assert all(done == total for _, total, done in counting.phases if total is not None)
            by = {n: (t, d_) for n, t, d_ in counting.phases}
            assert by["wake"] == (5, 5) and by["dream"] == (7, 7) and by["recognition"] == (3, 3) and by["solve"] == (2, 2)
            assert by["rescore"][0] == by["rescore"][1] > 0
            assert counting.rounds == [0] and counting.closed
        # Text output on a non-terminal stream: finished lines only, no carriage returns.
        out = io.StringIO()
        with ExploreCompress(d, k, NoCompression(), replace(cfg, workers=1), progress=Progress(stream=out, enabled=True)) as ec:
            ec.run(tasks)
        text = out.getvalue()
        assert "\r" not in text and "explore-compress: 1 round(s), 5 task(s)" in text
        assert "[round 1/1] wake" in text and "5/5 tasks" in text and "round 1/1 done in" in text and text.rstrip().endswith("s")
        assert Progress(stream=io.StringIO()).enabled is False     # auto mode is silent off a terminal


def test_progress_terminal_rendering_and_eta():
    import io
    class Tty(io.StringIO):
        def isatty(self): return True
    out = Tty(); p = Progress(stream=out, min_interval=0)   # redraw on every advance
    assert p.enabled and p.animate
    p.run_started(2, 3); p.round_started(0, 2)
    p.phase_started("wake", 4, "tasks"); p.advance(); p.advance(2); p.phase_finished("solved 2/3")
    p.phase_started("compress"); p.phase_finished("+1 invention(s)")
    p.round_finished(0, "solved 2/3"); p.close()
    text = out.getvalue()
    assert "\r[round 1/2] wake        |" in text and "3/4 tasks" in text and "eta" in text
    import re
    assert re.search(r"wake\s+3/4 tasks\s+[\d.]+s  solved 2/3\n", text) and "+1 invention(s)" in text
    assert "round 1/2 done in" in text and "est. remaining" in text and text.rstrip().endswith("s")
