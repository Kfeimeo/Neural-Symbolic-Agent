"""The frozen recognition network with a pool-aware ``fit_frontiers``.

``faithful.python.recognition.Recognition`` is part of the hash-recorded core
and is left untouched. It prepares its training data with one synchronous
kernel call per frontier plus one per entry. This subclass computes the same
summaries through ``kernel.map`` in two flat batches, so a
:class:`~faithful.lib.kernel.KernelPool` scores them on several processes; the
prepared data, the optimizer steps and the losses are identical.
"""
from __future__ import annotations
import random

import torch

from ..python import recognition as frozen
from .progress import NullProgress


class Recognition(frozen.Recognition):
    def fit_frontiers(self, kernel, data, steps=50, seed=0, objective="bias_optimal", progress=None):
        """``progress`` (a :class:`~faithful.lib.progress.Progress`) sees a ``summaries`` phase
        (one step per frontier and per entry) and a ``recognition`` phase (one per optimizer step)."""
        progress = progress or NullProgress()
        rng = random.Random(seed)
        data = [(features, frontier) for features, frontier in data if frontier["entries"]]
        progress.phase_started("summaries", len(data) + sum(len(f["entries"]) for _, f in data), "calls")
        tick = lambda _r: progress.advance()
        scored = kernel.map(lambda k, d: k.call("frontier", grammar=self.grammar, frontier=d[1]), data, on_done=tick)
        jobs = [(i, e["program"]) for i, f in enumerate(scored) for e in f["entries"]]
        events = kernel.map(lambda k, j: k.call("score", grammar=self.grammar, request=data[j[0]][1]["request"], program=j[1])["events"], jobs, on_done=tick)
        summaries = [[] for _ in scored]
        for (i, _), ev in zip(jobs, events): summaries[i].append(ev)
        prepared = [(features.to(self.device), f, s) for (features, _), f, s in zip(data, scored, summaries)]
        progress.phase_finished()
        if not prepared: return []
        optimizer = torch.optim.Adam(self.parameters(), lr=.001)
        history = []
        progress.phase_started("recognition", steps, "steps")
        for _ in range(steps):
            features, f, s = rng.choice(prepared); logits = self(features)
            if objective == "bias_optimal":
                loss = frozen.frontier_bias_optimal(logits, s, [e["log_likelihood"] for e in f["entries"]], self.keys)
            elif objective == "kl":
                i = rng.choices(range(len(s)), weights=[e["posterior"] for e in f["entries"]], k=1)[0]
                loss = -frozen.program_log_probability(logits, s[i], self.keys)
            else: raise ValueError(objective)
            optimizer.zero_grad(); loss.backward(); optimizer.step(); history.append(float(loss.detach()))
            progress.advance()
        progress.phase_finished(f"loss {history[-1]:.3f}")
        return history
