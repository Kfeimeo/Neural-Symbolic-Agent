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


class Recognition(frozen.Recognition):
    def fit_frontiers(self, kernel, data, steps=50, seed=0, objective="bias_optimal"):
        rng = random.Random(seed)
        data = [(features, frontier) for features, frontier in data if frontier["entries"]]
        scored = kernel.map(lambda k, d: k.call("frontier", grammar=self.grammar, frontier=d[1]), data)
        jobs = [(i, e["program"]) for i, f in enumerate(scored) for e in f["entries"]]
        events = kernel.map(lambda k, j: k.call("score", grammar=self.grammar, request=data[j[0]][1]["request"], program=j[1])["events"], jobs)
        summaries = [[] for _ in scored]
        for (i, _), ev in zip(jobs, events): summaries[i].append(ev)
        prepared = [(features.to(self.device), f, s) for (features, _), f, s in zip(data, scored, summaries)]
        if not prepared: return []
        optimizer = torch.optim.Adam(self.parameters(), lr=.001)
        history = []
        for _ in range(steps):
            features, f, s = rng.choice(prepared); logits = self(features)
            if objective == "bias_optimal":
                loss = frozen.frontier_bias_optimal(logits, s, [e["log_likelihood"] for e in f["entries"]], self.keys)
            elif objective == "kl":
                i = rng.choices(range(len(s)), weights=[e["posterior"] for e in f["entries"]], k=1)[0]
                loss = -frozen.program_log_probability(logits, s[i], self.keys)
            else: raise ValueError(objective)
            optimizer.zero_grad(); loss.backward(); optimizer.step(); history.append(float(loss.detach()))
        return history
