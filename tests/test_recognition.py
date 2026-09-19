import random

import torch

from dreamcoder.domains.grid import make_language, sample_grid
from dreamcoder.domains.grid.features import encode_task
from dreamcoder.dreaming import dream
from dreamcoder.grammar import Grammar
from dreamcoder.recognition import RecognitionModel
from dreamcoder.tasks import Task


def test_recognition_training_pooling_and_vocabulary():
    torch.set_num_threads(1)
    torch.manual_seed(2)
    grammar = Grammar.uniform(make_language())
    pairs = dream(grammar, sample_grid, random.Random(2), count=30)
    model = RecognitionModel(list(grammar.language.primitives), len(encode_task(pairs[0].task)[0]), encode_task)
    history = model.fit(pairs, seed=2, epochs=12)
    assert history[-1] < history[0]
    task = pairs[0].task
    reordered = Task("reordered", task.examples[::-1])
    one = model.contextual_grammar(task, grammar)
    two = model.contextual_grammar(reordered, grammar)
    assert set(one.log_probabilities) == set(grammar.log_probabilities)
    assert all(abs(one.log_probabilities[n]-two.log_probabilities[n]) < 1e-5 for n in one.log_probabilities)
    assert abs(sum(torch.exp(torch.tensor(list(one.log_probabilities.values())))).item()-1) < 1e-5
