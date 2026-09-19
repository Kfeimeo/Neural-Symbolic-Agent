from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass

from ..domains.grid import Grid, make_language, sample_grid
from ..domains.grid.canonical import canonical, depth
from ..language import INPUT, Language, Program
from ..tasks import Example, Task

BUCKETS = ("1-2", "3-4", "5-6", "7-8")


def bucket(p: Program) -> str:
    d = depth(p)
    return BUCKETS[min((d-1)//2, 3)]


def diverse_grid(rng: random.Random) -> Grid:
    """Mix the original generator with sparse grids and boundary cases."""
    if rng.random() < .5:
        return sample_grid(rng)
    h, w = rng.randint(1, 7), rng.randint(1, 7)
    density = rng.choice((0.0, .2, .5, 1.0))
    return tuple(tuple(rng.randint(1, 3) if rng.random() < density else 0 for _ in range(w)) for _ in range(h))


def fingerprint(language: Language, p: Program, probes: list[Grid]) -> tuple[Grid, ...]:
    return tuple(language.evaluate(p, x) for x in probes)


def program_record(p: Program) -> dict:
    return {"name": p.name, "arguments": [program_record(c) for c in p.arguments]}


def io_hash(task: Task) -> str:
    raw = json.dumps([(e.input, e.output) for e in task.examples], separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def make_task(language: Language, p: Program, rng: random.Random, name: str) -> Task:
    # Four original-distribution inputs for comparability, plus two diverse ones.
    xs = [sample_grid(rng) for _ in range(4)] + [diverse_grid(rng) for _ in range(2)]
    return Task(name, tuple(Example(x, language.evaluate(p, x)) for x in xs), p)


def wrap(p: Program, rng: random.Random, remaining: int = 8) -> Program:
    choices = ["rotate90", "rotate180", "flipH", "flipV", "transpose", "trim", "invert", "border",
               "recolor", "translate", "solid"]
    if remaining >= 3:
        choices.append("crop_largest")
    name = rng.choice(choices)
    if name == "recolor":
        a, b = rng.sample(["red", "blue", "green"], 2)
        return Program(name, (p, Program(a), Program(b)))
    if name == "solid":
        return Program(name, (p, Program(rng.choice(["red", "blue", "green"]))))
    if name == "translate":
        a, b = rng.choice([(a, b) for a in ("zero", "one", "minus_one")
                          for b in ("zero", "one", "minus_one") if (a, b) != ("zero", "zero")])
        return Program(name, (p, Program(a), Program(b)))
    if name == "crop_largest":
        return Program("crop", (Program("largest", (Program("objects", (p,)),)),))
    return Program(name, (p,))


@dataclass
class ProgramSplit:
    language: Language
    training_programs: list[Program]
    probes: list[Grid]

    def __post_init__(self):
        self.training_canonical = {canonical(self.language.expand(p)) for p in self.training_programs}
        self.training_behavior = {fingerprint(self.language, p, self.probes) for p in self.training_programs}
        self.accepted_behavior = set()
        self.accepted_canonical = set()
        self.rejections = {"training_overlap": 0, "duplicate_test": 0, "uninformative": 0}
        self.identity = tuple(self.probes)

    def accept(self, p: Program) -> bool:
        cp = canonical(self.language.expand(p))
        fp = fingerprint(self.language, p, self.probes)
        if cp in self.training_canonical or fp in self.training_behavior:
            self.rejections["training_overlap"] += 1
            return False
        if cp in self.accepted_canonical or fp in self.accepted_behavior:
            self.rejections["duplicate_test"] += 1
            return False
        if fp == self.identity or len(set(fp)) < 3:
            self.rejections["uninformative"] += 1
            return False
        self.accepted_canonical.add(cp)
        self.accepted_behavior.add(fp)
        return True


def stress_tasks(split: ProgramSplit, seed: int, per_bucket: int = 12) -> list[Task]:
    rng, inputs = random.Random(seed), random.Random(seed+1)
    tasks = []
    for low in (1, 3, 5, 7):
        accepted = 0
        for attempt in range(20000):
            target = rng.randint(low, low+1)
            p = INPUT
            while depth(p) < target:
                p = wrap(p, rng, target-depth(p))
            p = canonical(p)
            if depth(p) != target or not split.accept(p):
                continue
            tasks.append(make_task(split.language, p, inputs, f"stress_{low}-{low+1}_{accepted}"))
            accepted += 1
            if accepted == per_bucket:
                break
        if accepted != per_bucket:
            raise RuntimeError(f"Could only build {accepted}/{per_bucket} tasks at depth {low}-{low+1}")
    return tasks


def transfer_tasks(split: ProgramSplit, macro: str, seed: int, per_direction: int = 8) -> tuple[list[Task], list[str]]:
    rng, inputs = random.Random(seed), random.Random(seed+1)
    tasks, directions = [], []
    for direction in ("g(f(x))", "f(h(x))"):
        accepted = 0
        for attempt in range(10000):
            p = wrap(Program(macro, (INPUT,)), rng, 1) if direction == "g(f(x))" else Program(macro, (wrap(INPUT, rng, 1),))
            expanded = split.language.expand(p)
            # Keep only genuinely new compositions; no loss of the extra step
            # through the canonical identities supported by this audit.
            if depth(canonical(expanded)) < 3 or not split.accept(p):
                continue
            tasks.append(make_task(split.language, expanded, inputs, f"transfer_{len(tasks)}"))
            directions.append(direction)
            accepted += 1
            if accepted == per_direction:
                break
        if accepted != per_direction:
            raise RuntimeError(f"Insufficient distinct transfer tasks for {direction}")
    return tasks, directions
