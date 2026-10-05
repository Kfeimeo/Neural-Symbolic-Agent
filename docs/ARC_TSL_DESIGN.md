# ARC-TSL v0.1 — architecture and design note

This note documents the design decisions behind `arc_tsl/`, the prototype that
tests the hypothesis

> On fixed domain axioms, inducing a task-specific language (TSL) from the IO
> pairs of one ARC task *before* searching for the task program reduces search
> complexity compared with searching the fixed full DSL directly.

The prototype is a **minimal verifiable closed loop**: no neural perception,
no LLM proposals, no cross-task library learning, no ARC-2/3.

## 1. Three layers

```
ML  ──►  DSA  ──►  TSL_τ  ──►  Program_τ
```

| layer | module(s) | fixed? | contents |
|---|---|---|---|
| ML (meta language) | `arc_tsl/ml/` | fixed, domain-independent | monomorphic types, de Bruijn typed λ-AST, Bool/Int/Vec2 arithmetic, `map`/`filter`/`argmin`/`argmax`/`unique`/`count`/`insert`/`delete`/`replace`/`others`/`if_obj` |
| DSA (domain-specific axioms) | `arc_tsl/dsa/`, `arc_tsl/ontology/`, `arc_tsl/arc/` | fixed, task-independent | grid ↔ object parse/render, ObjectToken/ObjectClass ontology, transforms, observers, relations, RegionExpr |
| TSL_τ | `arc_tsl/tsl/` | induced per task | `(Base_{ML+DSA}, A_τ, θ_τ)` = a `Library` with invented abstractions and optional production costs |

`ML` never mentions grids or objects: `collection_primitives(ELEM, SET, make_set)`
is instantiated by the DSA at `(Object, ObjectSet)`.  The DSA never contains a
task rule.  `A_τ` is only ever produced by `arc_tsl/tsl/compression.py` from the
frontiers of the task's own IO pairs.

## 2. Symbolic grid encoding (no perception network)

* `Grid = tuple[tuple[int]]`, `Color` nominal (no primitive does arithmetic on colors;
  `dominant_color` ties are broken by smallest value only to be deterministic).
* `Instance` = maximal connected foreground pixel set.  `ExtractionConfig`
  exposes `connectivity ∈ {4, 8}`, `background ∈ {color0, most_frequent}`
  (a `BackgroundPolicy` interface), and `same_color_only` for ablation.
* `ObjectClass = Instance / (Z² ⋊ C₄)`: `shape_id` is the lexicographically minimal
  sorted coordinate tuple over the four quarter-turn rotations of the normalized
  support (`ontology/canonicalize.py`).  Reflection is **not** quotiented, so
  chiral shapes have distinct classes.
* `ObjectToken` keeps `pixels`, `grid_shape`, `token_id` (provenance only; equality
  is structural), and derives `shape_id`, `local_support`, `global_support`,
  `position` (bbox top-left), `center` (bbox center, half-integers allowed, as
  `Fraction`), `centroid` (observer only), `orientation`, `color_set`,
  `dominant_color`, `size`, `bbox`, `height`, `width`.
* `ObjectSet` is an ordered multiset (canonical scan order), so multiplicity is
  never lost: two identical squares are two tokens of one class.
* `render(parse(g)) == g` is a property test over random grids and real ARC grids
  for every extraction configuration.

## 3. Transformation primitives are object-centric

All transforms have type `Object × Param → Object` and operate in the object's
local frame: `translate(o, Vec2)`, `rotate(o, QuarterTurn)`, `reflect(o, Axis)`,
`recolor(o, Color)`, `replace_color(o, Color, Color)`, `add_region(o, Region, Color)`,
`remove_region(o, Region)`.  `rotate`/`reflect` keep the bbox top-left anchor.
There is **no** absolute-coordinate primitive at all (`translate` only takes
vectors built from constants/unit directions or object relations such as
`center_delta`, `bbox_*` differences via ML arithmetic).  `RegionExpr` is a
nominal symbol evaluated relative to the object (`support`, `bbox`,
`bbox_minus_support`, `boundary`, `neighbors4/8`, `row_span`, `column_span`,
`minimal_square_hull`).  Cardinality changes are ML collection operations
(`insert`/`delete`/`replace`), not transforms.

## 4. Program type and pipeline

```
Grid ──parse──► ObjectSet ──p_τ──► ObjectSet ──render──► Grid
```

A program is a term of type `ObjectSet` in context `($0 : ObjectSet)`; the render
step reuses the *input* grid's shape and background.  v0.1 therefore only
supports tasks whose outputs have the input shape; others are recorded as
`UNSUPPORTED` (138/400 training tasks).

## 5. Search engine

`arc_tsl/synthesis/enumerator.py` is a bottom-up, cost-ordered, typed enumerator
with observational equivalence (OE):

