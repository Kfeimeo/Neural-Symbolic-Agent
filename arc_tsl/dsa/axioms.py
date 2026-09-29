"""DSA primitive table: fixed, task-independent domain axioms."""
from __future__ import annotations

from ..ml.primitives import Primitive, constant, function
from ..ml.types import BOOL, INT
from ..ontology.object import make_object_set
from . import observers as obs, relations as rel, transforms as tf
from .region_expr import REGION_NAMES
from .types import AXIS, COLOR, COLORSET, OBJECT, OBJECTS, REGION, SHAPE, TURN, VEC2


def _nearest(reference, objects):
    candidates = [o for o in objects if o != reference]
    if not candidates:
        raise ValueError("nearest: no other objects")
    best, best_d = None, None
    for o in candidates:
        d = rel.distance(reference, o)
        if best is None or d < best_d:
            best, best_d = o, d
    return best


def dsa_primitives() -> list[Primitive]:
    L = "dsa"
    P: list[Primitive] = []
    # constants: colors, turns, axes, regions
    for c in range(10):
        P.append(constant(f"c{c}", COLOR, c, L, "nominal color"))
    P += [constant("r90", TURN, 1, L), constant("r180", TURN, 2, L), constant("r270", TURN, 3, L)]
    P += [constant("axis_h", AXIS, "h", L), constant("axis_v", AXIS, "v", L), constant("axis_d", AXIS, "d", L)]
    P += [constant(f"rg_{n}", REGION, n, L, "object-local region") for n in REGION_NAMES]
    # transforms: Object x Param -> Object
    P += [
        function("translate", (OBJECT, VEC2), OBJECT, tf.translate, L),
        function("rotate", (OBJECT, TURN), OBJECT, tf.rotate, L),
        function("reflect", (OBJECT, AXIS), OBJECT, tf.reflect, L),
        function("recolor", (OBJECT, COLOR), OBJECT, tf.recolor, L),
        function("replace_color", (OBJECT, COLOR, COLOR), OBJECT, tf.replace_color, L),
        function("add_region", (OBJECT, REGION, COLOR), OBJECT, tf.add_region, L),
        function("remove_region", (OBJECT, REGION), OBJECT, tf.remove_region, L),
    ]
    # observers
    P += [
        function("size", (OBJECT,), INT, obs.size, L),
        function("center", (OBJECT,), VEC2, obs.center, L),
        function("bbox_top", (OBJECT,), INT, obs.bbox_top, L),
        function("bbox_left", (OBJECT,), INT, obs.bbox_left, L),
        function("bbox_bottom", (OBJECT,), INT, obs.bbox_bottom, L),
        function("bbox_right", (OBJECT,), INT, obs.bbox_right, L),
        function("height", (OBJECT,), INT, obs.height, L),
        function("width", (OBJECT,), INT, obs.width, L),
        function("color_set", (OBJECT,), COLORSET, obs.color_set, L),
        function("dominant_color", (OBJECT,), COLOR, obs.dominant_color, L),
        function("num_colors", (OBJECT,), INT, obs.num_colors, L),
        function("shape_id", (OBJECT,), SHAPE, obs.shape_id, L),
        function("orientation", (OBJECT,), INT, obs.orientation, L),
        function("has_color", (COLORSET, COLOR), BOOL, lambda s, c: c in s, L),
        function("eq_color", (COLOR, COLOR), BOOL, lambda a, b: a == b, L),
        function("eq_shape", (SHAPE, SHAPE), BOOL, lambda a, b: a == b, L),
    ]
    # relations
    P += [
        function("same_shape", (OBJECT, OBJECT), BOOL, rel.same_shape, L),
        function("same_color", (OBJECT, OBJECT), BOOL, rel.same_color, L),
        function("left_of", (OBJECT, OBJECT), BOOL, rel.left_of, L),
        function("right_of", (OBJECT, OBJECT), BOOL, rel.right_of, L),
        function("above", (OBJECT, OBJECT), BOOL, rel.above, L),
        function("below", (OBJECT, OBJECT), BOOL, rel.below, L),
        function("touch4", (OBJECT, OBJECT), BOOL, rel.touch4, L),
        function("touch8", (OBJECT, OBJECT), BOOL, rel.touch8, L),
        function("distance", (OBJECT, OBJECT), INT, rel.distance, L),
        function("center_delta", (OBJECT, OBJECT), VEC2, rel.center_delta, L),
        function("nearest", (OBJECT, OBJECTS), OBJECT, _nearest, L),
    ]
    return P
