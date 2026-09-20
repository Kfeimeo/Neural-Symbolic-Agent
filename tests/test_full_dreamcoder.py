"""Phase 2 (full faithful DreamCoder, recognition ON) tests.

The learner, evaluation and analysis modules are exercised on tiny configurations
so that the suite stays fast; the long runs are validated by the parity report.
"""
import json
from pathlib import Path

import pytest

from faithful.compression.interface import BridgeKernel
from faithful.python.grid import Task, REQUEST
from benchmarks.latent_abstraction import generator as bench
from experiments.abstraction_learning import learner as phase1_learner
from experiments.abstraction_learning.evaluation import EVAL_SEARCH
from experiments.full_dreamcoder import learner, evaluation, analysis

ROOT = Path(__file__).resolve().parents[1]
INSTANCE = ROOT / 'benchmarks' / 'latent_abstraction' / 'data' / 'seed_101'


@pytest.fixture(scope='module')
def kernel():
    with BridgeKernel() as k:
        yield k


@pytest.fixture(scope='module')
def tasks():
    return [t for t in bench.load_tasks(INSTANCE / 'train.json') if t.name.startswith('train-medium-')][:10]


@pytest.fixture(scope='module')
def tiny_run(tmp_path_factory, tasks):
    out = tmp_path_factory.mktemp('fulldc')
    learner.run_condition(tasks, 'B', out, rounds=2, wake_limit=300, seed=1, dream_draws=6, recognition_steps=20, label='tiny', verbose=False)
    return out


def test_round_one_matches_recognition_off_learner(tmp_path, tasks):
    """Without a trained model the first round is exactly the Phase 1 loop."""
    on = tmp_path / 'on'
    off = tmp_path / 'off'
    learner.run_condition(tasks, 'B', on, rounds=1, wake_limit=300, seed=1, dream_draws=4, recognition_steps=5, verbose=False)
    phase1_learner.run_condition(tasks, 'B', off, rounds=1, wake_limit=300, verbose=False)
    a, b = phase1_learner.read_json(phase1_learner.round_path(on, 1)), phase1_learner.read_json(phase1_learner.round_path(off, 1))
    assert a['frontiers'] == b['frontiers']
    assert a['grammar'] == b['grammar']
    assert a['wake']['first_solution_nodes'] == b['wake']['first_solution_nodes']
    assert a['wake']['guided'] is False and a['options']['recognition'] == 'on' and b['options']['recognition'] == 'off'


def test_second_round_is_guided_and_resumable(tiny_run, tasks):
    record = phase1_learner.read_json(phase1_learner.round_path(tiny_run, 2))
    assert record['wake']['guided'] is True
    assert set(record['wake']['per_task']) == {t.name for t in tasks}
    assert record['recognition']['steps'] == 20 and len(record['recognition']['losses']) == 20
    assert record['dream']['draws'] == 6 and record['dream']['accepted'] + record['dream']['resource_or_evaluation_rejections'] == 6
    assert learner.checkpoint_path(tiny_run, 1).exists() and learner.checkpoint_path(tiny_run, 2).exists()
    model = learner.load_model(tiny_run, 2, record['grammar'])
    assert len(model.keys) == record['recognition']['context_count']
    before = json.dumps(record, sort_keys=True)
    learner.run_condition(tasks, 'B', tiny_run, rounds=2, wake_limit=300, seed=1, dream_draws=6, recognition_steps=20, verbose=False)
    assert json.dumps(phase1_learner.read_json(phase1_learner.round_path(tiny_run, 2)), sort_keys=True) == before


def test_guided_search_rescores_under_generative_grammar(kernel, tiny_run, tasks):
    record = phase1_learner.read_json(phase1_learner.round_path(tiny_run, 2))
    g = record['grammar']
    model = learner.load_model(tiny_run, 2, g)
    rows, _, _ = learner.guided_search(kernel, tasks[:3], g, model, dict(phase1_learner.SEARCH, limit=200))
    assert [r['name'] for r in rows] == [t.name for t in tasks[:3]]
    for r in rows:
        for s in r['solutions']:
            assert abs(kernel.call('score', grammar=g, request=REQUEST, program=s['program'])['log_probability'] - s['log_prior']) < 1e-9
    sg = model.search_grammar(__import__('faithful.python.grid', fromlist=['features']).features(tasks[0]))
    assert set(sg['contexts']) == set(model.keys) and all(len(v) == len(g['productions']) + 1 for v in sg['contexts'].values())


def test_guided_cache_is_keyed_by_search_grammar(kernel, tiny_run, tasks, tmp_path):
    record = phase1_learner.read_json(phase1_learner.round_path(tiny_run, 2))
    g = record['grammar']
    model = learner.load_model(tiny_run, 2, g)
    cache = tmp_path / 'cache'
    rows1, _, cached1 = evaluation.guided_cached_search(kernel, tasks[:2], g, model, cache, limit=100)
    rows2, _, cached2 = evaluation.guided_cached_search(kernel, tasks[:2], g, model, cache, limit=100)
    assert cached1 is False and cached2 is True and rows1 == rows2
    order = evaluation.derangement(2, 0)
    rows3, _, cached3 = evaluation.guided_cached_search(kernel, tasks[:2], g, model, cache, limit=100, guide_tasks=[tasks[j] for j in order])
    assert cached3 is False and [r['name'] for r in rows3] == [t.name for t in tasks[:2]]
    assert len(list(cache.glob('*.json.gz'))) == 4


def test_exposure_recall_and_rank_statistics():
    record = {'exposure': {'F0': {'count': 0}, 'F1': {'count': 1}, 'F2': {'count': 2}, 'F3': {'count': 5}},
              'per_task': [{'first_solution_nodes': 5}, {'first_solution_nodes': None}, {'first_solution_nodes': 400}, {'first_solution_nodes': 20}]}
    assert analysis.exposure_recall(record, 1) == 0.75 and analysis.exposure_recall(record, 2) == 0.5
    assert analysis.solved_ranks(record) == [5, 400, 20]
    assert analysis.quantile([1, 2, 3, 4], 0.5) == 2.5 and analysis.quantile([], 0.5) is None
    assert analysis.label_of({'base_arm': 'FullDC', 'training_seed': 1, 'mode': 'library', 'arm': 'FullDC_t1'}) == 'FullDC'
    assert analysis.label_of({'base_arm': 'FullDC', 'training_seed': 2, 'mode': 'recognition', 'arm': 'FullDC_t2'}) == 'FullDC_t2_rec'
    assert analysis.label_of({'arm': 'B'}) == 'B'


def test_derangement_never_maps_a_task_to_itself():
    for n in (2, 5, 30):
        order = evaluation.derangement(n, 7)
        assert sorted(order) == list(range(n)) and all(i != j for i, j in enumerate(order))
