import random
from dataclasses import dataclass
from typing import Any, Callable

from .grammar import Grammar
from .language import Program
from .search import Frontier
from .tasks import Example, Task


@dataclass(frozen=True)
class TrainingPair:
    task: Task
    program: Program


def dream(grammar: Grammar, sample_input: Callable[[random.Random], Any], rng: random.Random,
          count: int = 200, examples: int = 3, max_attempts: int | None = None) -> list[TrainingPair]:
    if count < 0 or examples < 1 or (max_attempts is not None and max_attempts < 0):
        raise ValueError("Invalid dream count, example count or attempt budget")
    pairs = []
    for attempt in range(max_attempts if max_attempts is not None else count * 100):
        if len(pairs) == count:
            return pairs
        try:
            program = grammar.sample(rng)
            inputs = [sample_input(rng) for _ in range(examples)]
            ios = tuple(Example(x, grammar.language.evaluate(program, x)) for x in inputs)
            pairs.append(TrainingPair(Task(f"dream_{attempt}", ios), program))
        except (ValueError, IndexError, ZeroDivisionError):
            continue
    if len(pairs) == count:
        return pairs
    raise RuntimeError(f"Only generated {len(pairs)}/{count} fantasies")


def replay(frontiers: list[Frontier]) -> list[TrainingPair]:
    return [TrainingPair(f.task, s.program) for f in frontiers for s in f.solutions]
