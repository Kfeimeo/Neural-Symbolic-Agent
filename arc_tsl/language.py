"""Base language Base_{ML+DSA}: the fixed primitive set shared by every
condition.  Nothing here is task-specific."""
from __future__ import annotations

from .dsa.axioms import dsa_primitives
from .dsa.types import OBJECT, OBJECTS, VEC2
from .ml.generic import bool_int_primitives, collection_primitives, vec2_primitives
from .ontology.object import make_object_set
from .synthesis.grammar import Library


def base_primitives():
    return (bool_int_primitives() + vec2_primitives(VEC2)
            + collection_primitives(OBJECT, OBJECTS, make_object_set) + dsa_primitives())


def base_library() -> Library:
    return Library.from_primitives(base_primitives())
