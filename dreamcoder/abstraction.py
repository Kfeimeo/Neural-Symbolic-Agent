from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass

from .grammar import Grammar
from .language import FunctionType, Language, Primitive, Program


@dataclass
class CompressionResult:
    grammar: Grammar
    programs: list[Program]
    added: list[str]
    description_length_before: int
    description_length_after: int


class Compressor(ABC):
    @abstractmethod
    def compress(self, grammar: Grammar, programs: list[Program]) -> CompressionResult:
        raise NotImplementedError


class RepeatedSubprogramCompressor(Compressor):
    """Greedy exact-subtree abstraction, parameterized by the task input.

    MDL is AST token count of corpus plus library definitions. No claim of
    e-graph unification or probabilistic optimality is made.
    """
    def compress(self, grammar: Grammar, programs: list[Program]) -> CompressionResult:
        old_language = grammar.language
        counts: Counter[Program] = Counter()
        def visit(p):
            if p.size >= 3 and old_language.infer(p) == old_language.output_type and "$input" in str(p):
                counts[p] += 1
            for c in p.arguments:
                visit(c)
        for p in programs:
            visit(p)
        existing_library_cost = sum(p.definition.size + 1 for p in old_language.primitives.values()
                                    if p.definition is not None)
        before = sum(p.size for p in programs) + existing_library_cost
        best = None
        for candidate, count in counts.items():
            saving = count * (candidate.size - 2) - (candidate.size + 1)
            if saving > 0 and (best is None or saving > best[0]):
                best = (saving, candidate)
        if best is None:
            return CompressionResult(grammar, programs[:], [], before, before)
        candidate = best[1]
        index = 0
        while f"learned_{index}" in old_language.primitives:
            index += 1
        name = f"learned_{index}"
        primitive = Primitive(name, FunctionType((old_language.input_type,), old_language.output_type),
                              lambda x: old_language.evaluate(candidate, x), candidate)
        language = Language(old_language.input_type, old_language.output_type,
                            {**old_language.primitives, name: primitive})
        def rewrite(p):
            if p == candidate:
                return Program(name, (Program("$input"),))
            return Program(p.name, tuple(rewrite(c) for c in p.arguments))
        rewritten = [rewrite(p) for p in programs]
        after = sum(p.size for p in rewritten) + existing_library_cost + candidate.size + 1
        # Count-based prior learning is separate from the token-MDL objective.
        new_grammar = Grammar.uniform(language).fit(rewritten)
        return CompressionResult(new_grammar, rewritten, [name], before, after)
