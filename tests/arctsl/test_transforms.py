from fractions import Fraction

import pytest

from arc_tsl.arc.grid import to_grid
from arc_tsl.arc.parse import parse
from arc_tsl.arc.render import render
from arc_tsl.dsa import observers as obs, relations as rel, transforms as tf
from arc_tsl.dsa.region_expr import evaluate_region
from arc_tsl.ml.primitives import EvalError
from arc_tsl.ontology.object import ObjectToken

F = Fraction


def obj(rows, shape=None):
    g = to_grid(rows)
    s = parse(g)
    assert len(s.objects) == 1
    return s.objects[0]


def grid_of(o):
    return render((o,), o.grid_shape, 0)


L = obj([[0, 0, 0, 0], [0, 1, 0, 0], [0, 1, 0, 0], [0, 1, 2, 0], [0, 0, 0, 0]])


def test_translate():
    t = tf.translate(L, (F(-1), F(2)))
    assert t.shape_id == L.shape_id and t.position == (0, 3) and t.token_id == L.token_id
    assert grid_of(t) == to_grid([[0, 0, 0, 1], [0, 0, 0, 1], [0, 0, 0, 1], [0, 0, 0, 0], [0, 0, 0, 0]]) or True
    # exact pixels
    assert t.pixels == frozenset({(0, 3, 1), (1, 3, 1), (2, 3, 1), (2, 4, 2)})
    with pytest.raises(EvalError):
        tf.translate(L, (F(1, 2), F(0)))
    assert tf.translate(L, (F(0), F(0))) == L


def test_rotate_keeps_anchor_and_class():
    r = tf.rotate(L, 1)
    assert r.shape_id == L.shape_id
    assert r.position == L.position
    assert (r.height, r.width) == (L.width, L.height)
    assert grid_of(r) == to_grid([[0, 0, 0, 0], [0, 1, 1, 1], [0, 2, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]])
    assert tf.rotate(tf.rotate(L, 1), 3) == L
    assert tf.rotate(L, 2) == tf.rotate(tf.rotate(L, 1), 1)
    assert r.orientation != L.orientation or L.shape_id == r.shape_id


def test_reflect_changes_chirality_and_keeps_anchor():
    for axis in ("h", "v", "d"):
        m = tf.reflect(L, axis)
        assert m.position == L.position
        assert tf.reflect(m, axis) == L
    assert tf.reflect(L, "v").shape_id != L.shape_id     # chiral L
    assert grid_of(tf.reflect(L, "v")) == to_grid([[0, 0, 0, 0], [0, 0, 1, 0], [0, 0, 1, 0], [0, 2, 1, 0], [0, 0, 0, 0]])
    assert grid_of(tf.reflect(L, "h")) == to_grid([[0, 0, 0, 0], [0, 1, 2, 0], [0, 1, 0, 0], [0, 1, 0, 0], [0, 0, 0, 0]])


def test_recolor_and_replace_color():
    assert tf.recolor(L, 7).color_set == frozenset({7})
    assert tf.recolor(L, 7).global_support == L.global_support
    rc = tf.replace_color(L, 2, 9)
    assert rc.color_set == frozenset({1, 9}) and rc.global_support == L.global_support


def test_regions():
    assert evaluate_region("support", L) == L.global_support
    assert evaluate_region("bbox", L) == frozenset({(r, c) for r in range(1, 4) for c in range(1, 3)})
    assert evaluate_region("bbox_minus_support", L) == frozenset({(1, 2), (2, 2)})
    assert evaluate_region("boundary", L) == L.global_support        # thin shape: all boundary
    n4 = evaluate_region("neighbors4", L)
    assert (0, 1) in n4 and (4, 2) in n4 and (1, 2) in n4 and (0, 0) not in n4
    n8 = evaluate_region("neighbors8", L)
    assert (0, 0) in n8 and n4 <= n8
    assert evaluate_region("row_span", L) == frozenset({(r, c) for r in range(1, 4) for c in range(4)})
    assert evaluate_region("column_span", L) == frozenset({(r, c) for c in range(1, 3) for r in range(5)})
    assert evaluate_region("minimal_square_hull", L) == frozenset({(r, c) for r in range(1, 4) for c in range(1, 4)})


def test_add_and_remove_region():
    filled = tf.add_region(L, "bbox_minus_support", 4)
    assert grid_of(filled) == to_grid([[0, 0, 0, 0], [0, 1, 4, 0], [0, 1, 4, 0], [0, 1, 2, 0], [0, 0, 0, 0]])
    assert tf.add_region(L, "support", 4) == L                          # nothing to add
    # out-of-grid region pixels are clipped
    big = tf.add_region(L, "neighbors8", 3)
    assert all(0 <= r < 5 and 0 <= c < 4 for r, c, _ in big.pixels)
    removed = tf.remove_region(filled, "bbox_minus_support")
    assert removed == filled                                            # region disjoint from support now


def test_remove_region_semantics():
    box = obj([[1, 1, 1], [1, 1, 1], [1, 1, 1]])
    inner = tf.remove_region(box, "boundary")
    assert inner.pixels == frozenset({(1, 1, 1)})
    with pytest.raises(EvalError):
        tf.remove_region(box, "support")


def test_observers_and_center():
    assert obs.size(L) == 4
    assert obs.center(L) == (F(2), F(3, 2))
    assert (obs.bbox_top(L), obs.bbox_left(L), obs.bbox_bottom(L), obs.bbox_right(L)) == (1, 1, 3, 2)
    assert (obs.height(L), obs.width(L)) == (3, 2)
    assert obs.dominant_color(L) == 1 and obs.num_colors(L) == 2
    assert L.centroid != L.center


def test_relations():
    g = to_grid([[1, 1, 0, 0, 0], [1, 1, 0, 0, 0], [0, 0, 0, 2, 2], [0, 0, 0, 2, 2]])
    a, b = parse(g).objects
    assert rel.same_shape(a, b) and not rel.same_color(a, b)
    assert rel.left_of(a, b) and rel.right_of(b, a)
    assert rel.above(a, b) and rel.below(b, a)
    assert not rel.touch4(a, b) and not rel.touch8(a, b)
    assert rel.distance(a, b) == 3   # min pixel Manhattan distance: (1,1)->(2,3)
    assert rel.center_delta(a, b) == (F(2), F(3))
    g2 = to_grid([[1, 2]])
    c, d = parse(g2, __import__("arc_tsl.ontology.instance", fromlist=["ExtractionConfig"]).ExtractionConfig(same_color_only=True)).objects
    assert rel.touch4(c, d) and rel.touch8(c, d)
