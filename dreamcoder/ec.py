"""Domain-neutral orchestration and reporting for one complete EC cycle."""
from __future__ import annotations

import random
from statistics import mean, median
from typing import Any, Callable

from .abstraction import RepeatedSubprogramCompressor
from .dreaming import TrainingPair, dream, replay
from .grammar import Grammar
from .recognition import RecognitionModel
from .search import SearchResult, search
from .tasks import Task


def wake(tasks: list[Task], grammar: Grammar, model: RecognitionModel | None = None,
         **search_options) -> list[SearchResult]:
    return [search(t, model.contextual_grammar(t, grammar) if model else grammar, **search_options) for t in tasks]


def summarize(results: list[SearchResult], grammar: Grammar,
              probes: list[Any]) -> dict:
    exact, expanded, behavioral = 0, 0, 0
    for result in results:
        gt = result.frontier.task.ground_truth
        if gt is not None:
            exact += any(s.program == gt for s in result.frontier.solutions)
            expanded += any(grammar.language.expand(s.program) == grammar.language.expand(gt)
                         for s in result.frontier.solutions)
            behavioral += any(all(grammar.language.evaluate(s.program, x) == grammar.language.evaluate(gt, x)
                                  for x in probes) for s in result.frontier.solutions)
    n = len(results)
    first_nodes = [r.first_solution_nodes for r in results if r.first_solution_nodes is not None]
    return dict(solve_rate=sum(bool(r.frontier.solutions) for r in results)/n,
                mean_enumerated_nodes=mean(r.enumerated_nodes for r in results),
                median_enumerated_nodes=median(r.enumerated_nodes for r in results),
                mean_expanded_states=mean(r.expanded_states for r in results),
                mean_search_seconds=mean(r.seconds for r in results),
                mean_first_solution_nodes=mean(first_nodes) if first_nodes else None,
                first_solution_sample_count=len(first_nodes),
                mean_censored_first_solution_nodes=mean(r.first_solution_nodes if r.first_solution_nodes is not None else r.enumerated_nodes for r in results),
                exact_program_recovery_rate=exact/n, expanded_ast_recovery_rate=expanded/n,
                behavioral_recovery_rate=behavioral/n,
                budget_exhausted=sum(r.budget_exhausted for r in results),
                budget_exhaustion_rate=sum(r.budget_exhausted for r in results)/n)


def run_iteration(base: Grammar, train: list[Task], heldout: list[Task],
                  sample_input: Callable, encoder: Callable, seed: int = 7,
                  dreams: int = 600, epochs: int = 100, **search_options) -> dict:
    import torch
    print("Wake: base grammar on training tasks", flush=True)
    initial = wake(train, base, **search_options)
    # Each task votes with its MAP solution; alternate frontier solutions are
    # retained for replay but do not multiply the corpus's compression weight.
    corpus = [r.frontier.solutions[0].program for r in initial if r.frontier.solutions]
    compressed = RepeatedSubprogramCompressor().compress(base, corpus)
    learned = compressed.grammar
    print(f"Compression: {compressed.added}; MDL {compressed.description_length_before} -> {compressed.description_length_after}", flush=True)
    print("Dream/replay and recognition training", flush=True)
    learned_dreams = dream(learned, sample_input, random.Random(seed+100), count=dreams)
    real_pairs = replay([r.frontier for r in initial])
    # Rewrite real solutions using the newly learned exact definitions.
    def rewrite(p):
        from .language import INPUT, Program
        for name in compressed.added:
            if learned.language.expand(p) == learned.language.expand(learned.language.primitives[name].definition):
                return Program(name, (INPUT,))
        return Program(p.name, tuple(rewrite(c) for c in p.arguments))
    learned_replay = [TrainingPair(p.task, rewrite(p.program)) for p in real_pairs]
    learned_pairs = learned_dreams + learned_replay * 5
    # Both recognition ablations see identical task/program semantics. C gets
    # macro-expanded labels because its vocabulary contains only base symbols.
    base_pairs = [TrainingPair(p.task, learned.language.expand(p.program)) for p in learned_pairs]
    models, losses = [], []
    for grammar, pairs in ((base, base_pairs), (learned, learned_pairs)):
        torch.manual_seed(seed)
        model = RecognitionModel(list(grammar.language.primitives), len(encoder(train[0])[0]), encoder)
        history = model.fit(pairs, seed, epochs)
        models.append(model)
        losses.append({"initial": history[0], "final": history[-1]})
    probes = [sample_input(random.Random(seed+1000+i)) for i in range(20)]
    configurations, detail = {}, {}
    for name, grammar, model in (("A", base, None), ("B", learned, None),
                                  ("C", base, models[0]), ("D", learned, models[1])):
        print(f"Held-out wake: configuration {name}", flush=True)
        results = wake(heldout, grammar, model, **search_options)
        configurations[name] = summarize(results, grammar, probes)
        detail[name] = [{"task": r.frontier.task.name,
                        "ground_truth": str(r.frontier.task.ground_truth),
                        "solutions": [{"program": str(s.program), "log_prior": s.log_prior,
                                       "log_likelihood": s.log_likelihood} for s in r.frontier.solutions],
                        "enumerated_nodes": r.enumerated_nodes, "expanded_states": r.expanded_states,
                        "seconds": r.seconds, "budget_exhausted": r.budget_exhausted} for r in results]
        print(configurations[name], flush=True)
    return {"seed": seed, "train_tasks": len(train), "heldout_tasks": len(heldout),
            "search_options": search_options, "dream_count": len(learned_dreams),
            "replay_count": len(real_pairs), "recognition_losses": losses,
            "training_wake": summarize(initial, base, probes),
            "compression": {"added": {n: str(learned.language.primitives[n].definition) for n in compressed.added},
                            "mdl_before": compressed.description_length_before,
                            "mdl_after": compressed.description_length_after},
            "configurations": configurations, "frontiers": detail,
            "recognition_improves_nodes": configurations["C"]["mean_enumerated_nodes"] < configurations["A"]["mean_enumerated_nodes"]}
