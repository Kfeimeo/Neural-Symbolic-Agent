from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean

from ..domains.grid import GRID
from ..domains.grid.canonical import canonical, depth
from ..language import INPUT, Language, Program
from .benchmark import fingerprint


def walk(p: Program):
    yield p
    for child in p.arguments:
        yield from walk(child)


def decode(p: dict) -> Program:
    return Program(p["name"], tuple(decode(c) for c in p["arguments"]))


def profile(programs: list[Program], language: Language) -> dict:
    symbols = Counter(n for p in programs for n in p.symbols())
    fragments, proper, support = Counter(), Counter(), defaultdict(set)
    branching = defaultdict(list)
    for p in programs:
        for node in walk(p):
            if node.arguments:
                branching[depth(p)].append(len(node.arguments))
            if node.size >= 3 and language.infer(node) == GRID and INPUT in set(walk(node)):
                fragments[str(node)] += 1
                support[str(node)].add(str(p))
        for child in p.arguments:
            for node in walk(child):
                if node.size >= 3 and language.infer(node) == GRID and INPUT in set(walk(node)):
                    proper[str(node)] += 1
    recurring = {p: c for p, c in fragments.items() if c >= 2}
    return {"program_count": len(programs), "unique_raw_programs": len(set(programs)),
            "unique_canonical_programs": len({canonical(p) for p in programs}),
            "depth_histogram": dict(Counter(depth(p) for p in programs)),
            "effective_depth_histogram": dict(Counter(depth(canonical(p)) for p in programs)),
            "ast_size_histogram": dict(Counter(p.size for p in programs)),
            "primitive_frequency": dict(symbols),
            "primitive_relative_frequency": {n: c/sum(symbols.values()) for n, c in symbols.items()},
            "mean_ast_arity_by_program_depth": {d: mean(xs) for d, xs in branching.items()},
            "recurring_grid_fragments": recurring,
            "recurring_occurrence_frequency_histogram": dict(Counter(recurring.values())),
            "proper_fragment_counts": dict(proper),
            "cross_distinct_program_support": {p: len(s) for p, s in support.items()},
            "recurring_proper_fragment_count": sum(c >= 2 for c in proper.values())}


def typed_search_growth(language: Language, max_depth: int = 8) -> list[dict]:
    types = {language.input_type, language.output_type}
    for p in language.primitives.values():
        types.update(p.signature.arguments)
        types.add(p.signature.result)
    def terminals(t):
        return int(t == language.input_type)+sum(not p.signature.arguments and p.signature.result == t for p in language.primitives.values())
    counts = {t: terminals(t) for t in types}
    rows = [{"depth": 0, "grid_programs_at_most_depth": str(counts[language.output_type])}]
    for d in range(1, max_depth+1):
        new = {t: terminals(t) for t in types}
        for p in language.primitives.values():
            if not p.signature.arguments:
                continue
            count = 1
            for arg in p.signature.arguments:
                count *= counts[arg]
            new[p.signature.result] += count
        before, after = counts[language.output_type], new[language.output_type]
        rows.append({"depth": d, "grid_programs_at_most_depth": str(after),
                     "grid_programs_exact_depth": str(after-before),
                     "growth_factor": after/before if before else None})
        counts = new
    return rows


def match_body(pattern: Program, candidate: Program):
    """Unary alpha-normalized syntactic match, for OFFLINE metrics only."""
    captured = []
    def match(a, b):
        if a == INPUT:
            captured.append(b)
            return True
        return a.name == b.name and len(a.arguments) == len(b.arguments) and all(match(x, y) for x, y in zip(a.arguments, b.arguments))
    if match(pattern, candidate) and captured and all(x == captured[0] for x in captured):
        return captured[0]
    return None


def rewrite_for_measurement(p: Program, definitions: dict[str, Program], *, canonicalize=False, parameterized=True) -> Program:
    """Representational capacity diagnostic, never supplied to the learner.

    Parameterized matching tests use of an ALREADY learned macro at new inputs;
    it does not propose new abstractions and is not a compressor replacement.
    """
    if canonicalize:
        p = canonical(p)
        definitions = {n: canonical(d) for n, d in definitions.items()}
    def rewrite(node):
        best = Program(node.name, tuple(rewrite(c) for c in node.arguments))
        for name, definition in definitions.items():
            argument = match_body(definition, node) if parameterized else (INPUT if node == definition else None)
            if argument is not None:
                option = Program(name, (rewrite(argument),))
                if option.size < best.size:
                    best = option
        return best
    return rewrite(p)


def abstraction_metrics(definitions: dict[str, Program], latents: dict[str, Program], language: Language, probes: list) -> dict:
    rows = []
    for name, definition in definitions.items():
        fp = fingerprint(language, definition, probes)
        rows.append({"name": name, "definition": str(definition),
                     "alpha_matches": [n for n, p in latents.items() if definition == p],
                     "canonical_matches": [n for n, p in latents.items() if canonical(definition) == canonical(p)],
                     "behavioral_matches": [n for n, p in latents.items() if fp == fingerprint(language, p, probes)]})
    result = {"learned": rows, "hidden_count": len(latents), "learned_count": len(definitions),
              "recall_ceiling_one_macro": min(1.0, 1/len(latents)) if latents else None}
    for criterion in ("alpha", "canonical", "behavioral"):
        matched = {n for row in rows for n in row[criterion+"_matches"]}
        result[criterion+"_precision"] = sum(bool(row[criterion+"_matches"]) for row in rows)/len(rows) if rows else 0.0
        result[criterion+"_recall"] = len(matched)/len(latents) if latents else 0.0
    return result


def overlap(training: list[Program], testing: list[Program], language: Language, probes: list) -> dict:
    raw, canon = set(training), {canonical(p) for p in training}
    behavior = {fingerprint(language, p, probes) for p in training}
    subtrees = {c for p in training for c in walk(p) if c.size >= 3}
    shared = {c for p in testing for c in walk(p) if c.size >= 3} & subtrees
    return {"full_program_overlap": sum(p in raw for p in testing),
            "canonical_program_overlap": sum(canonical(p) in canon for p in testing),
            "behavioral_probe_overlap": sum(fingerprint(language, p, probes) in behavior for p in testing),
            "shared_nontrivial_subtree_count": len(shared), "shared_subtrees": sorted(map(str, shared)),
            "test_programs_with_shared_subtree": sum(any(c in subtrees for c in walk(p) if c.size >= 3) for p in testing)}
