"""End-to-end pipeline tests on small synthetic tasks (fast budgets)."""
from arc_tsl.arc.grid import to_grid
from arc_tsl.arc.parse import parse
from arc_tsl.arc.render import render
from arc_tsl.dsa.types import OBJECT
from arc_tsl.language import base_library
from arc_tsl.ml.ast import Abs, App, Prim, Var
from arc_tsl.ontology.instance import ExtractionConfig
from arc_tsl.synthesis.enumerator import EnumerationConfig, _subsample
from arc_tsl.synthesis.evaluator import evaluate
from arc_tsl.tsl.pipeline import (STATUS_SOLVED, STATUS_UNSUPPORTED, PipelineConfig, library_key, run_baseline,
                                  run_tsl)

L = base_library()


def synthetic_task(program, grids):
    out = []
    for g in grids:
        s = parse(g)
        out.append((g, render(evaluate(program, L, (s.objects,)), s.grid_shape, s.background)))
    return out


GRIDS = [to_grid([[0, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]),
         to_grid([[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 3, 0], [0, 0, 0, 0]]),
         to_grid([[0, 4, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]])]
MOVE_DOWN = App("map", (Abs(OBJECT, App("translate", (Var(0), Prim("down")))), Var(0)))
CFG = PipelineConfig(ExtractionConfig(), EnumerationConfig(7, 100_000, 60), EnumerationConfig(7, 100_000, 60), 1, 3, 3, 2)


def test_subsample_is_deterministic_and_bounded():
    items = list(range(100))
    assert _subsample(items, 200) == items
    s = _subsample(items, 10)
    assert len(s) == 10 and s == sorted(s) and s[0] == 0
    assert _subsample(items, 10) == s


def test_unsupported_task_is_reported_not_searched():
    train = [(to_grid([[1, 0]]), to_grid([[1], [0]]))]
    assert run_baseline(train, CFG)["status"] == STATUS_UNSUPPORTED
    assert run_tsl(train, CFG)["status"] == STATUS_UNSUPPORTED


def test_baseline_and_tsl_pipeline_records():
    train = synthetic_task(MOVE_DOWN, GRIDS)
    b = run_baseline(train, CFG)
    assert b["status"] == STATUS_SOLVED and b["program_length"] == 6
    assert b["search"]["first_solution_states"] is not None
    cache = {}
    t = run_tsl(train, CFG, abstractions=True, reweight=False, rewake_cache=cache)
    assert t["status"] == STATUS_SOLVED
    assert t["wake"]["solved_pairs"] == 3
    assert t["sleep"]["num_abstractions"] == 1
    assert t["abstractions_used"] == ["#f0"]
    assert t["expanded_program"] == str(MOVE_DOWN)
    assert t["total_mdl"] == t["sleep"]["library_description_length"] + t["program_length"]
    assert t["rewake"]["expanded_states"] < b["search"]["expanded_states"]
    # reweight-only shares nothing with the TSL library but is still solved
    r = run_tsl(train, CFG, abstractions=False, reweight=True, rewake_cache=cache)
    assert r["status"] == STATUS_SOLVED and r["sleep"]["num_abstractions"] == 0
    assert r["sleep"]["costs"]["rotate"] == 2 and "translate" not in r["sleep"]["costs"]
    assert r["program"] == b["program"]
    # a second identical condition reuses the cached re-wake
    r2 = run_tsl(train, CFG, abstractions=False, reweight=True, rewake_cache=cache)
    assert r2["rewake_shared"] is True and r2["rewake"] == r["rewake"]


def test_library_key_distinguishes_costs_and_abstractions():
    assert library_key(L) == ((), ())
    assert library_key(L.with_costs({"rotate": 2})) != library_key(L)
