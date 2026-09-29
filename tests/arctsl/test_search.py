from arc_tsl.arc.grid import to_grid
from arc_tsl.arc.parse import parse
from arc_tsl.arc.render import render
from arc_tsl.dsa.types import OBJECT, OBJECTS
from arc_tsl.language import base_library
from arc_tsl.ml.ast import Abs, App, Prim, Var
from arc_tsl.synthesis.enumerator import EnumerationConfig
from arc_tsl.synthesis.evaluator import ERR, evaluate
from arc_tsl.synthesis.search import Pair, search

L = base_library()
G1 = to_grid([[1, 1, 0, 0], [1, 1, 0, 0], [0, 0, 0, 0], [0, 0, 2, 0], [0, 0, 0, 0]])
G2 = to_grid([[0, 0, 0, 3], [0, 4, 4, 0], [0, 0, 0, 0], [0, 0, 0, 0]])


def apply(program, grid):
    scene = parse(grid)
    out = evaluate(program, L, (scene.objects,))
    assert out is not ERR
    return render(out, scene.grid_shape, scene.background)


def test_evaluate_map_translate():
    p = App("map", (Abs(OBJECT, App("translate", (Var(0), Prim("down")))), Var(0)))
    assert apply(p, G1) == to_grid([[0, 0, 0, 0], [1, 1, 0, 0], [1, 1, 0, 0], [0, 0, 0, 0], [0, 0, 2, 0]])


def test_evaluate_errors_are_err():
    p = App("argmin", (Abs(OBJECT, App("size", (Var(0),))), Var(0)))
    assert evaluate(p, L, ((),)) is ERR


def test_search_finds_program_and_reports_stats():
    p = App("map", (Abs(OBJECT, App("translate", (Var(0), Prim("down")))), Var(0)))
    pairs = [Pair(parse(g), apply(p, g)) for g in (G1, G2)]
    r = search(pairs, L, EnumerationConfig(max_cost=7, max_expanded_states=200_000, time_limit_seconds=60))
    assert r.solved
    best = r.frontier.best
    assert best.description_length == 6
    assert r.first_solution_nodes is not None and r.first_solution_states is not None
    assert r.stats.expanded_states >= r.first_solution_states
    assert r.stats.evaluated_programs > 0
    for pair in pairs:
        assert render(evaluate(best.program, L, (pair.scene.objects,)), pair.scene.grid_shape, 0) == pair.output


def test_search_top_k_collects_distinct_programs_with_same_behaviour():
    # Observational equivalence merges programs that agree on every sample
    # binding, so top-K frontiers only contain programs that differ somewhere
    # (here: different off-grid positions all render to the empty grid).
    g = to_grid([[0, 0, 0], [0, 0, 0], [0, 7, 0]])
    empty = to_grid([[0, 0, 0]] * 3)
    r = search([Pair(parse(g), empty)], L, EnumerationConfig(max_cost=7, max_expanded_states=100_000, time_limit_seconds=60),
               top_k=3)
    assert len(r.frontier.solutions) == 3
    assert len({str(s.program) for s in r.frontier.solutions}) == 3
    assert r.termination_reason == "frontier_complete"


def test_search_budget_and_termination_reason():
    pairs = [Pair(parse(G1), G2[:5] if False else to_grid([[9] * 4] * 5))]
    r = search(pairs, L, EnumerationConfig(max_cost=4, max_expanded_states=500, time_limit_seconds=60))
    assert not r.solved
    assert r.termination_reason in ("max_expanded_states", "max_cost")
    assert r.stats.expanded_states <= 500


def test_observational_equivalence_prunes():
    pairs = [Pair(parse(G1), to_grid([[9] * 4] * 5))]
    r = search(pairs, L, EnumerationConfig(max_cost=4, max_expanded_states=50_000, time_limit_seconds=60))
    assert r.stats.equivalent_terms > 0
    assert r.stats.retained_terms < r.stats.expanded_states
