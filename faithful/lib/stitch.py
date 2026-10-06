"""Python wrapper around the Rust ``stitch_core`` backend (Bowers et al., 2023).

This module is deliberately *only* about Stitch: converting protocol v1 programs
to Stitch s-expressions and back, exposing every backend option, and returning
abstractions as ``invented`` ASTs. Typing, rewriting under DreamCoder's grammar
and MDL acceptance are handled by :class:`faithful.lib.compression.StitchCompressor`.

``stitch_core`` is imported from the environment when installed, otherwise from
the vendored copy in ``faithful/vendor`` (``pip install stitch_core==0.1.29``).
"""
from __future__ import annotations
import copy
import re
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Optional, Sequence

from . import ast

def _import_backend():
    try:
        import stitch_core  # noqa: F401
    except ImportError:
        vendor = Path(__file__).resolve().parents[1] / "vendor"
        if vendor.is_dir() and str(vendor) not in sys.path: sys.path.append(str(vendor))
        import stitch_core  # noqa: F401
    return stitch_core

def backend():
    """The ``stitch_core`` module (raises ImportError with install advice)."""
    try: return _import_backend()
    except ImportError as e:
        raise ImportError("stitch_core is not installed; `pip install stitch_core==0.1.29` or keep faithful/vendor") from e

def backend_version() -> Optional[str]:
    try:
        from importlib.metadata import version
        return version("stitch_core")
    except Exception:
        return None

# ---- options -----------------------------------------------------------------------

@dataclass
class StitchOptions:
    """Every flag of the ``stitch_core`` 0.1.29 compress/rewrite backend. ``None``
    means "backend default". Unknown or newer flags go in :attr:`extra`."""
    max_arity: int = 2
    threads: int = 1
    silent: bool = True
    quiet: Optional[bool] = None
    # program cost model (Stitch defaults: app 1, lam 1, var 100, ivar 100, prim 100)
    cost_app: Optional[int] = None
    cost_lam: Optional[int] = None
    cost_var: Optional[int] = None
    cost_ivar: Optional[int] = None
    cost_prim_default: Optional[int] = None
    # objective
    structure_penalty: Optional[float] = None   # DreamCoder-style; needs utility_by_rewrite or no_other_util semantics as documented by Stitch
    no_other_util: Optional[bool] = None        # utility purely by program size (ignore abstraction size)
    allow_single_task: Optional[bool] = None
    # rewriting form
    eta_long: Optional[bool] = None             # Stitch's η-long form (needs utility_by_rewrite or no_mismatch_check);
                                                # NOT the kernel's η-long form, see StitchCompressor
    utility_by_rewrite: Optional[bool] = None   # WARNING: overflows the Rust stack in the vendored 0.1.29 Windows wheel
    no_mismatch_check: Optional[bool] = None
    rewrite_check: Optional[bool] = None
    no_curried_metavars: Optional[bool] = None
    no_curried_bodies: Optional[bool] = None
    fused_lambda_tags: Optional[bool] = None
    # search
    hole_choice: Optional[str] = None           # e.g. "depth-first"
    inv_candidates: Optional[int] = None
    batch: Optional[int] = None
    dynamic_batch: Optional[bool] = None
    inv_arg_cap: Optional[bool] = None
    no_opt_single_use: Optional[bool] = None
    no_opt_upper_bound: Optional[bool] = None
    no_opt_force_multiuse: Optional[bool] = None
    no_opt_useless_abstract: Optional[bool] = None
    no_opt_arity_zero: Optional[bool] = None
    no_stats: Optional[bool] = None
    # tracing / output
    follow: Optional[str] = None
    follow_types: Optional[str] = None
    follow_prune: Optional[bool] = None
    verbose_worklist: Optional[bool] = None
    verbose_best: Optional[bool] = None
    print_stats: Optional[int] = None
    show_rewritten: Optional[bool] = None
    rewritten_intermediates: Optional[bool] = None
    dreamcoder_comparison: Optional[bool] = None
    panic_loud: Optional[bool] = None
    extra: dict = field(default_factory=dict)

    def kwargs(self) -> dict:
        out = {}
        for f in fields(self):
            if f.name == "extra": continue
            v = getattr(self, f.name)
            if v is not None: out[f.name] = v
        out.update(self.extra)
        return out

    def rewrite_kwargs(self) -> dict:
        """Only the cost flags, which is all ``rewrite`` accepts."""
        return {k: v for k, v in self.kwargs().items() if k.startswith("cost_")}

LEAF_COST = dict(cost_app=0, cost_lam=0, cost_var=100, cost_ivar=100, cost_prim_default=100)
"""Cost preset of the frozen compression study: only leaves count, like the kernel's size."""

# ---- program <-> s-expression ---------------------------------------------------------

_SAFE = re.compile(r"^[^\s()#$]+$")
_RESERVED = re.compile(r"^(lam|lambda|fn_\d+)$")

class Atoms:
    """Bijection between opaque leaves (primitives, prior inventions) and Stitch symbols."""
    def __init__(self, inline_inventions: bool = False):
        self.by_key: dict[str, str] = {}
        self.programs: dict[str, ast.Program] = {}
        self.inline_inventions = inline_inventions

    def symbol(self, p: ast.Program) -> str:
        key = ast.program_key(p)
        if key in self.by_key: return self.by_key[key]
        if "primitive" in p and _SAFE.match(p["primitive"]) and not _RESERVED.match(p["primitive"]):
            name = p["primitive"]
            if name in self.programs: name = f"prim_{len(self.programs)}"
        else:
            name = f"{'inv' if 'invented' in p else 'prim'}_{len(self.programs)}"
        self.by_key[key] = name; self.programs[name] = copy.deepcopy(p)
        return name

    def define(self, name: str, p: ast.Program) -> None:
        self.programs[name] = copy.deepcopy(p); self.by_key[ast.program_key(p)] = name

