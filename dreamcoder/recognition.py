from __future__ import annotations

import random
from collections import Counter
from typing import Callable

import torch
from torch import nn

from .dreaming import TrainingPair
from .grammar import Grammar
from .tasks import Task


class RecognitionModel(nn.Module):
    """Permutation-invariant example pooling; predicts only grammar logits."""
    def __init__(self, names: list[str], feature_count: int,
                 encoder: Callable[[Task], list[list[float]]]):
        super().__init__()
        self.names = names
        self.encoder = encoder
        self.network = nn.Sequential(nn.Linear(feature_count, 96), nn.ReLU(),
                                     nn.Linear(96, len(names)))

    def forward(self, examples: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        per_example = self.network(examples)
        return (per_example * mask[..., None]).sum(1) / mask.sum(1, keepdim=True)

    def batch(self, tasks: list[Task]) -> tuple[torch.Tensor, torch.Tensor]:
        arrays = [torch.tensor(self.encoder(t), dtype=torch.float32) for t in tasks]
        maximum = max(len(a) for a in arrays)
        x = torch.zeros(len(arrays), maximum, arrays[0].shape[-1])
        mask = torch.zeros(len(arrays), maximum)
        for i, array in enumerate(arrays):
            x[i, :len(array)] = array
            mask[i, :len(array)] = 1
        return x, mask

    def fit(self, pairs: list[TrainingPair], seed: int, epochs: int = 100) -> list[float]:
        rng = random.Random(seed)
        optimizer = torch.optim.Adam(self.parameters(), lr=.003)
        x, mask = self.batch([p.task for p in pairs])
        target = torch.zeros(len(pairs), len(self.names))
        for i, pair in enumerate(pairs):
            counts = Counter(pair.program.symbols())
            for j, name in enumerate(self.names):
                target[i, j] = counts[name] + .015
        target /= target.sum(1, keepdim=True)
        losses = []
        self.train()
        for _ in range(epochs):
            order = list(range(len(pairs)))
            rng.shuffle(order)
            total = 0.0
            for offset in range(0, len(order), 64):
                idx = order[offset:offset+64]
                logits = self(x[idx], mask[idx])
                loss = -(target[idx] * logits.log_softmax(-1)).sum(-1).mean()
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total += loss.item()*len(idx)
            losses.append(total/len(pairs))
        self.eval()
        return losses

    @torch.no_grad()
    def contextual_grammar(self, task: Task, base: Grammar) -> Grammar:
        if set(self.names) != set(base.language.primitives):
            raise ValueError("Model vocabulary does not match grammar")
        logits = self(*self.batch([task]))[0].log_softmax(-1).tolist()
        # A fixed base mixture keeps all primitives reachable.
        import math
        return Grammar.from_logits(base.language, {
            n: math.log(.9*math.exp(v) + .1*math.exp(base.log_probabilities[n]))
            for n, v in zip(self.names, logits)})
