"""Grid -> ObjectSet (symbolic scene)."""
from __future__ import annotations

from dataclasses import dataclass

from ..ontology.instance import ExtractionConfig, extract_instances
from ..ontology.object import ObjectSet, ObjectToken, make_object_set
from .grid import Grid, shape


@dataclass(frozen=True)
class Scene:
    objects: ObjectSet
    grid_shape: tuple[int, int]
    background: int


def parse(grid: Grid, config: ExtractionConfig = ExtractionConfig()) -> Scene:
    instances, bg = extract_instances(grid, config)
    H, W = shape(grid)
    tokens = [ObjectToken(inst.pixels, (H, W), token_id=i) for i, inst in enumerate(instances)]
    return Scene(make_object_set(tokens), (H, W), bg)
