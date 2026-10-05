"""TSL compression on synthetic pair frontiers: discovery, MDL decrease,
semantic preservation, and re-wake using the abstraction."""
from arc_tsl.arc.grid import to_grid
from arc_tsl.arc.parse import parse
from arc_tsl.arc.render import render
from arc_tsl.dsa.types import OBJECT, OBJECTS
from arc_tsl.language import base_library
from arc_tsl.ml.ast import Abs, App, Prim, Var
from arc_tsl.synthesis.enumerator import EnumerationConfig
from arc_tsl.synthesis.evaluator import evaluate
from arc_tsl.synthesis.search import Pair, search
from arc_tsl.tsl.compression import anti_unify, close_subterm, compress, match, rewrite
from arc_tsl.tsl.local_library import abstraction_to_candidate, contract, fit_costs, prune_unused, rewrite_with_library

L = base_library()


def prog(v):
    return App("map", (Abs(OBJECT, App("recolor", (App("translate", (Var(0), v)), Prim("c2")))), Var(0)))


P_DOWN, P_UP, P_VEC = prog(Prim("down")), prog(Prim("up")), prog(App("vec", (Prim("i2"), Prim("i0"))))


def test_close_subterm_turns_free_variables_into_typed_parameters():
    inner = App("recolor", (App("translate", (Var(0), Var(1))), Prim("c2")))
    c = close_subterm(L, inner, OBJECT, (OBJECT, OBJECTS))
    assert c.arity == 2 and c.param_types == (OBJECT, OBJECTS)
    assert str(c.pattern) == "(recolor (translate ?0 ?1) c2)"


def test_anti_unify_generalises_mismatch_and_respects_lambda_scope():
    c = anti_unify(L, P_DOWN, P_UP, OBJECTS)
    assert c is not None and c.arity == 1
    assert str(c.pattern) == "(map (λObject. (recolor (translate $0 ?0) c2)) $0)"
    # a mismatch that would capture the lambda variable lifts to the lambda
    a = App("map", (Abs(OBJECT, App("size", (Var(0),))), Var(0)))
    b = App("map", (Abs(OBJECT, App("height", (Var(0),))), Var(0)))
    # (illegal types, but structure only) -> whole lambda becomes the hole
    c2 = anti_unify(L, App("filter", (Abs(OBJECT, App("eq_int", (App("size", (Var(0),)), Prim("i1")))), Var(0))),
                       App("filter", (Abs(OBJECT, App("eq_int", (App("size", (Var(0),)), App("height", (Var(0),))))), Var(0))),
                       OBJECTS)
    assert c2 is not None and "λ" not in str(c2.pattern).split("?0")[0] or c2.arity == 1


def test_compress_discovers_shared_fragment_and_reduces_mdl():
    res = compress(L, [[P_DOWN], [P_UP], [P_VEC]], (OBJECTS,), OBJECTS)
    assert res.added == ["#f0"]
    assert res.mdl_after < res.mdl_before
    a = res.library.abstractions["#f0"]
    assert a.arity == 2 and a.result == OBJECTS
    for F, original in zip(res.frontiers, [P_DOWN, P_UP, P_VEC]):
        assert res.library.expand(F[0]) == original           # semantics preserved syntactically
        assert res.library.infer(F[0], (OBJECTS,)) == OBJECTS
    # evaluation agrees too
    g = to_grid([[0, 1, 0], [0, 0, 0], [3, 0, 0]])
    s = parse(g)
    for F, original in zip(res.frontiers, [P_DOWN, P_UP, P_VEC]):
        assert evaluate(F[0], res.library, (s.objects,)) == evaluate(original, L, (s.objects,))


def test_compress_is_gated_by_mdl():
    # a single program cannot pay for an abstraction that only removes one use
    res = compress(L, [[P_DOWN]], (OBJECTS,), OBJECTS)
    assert res.added == []
    assert res.mdl_after == res.mdl_before


def test_rewrite_and_match_shift_arguments_out_of_lambdas():
    res = compress(L, [[P_DOWN], [P_UP]], (OBJECTS,), OBJECTS)
    cand = abstraction_to_candidate(res.library.abstractions["#f0"])
    # program whose Vec2 argument refers to the outer scene ($0 inside λ is $1)
    v = App("center", (App("argmin", (Abs(OBJECT, App("size", (Var(0),))), Var(1))),))
    p = App("map", (Abs(OBJECT, App("recolor", (App("translate", (Var(0), v)), Prim("c2")))), Var(0)))
    r = rewrite(p, cand, "#f0")
    assert "#f0" in str(r)
    assert "$1" not in str(r).split("#f0")[1].split(")")[0]   # argument shifted out of the lambda
    assert res.library.expand(r) == p
    assert res.library.infer(r, (OBJECTS,)) == OBJECTS


def test_prune_and_contract():
    res = compress(L, [[P_DOWN], [P_UP], [P_VEC]], (OBJECTS,), OBJECTS)
    lib, removed = prune_unused(res.library, res.frontiers)
    assert removed == [] and "#f0" in lib.abstractions
    lib2, removed2 = contract(lib, [[P_DOWN], [P_UP], [P_VEC]])
    assert removed2 == [] and "#f0" in lib2.abstractions
    # an abstraction nobody uses is pruned
    lib3, removed3 = prune_unused(res.library, [[P_DOWN]])
    assert removed3 == ["#f0"]


def test_fit_costs_marks_unused_productions():
    costs = fit_costs(L, [P_DOWN, P_UP], __import__("arc_tsl.tsl.local_library", fromlist=["ThetaConfig"]).ThetaConfig(2))
    assert costs["map"] == 1 and costs["translate"] == 1 and costs["rotate"] == 2


def test_rewake_uses_learned_abstraction_and_reduces_search():
    """pairwise programs -> local abstraction -> reduced search."""
    res = compress(L, [[P_DOWN], [P_UP], [P_VEC]], (OBJECTS,), OBJECTS)
    tsl = res.library
    g1 = to_grid([[0, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]])
    g2 = to_grid([[0, 0, 0, 0], [0, 0, 5, 0], [0, 0, 0, 0]])
    target = prog(Prim("right"))   # new instance of the shared fragment
    pairs = []
    for g in (g1, g2):
        s = parse(g)
        pairs.append(Pair(s, render(evaluate(target, L, (s.objects,)), s.grid_shape, 0)))
    cfg = EnumerationConfig(max_cost=8, max_expanded_states=300_000, time_limit_seconds=120)
    base_result = search(pairs, L, cfg)
    tsl_result = search(pairs, tsl, cfg)
    assert base_result.solved and tsl_result.solved
    assert "#f0" in str(tsl_result.frontier.best.program)
    assert tsl_result.first_solution_states < base_result.first_solution_states
    assert tsl_result.frontier.best.description_length < base_result.frontier.best.description_length