def encode(p: ast.Program, atoms: Atoms) -> str:
    if "application" in p:
        spine = []
        while "application" in p:
            f, x = p["application"]; spine.append(x); p = f
        return "(" + " ".join(encode(x, atoms) for x in [p, *reversed(spine)]) + ")"
    if "abstraction" in p: return "(lam " + encode(p["abstraction"], atoms) + ")"
    if "index" in p: return "$" + str(p["index"])
    if "invented" in p and atoms.inline_inventions: return encode(p["invented"], atoms)
    return atoms.symbol(p)

def decode(text: str, atoms: Atoms, arity: int = 0) -> ast.Program:
    """Parse a Stitch program or abstraction body. ``#i`` metavariables become the
    de Bruijn indices of ``arity`` enclosing lambdas (``#0`` is the first argument)."""
    tokens = iter(re.findall(r"\(|\)|[^\s()]+", text))
    def read(token, depth=0):
        if token == "(":
            first = next(tokens)
            if first == "lam":
                body = read(next(tokens), depth + 1)
                if next(tokens) != ")": raise ValueError("Malformed lam")
                return ast.abstraction(body)
            result = read(first, depth)
            for t in tokens:
                if t == ")": return result
                result = {"application": [result, read(t, depth)]}
            raise ValueError("Unclosed application")
        if token.startswith("$"): return ast.index(int(token[1:]))
        if token.startswith("#"): return ast.index(depth + arity - 1 - int(token[1:]))
        if token not in atoms.programs: raise ValueError(f"Unknown Stitch symbol {token!r}")
        return copy.deepcopy(atoms.programs[token])
    result = read(next(tokens))
    if next(tokens, None) is not None: raise ValueError("Trailing tokens")
    return ast.abstractions(result, arity)

# ---- results ----------------------------------------------------------------------------

@dataclass
class Abstraction:
    name: str            # Stitch's name (fn_0, ...)
    arity: int
    body: str            # Stitch body with #i metavariables
    program: ast.Program # ``{"invented": λ^arity. body}`` with earlier abstractions substituted
    utility: Optional[float] = None
    uses: Optional[int] = None
    raw: dict = field(default_factory=dict)

@dataclass
class StitchResult:
    abstractions: list[Abstraction]
    rewritten: list[ast.Program]        # one per input program, after all abstractions
    programs: list[str]                 # the Stitch-format inputs
    rewritten_text: list[str]
    atoms: Atoms
    json: dict                           # raw backend output

    def rewritten_after(self, k: int) -> Optional[list[ast.Program]]:
        """Programs rewritten with the first ``k+1`` abstractions (needs ``rewritten_intermediates``)."""
        rows = self.json["abstractions"][k].get("rewritten")
        return [decode(s, self.atoms) for s in rows] if rows else None

def _absorb(result_json: dict, atoms: Atoms) -> list[Abstraction]:
    out = []
    for a in result_json["abstractions"]:
        program = ast.invented(decode(a["body"], atoms, a["arity"]))
        atoms.define(a["name"], program)
        out.append(Abstraction(a["name"], a["arity"], a["body"], program, a.get("utility"), a.get("uses"), a))
    return out

def compress(programs: Sequence[ast.Program], iterations: int = 1, *, tasks: Optional[Sequence[Any]] = None,
             weights: Optional[Sequence[float]] = None, options: Optional[StitchOptions] = None,
             atoms: Optional[Atoms] = None, inline_inventions: bool = False) -> StitchResult:
    """Run Stitch abstraction learning on protocol v1 programs.

    ``tasks`` (any hashable per program) enables Stitch's multi-task pruning;
    ``weights`` scales each program's contribution. Prior ``invented`` leaves are
    opaque symbols unless ``inline_inventions``.
    """
    options = options or StitchOptions()
    atoms = atoms or Atoms(inline_inventions)
    text = [encode(p, atoms) for p in programs]
    kwargs = options.kwargs()
    if tasks is not None: kwargs["tasks"] = [str(t) for t in tasks]
    if weights is not None: kwargs["weights"] = [float(w) for w in weights]
    result = backend().compress(text, iterations=iterations, **kwargs)
    abstractions = _absorb(result.json, atoms)
    rewritten = [decode(s, atoms) for s in result.rewritten]
    return StitchResult(abstractions, rewritten, text, list(result.rewritten), atoms, result.json)

def rewrite(programs: Sequence[ast.Program], abstractions: Sequence[Abstraction], *, options: Optional[StitchOptions] = None,
            atoms: Optional[Atoms] = None) -> list[ast.Program]:
    """Rewrite programs with existing abstractions through the backend (only when compressive)."""
    options = options or StitchOptions()
    atoms = atoms or Atoms()
    for a in abstractions: atoms.define(a.name, a.program)
    text = [encode(p, atoms) for p in programs]
    sc = backend()
    native = [sc.Abstraction(a.name, a.body, a.arity) for a in abstractions]
    result = sc.rewrite(text, native, **options.rewrite_kwargs())
    return [decode(s, atoms) for s in result.rewritten]
