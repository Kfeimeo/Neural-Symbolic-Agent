"""Per-task pipeline for every experimental condition.

    baseline      : fixed Base_{ML+DSA} search over all pairs
    tsl           : local wake -> compression -> A_tau -> re-wake (uniform theta)
    reweight      : local wake -> theta_tau only -> re-wake (no abstractions)
    tsl_reweight  : local wake -> A_tau + theta_tau -> re-wake
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

from ..arc.grid import Grid, shape
from ..arc.parse import parse
from ..dsa.types import OBJECTS
from ..language import base_library
from ..ontology.instance import ExtractionConfig
from ..synthesis.enumerator import EnumerationConfig
from ..synthesis.grammar import Library
from ..synthesis.search import Pair, SearchResult, search
from .compression import CompressionResult, compress
from .local_library import ThetaConfig, contract, fit_costs, prune_unused, rewrite_with_library, used_productions
from .local_wake import WakeResult, local_wake
from .rewake import rewake

STATUS_SOLVED = "SOLVED"
STATUS_UNSUPPORTED = "UNSUPPORTED"
STATUS_TIMEOUT = "SEARCH_TIMEOUT"
STATUS_NO_PAIRWISE = "NO_PAIRWISE_SOLUTION"
STATUS_NO_SHARED = "NO_SHARED_PROGRAM"


@dataclass
class PipelineConfig:
    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)
    wake: EnumerationConfig = field(default_factory=lambda: EnumerationConfig(max_cost=8, max_expanded_states=100_000,
                                                                              time_limit_seconds=30.0))
    full: EnumerationConfig = field(default_factory=lambda: EnumerationConfig(max_cost=10, max_expanded_states=300_000,
                                                                              time_limit_seconds=90.0))
    wake_top_k: int = 5
    max_abstractions: int = 3
    max_arity: int = 3
    unused_cost: int = 2

    def to_dict(self) -> dict:
        return {"extraction": asdict(self.extraction), "wake": asdict(self.wake), "full": asdict(self.full),
                "wake_top_k": self.wake_top_k, "max_abstractions": self.max_abstractions,
                "max_arity": self.max_arity, "unused_cost": self.unused_cost}


def make_pairs(train: list[tuple[Grid, Grid]], extraction: ExtractionConfig) -> list[Pair]:
    return [Pair(parse(x, extraction), y) for x, y in train]


def supported(train: list[tuple[Grid, Grid]]) -> tuple[bool, str]:
    for x, y in train:
        if shape(x) != shape(y):
            return False, "output shape differs from input shape"
    return True, ""


def _status_from_search(r: SearchResult) -> str:
    if r.solved:
        return STATUS_SOLVED
    return STATUS_TIMEOUT


def run_baseline(train, config: PipelineConfig, library: Library | None = None) -> dict:
    ok, why = supported(train)
    record = {"num_train_pairs": len(train), "condition": "baseline"}
    if not ok:
        record.update(status=STATUS_UNSUPPORTED, reason=why, search=None)
        return record
    lib = library or base_library()
    pairs = make_pairs(train, config.extraction)
    r = search(pairs, lib, config.full, top_k=1)
    record.update(status=_status_from_search(r), search=r.summary(),
                  program=str(r.frontier.best.program) if r.solved else None,
                  program_length=r.frontier.best.description_length if r.solved else None)
    return record


@dataclass
class TSLRun:
    wake: WakeResult
    compression: CompressionResult | None
    pruned: list[str]
    tsl: Library
    costs: dict[str, int]
    rewake: SearchResult
    sleep_seconds: float


def library_key(lib: Library) -> tuple:
    return (tuple((n, str(a)) for n, a in lib.abstractions.items()),
            tuple(sorted((k, v) for k, v in lib.costs.items() if v != 1)))


def run_tsl(train, config: PipelineConfig, abstractions: bool = True, reweight: bool = False,
            library: Library | None = None, wake: WakeResult | None = None,
            rewake_cache: dict | None = None) -> dict:
    """``rewake_cache`` (optional) maps ``library_key`` -> SearchResult so that
    conditions ending up with the same TSL share one (deterministic) re-wake."""
    condition = {(True, False): "tsl", (False, True): "reweight", (True, True): "tsl_reweight",
                 (False, False): "baseline"}[(abstractions, reweight)]
    record = {"num_train_pairs": len(train), "condition": condition}
    ok, why = supported(train)
    if not ok:
        record.update(status=STATUS_UNSUPPORTED, reason=why)
        return record
    base = library or base_library()
    pairs = make_pairs(train, config.extraction)

    # ---- local wake ------------------------------------------------------
    if wake is None:
        wake = local_wake(pairs, base, config.wake, config.wake_top_k)
    record["wake"] = wake.to_dict()
    frontiers = [F for F in wake.frontiers if F]

    # ---- local sleep -----------------------------------------------------
    t0 = time.perf_counter()
    tsl = base
    comp = None
    pruned: list[str] = []
    if abstractions and frontiers:
        comp = compress(base, frontiers, (OBJECTS,), OBJECTS, config.max_abstractions, config.max_arity)
        tsl, pruned = prune_unused(comp.library, comp.frontiers)
        expanded = [[comp.library.expand(p) for p in F] for F in comp.frontiers]
        tsl, pruned2 = contract(tsl, expanded)
        pruned += pruned2
    costs: dict[str, int] = {}
    if reweight and frontiers:
        rewritten = [[rewrite_with_library(tsl, p) for p in F] for F in frontiers]
        costs = fit_costs(tsl, [p for F in rewritten for p in F], ThetaConfig(config.unused_cost))
        tsl = tsl.with_costs(costs)
    sleep_seconds = time.perf_counter() - t0

    record["sleep"] = {
        "seconds": sleep_seconds,
        "num_abstractions": len(tsl.abstractions),
        "abstractions": [str(a) for a in tsl.abstractions.values()],
        "abstraction_lengths": {n: base.description_length(a.body) + 1 for n, a in tsl.abstractions.items()},
        "library_description_length": tsl.library_description_length(),
        "mdl_before": comp.mdl_before if comp else None,
        "mdl_after": comp.mdl_after if comp else None,
        "pruned": pruned,
        "steps": [s.to_dict() for s in comp.steps] if comp else [],
        "rewritten_frontiers": [[str(p) for p in F] for F in comp.frontiers] if comp else [],
        "costs": {k: v for k, v in costs.items() if v != 1},
    }

    # ---- local re-wake ---------------------------------------------------
    key = library_key(tsl)
    if rewake_cache is not None and key in rewake_cache:
        r = rewake_cache[key]
        record["rewake_shared"] = True
    else:
        r = rewake(pairs, tsl, config.full, top_k=1)
        if rewake_cache is not None:
            rewake_cache[key] = r
        record["rewake_shared"] = False
    record["rewake"] = r.summary()
    record["tsl_is_base"] = key == ((), ())
    if r.solved:
        best = r.frontier.best
        prog = best.program
        expanded_prog = tsl.expand(prog)
        used = [n for n in tsl.abstractions if n in used_productions(prog)]
        record.update(status=STATUS_SOLVED, program=str(prog), program_length=best.description_length,
                      expanded_program=str(expanded_prog), expanded_program_length=base.description_length(expanded_prog),
                      abstractions_used=used,
                      total_mdl=tsl.library_description_length() + best.description_length)
    else:
        if wake.solved_pairs == 0:
            status = STATUS_NO_PAIRWISE
        elif wake.solved_pairs == len(pairs):
            status = STATUS_NO_SHARED
        else:
            status = STATUS_NO_PAIRWISE
        record.update(status=status, program=None, program_length=None, abstractions_used=[],
                      total_mdl=None)
    record["wake_unsolved_pairs"] = len(pairs) - wake.solved_pairs
    return record
