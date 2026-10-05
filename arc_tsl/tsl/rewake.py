"""Local re-wake: search one program satisfying every IO pair, in TSL_tau."""
from __future__ import annotations

from ..synthesis.enumerator import EnumerationConfig
from ..synthesis.grammar import Library
from ..synthesis.search import Pair, SearchResult, search


def rewake(pairs: list[Pair], tsl: Library, config: EnumerationConfig, top_k: int = 1) -> SearchResult:
    return search(pairs, tsl, config, top_k=top_k)
