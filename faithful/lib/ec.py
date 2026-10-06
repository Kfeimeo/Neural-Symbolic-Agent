"""Explore–Compress driver with explicit dependencies.

``ExploreCompress(domain, kernel, compressor, config)`` reproduces the frozen
``faithful.python.ec`` round structure — wake every task, merge with persistent
frontiers, rescore priors, compress, dream, train recognition — but every
domain-specific step goes through the :class:`~faithful.lib.domain.Domain`
interface instead of module globals.

Wake enumerates with the kernel (``enumerate_budget``), evaluates each candidate
through the domain and keeps the ``top_k`` by posterior. Domains whose semantics
live in the kernel and whose likelihood is the deterministic default use the
kernel's own I/O filter (``search_tasks``), which avoids one round trip per
candidate.
"""
from __future__ import annotations
import copy
import json
import math
import random
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Optional, Sequence

import torch

from . import ast
from .domain import Domain, KernelEvaluator, Task
from .kernel import Kernel, KernelError
from .compression import Compressor, OriginalCompressor
from ..python.recognition import Recognition

@dataclass
class SearchConfig:
    upper_bound: float = 100.
    maximum_depth: int = 14
    max_size: int = 33
    limit: int = 3000          # complete programs consumed (an output budget, not a bound on work)
    max_states: int = 500_000  # popped agenda states
    top_k: int = 5             # frontier size retained per task
    def budget(self) -> dict:
        return dict(upper_bound=self.upper_bound, maximum_depth=self.maximum_depth, max_size=self.max_size,
                    limit=self.limit, max_states=self.max_states)

@dataclass
class DreamConfig:
    enabled: bool = True
    draws: int = 20
    fuel: int = 128            # uniforms per ancestral draw; exhausted fuel rejects the draw

@dataclass
class RecognitionConfig:
    enabled: bool = True
    steps: int = 30
    hidden: int = 64
    objective: str = "bias_optimal"   # or "kl"
    device: Optional[str] = None

@dataclass
class ECConfig:
    rounds: int = 3
    seed: int = 7
    search: SearchConfig = field(default_factory=SearchConfig)
    dream: DreamConfig = field(default_factory=DreamConfig)
    recognition: RecognitionConfig = field(default_factory=RecognitionConfig)
    output: Optional[Path | str] = None
    def to_dict(self) -> dict:
        d = asdict(self); d["output"] = str(self.output) if self.output else None; return d

@dataclass
class WakeTrace:
    task: str
    enumerated: int
    expanded_states: int
    stop_reason: str
    first_solution: Optional[int]
    solutions: int
    seconds: float

@dataclass
class RoundRecord:
    round: int
    grammar: ast.Grammar
    frontiers: list[ast.Frontier]
    compression: dict
    dream: dict
    recognition_losses: list[float]
    solved: int
    traces: list[WakeTrace]
    seconds: dict
    def to_dict(self) -> dict:
        d = asdict(self); return d

WakeFunction = Callable[["ExploreCompress", Task, ast.Grammar, ast.Grammar], tuple[ast.Frontier, WakeTrace]]

def generic_wake(ec: "ExploreCompress", task: Task, grammar: ast.Grammar, search_grammar: ast.Grammar):
    """Enumerate in the kernel, evaluate and score through the domain."""
    cfg = ec.config.search; start = time.perf_counter()
    r = ec.kernel.call("enumerate_budget", grammar=grammar, search_grammar=search_grammar, request=task.request, **cfg.budget())
    entries, first = [], None
    for rank, e in enumerate(r["programs"], 1):
        outputs = ec.domain.evaluate_batch(e["program"], task.inputs, ec.kernel)
        ll = ec.domain.log_likelihood(task, e["program"], outputs)
        if ll > -math.inf:
            if first is None: first = rank
            entries.append(ast.entry(e["program"], ll, log_prior=e["log_prior"], search_rank=rank, search_log_score=e["search_log_score"]))
    entries.sort(key=lambda e: e["log_prior"] + e["log_likelihood"], reverse=True)
    trace = WakeTrace(task.name, len(r["programs"]), r["expanded_states"], r["stop_reason"], first, len(entries), time.perf_counter() - start)
    return ast.frontier(task.request, entries[:cfg.top_k]), trace

