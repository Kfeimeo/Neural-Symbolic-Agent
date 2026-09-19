"""Private generative grammar for an outcome-independent compositional benchmark.

Only expanded base-DSL I/O tasks cross the learner boundary. Hidden functions,
generation recipes and ground truths are evaluation metadata, never labels.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from ..domains.grid import make_language, sample_grid
from ..domains.grid.canonical import canonical, depth
from ..language import INPUT, Program
from ..tasks import Example, Task
from .benchmark import diverse_grid, fingerprint, program_record


@dataclass(frozen=True)
class ControlledConfig:
    seed: int = 7
    latent_count: int = 4
    low_reuse: int = 4
    high_reuse: int = 12
    context_extras: tuple[int, ...] = (0, 2)
    anchor_count: int = 8
    examples: int = 5


def substitute(body: Program, argument: Program) -> Program:
    return argument if body == INPUT else Program(body.name, tuple(substitute(c, argument) for c in body.arguments))


def context(rng: random.Random, difficulty: str) -> Program:
    if difficulty == "narrow":
        return Program(rng.choice(("rotate90", "rotate180", "flipH", "flipV", "transpose", "trim", "invert", "border")), (INPUT,))
    name = rng.choice(("translate", "recolor", "solid"))
    if name == "translate":
        a, b = rng.choice([(a, b) for a in ("minus_one", "zero", "one")
                          for b in ("minus_one", "zero", "one") if (a, b) != ("zero", "zero")])
        return Program(name, (INPUT, Program(a), Program(b)))
    if name == "solid":
        return Program(name, (INPUT, Program(rng.choice(("red", "blue", "green")))))
    a, b = rng.sample(("red", "blue", "green"), 2)
    return Program(name, (INPUT, Program(a), Program(b)))


@dataclass
class ControlledBenchmark:
    config: ControlledConfig
    latents: dict[str, Program]
    training: list[Task]
    testing: list[Task]
    metadata: dict[str, dict]
    split_probes: list
    evaluation_probes: list

    def learner_training(self) -> list[Task]:
        return [Task(f"train_{i}", t.examples) for i, t in enumerate(self.training)]

    def learner_testing(self) -> list[Task]:
        return [Task(f"test_{i}", t.examples) for i, t in enumerate(self.testing)]


def generate(config: ControlledConfig = ControlledConfig()) -> ControlledBenchmark:
    if config.latent_count < 2 or min(config.low_reuse, config.high_reuse, config.examples) < 1:
        raise ValueError("At least two latents and positive repetitions/examples required")
    language = make_language()
    rng, io_rng = random.Random(config.seed+11000), random.Random(config.seed+12000)
    probes = [diverse_grid(random.Random(config.seed+13000+i)) for i in range(32)]
    evaluation = [diverse_grid(random.Random(config.seed+14000+i)) for i in range(64)]
    latent_fp, latents = set(), {}
    elementary = [INPUT] + [Program(n, (INPUT,)) for n in
                            ("identity", "rotate90", "rotate180", "flipH", "flipV", "transpose", "trim", "invert", "border")]
    elementary_fp = {fingerprint(language, p, probes) for p in elementary}
    for i in range(config.latent_count):
        # Equal application depth, independently varied primitive arity/cost.
        family = "narrow" if i % 2 == 0 else "wide"
        for _ in range(10000):
            p = substitute(context(rng, "narrow"), context(rng, family))
            fp = fingerprint(language, p, probes)
            if depth(canonical(p)) != 2 or fp in elementary_fp | latent_fp or len(set(fp)) < 8:
                continue
            latents[f"F{i}"] = p
            latent_fp.add(fp)
            break
        else:
            raise RuntimeError("Latent grammar generation exhausted")
    train_programs, train_fp, train_canonical = [], set(), set()
    meta = {}
    for i, (name, f) in enumerate(latents.items()):
        repetitions = config.low_reuse if i < config.latent_count//2 else config.high_reuse
        recipes = [("F(x)", f)]
        local = {fingerprint(language, f, probes)}
        for g_index in range(2):
            for _ in range(10000):
                p = substitute(context(rng, "narrow"), f)
                fp = fingerprint(language, p, probes)
                if depth(canonical(p)) < 3 or fp in local | train_fp | latent_fp:
                    continue
                recipes.append((f"g{g_index+1}(F(x))", p))
                local.add(fp)
                break
            else:
                raise RuntimeError("Cannot generate distinct training contexts")
        for recipe, p in recipes:
            train_fp.add(fingerprint(language, p, probes))
            train_canonical.add(canonical(p))
            for repetition in range(repetitions):
                task_name = f"train_{len(train_programs)}"
                train_programs.append((task_name, p))
                meta[task_name] = {"latent": name, "recipe": recipe, "reuse": repetitions,
                                   "repetition": repetition, "difficulty": "narrow_context"}
    all_inputs = set()
    def task(name, p, forbidden):
        xs = []
        while len(xs) < config.examples:
            x = sample_grid(io_rng)
            if x not in forbidden and x not in xs:
                xs.append(x)
        all_inputs.update(xs)
        return Task(name, tuple(Example(x, language.evaluate(p, x)) for x in xs), p)
    training = [task(n, p, set()) for n, p in train_programs]
    train_inputs = set(all_inputs)
    testing, test_fp, test_canonical = [], set(), set()

    def accept(p):
        cp = canonical(p)
        fp = fingerprint(language, p, probes)
        if cp in train_canonical | test_canonical or fp in train_fp | test_fp or len(set(fp)) < 8:
            return False
        test_fp.add(fp)
        test_canonical.add(cp)
        return True

    def append(p, metadata):
        name = f"test_{len(testing)}"
        testing.append(task(name, p, train_inputs))
        meta[name] = {**metadata, "raw_depth": depth(p), "effective_depth": depth(canonical(p)),
                      "ast_size": p.size, "effective_ast_size": canonical(p).size,
                      "primitive_occurrences": len(p.symbols())}

    # Small anchor stratum has no latent calls; this is declared before search.
    for i in range(config.anchor_count):
        for _ in range(10000):
            p = context(rng, "narrow" if i % 2 == 0 else "wide")
            if not accept(p):
                continue
            append(p, {"latent": None, "recipe": "anchor", "reuse": 0,
                       "complexity_extra": 0, "difficulty": "narrow" if i % 2 == 0 else "wide"})
            break
        else:
            raise RuntimeError("Anchor generation exhausted")
    for i, (name, f) in enumerate(latents.items()):
        reuse = config.low_reuse if i < config.latent_count//2 else config.high_reuse
        for recipe in ("g3(F(x))", "F(h(x))", "g(F(h(x)))"):
            for difficulty in ("narrow", "wide"):
                for extra in config.context_extras:
                    base_depth = 4 if recipe == "g(F(h(x)))" else 3
                    target = base_depth+extra
                    for _ in range(20000):
                        h = context(rng, difficulty) if recipe != "g3(F(x))" else INPUT
                        p = substitute(f, h)
                        if recipe != "F(h(x))":
                            p = substitute(context(rng, difficulty), p)
                        for _ in range(extra):
                            p = substitute(context(rng, difficulty), p)
                        if depth(canonical(p)) != target or not accept(p):
                            continue
                        append(p, {"latent": name, "recipe": recipe, "reuse": reuse,
                                   "complexity_extra": extra, "difficulty": difficulty})
                        break
                    else:
                        raise RuntimeError(f"Cannot construct {name}/{recipe}/{difficulty}/{target} without overlap")
        # One predeclared depth-8 tail case per latent, independent of all results.
        for _ in range(20000):
            p = substitute(f, context(rng, "wide"))
            for _ in range(5):
                p = substitute(context(rng, "wide"), p)
            if depth(canonical(p)) != 8 or not accept(p):
                continue
            append(p, {"latent": name, "recipe": "hard_tail", "reuse": reuse,
                       "complexity_extra": 4, "difficulty": "wide"})
            break
        else:
            raise RuntimeError("Hard tail generation exhausted")
    return ControlledBenchmark(config, latents, training, testing, meta, probes, evaluation)


def private_record(benchmark: ControlledBenchmark) -> dict:
    from dataclasses import asdict
    def encode(task):
        return {"name": task.name, "ground_truth": program_record(task.ground_truth),
                "examples": [{"input": e.input, "output": e.output} for e in task.examples]}
    return {"config": asdict(benchmark.config), "hidden_latents": {n: program_record(p) for n, p in benchmark.latents.items()},
            "training": [encode(t) for t in benchmark.training], "testing": [encode(t) for t in benchmark.testing],
            "metadata": benchmark.metadata, "split_probes": benchmark.split_probes,
            "evaluation_probes": benchmark.evaluation_probes}
