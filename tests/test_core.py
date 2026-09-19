import itertools
import random

import pytest

from dreamcoder.abstraction import RepeatedSubprogramCompressor
from dreamcoder.domains.grid import make_language, sample_grid, synthetic_tasks
from dreamcoder.dreaming import dream, replay
from dreamcoder.grammar import Grammar
from dreamcoder.language import INPUT, FunctionType, Language, Primitive, Program, Type
from dreamcoder.search import EnumerationStats, Frontier, Solution, enumerate_programs, search
from dreamcoder.tasks import Example, Task


def test_domain_independent_language_and_order():
    number = Type("Number")
    language = Language(number, number, {
        n: Primitive(n, FunctionType((number,), number), f)
        for n, f in [("inc", lambda x: x+1), ("double", lambda x: x*2)]})
    grammar = Grammar.from_logits(language, {"inc": 2, "double": 0})
    programs = list(itertools.islice(enumerate_programs(grammar, max_size=4), 8))
    assert programs[1].name == "inc"
    assert [-grammar.log_prior(p) for p in programs] == sorted(-grammar.log_prior(p) for p in programs)
    other = Grammar.from_logits(language, {"inc": 0, "double": 2})
    assert list(itertools.islice(enumerate_programs(other), 2))[1].name == "double"
    assert language.evaluate(Program("inc", (INPUT,)), 5) == 6


def test_typing_and_grid_operations():
    language = make_language()
    with pytest.raises(TypeError):
        language.evaluate(Program("rotate90", (Program("red"),)), ((1,),))
    assert language.evaluate(Program("rotate90", (INPUT,)), ((1, 2, 3), (0, 1, 2))) == ((0, 1), (1, 2), (2, 3))
    p = Program("crop", (Program("largest", (Program("objects", (INPUT,)),)),))
    assert language.evaluate(p, ((0, 0, 0), (0, 2, 3))) == ((2, 3),)
    assert language.evaluate(p, ((0,),)) == ((0,),)
    translated = Program("translate", (INPUT, Program("one"), Program("zero")))
    assert language.evaluate(translated, ((1, 2), (3, 1))) == ((0, 0), (1, 2))


def test_frontier_matches_exhaustive_top_k():
    typ = Type("Integer")
    language = Language(typ, typ, {
        "id": Primitive("id", FunctionType((typ,), typ), lambda x: x),
        "neg": Primitive("neg", FunctionType((typ,), typ), lambda x: -x)})
    grammar = Grammar.from_logits(language, {"id": 1.0, "neg": -.2})
    task = Task("identity", (Example(2, 2), Example(3, 3)))
    result = search(task, grammar, top_k=4, max_size=5)
    all_solutions = [p for p in enumerate_programs(grammar, max_size=5) if task.accepts(language, p)]
    expected = sorted([grammar.log_prior(p) for p in all_solutions], reverse=True)[:4]
    assert [s.log_prior for s in result.frontier.solutions] == expected
    assert len(set(s.program for s in result.frontier.solutions)) == 4
    assert not Task("conflict", (Example(2, 2), Example(3, 5))).accepts(language, INPUT)


def test_program_recovery():
    language = make_language()
    task = synthetic_tasks(language, random.Random(9), 1)[0]
    result = search(task, Grammar.uniform(language), top_k=3, max_nodes=1500)
    assert task.ground_truth in [s.program for s in result.frontier.solutions]
    assert len(result.frontier.solutions) == 3


def test_compression_mdl_and_semantics():
    language = make_language()
    p = Program("rotate90", (Program("trim", (INPUT,)),))
    compression = RepeatedSubprogramCompressor().compress(Grammar.uniform(language), [p]*12)
    assert compression.added
    assert compression.description_length_after < compression.description_length_before
    assert not any(n.startswith("learned") for n in language.primitives)
    for rewritten in compression.programs:
        assert compression.grammar.language.expand(rewritten) == p
        x = sample_grid(random.Random(4))
        assert compression.grammar.language.evaluate(rewritten, x) == language.evaluate(p, x)
    assert not RepeatedSubprogramCompressor().compress(Grammar.uniform(language), [p]).added


def test_dream_reproducibility_and_replay():
    grammar = Grammar.uniform(make_language())
    a = dream(grammar, sample_grid, random.Random(7), count=15)
    b = dream(grammar, sample_grid, random.Random(7), count=15)
    assert a == b
    assert all(p.task.accepts(grammar.language, p.program) for p in a)
    frontier = Frontier(a[0].task, 3)
    frontier.add(Solution(a[0].program, grammar.log_prior(a[0].program)))
    assert replay([frontier])[0].program == a[0].program


def test_state_budget():
    stats = EnumerationStats()
    list(enumerate_programs(Grammar.uniform(make_language()), max_states=2, stats=stats))
    assert stats.expanded_states == 2
    assert stats.budget_exhausted