def kernel_io_wake(ec: "ExploreCompress", task: Task, grammar: ast.Grammar, search_grammar: ast.Grammar):
    """Kernel-side I/O filtering (``search_tasks``); only valid for kernel-evaluated
    domains with the deterministic likelihood."""
    cfg = ec.config.search; start = time.perf_counter()
    r = ec.kernel.call("search_tasks", grammar=grammar, search_grammar=search_grammar, request=task.request,
                       tasks=[task.wire()], top_k=cfg.top_k, **cfg.budget())
    row = r["tasks"][0]
    entries = [ast.entry(s["program"], s["log_likelihood"], log_prior=s["log_prior"], search_rank=s["search_rank"],
                         search_log_score=s["search_log_score"]) for s in row["solutions"]]
    trace = WakeTrace(task.name, r["enumerated_nodes"], r["expanded_states"], r["stop_reason"], row["first_solution_nodes"], len(entries), time.perf_counter() - start)
    return ast.frontier(task.request, entries), trace

def uses_kernel_io(domain: Domain) -> bool:
    return (isinstance(domain.evaluator, KernelEvaluator)
            and type(domain).log_likelihood is Domain.log_likelihood
            and type(domain).outputs_equal is Domain.outputs_equal)

class ExploreCompress:
    def __init__(self, domain: Domain, kernel: Kernel, compressor: Optional[Compressor] = None,
                 config: Optional[ECConfig] = None, *, wake: Optional[WakeFunction] = None,
                 recognition_factory: Optional[Callable[[ast.Grammar], Recognition]] = None,
                 base_grammar: Optional[ast.Grammar] = None):
        self.domain, self.kernel = domain, kernel
        self.compressor = compressor or OriginalCompressor()
        self.config = config or ECConfig()
        self._wake = wake or (kernel_io_wake if uses_kernel_io(domain) else generic_wake)
        self._recognition = recognition_factory or self.default_recognition
        self.base_grammar = copy.deepcopy(base_grammar) if base_grammar is not None else domain.grammar()
        self.history: list[RoundRecord] = []
        self.model: Optional[Recognition] = None
        self.grammar: ast.Grammar = copy.deepcopy(self.base_grammar)
        self.frontiers: dict[str, ast.Frontier] = {}   # persistent frontiers by task name

    # -- components --------------------------------------------------------------------------
    def default_recognition(self, grammar: ast.Grammar) -> Recognition:
        c = self.config.recognition
        return Recognition(grammar, feature_dim=self.domain.feature_dim, hidden=c.hidden, device=c.device)

    def search_grammar(self, task: Task, grammar: Optional[ast.Grammar] = None) -> ast.Grammar:
        """Recognition-conditioned grammar for ``task`` (the generative one without a model)."""
        if self.model is None: return grammar if grammar is not None else self.grammar
        return self.model.search_grammar(self.domain.features(task))

    def wake(self, task: Task, grammar: Optional[ast.Grammar] = None, search_grammar: Optional[ast.Grammar] = None):
        grammar = grammar if grammar is not None else self.grammar
        return self._wake(self, task, grammar, search_grammar if search_grammar is not None else self.search_grammar(task, grammar))

    def rescore(self, frontier: ast.Frontier, grammar: ast.Grammar, top_k: Optional[int] = None) -> ast.Frontier:
        """Recompute generative priors under ``grammar``; keep the best ``top_k`` by posterior."""
        scored = []
        for e in frontier["entries"]:
            e = copy.deepcopy(e)
            e["log_prior"] = self.kernel.score(grammar, frontier["request"], e["program"])["log_probability"]
            scored.append(e)
        scored.sort(key=lambda e: e["log_prior"] + e["log_likelihood"], reverse=True)
        return ast.frontier(frontier["request"], scored[: (top_k or self.config.search.top_k)])

    @staticmethod
    def merge(persistent: ast.Frontier, found: ast.Frontier) -> ast.Frontier:
        unique = {ast.program_key(e["program"]): e for e in persistent["entries"] + found["entries"]}
        return ast.frontier(persistent["request"], unique.values())

    def dream(self, grammar: ast.Grammar, tasks: Sequence[Task], rng: random.Random):
        """Sample programs from the library and let the domain turn them into tasks."""
        cfg = self.config.dream; data, rejected, failed = [], 0, 0
        if not cfg.enabled: return data, {"draws": 0, "accepted": 0, "rejected": 0}
        requests = sorted({ast.program_key(t.request) for t in tasks})
        for n in range(cfg.draws):
            request = json.loads(rng.choice(requests))
            try:
                sample = self.kernel.sample(grammar, request, [rng.random() for _ in range(cfg.fuel)])
            except KernelError:
                rejected += 1; continue
            task = self.domain.dream(sample["program"], request, tasks, rng, self.kernel, name=f"dream-{n}")
            if task is None: failed += 1; continue
            data.append((self.domain.features(task), ast.frontier(request, [ast.entry(sample["program"], 0., log_prior=sample["log_probability"])])))
        return data, {"draws": cfg.draws, "accepted": len(data), "rejected": rejected + failed,
                      "sampling_rejections": rejected, "domain_rejections": failed}

    def train_recognition(self, grammar: ast.Grammar, data: list, seed: int) -> list[float]:
        cfg = self.config.recognition
        if not cfg.enabled: self.model = None; return []
        self.model = self._recognition(grammar)
        return self.model.fit_frontiers(self.kernel, data, steps=cfg.steps, seed=seed, objective=cfg.objective)

    # -- the loop -------------------------------------------------------------------------------
    def run(self, tasks: Sequence[Task], rounds: Optional[int] = None) -> list[RoundRecord]:
        """Run ``rounds`` (default ``config.rounds``) more rounds; frontiers, grammar,
        model and history persist on the instance, so calling again continues."""
        cfg = self.config; first = len(self.history)
        rng = random.Random(cfg.seed + first); torch.manual_seed(cfg.seed + first)
        persistent = [self.frontiers.get(t.name, ast.frontier(t.request)) for t in tasks]
        for r in range(first, first + (rounds if rounds is not None else cfg.rounds)):
            seconds = {}; t0 = time.perf_counter(); traces = []
            for i, task in enumerate(tasks):
                found, trace = self.wake(task); traces.append(trace)
                persistent[i] = self.rescore(self.merge(persistent[i], found), self.grammar)
            seconds["wake"] = time.perf_counter() - t0; t0 = time.perf_counter()
            solved = sum(1 for f in persistent if f["entries"])
            compression = self.compressor.compress(self.kernel, self.grammar, persistent)
            self.grammar, persistent = compression.grammar, compression.frontiers
            self.frontiers = {t.name: f for t, f in zip(tasks, persistent)}
            seconds["compress"] = time.perf_counter() - t0; t0 = time.perf_counter()
            dreamed, dream_stats = self.dream(self.grammar, tasks, rng)
            seconds["dream"] = time.perf_counter() - t0; t0 = time.perf_counter()
            replay = [(self.domain.features(t), f) for t, f in zip(tasks, persistent) if f["entries"]]
            losses = self.train_recognition(self.grammar, replay + dreamed, cfg.seed + r)
            seconds["recognition"] = time.perf_counter() - t0
            record = RoundRecord(r, copy.deepcopy(self.grammar), copy.deepcopy(persistent),
                                 dict(history=compression.history, inventions=compression.inventions, statistics=compression.statistics),
                                 dream_stats, losses, solved, traces, seconds)
            self.history.append(record)
            self.checkpoint(r)
        return self.history

    def checkpoint(self, round: int) -> None:
        if not self.config.output: return
        out = Path(self.config.output); out.mkdir(parents=True, exist_ok=True)
        (out / "history.json").write_text(json.dumps([h.to_dict() for h in self.history], indent=2), encoding="utf8")
        (out / "config.json").write_text(json.dumps(dict(self.config.to_dict(), domain=self.domain.name, compressor=self.compressor.name), indent=2), encoding="utf8")
        if self.model is not None:
            torch.save({"state": self.model.state_dict(), "grammar": self.grammar}, out / f"recognition_{round}.pt")

    def load_recognition(self, path: Path | str) -> Recognition:
        saved = torch.load(Path(path), map_location="cpu", weights_only=False)
        self.grammar = saved["grammar"]; self.model = self._recognition(self.grammar)
        self.model.load_state_dict(saved["state"]); return self.model

    # -- evaluation --------------------------------------------------------------------------------
    def solve(self, tasks: Sequence[Task], *, use_recognition: bool = True) -> list[tuple[ast.Frontier, WakeTrace]]:
        """Wake-only pass with the current library (and recognition model when present)."""
        results = []
        for task in tasks:
            sg = self.search_grammar(task) if use_recognition else self.grammar
            results.append(self.wake(task, self.grammar, sg))
        return results

def explore_compress(domain: Domain, tasks: Sequence[Task], *, kernel: Optional[Kernel] = None, compressor: Optional[Compressor] = None,
                     config: Optional[ECConfig] = None, **kwargs) -> list[RoundRecord]:
    """One-call convenience: owns a kernel when none is given."""
    if kernel is not None:
        return ExploreCompress(domain, kernel, compressor, config, **kwargs).run(tasks)
    with Kernel() as k:
        return ExploreCompress(domain, k, compressor, config, **kwargs).run(tasks)
