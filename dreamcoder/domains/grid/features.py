"""Fixed spatial/color correspondence features, independent of task labels.

The encoder exposes geometric correlations to a small MLP. It neither searches
programs nor reads ground truth. This is a deliberately domain-informed baseline.
"""
from . import Grid, rotate90, trim
from ...tasks import Task


def example_features(a: Grid, b: Grid) -> list[float]:
    features = [len(a)/12, len(a[0])/12, len(b)/12, len(b[0])/12]
    for x, y in ((a, b), (trim(a), trim(b))):
        for view in (x, rotate90(x), rotate90(rotate90(x)), tuple(r[::-1] for r in x), x[::-1], tuple(zip(*x))):
            h, w = max(len(view), len(y)), max(len(view[0]), len(y[0]))
            matrix = [0.0] * 25
            for r in range(h):
                for c in range(w):
                    u = view[r][c] if r < len(view) and c < len(view[0]) else 4
                    v = y[r][c] if r < len(y) and c < len(y[0]) else 4
                    matrix[u*5+v] += 1/(h*w)
            features.extend(matrix)
    return features


def encode_task(task: Task) -> list[list[float]]:
    return [example_features(e.input, e.output) for e in task.examples]