* terms are built per `(context, type, cost)`; contexts are `C0=(ObjectSet)`,
  `C1=(Object, ObjectSet)`, `C2=(Object, Object, ObjectSet)` (lambda depth ≤ 2);
* every term is evaluated on all sample bindings of its context (the training
  scenes; every object of every scene for C1; every ordered object pair for C2);
  terms with identical observation vectors are merged, all-`ERR` terms dropped;
  function-typed terms are observed through their values on the scene's objects;
* the top cell `(C0, ObjectSet)` is expanded first at each cost level (its parts
  are strictly cheaper), so solutions of cost *k* are reported before the rest of
  level *k*;
* statistics: `expanded_states` (terms constructed), `retained_terms`,
  `evaluated_programs` (top-level programs checked), `first_solution_nodes`,
  `first_solution_states`, wall time, termination reason.

Cost convention (identical in every condition): each production occurrence
(primitive, invented abstraction, variable) costs an integer weight (1 under the
uniform grammar), application 0, lambda 1.  Program description length always
uses unit weights; `θ_τ` only changes the *search* order.

Consequence of OE: for a single IO pair, every program producing the right output
has the same observation, so the wake frontier is essentially one canonical
program per pair (top-K only adds programs that differ off-grid).  This is
narrower than DreamCoder's likelihood-weighted frontiers and is discussed in the
README.

## 6. Task-local DreamCoder-style induction (`arc_tsl/tsl/`)

```
local wake      : for each pair i, search p_i with p_i(x_i) = y_i in Base
local sleep     : A_τ = argmin  L(A) + Σ_i min_{p∈F_i} L(p | Base + A)
local re-wake   : search p_τ with ∀i p_τ(x_i)=y_i in Base + A_τ (+ θ_τ)
```

Compression (`compression.py`):

1. **Proposal by typed anti-unification.** Every subterm of every frontier
   program is *closed* (free de Bruijn variables become typed parameters), and
   every pair of closed subterms with the same type and head symbol is
   anti-unified.  Holes are never created inside a lambda when the abstracted
   subterms would capture the lambda's variable; the enclosing lambda becomes the
   hole instead.  Candidates must be non-trivial (>1 primitive leaf, or a repeated
   parameter) and have arity ≤ 3.
2. **Selection by MDL.** Each candidate is scored by rewriting every frontier
   program (greedy top-down match with de Bruijn shifting, semantics preserving —
   tested by expansion equality and evaluation equality) and recomputing
   `L(A) + Σ_i min_p L(p|A)`.  The best strictly improving candidate is accepted;
   the loop repeats on the rewritten frontiers, so later abstractions can use
   earlier ones (≤ 3 rounds).
3. **Contraction.** `prune_unused` removes abstractions not used by any
   frontier's best program (transitively through bodies); `contract` removes any
   abstraction whose removal does not increase total MDL.  The TSL is therefore
   not monotone.
4. **θ_τ (ablation C).** Productions absent from every wake program get cost 2,
   the others (and all abstractions) cost 1.  This is a quantised task-local
   prior, not a fitted `-log p`.

Honest differences from the original DreamCoder compressor: no version-space /
refactoring enumeration, no inside-outside grammar fitting inside the objective,
greedy instead of beam acceptance, unit costs instead of `-log p`, MAP (min over
frontier) instead of a marginal over frontier entries.  The Haskell kernel and
Stitch bridge already in this repository (`faithful/`) could not be reused: no
GHC or `stitch_core` is available in the execution environment, and the
Python `dreamcoder/` core is first-order (no lambdas, no higher-order
`map`/`filter`), which the ML layer requires.  The search/frontier/compression
*interfaces* of `dreamcoder/` were mirrored.

## 7. Experimental conditions

| condition | wake | A_τ | θ_τ | re-wake library |
|---|---|---|---|---|
| baseline | – | – | – | Base |
| tsl | ✓ | ✓ | uniform | Base + A_τ |
| reweight | ✓ | – | ✓ | Base with θ_τ |
| tsl_reweight | ✓ | ✓ | ✓ | Base + A_τ with θ_τ |

All conditions use the same enumeration budget for the full-task search; wake
uses the same budget per pair by default.  Metrics per task are listed in the
README; ratios `baseline / tsl` are reported per task and as mean / median /
std / geometric mean, for solved-only and all in-scope tasks, and additionally
counting the wake cost (`total_states_ratio`).

## 8. Things v0.1 deliberately does not do

Neural perception or selectors, LLM primitive proposals, learned DSA, ARC-2/3,
hierarchical `partOf`, dependent/refinement types, cross-task abstraction
learning, output-shape-changing tasks, whole-grid transformations (rotate/flip of
the entire grid), polymorphic type inference (ML operators are instantiated
monomorphically), partial application / variables of function type.
