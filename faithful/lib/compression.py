"""Compression backends behind one interface.

``compress(kernel, grammar, frontiers)`` returns a :class:`CompressionResult`
whose ``grammar`` and ``frontiers`` plug straight back into the driver. Unsolved
(empty) frontiers are passed through untouched; inputs are never mutated.

* :class:`OriginalCompressor` — the frozen Haskell ``compress`` (explicit finite
  version sets, DreamCoder MDL objective).
* :class:`VersionSpaceCompressor` — the shared version-table port (``vs_compress``),
  needs the ``versionspace`` kernel target (the default).
* :class:`StitchCompressor` — Stitch proposes abstractions through the Rust
  backend; typing, rewriting and acceptance are configurable (see its docstring).
"""
from __future__ import annotations
import copy
from dataclasses import dataclass, field
from typing import Optional, Sequence

from . import ast
from .kernel import Kernel, KernelError
from . import stitch as stitch_api

@dataclass
class CompressionResult:
    grammar: ast.Grammar
    frontiers: list[ast.Frontier]
    inventions: list[dict]            # new productions {program,type,log_weight}
    history: list[dict]               # per accepted step: before/after objective, invention
    statistics: dict = field(default_factory=dict)

    @property
    def accepted(self) -> int:
        return len(self.inventions)

def new_productions(before: ast.Grammar, after: ast.Grammar) -> list[dict]:
    old = {ast.program_key(p["program"]) for p in before["productions"]}
    return [p for p in after["productions"] if ast.program_key(p["program"]) not in old]

def accounting(kernel: Kernel, grammar: ast.Grammar, frontiers: Sequence[ast.Frontier]) -> dict:
    """DreamCoder MDL terms: library cost + corpus cost (negative log marginals)."""
    marginals = [kernel.call("frontier", grammar=grammar, frontier=f)["log_marginal"] for f in frontiers if f["entries"]]
    library = len(grammar["productions"]) + .001 * sum(ast.leaves(p["program"].get("invented", p["program"])) for p in grammar["productions"])
    return dict(mdl=library - sum(marginals), library_cost=library, corpus_cost=-sum(marginals))

class Compressor:
    name = "abstract"
    def compress(self, kernel: Kernel, grammar: ast.Grammar, frontiers: Sequence[ast.Frontier]) -> CompressionResult:
        solved = [copy.deepcopy(f) for f in frontiers if f["entries"]]
        if not solved:
            return CompressionResult(copy.deepcopy(grammar), [copy.deepcopy(f) for f in frontiers], [], [], {"backend": self.name, "skipped": "no solved frontiers"})
        result = self._compress(kernel, copy.deepcopy(grammar), solved)
        rewritten = iter(result.frontiers)
        result.frontiers = [next(rewritten) if f["entries"] else copy.deepcopy(f) for f in frontiers]
        result.statistics.setdefault("backend", self.name)
        result.statistics["input_sha256"] = ast.digest(dict(grammar=grammar, frontiers=list(frontiers)))
        return result
    def _compress(self, kernel, grammar, frontiers) -> CompressionResult:
        raise NotImplementedError

class OriginalCompressor(Compressor):
    name = "original"
    def __init__(self, arity: int = 1, iterations: int = 3, pseudo_counts: float = 1., aic: float = 1., structure_penalty: float = .001):
        self.arity, self.iterations = arity, iterations
        self.pseudo_counts, self.aic, self.structure_penalty = pseudo_counts, aic, structure_penalty
    def _compress(self, kernel, grammar, frontiers):
        r = kernel.call("compress", grammar=grammar, frontiers=frontiers, arity=self.arity, iterations=self.iterations,
                        pseudo_counts=self.pseudo_counts, aic=self.aic, structure_penalty=self.structure_penalty)
        return CompressionResult(r["grammar"], r["frontiers"], new_productions(grammar, r["grammar"]), r["history"])

class VersionSpaceCompressor(Compressor):
    """Options are the reference's: ``arity``, ``top_k``, ``top_i``, ``beam_size``,
    ``inline``, ``likelihood`` ('ocaml' selects the reference normaliser), ``trace``."""
    name = "versionspace"
    def __init__(self, iterations: int = 3, arity: int = 1, **options):
        self.iterations, self.options = iterations, dict(arity=arity, **options)
    def _compress(self, kernel, grammar, frontiers):
        if not kernel.supports("vs_compress"):
            raise KernelError("vs_compress needs the 'versionspace' kernel target", "vs_compress")
        r = kernel.call("vs_compress", grammar=grammar, frontiers=frontiers, iterations=self.iterations, **self.options)
        return CompressionResult(r["grammar"], r["frontiers"], new_productions(grammar, r["grammar"]), r["history"],
                                 {"options": self.options, "final_step": r["final_step"]})

class NoCompression(Compressor):
    name = "none"
    def _compress(self, kernel, grammar, frontiers):
        return CompressionResult(grammar, frontiers, [], [])

