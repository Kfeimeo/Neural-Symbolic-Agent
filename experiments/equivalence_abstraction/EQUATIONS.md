# Phase 3 equational theory

Domain: well-typed frozen Grid DSL terms, on **nonempty rectangular grids with
palette {0,1,2,3}**, and the frozen int/color primitives. All primitive grid
operations preserve this invariant. Inventions are opaque atoms. These equations
are not asserted for ragged arrays, out-of-palette inputs, errors, or arbitrary
foreign primitives. The semantic authority is `faithful/haskell/Evaluation.hs`.

## Reduction rules R

| Schema | Reason |
|---|---|
| identity(x) → x | Evaluator is `Function Right`. |
| H(H(x)), V(V(x)), T(T(x)), R180(R180(x)) → x | Each coordinate permutation is an involution on rectangles. |
| invert(invert(x)) → x | 0 maps to 0; on {1,2,3}, c maps to 4-c. |
| trim(trim(x)) → trim(x) | Nonzero bounding box is tight after cropping; all-zero case is the fixed 1×1 zero grid. |
| translate(x,zero,zero) → x | Every destination coordinate reads the same source coordinate. |
| recolor(x,c,c) → x | Both branches return the original value. Color arguments are total atoms in this DSL. |
| R90(R90(R90(R90(x)))) → x | Four quarter turns compose to the identity. |

Each rewrite strictly decreases AST node count. This is a well-founded
termination measure, independent of the grammar weights and data.

Critical overlaps: distinct head-symbol rules have no root overlap. Involution
self-overlap at length three joins to a single operator; trim self-overlap joins
to one trim; the R90 length-four rule overlaps itself in runs of lengths five,
six and seven, with either branch removing exactly four rotations. Disjoint
redexes commute. Nested reductions in a grid variable survive in the retained
subterm, so the peak joins after the same inner reduction. The two repeated color
arguments of recolor are atoms (no color-producing rewrite rules), introducing no
additional reduction peak. Thus this restricted typed R is locally confluent;
termination gives confluence by Newman's lemma. Tests additionally enumerate
short unary words and check all one-step peaks. This argument does not assert
confluence of E-oriented rewriting or arbitrary extensions of the DSL.

## Equations E

Let G be H, V, transpose, rotate90, or rotate180.

* G commutes in both directions with invert, recolor (retaining both color
  arguments), and solid (retaining its color argument). G permutes positions;
  these operations apply the same map independently at each position.
* G commutes with border. A one-cell zero frame maps to the same one-cell zero
  frame under these rectangle symmetries.
* G commutes with trim. The transformed nonzero bounding box is exactly the
  bounding box of the transformed cells; the all-zero special case remains 1×1.
* H(V(x)) ↔ V(H(x)); these act on independent coordinate axes.
* G(translate(x,dr,dc)) ↔ translate(G(x),G_offset(dr,dc)).

| G | G_offset(dr,dc) | inverse offset map |
|---|---|---|
| H | (dr,-dc) | same |
| V | (-dr,dc) | same |
| transpose | (dc,dr) | same |
| rotate180 | (-dr,-dc) | same |
| rotate90 clockwise | (dc,-dr) | (-dc,dr) |

Translation uses zero padding and clips to its input rectangle. G bijectively maps
that rectangle and its valid source coordinates to the rotated/reflected
rectangle; invalid source coordinates remain invalid. Thus the offset equations
hold even when clipping occurs. Negation is instantiated only for zero/one/
minus_one; no new primitive or symbolic negation is introduced. Transpose needs
no negation and also applies with variable offsets.

**Excluded:** cancellation or addition of successive translations, translation
commuting with trim/border, and equations inferred from probe agreement. For
example shifting `[1,2,3]` right then left yields `[1,2,0]`, not the input.

## Saturation and abstraction scope

Start at NF_R(p). Apply one E equation at any context, then NF_R again before
insertion. E preserves node count and uses a finite atom alphabet; R decreases
node count, so the reachable normalized-term closure is finite. At 512 terms,
the implementation fails the cell instead of returning an incomplete closure.
Canonical extraction minimizes (node count, deterministic term serialization).

The graph hash-conses enodes and unions certified equal roots, then rebuilds
congruence. Anti-unification traverses pairs of e-classes from distinct task
frontiers, sharing repeated mismatch pairs as parameters. It does not extract a
single program before proposing patterns. This is a first-order, two-parameter
Babble-style implementation, not a reproduction of Babble's library beam search
or objective. See the [Babble paper](https://arxiv.org/abs/2212.04596).

After a candidate exists, the implementation selects a witness representation
per frontier entry using structural rewrite size, and calls the unchanged
Haskell `compression_trial`. Selection is a deterministic witness heuristic,
not an exact joint MDL optimum over every representation assignment. The frozen
inside-outside/MDL score determines acceptance. This limitation must accompany
any empirical B3-versus-B2 conclusion.
