from dataclasses import replace

from arc_tsl.arc.grid import to_grid
from arc_tsl.arc.parse import parse
from arc_tsl.arc.render import render
from arc_tsl.dsa.types import COLOR, OBJECT, OBJECTS
from arc_tsl.experiments.evaluation import evaluate_test
from arc_tsl.language import base_library
from arc_tsl.ml.ast import Abs, App, Prim, Var
from arc_tsl.ontology.instance import ExtractionConfig
from arc_tsl.synthesis.enumerator import EnumerationConfig, Enumerator
from arc_tsl.synthesis.evaluator import evaluate
from arc_tsl.synthesis.grammar import Abstraction, Library
from arc_tsl.synthesis.search import Pair
from arc_tsl.tsl.compression import compress
from arc_tsl.tsl.local_wake import local_wake
from arc_tsl.tsl.parameter_search import parameter_search


def fixture():
    # Different colors occupy the largest object; the constant per-pair
    # programs are insufficient on the other pairs or the held-out scene.
    base = base_library()
    names = {"map", "replace_color", "dominant_color", "argmax", "size"} | {f"c{i}" for i in range(10)}
    lib = Library({n: p for n, p in base.primitives.items() if n in names})
    pairs, frontiers = [], []
    for color in (1, 2, 3):
        grid = to_grid([[color, color, 0, 0, 8], [color, 0, 0, 0, 0]])
        scene = parse(grid)
        program = App("map", (Abs(OBJECT, App("replace_color", (Var(0), Prim(f"c{color}"), Prim("c5")))), Var(0)))
        output = render(evaluate(program, lib, (scene.objects,)), scene.grid_shape, scene.background)
        pairs.append(Pair(scene, output))
        frontiers.append([program])
    learned = compress(lib, frontiers, (OBJECTS,), OBJECTS, 3, 3).library
    return pairs, frontiers, learned


CFG = EnumerationConfig(10, 30_000, 30, max_lambda_depth=1)


def test_learned_call_completes_varying_parameter_and_generalizes():
    pairs, frontiers, learned = fixture()
    result, details = parameter_search(pairs, learned, frontiers, CFG)
    assert result.solved
    assert details["templates"][0]["varying_parameters"]
    assert "dominant_color" in str(result.frontier.best.program)
    assert details["complete_program_checks"] == 1
    assert result.frontier.best.cost <= CFG.max_cost
    expanded = learned.expand(result.frontier.best.program)
    test = to_grid([[4, 4, 0, 8], [4, 0, 0, 0]])
    expected = to_grid([[5, 5, 0, 8], [5, 0, 0, 0]])
    record = {"expanded_program": str(expanded)}
    score = evaluate_test(record, [(test, expected)], ExtractionConfig())
    assert score["all_test_correct"] is True
    wrong = evaluate_test(record, [(test, test)], ExtractionConfig())
    assert wrong["all_test_correct"] is False
    assert wrong["pairs"][0]["prediction"] == score["pairs"][0]["prediction"]
    assert evaluate_test(record, [(test, None)], ExtractionConfig())["all_test_correct"] is None


def test_parameter_search_respects_budget_and_full_call_cost():
    pairs, frontiers, learned = fixture()
    for config, reason in [(replace(CFG, max_expanded_states=0), "max_expanded_states"),
                           (replace(CFG, time_limit_seconds=0), "time_limit"),
                           (replace(CFG, max_expanded_states=10), "max_expanded_states"),
                           (replace(CFG, max_cost=3), "max_cost")]:
        result, _ = parameter_search(pairs, learned, frontiers, config)
        assert not result.solved
        assert result.termination_reason == reason
        assert result.stats.expanded_states <= config.max_expanded_states


def test_missing_pair_or_invalid_witness_does_not_claim_a_solution():
    pairs, frontiers, learned = fixture()
    result, _ = parameter_search(pairs, learned, [frontiers[0], [], frontiers[2]], CFG)
    assert not result.solved and result.termination_reason == "no_applicable_template"
    result, _ = parameter_search(pairs, learned, [frontiers[0]] * 3, CFG)
    assert not result.solved and result.termination_reason == "no_applicable_template"


def test_demand_pruning_preserves_ground_observations_at_small_cost():
    pairs, _, learned = fixture()
    config = replace(CFG, max_cost=6, max_expanded_states=100_000)
    scenes = [p.scene.objects for p in pairs]
    full = Enumerator(learned, scenes, config)
    directed = Enumerator(learned, scenes, config)
    a = {tuple(e.values) for _, e in full.expressions({COLOR: 6})}
    b = {tuple(e.values) for _, e in directed.expressions({COLOR: 6}, demand_driven=True)}
    assert a == b
    assert directed.stats.expanded_states < full.stats.expanded_states


