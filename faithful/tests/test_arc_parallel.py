from dataclasses import replace, asdict
import random
import time

import pytest

from faithful.lib import (Kernel, ExploreCompress, ECConfig, SearchConfig, DreamConfig,
                          RecognitionConfig, NoCompression, OriginalCompressor, ast)
from faithful.lib.domains.arc_shapes import ARCShapesDomain, convert_term
from faithful.lib.domains.lists import ArithmeticDomain
from faithful.lib.ec import generic_wake
from arc_tsl.ml.parser import parse_term
from arc_tsl.language import grid_library
from arc_tsl.synthesis.evaluator import evaluate


def slow_wake(*args):
    time.sleep(0.5)  # Ensure both spawned workers receive work, independent of startup skew.
    return generic_wake(*args)


def bad_wake(*args):
    raise RuntimeError("intentional worker failure")


def cfg(workers):
    return ECConfig(rounds=1, workers=workers, search=SearchConfig(limit=12, max_states=300),
                    dream=DreamConfig(draws=2), recognition=RecognitionConfig(steps=1))


def test_adapter_semantics_types_and_dreams():
    d = ARCShapesDomain()
    term = parse_term('(paint (shape (argmax (lambdaObject. (size $0)) (objects4 $0 c0))) '
                      '(position i0 i0) (canvas (grid_dims $0) c0))')
    program = ast.abstraction(convert_term(term))
    grid = ((0, 2, 2), (0, 0, 0))
    expected = evaluate(term, grid_library(), (grid,))
    assert d.evaluate(program, [grid]) == expected
    task = d.unary_task('example', [(grid, expected)])
    assert d.features(task).shape == (24,)
    dream = d.dream(program, d.request, [task], random.Random(1))
    assert dream.outputs == [expected]
    with Kernel(timeout=30) as k:
        k.infer(d.grammar(), program)
    # A black pixel is opaque even through the curried faithful interpreter.
    black = ast.abstraction(convert_term(parse_term(
        '(paint (shape (argmax (lambdaObject. (size $0)) (objects4 $0 c2))) '
        '(position i0 i0) (canvas (grid_dims $0) c9))')))
    assert d.evaluate(black, [((2, 0),)]) == ((0, 9),)


def test_parallel_equal_serial_budget_order_and_kernel_isolation():
    d = ArithmeticDomain()
    tasks = [d.unary_task(f't{i}', [(1, 2), (5, 6)]) for i in range(6)]
    with Kernel(timeout=30) as k:
        serial = ExploreCompress(d, k, NoCompression(), cfg(1)).solve(tasks)
        parallel = ExploreCompress(d, k, NoCompression(), cfg(2), wake=slow_wake).solve(tasks)
        assert [f for f, _ in serial] == [f for f, _ in parallel]
        for (_, a), (_, b) in zip(serial, parallel):
            assert (a.task, a.enumerated, a.expanded_states, a.stop_reason) == (
                b.task, b.enumerated, b.expanded_states, b.stop_reason)
        assert len({t.worker_pid for _, t in parallel}) == 2
        assert len({t.kernel_pid for _, t in parallel}) == 2
        assert all(t.kernel_pid != k.process.pid for _, t in parallel)


def test_arc_parallel_full_round_and_solve():
    d = ARCShapesDomain()
    tasks = [d.unary_task(str(i), [(((i, 0),), ((i, 0),))]) for i in (1, 2)]
    with Kernel(timeout=30) as k:
        a = ExploreCompress(d, k, OriginalCompressor(), cfg(1))
        b = ExploreCompress(d, k, OriginalCompressor(), cfg(2))
        ha, hb = a.run(tasks)[0], b.run(tasks)[0]
        assert ha.frontiers == hb.frontiers
        assert ha.grammar == hb.grammar
        assert ha.dream == hb.dream
        assert ha.recognition_losses == hb.recognition_losses
        assert ha.solved == hb.solved == 2
        assert [f for f, _ in a.solve(tasks)] == [f for f, _ in b.solve(tasks)]


def test_parallel_failure_is_not_unsolved():
    d = ArithmeticDomain()
    tasks = [d.unary_task(str(i), [(1, 2)]) for i in range(2)]
    with Kernel(timeout=30) as k:
        ec = ExploreCompress(d, k, NoCompression(), cfg(2), wake=bad_wake)
        with pytest.raises(RuntimeError, match='intentional worker failure'):
            ec.solve(tasks)
        assert ec.solve([]) == []
        k.infer(d.grammar(), ast.primitive('incr'))


def test_workers_validation():
    for n in (0, -1, 1.5):
        with pytest.raises(ValueError):
            ECConfig(workers=n)
