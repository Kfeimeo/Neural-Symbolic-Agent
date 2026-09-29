import random

from arc_tsl.ontology.canonicalize import orientation, shape_id
from arc_tsl.ontology.geometry import bbox_center, normalize, reflect_local, rotate_local, translate

L_SHAPE = frozenset({(0, 0), (1, 0), (2, 0), (2, 1)})       # chiral "L"
SQUARE = frozenset({(0, 0), (0, 1), (1, 0), (1, 1)})


def random_support(rng, n=6):
    pts = set()
    while len(pts) < n:
        pts.add((rng.randrange(6), rng.randrange(6)))
    return frozenset(pts)


def test_shape_id_invariant_under_translation_and_rotation():
    rng = random.Random(0)
    for _ in range(200):
        s = random_support(rng, rng.randint(1, 7))
        sid = shape_id(s)
        assert shape_id(translate(s, rng.randint(-9, 9), rng.randint(-9, 9))) == sid
        for k in range(4):
            assert shape_id(rotate_local(s, k)) == sid
            assert shape_id(translate(rotate_local(s, k), 3, -2)) == sid


def test_shape_id_distinguishes_reflection_of_chiral_shape():
    assert shape_id(L_SHAPE) != shape_id(reflect_local(L_SHAPE, "v"))
    assert shape_id(L_SHAPE) != shape_id(reflect_local(L_SHAPE, "h"))
    # achiral shapes are unaffected
    assert shape_id(SQUARE) == shape_id(reflect_local(SQUARE, "v"))


def test_shape_id_is_lexicographically_minimal_rotation():
    sid = shape_id(L_SHAPE)
    forms = [tuple(sorted(rotate_local(L_SHAPE, k))) for k in range(4)]
    assert sid == min(forms)
    assert sid in forms


def test_rotation_is_cyclic_and_normalized():
    for k in range(4):
        s = rotate_local(L_SHAPE, k)
        assert normalize(s) == s
    assert rotate_local(L_SHAPE, 4) == normalize(L_SHAPE)
    assert rotate_local(rotate_local(L_SHAPE, 1), 3) == normalize(L_SHAPE)


def test_orientation_matches_rotation_of_canonical_form():
    for k in range(4):
        s = rotate_local(L_SHAPE, k)
        o = orientation(s)
        assert tuple(sorted(rotate_local(frozenset(shape_id(s)), o))) == tuple(sorted(s))
    # symmetric shapes report the smallest matching orientation
    assert orientation(SQUARE) == 0


def test_bbox_center_supports_half_integers():
    assert bbox_center(SQUARE) == (0.5, 0.5)                 # even bbox -> half-integer
    assert bbox_center(frozenset({(0, 0), (0, 1), (0, 2)})) == (0, 1)   # odd -> integer
    assert bbox_center(L_SHAPE) == (1, 0.5)                  # mixed
    assert bbox_center(translate(SQUARE, 3, 4)) == (3.5, 4.5)
