import argparse
from dataclasses import replace

from arc_tsl.arc.grid import to_grid
from arc_tsl.arc.parse import parse
from arc_tsl.dsa.types import OBJECTS
from arc_tsl.experiments.common import add_common_args, pipeline_config
from arc_tsl.experiments.generalization import aggregate, arm_config, split_pairs
from arc_tsl.experiments.resources import peak_rss_bytes
from arc_tsl.language import base_library
from arc_tsl.ml.ast import App, Prim, Var
from arc_tsl.ml.primitives import function
from arc_tsl.synthesis.diversity import structure_key
from arc_tsl.synthesis.enumerator import EnumerationConfig, Enumerator
from arc_tsl.synthesis.grammar import Library
from arc_tsl.synthesis.search import Pair, search
from arc_tsl.tsl.pipeline import PipelineConfig


def test_structure_key_ignores_literals_but_keeps_operators_and_bindings():
    lib = base_library()
    a = App("replace_color", (Var(0), Prim("c1"), Prim("c2")))
    b = App("replace_color", (Var(0), Prim("c3"), Prim("c4")))
    assert structure_key(a, lib) == structure_key(b, lib)
    assert structure_key(a, lib) != structure_key(App("recolor", (Var(0), Prim("c2"))), lib)
    assert structure_key(Var(0), lib) != structure_key(Var(1), lib)


def test_bounded_structural_representatives_preserve_equivalent_alternatives():
    lib = Library.from_primitives([function("a", (OBJECTS,), OBJECTS, lambda x: x),
                                   function("b", (OBJECTS,), OBJECTS, lambda x: x)])
    config = EnumerationConfig(max_cost=2, max_expanded_states=100, oe_representatives=2)
    enum = Enumerator(lib, [()], config)
    found = list(enum.expressions({OBJECTS: 2}, demand_driven=True))
    assert len(found) == 2  # $0 and one alternate structure share the same observation
    assert enum.stats.additional_oe_representatives == 1
    assert all(len(v) <= 2 for v in enum.representatives.values())
    ordinary = Enumerator(lib, [()], replace(config, oe_representatives=1))
    assert len(list(ordinary.expressions({OBJECTS: 2}, demand_driven=True))) == 1


def test_diverse_frontier_collects_distinct_correct_structures_under_oe():
    lib = Library.from_primitives([function("a", (OBJECTS,), OBJECTS, lambda x: x),
                                   function("b", (OBJECTS,), OBJECTS, lambda x: x)])
    grid = to_grid([[1, 0], [0, 0]])
    config = EnumerationConfig(max_cost=2, max_expanded_states=100, oe_representatives=2)
    result = search([Pair(parse(grid), grid)], lib, config, top_k=3, diverse=True, demand_driven=True)
    assert result.solved and len(result.frontier.solutions) == 3
    assert result.summary()["frontier_structural_count"] == 3


def test_wake_diversity_flags_do_not_change_full_search_config():
    p = argparse.ArgumentParser()
    add_common_args(p)
    args = p.parse_args(["--wake-oe-representatives", "2", "--wake-diverse", "--wake-demand-driven"])
    config = pipeline_config(args)
    assert config.wake.oe_representatives == 2
    assert config.full.oe_representatives == 1
    assert config.wake_diverse and config.wake_demand_driven
    single, diverse = arm_config(PipelineConfig(), "demand_single"), arm_config(PipelineConfig(), "diverse")
    assert single.full == diverse.full
    assert single.wake_demand_driven and diverse.wake_demand_driven
    assert single.wake_top_k == 1 and diverse.wake_top_k == 5


def test_loo_split_excludes_heldout_example_and_preserves_pair_identity():
    pairs = [(object(), object()) for _ in range(3)]
    for i in range(3):
        train, heldout = split_pairs(pairs, i)
        assert len(train) == 2 and heldout == [pairs[i]]
        assert all(p is not pairs[i] for p in train)


def test_unknown_labels_are_not_failures_and_diagnostics_cost_is_separate():
    def row(fold, correct, fitted):
        return {"arm": "diverse", "heldout_index": fold, "evaluation": {"all_test_correct": correct},
                "training_evaluation": {"all_test_correct": fitted}, "total_expanded_states": 10,
                "resources": {"solve_wall_seconds": 2, "solve_cpu_seconds": 1, "peak_rss_bytes": 100}}
    stats = aggregate([row(None, None, True), row(0, False, False), row(1, True, True)])["diverse"]
    assert stats["full"]["scored_runs"] == 0 and stats["full"]["accuracy"] is None
    assert stats["loo"]["accuracy"] == .5
    assert stats["loo"]["generalization_given_fit"] == 1
    assert stats["loo"]["total_expanded_states"] == 20
    assert stats["full"]["total_expanded_states"] == 10


def test_native_peak_memory_is_reported_in_bytes():
    assert peak_rss_bytes() > 1024 * 1024


def test_worker_does_not_pass_heldout_labels_to_the_learner(tmp_path, monkeypatch):
    import json
    from arc_tsl.experiments import generalization
    path = tmp_path / "task.json"
    data = {"train": [{"input": [[1]], "output": [[1]]},
                       {"input": [[2]], "output": [[2]]},
                       {"input": [[3]], "output": [[3]]}],
            "test": [{"input": [[4]], "output": [[9]]}]}
    calls = []
    def learn(train, config, parameter_completion):
        calls.append(train)
        assert train == [(to_grid([[1]]), to_grid([[1]])), (to_grid([[2]]), to_grid([[2]]))]
        return {"status": "SOLVED", "program": "$0", "total_expanded_states": 1}
    monkeypatch.setattr(generalization, "run_tsl", learn)
    job = {"task_id": "test", "arm": "diverse", "heldout_index": 2,
           "data_path": str(path), "config": PipelineConfig().to_dict()}
    path.write_text(json.dumps(data))
    before = generalization.run_worker(job)
    data["train"][2]["output"] = [[8]]
    path.write_text(json.dumps(data))
    after = generalization.run_worker(job)
    assert len(calls) == 2 and calls[0] == calls[1]
    assert before["frozen_program_sha256"] == after["frozen_program_sha256"]
    assert before["evaluation"]["all_test_correct"] is True
    assert after["evaluation"]["all_test_correct"] is False
    assert before["train_indices"] == [0, 1]
