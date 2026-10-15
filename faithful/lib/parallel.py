"""Spawn-safe task parallelism, with one persistent Kernel per worker.

Only trusted, in-process Domain/Wake objects are cloudpickled. Models and live
Kernel handles stay in the parent. Compression and recognition remain there.
"""
import multiprocessing
from multiprocessing.util import Finalize
from concurrent.futures import ProcessPoolExecutor
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
    task, grammar, search_grammar = job
    _ec.grammar = grammar
    frontier, trace = _ec.wake(task, grammar, search_grammar)
    trace = replace(trace, worker_pid=os.getpid(), kernel_pid=_ec.kernel.process.pid)
    return frontier, trace


def parallel_wake(ec, tasks, use_recognition):
    from .kernel import KernelOptions
    # Freeze recognition-conditioned grammars in the parent, before any work.
    jobs = [(task, ec.grammar, ec.search_grammar(task) if use_recognition else ec.grammar)
            for task in tasks]
    try:
        payload = cloudpickle.dumps((ec.domain, replace(ec.config, workers=1, output=None), ec._wake))
    except Exception as exc:
        raise TypeError("Parallel Wake requires a serializable Domain and wake callback; "
                        "keep process handles outside the Domain") from exc
    k = ec.kernel
    options = KernelOptions(target=k.target, executable=str(k.executable.resolve()), auto_build=False,
                            timeout=k.timeout, restart=k.restart, trace=str(k.trace) if k.trace else None,
                            env=k.env, extra_args=k.extra_args)
    with ProcessPoolExecutor(max_workers=min(ec.config.workers, len(jobs)),
                             mp_context=multiprocessing.get_context("spawn"),
                             initializer=_initialize, initargs=(payload, options)) as pool:
        # map preserves task order regardless of completion order; failure is
        # propagated, not silently recorded as an unsolved task.
        return list(pool.map(_run, jobs))
