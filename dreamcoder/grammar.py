from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass

from .language import INPUT, Language, Program, Type


@dataclass
class Grammar:
    language: Language
    log_probabilities: dict[str, float]

    @classmethod
    def uniform(cls, language: Language) -> Grammar:
        return cls.from_logits(language, {n: 0.0 for n in language.primitives})

    @classmethod
    def from_logits(cls, language: Language, logits: dict[str, float]) -> Grammar:
        if set(logits) != set(language.primitives) or not all(math.isfinite(x) for x in logits.values()):
            raise ValueError("Supply finite logits for every primitive")
        maximum = max(logits.values())
        norm = maximum + math.log(sum(math.exp(v - maximum) for v in logits.values()))
        return cls(language, {n: v - norm for n, v in logits.items()})

    def log_prior(self, program: Program) -> float:
        return sum(self.log_probabilities[n] for n in program.symbols())

    def fit(self, programs: list[Program], smoothing: float = 1.0) -> Grammar:
        if smoothing <= 0:
            raise ValueError("Smoothing must be positive")
        counts = Counter(s for p in programs for s in p.symbols())
        return self.from_logits(self.language, {n: math.log(counts[n] + smoothing) for n in self.language.primitives})

    def sample(self, rng: random.Random, max_depth: int = 4) -> Program:
        def draw(typ: Type, depth: int) -> Program:
            choices = [p for p in self.language.primitives.values()
                       if p.signature.result == typ and (depth > 0 or not p.signature.arguments)]
            options = [p.name for p in choices]
            weights = [math.exp(self.log_probabilities[n]) for n in options]
            if typ == self.language.input_type:
                options.append("$input")
                weights.append(0.35)
            if not options:
                raise ValueError("No finite inhabitant within depth bound")
            name = rng.choices(options, weights=weights)[0]
            if name == "$input":
                return INPUT
            return Program(name, tuple(draw(t, depth - 1) for t in self.language.primitives[name].signature.arguments))
        return draw(self.language.output_type, max_depth)
