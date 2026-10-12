# Grid / local shape DSL (v1)

This opt-in extension implements finite `Grid -> Grid` programs. The original
`base_library()` and ObjectSet-based Wake/Sleep pipeline retain their language.
Use `grid_library()` and `search_grids()` for this extension; learned-parameter
completion and the old multi-arm generalization runner are not yet Grid-aware.

## Values and semantics

- `Grid`: immutable rectangular tuples of colors; ARC canvases have height and
  width in 1..30. Output dimensions may differ from input dimensions.
- `Pos`: nonnegative integer (row, column). This is separate from existing
  signed / fractional `Vec2` displacements. Invalid positions evaluate to ERR.
- `Shape`: immutable local colored pixels, retaining orientation. `None` is
  transparent, while 0 is opaque black. This is distinct from `ShapeId`, which
  forgets color and identifies quarter-turn rotations.
- `LocalMask`: immutable local support coordinates, including opaque black.
- `Dims`: positive integer (height, width), each at most 30.

## New productions

```text
objects4 : Grid -> Color -> ObjectSet  # same-color, 4-connected
objects8 : Grid -> Color -> ObjectSet  # mixed-color, 8-connected
pos      : Object -> Pos
position : Int -> Int -> Pos
row,col  : Pos -> Int
shape    : Object -> Shape
support  : Shape -> LocalMask
dims     : Shape -> Dims
dimensions : Int -> Int -> Dims
grid_dims  : Grid -> Dims
dim_h,dim_w : Dims -> Int
same_geometry           : LocalMask -> LocalMask -> Bool
same_geometry_rot       : LocalMask -> LocalMask -> Bool
same_geometry_dihedral  : LocalMask -> LocalMask -> Bool
canvas   : Dims -> Color -> Grid
paint    : Shape -> Pos -> Grid -> Grid
```

Both extraction views take an explicit background color. They reuse connected
component extraction, including nonzero backgrounds; there is no task-ID logic.
ObjectSet remains a canonically ordered multiset, not a user-sortable list.
Mask comparisons normalize translation: exact orientation, C4 rotation, and D4
rotation/reflection are separate predicates. Colors do not affect these tests.

`paint` preserves the destination canvas dimensions, clips pixels beyond its
bottom/right edges, skips transparent pixels and overwrites all other pixels.
Nested calls compose in evaluation order: the outer paint wins overlaps.
Canvas fill is explicit. Black pixels can therefore erase previous content.
`br`, sorting, arbitrary mask lambdas and recursion are not search productions.

## Example

Copy the largest same-color 4-connected foreground object's colored patch to
the top-left of a blank canvas with the input dimensions:

```text
(paint
  (shape (argmax (lambdaObject. (size $0)) (objects4 $0 c0)))
  (position i0 i0)
  (canvas (grid_dims $0) c0))
```

```python
from arc_tsl.language import grid_library
from arc_tsl.synthesis.enumerator import EnumerationConfig
from arc_tsl.synthesis.grid_search import search_grids

result = search_grids(train_pairs, grid_library(),
    EnumerationConfig(max_cost=12, max_expanded_states=300_000,
                      time_limit_seconds=60))
```

Search uses on-demand typed enumeration with root context `(Grid,)`. Object
lambda observations use a deduplicated union of both input views across the
ten possible background colors, subject to the existing binding cap. This is
an observational pruning heuristic, not universal semantic equivalence.
Parsing alternatives share one state/time budget; preprocessing is included in
the reported fit wall time and subtracted from the enumeration time allowance.
The enumerator retains its periodic time checks, so deadlines are approximate.
All new productions have fixed cost 1; this is a new language condition, not a
cost-matched result directly comparable with the old DSL.

## Real-task runner

```powershell
python -m arc_tsl.experiments.run_grid --task data/arc/training/63613498.json --out results/arc_tsl/grid_shapes_v1/63613498.json --max-cost 12 --max-states 300000 --time-limit 30
```

The runner fits training pairs, freezes the selected program and its hash, then
scores test pairs. It records source/data hashes, budgets, search statistics,
fit wall/CPU time and scoring time. Test labels never rerank candidates. This
minimal runner does not yet provide LOO or worker peak-memory measurements.
The previously inspected task 63613498 is a development diagnostic, not fresh
evidence of generalization.
