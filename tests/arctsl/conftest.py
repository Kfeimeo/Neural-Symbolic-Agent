import random

import pytest

from arc_tsl.arc.grid import to_grid


def random_grid(rng: random.Random, h: int, w: int, density: float = 0.4, colors=(1, 2, 3)):
    return to_grid([[rng.choice(colors) if rng.random() < density else 0 for _ in range(w)] for _ in range(h)])


@pytest.fixture
def rng():
    return random.Random(1234)