def test_shared_wake_budget_keeps_pair_positions():
    pairs, _, learned = fixture()
    wake = local_wake(pairs, learned, CFG, 1, total_config=replace(CFG, max_expanded_states=2))
    assert len(wake.results) == len(pairs)
    assert wake.total_expanded <= 2
    assert wake.results[-1].termination_reason == "total_budget_exhausted"


def test_multiple_parameters_are_constrained_on_every_pair():
    from arc_tsl.ml.parser import parse_term
    base = base_library()
    names = {"map", "replace_color", "dominant_color", "argmin", "argmax", "size"} | {f"c{i}" for i in range(10)}
    lib = Library({n: p for n, p in base.primitives.items() if n in names})
    abstraction = Abstraction("#swap", (COLOR, COLOR, OBJECTS), OBJECTS,
                              parse_term("(map (lambdaObject. (replace_color $0 $3 $2)) $0)"))
    lib = lib.with_abstraction(abstraction)
    pairs, frontiers = [], []
    for source, destination in ((1, 6), (2, 7), (3, 8)):
        scene = parse(to_grid([[source, source, 0, destination], [source, 0, 0, 0]]))
        call = App("#swap", (Prim(f"c{source}"), Prim(f"c{destination}"), Var(0)))
        output = render(evaluate(call, lib, (scene.objects,)), scene.grid_shape, scene.background)
        pairs.append(Pair(scene, output))
        frontiers.append([call])
    result, details = parameter_search(pairs, lib, frontiers, replace(CFG, max_cost=14))
    assert result.solved
    assert len(details["parameter_programs"]) == 2
    assert "argmin" in str(result.frontier.best.program) and "argmax" in str(result.frontier.best.program)
    for pair in pairs:
        assert render(evaluate(result.frontier.best.program, lib, (pair.scene.objects,)), pair.scene.grid_shape, 0) == pair.output


def test_multiple_goal_types_and_weighted_costs_preserve_observations():
    from arc_tsl.ml.types import INT
    pairs, _, learned = fixture()
    learned = learned.with_costs({"dominant_color": 2, "argmax": 2})
    config = replace(CFG, max_cost=6, max_expanded_states=100_000)
    scenes = [p.scene.objects for p in pairs]
    ordinary = Enumerator(learned, scenes, config)
    directed = Enumerator(learned, scenes, config)
    goals = {COLOR: 6, INT: 5}
    a = {(str(t), tuple(e.values)) for t, e in ordinary.expressions(goals)}
    b = {(str(t), tuple(e.values)) for t, e in directed.expressions(goals, demand_driven=True)}
    assert a == b


def test_pipeline_learns_parameters_from_fresh_wake_with_total_budget():
    from arc_tsl.tsl.pipeline import PipelineConfig, run_tsl
    pairs, _, learned = fixture()
    base = Library(learned.primitives)
    train = [(render(p.scene.objects, p.scene.grid_shape, p.scene.background), p.output) for p in pairs]
    config = PipelineConfig(wake=CFG, full=CFG, wake_top_k=1, total_budget=True)
    record = run_tsl(train, config, library=base, parameter_completion=True)
    assert record["condition"] == "tsl_parameters" and record["status"] == "SOLVED"
    assert record["wake"]["solved_pairs"] == len(pairs)
    assert record["parameter_search"]["templates"][0]["varying_parameters"]
    assert record["total_expanded_states"] <= CFG.max_expanded_states
    assert record["rewake_budget"]["max_expanded_states"] == CFG.max_expanded_states - record["wake"]["total_expanded_states"]
    from arc_tsl.experiments.compare import row, summarize
    baseline = {"task_id": "synthetic", "num_train_pairs": len(pairs), "status": "SEARCH_TIMEOUT"}
    summary = summarize([row(baseline, record)], "tsl_parameters")
    assert summary["solved_by_tsl_only"] == ["synthetic"]
    assert summary["num_solved_using_abstraction"] == 1
    assert summary["test_scored_tasks"] == 0


def test_parameter_search_consumes_alternative_wake_witnesses_with_a_cap():
    pairs, frontiers, learned = fixture()
    from arc_tsl.ml.parser import parse_term
    name = next(iter(learned.abstractions))
    argument = parse_term("(dominant_color (argmax (lambdaObject. (size $0)) $0))")
    common = App(name, (argument, Var(0)))
    alternatives = [f + [common] for f in frontiers]
    result, details = parameter_search(pairs, learned, alternatives, CFG, max_templates=64)
    assert result.solved
    assert details["witness_assignments_considered"] > 1
    assert result.stats.expanded_states == 0  # common non-cheapest witness is verified directly
    _, capped = parameter_search(pairs, learned, alternatives, CFG, max_templates=1)
    assert capped["templates_truncated"] is True
    assert capped["witness_assignments_considered"] == 1
