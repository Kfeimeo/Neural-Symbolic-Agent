from arc_tsl.dsa.types import OBJECT, OBJECTS, VEC2
from arc_tsl.language import base_library
from arc_tsl.ml.ast import Abs, App, Prim, Var, free_variables, shift, substitute
from arc_tsl.ml.types import INT, Arrow
from arc_tsl.synthesis.grammar import Abstraction

L = base_library()
P = App("map", (Abs(OBJECT, App("recolor", (App("translate", (Var(0), Prim("down"))), Prim("c2")))), Var(0)))


def test_typing():
    assert L.infer(P, (OBJECTS,)) == OBJECTS
    assert L.infer(Abs(OBJECT, App("size", (Var(0),))), ()) == Arrow((OBJECT,), INT)
    try:
        L.infer(App("translate", (Prim("c1"), Prim("down"))), ())
        assert False
    except TypeError:
        pass


def test_free_variables_shift_substitute():
    body = Abs(OBJECT, App("translate", (Var(0), Var(2))))
    assert free_variables(body) == {1}
    assert shift(body, 3) == Abs(OBJECT, App("translate", (Var(0), Var(5))))
    assert substitute(body, 1, Prim("up")) == Abs(OBJECT, App("translate", (Var(0), Prim("up"))))


def test_abstraction_instantiate_and_expand():
    # #f(v, s) = map (λo. recolor (translate o v) c2) s
    body = App("map", (Abs(OBJECT, App("recolor", (App("translate", (Var(0), Var(2))), Prim("c2")))), Var(0)))
    a = Abstraction("#f", (VEC2, OBJECTS), OBJECTS, body)
    lib = L.with_abstraction(a)
    call = App("#f", (Prim("down"), Var(0)))
    assert lib.infer(call, (OBJECTS,)) == OBJECTS
    assert lib.expand(call) == P
    # argument with a free variable is shifted under the lambda correctly
    call2 = App("#f", (App("center", (App("argmin", (Abs(OBJECT, App("size", (Var(0),))), Var(0))),)), Var(0)))
    expanded = lib.expand(call2)
    assert L.infer(expanded, (OBJECTS,)) == OBJECTS
    assert free_variables(expanded) == {0}


def test_description_length_convention():
    assert L.description_length(P) == 8
    assert L.description_length(Var(0)) == 1
    assert L.with_costs({"map": 3}).description_length(P, uniform=False) == 10
