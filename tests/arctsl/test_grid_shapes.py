import pytest

from arc_tsl.dsa.shapes import (Shape, canvas, dimensions, local_shape, objects4, objects8,
                               paint, same_geometry, same_geometry_rot,
                               same_geometry_dihedral, support)
from arc_tsl.dsa.types import GRID
from arc_tsl.language import base_library, grid_library
from arc_tsl.ml.parser import parse_term
from arc_tsl.synthesis.enumerator import EnumerationConfig
from arc_tsl.synthesis.evaluator import ERR, evaluate
from arc_tsl.synthesis.grid_search import search_grids


def test_views_background_and_roundtrip():
    grid = ((1, 2, 0), (0, 1, 0), (0, 0, 3))
    assert len(objects4(grid, 0)) == 4
    assert len(objects8(grid, 0)) == 1
    for bg in (0, 2, 7):
        for view in (objects4, objects8):
            output = canvas((3, 3), bg)
            for obj in view(grid, bg):
                output = paint(local_shape(obj), obj.position, output)
            assert output == grid
    assert objects4(((0, 0),), 0) == ()


def test_transparent_holes_black_overwrite_clipping_and_order():
    patch = Shape(((0, None), (None, 2)))
    assert paint(patch, (0, 0), canvas((2, 2), 9)) == ((0, 9), (9, 2))
    assert paint(patch, (1, 1), canvas((2, 2), 9)) == ((9, 9), (9, 0))
    assert paint(patch, (3, 3), canvas((2, 2), 9)) == canvas((2, 2), 9)
    assert support(patch) == frozenset({(0, 0), (1, 1)})
    assert paint(Shape(((3,),)), (0, 0), paint(patch, (0, 0), canvas((2, 2), 9)))[0][0] == 3


def test_geometry_modes_and_color_independence():
    a = support(Shape(((1, None, None), (1, 1, 1))))
    b = support(Shape(((None, 2), (None, 2), (2, 2))))
    mirror = frozenset((r, -c) for r, c in a)
    assert not same_geometry(a, b)
    assert same_geometry_rot(a, b)
    assert not same_geometry_rot(a, mirror)
    assert same_geometry_dihedral(a, mirror)
    assert same_geometry(a, support(Shape(((7, None, None), (7, 7, 7)))))
    assert same_geometry_rot(frozenset(), frozenset())


@pytest.mark.parametrize("dims", [(0, 2), (31, 2), (-1, 2), (1.5, 2)])
def test_invalid_dimensions(dims):
    with pytest.raises(ValueError):
        dimensions(*dims)


def test_typed_composition_and_invalid_position():
    lib = grid_library()
    program = parse_term('(paint (shape (argmax (lambdaObject. (size $0)) (objects4 $0 c0))) '
                         '(position i0 i0) (canvas (grid_dims $0) c0))')
    assert lib.infer(program, (GRID,)) == GRID
    assert evaluate(program, lib, (((0, 2, 2), (0, 0, 0)),)) == ((2, 2, 0), (0, 0, 0))
    assert evaluate(parse_term('(position (neg i1) i0)'), lib) is ERR
    assert "paint" not in base_library().primitives


def test_search_changes_canvas_size_and_generalizes_to_new_size():
    lib = grid_library()
    config = EnumerationConfig(max_cost=9, max_expanded_states=20000, time_limit_seconds=10,
                               max_lambda_depth=0)
    result = search_grids([(((1, 0, 0), (0, 0, 0)), ((2, 2), (2, 2), (2, 2))),
                           (((0, 0),), ((2,), (2,)))], lib, config)
    assert result.solved
    assert evaluate(result.frontier.best.program, lib, (((0, 0, 0, 0),),)) == ((2,),) * 4


def test_search_lambdas_use_objects_from_both_views():
    # Restrict the grammar to make this a small integration test of typed
    # enumeration, object lambda bindings, geometry extraction, and painting.
    from arc_tsl.synthesis.grammar import Library
    names = {'objects4', 'argmax', 'size', 'shape', 'dims', 'canvas', 'c0', 'c2'}
    full = grid_library()
    lib = Library({n: p for n, p in full.primitives.items() if n in names})
    result = search_grids([(((0, 1, 1), (0, 0, 0)), ((2, 2),)),
                           (((3, 0), (3, 0), (3, 0)), ((2,), (2,), (2,)))], lib,
                          EnumerationConfig(max_cost=12, max_expanded_states=30000,
                                            time_limit_seconds=10, max_lambda_depth=1))
    assert result.solved
    assert evaluate(result.frontier.best.program, lib, (((0, 4, 4, 4, 4),),)) == ((2, 2, 2, 2),)


def test_search_synthesizes_paint_program():
    from arc_tsl.synthesis.grammar import Library
    names = {'objects4', 'argmax', 'size', 'shape', 'paint', 'position', 'i0', 'c0'}
    full = grid_library()
    lib = Library({n: p for n, p in full.primitives.items() if n in names})
    train = [(((0, 0, 0), (0, 2, 2)), ((2, 2, 0), (0, 2, 2))),
             (((0, 0), (3, 0), (3, 0)), ((3, 0), (3, 0), (3, 0)))]
    result = search_grids(train, lib, EnumerationConfig(max_cost=12, max_expanded_states=30000,
                                                       time_limit_seconds=10, max_lambda_depth=1))
    assert result.solved
    assert 'paint' in str(result.frontier.best.program)
    assert evaluate(result.frontier.best.program, lib, (((0, 0, 0, 0), (0, 4, 4, 4)),)) == (
        (4, 4, 4, 0), (0, 4, 4, 4))


def test_grid_search_zero_budget_and_empty_train():
    result = search_grids([(((1,),), ((2,),))], config=EnumerationConfig(max_expanded_states=0))
    assert not result.solved
    assert result.stats.expanded_states == 0
    assert result.termination_reason == 'max_expanded_states'
    with pytest.raises(ValueError):
        search_grids([])
