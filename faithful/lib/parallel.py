"""Spawn-safe task parallelism, with one persistent Kernel per worker.

:class:`WakePool` owns a ``ProcessPoolExecutor`` that outlives a single
``solve``: :class:`~faithful.lib.ec.ExploreCompress` creates it on the first
parallel Wake and reuses it for every later Wake and round, so the Python
interpreter, the torch import and the worker's Kernel are started once per
worker rather than once per call. ``ExploreCompress.close()`` (or its context
manager) releases it.

Only trusted, in-process Domain/Wake objects are cloudpickled, once, when the
pool starts. Grammars and the search configuration travel with every job, so a
pool created in round 0 is still correct in round 5. Models and live Kernel
handles stay in the parent. Independent Dream draws (``DreamConfig.seeding=
"independent"``) run on the same workers. Compression and recognition remain
in the parent.
"""
import multiprocessing
from multiprocessing.util import Finalize
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from dataclasses import replace
import os
from pathlib import Path

import cloudpickle

_ec = None


def _initialize(payload, options):
    global _ec
    import torch
    from .ec import ExploreCompress
    from .kernel import Kernel
    torch.set_num_threads(1)
    domain, config, wake = cloudpickle.loads(payload)
    if options.trace:
        path = Path(options.trace)
        options.trace = str(path.with_name(f"{path.stem}.worker-{os.getpid()}{path.suffix}"))
    kernel = Kernel(options=options)
    Finalize(None, kernel.close, exitpriority=10)
    _ec = ExploreCompress(domain, kernel, config=config, wake=wake)


def _run(job):
    task, grammar, search_grammar, config = job
    _ec.config = config
    _ec.grammar = grammar
    frontier, trace = _ec.wake(task, grammar, search_grammar)
    trace = replace(trace, worker_pid=os.getpid(), kernel_pid=_ec.kernel.process.pid)
    return frontier, trace


def dream_chunk(job):
    """Independent Dream draws ``(n, seed)`` on this worker's Domain and Kernel."""
    import random
    from .ec import dream_draw
    grammar, requests, tasks, fuel, draws = job
    return [dream_draw(_ec.domain, _ec.kernel, grammar, requests, tasks, random.Random(seed), fuel, n) for n, seed in draws]


def dream_jobs(grammar, requests, tasks, fuel, seeds, workers):
    """Split independent draws into at most ``workers`` contiguous chunks (tasks are pickled once per chunk)."""
    draws = list(enumerate(seeds)); size = -(-len(draws) // workers)
    return [(grammar, requests, tasks, fuel, draws[i:i + size]) for i in range(0, len(draws), size)]


def worker_config(config):
    """The per-job copy of the driver configuration a worker runs with."""
    return replace(config, workers=1, output=None)


class WakePool:
    """``workers`` spawned processes, each with its own Kernel, kept across calls.

    Processes start lazily on the first job and stay until :meth:`close`. A job
    that raises propagates its exception and leaves the pool usable; a worker
    process that dies (``BrokenProcessPool``) closes the pool, and the driver
    builds a fresh one on its next parallel Wake.
    """
    def __init__(self, ec):
        from .kernel import KernelOptions
        try:
            payload = cloudpickle.dumps((ec.domain, worker_config(ec.config), ec._wake))
        except Exception as exc:
            raise TypeError("Parallel Wake requires a serializable Domain and wake callback; "
                            "keep process handles outside the Domain") from exc
        k = ec.kernel
        options = KernelOptions(target=k.target, executable=str(k.executable.resolve()), auto_build=False,
                                timeout=k.timeout, restart=k.restart, trace=str(k.trace) if k.trace else None,
                                env=k.env, extra_args=k.extra_args)
        self.workers = ec.config.workers
        self._pool = ProcessPoolExecutor(max_workers=self.workers, mp_context=multiprocessing.get_context("spawn"),
                                         initializer=_initialize, initargs=(payload, options))

    @property
    def alive(self) -> bool:
        return self._pool is not None

    def map(self, fn, jobs, on_done=None):
        """``fn`` is a module-level worker function (``_run`` for Wake, ``dream_chunk`` for
        dreams); results come back in job order. ``on_done(result)`` runs in the parent as
        each job completes, for progress reporting."""
        if self._pool is None:
            raise RuntimeError("WakePool is closed")
        try:
            # Results are returned in job order regardless of completion order; a failure
            # is propagated, not silently recorded as an unsolved task.
            futures = [self._pool.submit(fn, job) for job in jobs]
            for f in as_completed(futures):
                r = f.result()
                if on_done: on_done(r)
            return [f.result() for f in futures]
        except BrokenProcessPool:
            self.close(); raise

    def close(self) -> None:
        pool, self._pool = self._pool, None
        if pool is not None: pool.shutdown(wait=True)

    def __enter__(self): return self
    def __exit__(self, *exc): self.close()


def parallel_wake(ec, tasks, use_recognition, on_done=None):
    """Wake ``tasks`` on the driver's persistent :class:`WakePool`, in task order."""
    # Freeze recognition-conditioned grammars in the parent, before any work.
    config = worker_config(ec.config)
    jobs = [(task, ec.grammar, ec.search_grammar(task) if use_recognition else ec.grammar, config)
            for task in tasks]
    return ec.pool().map(_run, jobs, on_done)
