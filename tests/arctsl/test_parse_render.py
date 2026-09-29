import random

import pytest

from arc_tsl.arc.grid import load_arc_task, to_grid
from arc_tsl.arc.parse import parse
from arc_tsl.arc.render import render
from arc_tsl.ontology.instance import ExtractionConfig, extract_instances
from tests.arctsl.conftest import random_grid

ROOT = "data/arc/training"


@pytest.mark.parametrize("connectivity", [4, 8])
@pytest.mark.parametrize("background", ["color0", "most_frequent"])
@pytest.mark.parametrize("same_color_only", [False, True])
def test_render_parse_identity_random(connectivity, background, same_color_only):
    rng = random.Random(7)
    cfg = ExtractionConfig(connectivity, background, same_color_only)
    for _ in range(60):
        g = random_grid(rng, rng.randint(1, 9), rng.randint(1, 9), rng.random())
        scene = parse(g, cfg)
        assert render(scene.objects, scene.grid_shape, scene.background) == g


def test_render_parse_identity_on_real_arc_tasks():
    import os
    files = sorted(os.listdir(ROOT))[:40]
    for f in files:
        task = load_arc_task(os.path.join(ROOT, f))
        for x, y in task["train"] + [(t[0], t[1]) for t in task["test"] if t[1] is not None]:
            for g in (x, y):
                for cfg in (ExtractionConfig(8, "color0"), ExtractionConfig(4, "most_frequent", True)):
                    scene = parse(g, cfg)
                    assert render(scene.objects, scene.grid_shape, scene.background) == g


def test_connectivity_policy_changes_component_count():
    g = to_grid([[1, 0], [0, 1]])
    assert len(extract_instances(g, ExtractionConfig(4))[0]) == 2
    assert len(extract_instances(g, ExtractionConfig(8))[0]) == 1


def test_background_policies():
    g = to_grid([[5, 5, 5], [5, 1, 5], [5, 5, 5]])
    inst0, bg0 = extract_instances(g, ExtractionConfig(background="color0"))
    instm, bgm = extract_instances(g, ExtractionConfig(background="most_frequent"))
    assert bg0 == 0 and len(inst0) == 1 and len(inst0[0].pixels) == 9
    assert bgm == 5 and len(instm) == 1 and len(instm[0].pixels) == 1


def test_same_color_only_splits_multicolor_component():
    g = to_grid([[1, 2]])
    assert len(extract_instances(g, ExtractionConfig(8, same_color_only=False))[0]) == 1
    assert len(extract_instances(g, ExtractionConfig(8, same_color_only=True))[0]) == 2


def test_object_multiplicity_and_class_identity():
    g = to_grid([[1, 1, 0, 0, 1, 1], [1, 1, 0, 0, 1, 1]])
    scene = parse(g)
    assert len(scene.objects) == 2
    a, b = scene.objects
    assert a.shape_id == b.shape_id
    assert a.object_class == b.object_class
    assert a != b and a.token_id != b.token_id
    assert a.position != b.position
    assert a.local_support == b.local_support
    assert a.global_support != b.global_support