# ---- Stitch ----------------------------------------------------------------------------------

def _uniform_with(grammar: ast.Grammar, invention: ast.Program, type: ast.Type) -> ast.Grammar:
    """Bridge semantics: all weights reset to 0 before refitting with the new production."""
    productions = [dict(p, log_weight=0.) for p in grammar["productions"]] + [ast.production(invention, type, 0.)]
    return ast.grammar(productions, 0.)

class StitchCompressor(Compressor):
    """Abstraction learning with the ``stitch_core`` backend.

    ``mode``
        ``"iterative"`` (default): one backend call per accepted abstraction on the
        current programs, so every option below applies step by step.
        ``"batch"``: one backend call with ``iterations`` steps; all abstractions
        are taken in Stitch's order (``gate`` must be ``"none"``).
    ``rewrite``
        ``"auto"`` (default): use the backend's rewritten programs when every one
        is β-equivalent to its original and scorable under the new grammar, else
        fall back to ``"kernel"`` for that abstraction.
        ``"stitch"``: always use the backend's rewrites; entries failing the check
        keep their original program (counted in ``rewrite_fallbacks``).
        ``"kernel"``: Haskell inverse-β rewriting through ``compression_trial``
        (the frozen study's protocol); always η-long and typed.
        Note: Stitch's own ``eta_long`` flag yields lambda-rooted abstractions used
        as bare arguments, which the kernel's η-long grammar rejects; leave it off.
    ``gate``
        ``"none"``: accept every well-typed abstraction. ``"mdl"``: accept only if
        the DreamCoder MDL objective improves; stop at the first rejection.
    ``options``
        :class:`faithful.lib.stitch.StitchOptions`; costs default to Stitch's own and
        ``no_curried_metavars`` defaults to ``True`` (see ``__init__``).
        Use ``StitchOptions(**LEAF_COST)`` for the frozen study's leaf-only cost.
    ``strip_request_lambdas``
        Send Stitch program bodies with the request's outer lambdas removed (inputs
        are free ``$i``), so abstractions are closed DreamCoder inventions rather
        than wrappers around the η-long scaffolding. ``False`` reproduces the frozen
        study's encoding.
    """
    name = "stitch"
    def __init__(self, iterations: int = 3, options: Optional[stitch_api.StitchOptions] = None, *, mode: str = "iterative",
                 rewrite: str = "auto", gate: str = "none", epsilon: float = 1e-10, inline_inventions: bool = False,
                 strip_request_lambdas: bool = True):
        if mode not in ("iterative", "batch") or rewrite not in ("auto", "stitch", "kernel") or gate not in ("none", "mdl"):
            raise ValueError("mode in {iterative,batch}, rewrite in {auto,stitch,kernel}, gate in {none,mdl}")
        if mode == "batch" and gate != "none": raise ValueError("batch mode cannot gate per abstraction")
        self.options = copy.copy(options) if options else stitch_api.StitchOptions()
        if self.options.no_curried_metavars is None:
            # Kernel programs are η-long: function-typed arguments are always lambdas,
            # so a metavariable in function position (``(lam (#0 $0))``) only abstracts
            # scaffolding the kernel restores. Stitch documents this flag for η-long corpora.
            self.options.no_curried_metavars = True
        self.iterations = iterations
        self.mode, self.rewrite, self.gate, self.epsilon, self.inline = mode, rewrite, gate, epsilon, inline_inventions
        self.strip = strip_request_lambdas

    # -- helpers
    def _flatten(self, frontiers):
        """Programs for Stitch, their task ids, frontier slots and stripped lambda counts.

        With ``strip_request_lambdas`` the outer lambdas introduced by an arrow
        request are removed (inputs become free ``$i``). Otherwise Stitch's cost
        model rewards abstracting ``(lambda (f … $0))`` into a partial application
        that the kernel's η-long form immediately undoes, proposing the same
        wrapper forever."""
        programs, tasks, slots, wraps = [], [], [], []
        for i, f in enumerate(frontiers):
            n = ast.arity(f["request"]) if self.strip else 0
            for j, e in enumerate(f["entries"]):
                p, k = e["program"], 0
                while k < n and "abstraction" in p: p, k = p["abstraction"], k + 1
                programs.append(p); tasks.append(i); slots.append((i, j)); wraps.append(k)
        return programs, tasks, slots, wraps

    @staticmethod
    def _wrap(rows, wraps):
        return [ast.abstractions(p, n) for p, n in zip(rows, wraps)] if rows is not None else None

    @staticmethod
    def _typed(kernel, grammar, invention):
        """Principal type of the invention under the DreamCoder grammar, or ``None``."""
        try: return kernel.infer(grammar, invention)
        except KernelError: return None

    def _apply_stitch_rewrite(self, kernel, grammar, frontiers, invention, type, rewritten_programs, slots):
        g2 = _uniform_with(grammar, invention, type)
        fs = copy.deepcopy(frontiers); fallbacks = 0
        for (i, j), q in zip(slots, rewritten_programs):
            entry = fs[i]["entries"][j]; p = entry["program"]
            ok = False
            try:
                ok = kernel.beta(p) == kernel.beta(q)
                if ok: kernel.score(g2, fs[i]["request"], q)
            except KernelError: ok = False
            if ok: entry["program"] = q
            else: fallbacks += 1
        return g2, fs, fallbacks

    def _trial(self, kernel, grammar, frontiers, invention, type, rewritten_programs, slots):
        """Returns (fitted grammar, rewritten frontiers, objective, statistics)."""
        if self.rewrite != "kernel":
            g2, fs, fallbacks = self._apply_stitch_rewrite(kernel, grammar, frontiers, invention, type, rewritten_programs, slots)
            if fallbacks == 0 or self.rewrite == "stitch":
                fit = kernel.call("compression_objective", grammar=g2, frontiers=fs)
                return fit["grammar"], fs, fit["objective"], {"rewrite": "stitch", "rewrite_fallbacks": fallbacks}
        t = kernel.call("compression_trial", grammar=grammar, frontiers=frontiers, invention=invention)
        return t["grammar"], t["frontiers"], t["objective"], {"rewrite": "kernel"}

    # -- modes
    def _compress(self, kernel, grammar, frontiers):
        if not kernel.supports("compression_objective"):
            raise KernelError("StitchCompressor needs the 'bridge' or 'versionspace' kernel target", "compression_objective")
        stats = {"backend_version": stitch_api.backend_version(), "options": self.options.kwargs(), "mode": self.mode,
                 "rewrite": self.rewrite, "gate": self.gate, "attempts": []}
        g, fs, history = grammar, frontiers, []
        base = kernel.call("compression_objective", grammar=g, frontiers=fs)
        g, objective = base["grammar"], base["objective"]
        if self.mode == "batch":
            programs, tasks, slots, wraps = self._flatten(fs)
            options = self.options
            if self.rewrite != "kernel":  # per-abstraction rewrites let the grammar grow one step at a time
                options = copy.copy(options); options.rewritten_intermediates = True
            result = stitch_api.compress(programs, self.iterations, tasks=tasks, options=options, inline_inventions=self.inline)
            stats["native"] = result.json
            for k, a in enumerate(result.abstractions):
                attempt = {"name": a.name, "arity": a.arity, "body": a.body, "proposal": a.program, "utility": a.utility}
                stats["attempts"].append(attempt)
                tp = self._typed(kernel, g, a.program)
                if tp is None: attempt["rejection"] = "ill-typed under the DreamCoder grammar"; continue
                rows = self._wrap(result.rewritten_after(k) or result.rewritten, wraps) if self.rewrite != "kernel" else None
                try:
                    g2, fs2, objective2, extra = self._trial(kernel, g, fs, a.program, tp, rows, slots)
                except KernelError as e:
                    attempt["rejection"] = f"type/grammar: {e}"; continue
                attempt.update(extra, objective=objective2)
                history.append(dict(before=objective, after=objective2, invented=a.program, type=tp))
                g, fs, objective = g2, fs2, objective2
            return CompressionResult(g, fs, new_productions(grammar, g), history, stats)
        for _ in range(self.iterations):
            programs, tasks, slots, wraps = self._flatten(fs)
            result = stitch_api.compress(programs, 1, tasks=tasks, options=self.options, inline_inventions=self.inline)
            attempt = {"native": result.json}; stats["attempts"].append(attempt)
            if not result.abstractions: attempt["rejection"] = "no compressive abstraction"; break
            a = result.abstractions[0]
            attempt.update(name=a.name, arity=a.arity, body=a.body, proposal=a.program, utility=a.utility)
            tp = self._typed(kernel, g, a.program)
            if tp is None: attempt["rejection"] = "ill-typed under the DreamCoder grammar"; break
            try:
                g2, fs2, objective2, extra = self._trial(kernel, g, fs, a.program, tp, self._wrap(result.rewritten, wraps), slots)
            except KernelError as e:
                attempt["rejection"] = f"type/grammar: {e}"; break
            attempt.update(extra, objective=objective2)
            if self.gate == "mdl" and objective2 <= objective + self.epsilon:
                attempt["rejection"] = "no improvement in DreamCoder MDL"; break
            history.append(dict(before=objective, after=objective2, invented=a.program, type=tp))
            g, fs, objective = g2, fs2, objective2
        return CompressionResult(g, fs, new_productions(grammar, g), history, stats)

def make_compressor(spec: str | Compressor | None, **kwargs) -> Compressor:
    """``"original" | "versionspace" | "stitch" | "none"`` or an instance."""
    if spec is None: return OriginalCompressor(**kwargs)
    if isinstance(spec, Compressor): return spec
    return {"original": OriginalCompressor, "versionspace": VersionSpaceCompressor, "stitch": StitchCompressor, "none": NoCompression}[spec](**kwargs)
