import itertools
import random
from statistics import mean
from functools import lru_cache

import pytest
import torch

from dreamcoder.abstraction import RepeatedSubprogramCompressor
from dreamcoder.audit.benchmark import ProgramSplit, diverse_grid
from dreamcoder.audit.benchmark import wrap
from dreamcoder.audit.metrics import derangement, record, summarize
from dreamcoder.domains.grid import make_language, sample_grid
from dreamcoder.domains.grid.canonical import canonical, depth
from dreamcoder.domains.grid.features import encode_task
from dreamcoder.dreaming import dream
from dreamcoder.ec import summarize as summarize_v1
from dreamcoder.grammar import Grammar
from dreamcoder.language import INPUT, Program, Type, Language, Primitive, FunctionType
from dreamcoder.recognition import RecognitionModel
from dreamcoder.search import Frontier, SearchResult, Solution, enumerate_programs, search
from dreamcoder.tasks import Example, Task


def chain(*names):
    p = INPUT
    for name in reversed(names):
        p = Program(name, (p,))
    return p


def test_dream_last_attempt_and_zero_count():
    grammar = Grammar.uniform(make_language())
    grammar.sample = lambda rng: INPUT
    assert len(dream(grammar, sample_grid, random.Random(3), count=1, max_attempts=1)) == 1
    assert dream(grammar, sample_grid, random.Random(3), count=0) == []
    with pytest.raises(RuntimeError):
        dream(grammar, sample_grid, random.Random(3), count=1, max_attempts=0)


def test_uniform_baseline_survives_compression_and_fit():
    grammar = Grammar.uniform(make_language())
    snapshot = dict(grammar.log_probabilities)
    p = chain("rotate90", "trim")
    compressed = RepeatedSubprogramCompressor().compress(grammar, [p]*12)
    compressed.grammar.fit(compressed.programs)
    assert grammar.log_probabilities == snapshot
    assert len(set(snapshot.values())) == 1
    assert set(grammar.language.primitives).isdisjoint(compressed.added)


def test_original_mdl_and_existing_definition_accounting():
    grammar = Grammar.uniform(make_language())
    corpus = [chain(n, "trim") for n in ("rotate90", "flipH", "invert") for _ in range(12)]
    first = RepeatedSubprogramCompressor().compress(grammar, corpus)
    assert (first.description_length_before, first.description_length_after) == (108, 100)
    assert sum(p.size for p in first.programs) == 96
    second = RepeatedSubprogramCompressor().compress(first.grammar, first.programs)
    assert second.description_length_before == first.description_length_after
    assert second.description_length_after < second.description_length_before


def test_learned_primitive_composes_on_either_side():
    language = make_language()
    p = chain("rotate90", "trim")
    result = RepeatedSubprogramCompressor().compress(Grammar.uniform(language), [p]*12)
    learned = result.grammar.language
    f = result.added[0]
    programs = [Program("border", (Program(f, (INPUT,)),)), Program(f, (chain("invert"),))]
    for program in programs:
        assert learned.infer(program) == language.output_type
        for seed in range(10):
            x = sample_grid(random.Random(seed))
            assert learned.evaluate(program, x) == language.evaluate(learned.expand(program), x)


def test_canonical_rules_sound_and_idempotent():
    language = make_language()
    probes = [((0,),), ((1, 0), (0, 0)), ((1, 2, 3),)] + [diverse_grid(random.Random(s)) for s in range(8)]
    operations = ("identity", "rotate90", "rotate180", "flipH", "flipV", "transpose", "trim", "invert", "border")
    for names in itertools.product(operations, repeat=3):
        p = chain(*names)
        c = canonical(p)
        assert canonical(c) == c
        assert all(language.evaluate(c, x) == language.evaluate(p, x) for x in probes)
    assert canonical(chain("rotate90", "rotate90")) == canonical(chain("rotate180"))
    assert canonical(chain("trim", "rotate90")) == canonical(chain("rotate90", "trim"))
    assert depth(canonical(chain("identity", "identity", "trim", "trim"))) == 1


def test_color_and_shape_canonicalization_removes_fake_depth():
    language = make_language()
    nested = Program("solid", (Program("solid", (chain("flipH"), Program("red"))), Program("green")))
    assert depth(canonical(nested)) == 2
    assert depth(canonical(chain("border", "rotate90", "border", "transpose", "border"))) == 4
    rng = random.Random(71)
    probes = [diverse_grid(random.Random(s)) for s in range(12)]
    for _ in range(250):
        p = INPUT
        for _ in range(rng.randint(1, 8)):
            p = wrap(p, rng)
        c = canonical(p)
        assert canonical(c) == c
        assert all(language.evaluate(p, x) == language.evaluate(c, x) for x in probes)


def test_raw_expanded_canonical_and_behavioral_recovery_are_distinct():
    language = make_language()
    p = chain("rotate90", "trim")
    compressed = RepeatedSubprogramCompressor().compress(Grammar.uniform(language), [p]*12)
    learned = compressed.grammar.language
    x = ((0, 0, 0), (0, 1, 2))
    task = Task("test", (Example(x, language.evaluate(p, x)),), p)
    macro = Program(compressed.added[0], (INPUT,))
    frontier = Frontier(task, 3, [Solution(macro, -1)])
    result = SearchResult(frontier, 2, 3, .01, 2, False, "frontier_complete")
    row = record(result, learned, [x])
    assert not row["exact_program_recovery"]
    assert row["expanded_ast_recovery"] and row["canonical_program_recovery"] and row["behavioral_recovery"]
    frontier.solutions = [Solution(chain("trim", "rotate90"), -2)]
    row = record(result, learned, [x])
    assert not row["expanded_ast_recovery"] and row["canonical_program_recovery"]
    legacy = summarize_v1([result], compressed.grammar, [x])
    assert legacy["exact_program_recovery_rate"] == 0


def test_fitting_observed_examples_is_not_semantic_recovery():
    language = make_language()
    task = Task("ambiguous", (Example(((1,),), ((1,),)),), INPUT)
    frontier = Frontier(task, 1, [Solution(chain("flipH"), -1)])
    row = record(SearchResult(frontier, 2, 3, .01, 2, False), language, [((1, 2),)])
    assert row["solved"] and not row["behavioral_recovery"]


def test_first_solution_metric_does_not_impute_failures():
    language = make_language()
    task = Task("identity", (Example(((1,),), ((1,),)),), INPUT)
    good = SearchResult(Frontier(task, 1, [Solution(INPUT, 0)]), 2, 3, .01, 2, False)
    bad = SearchResult(Frontier(task, 1), 100, 200, .1, None, True)
    rows = [record(r, language, [((1,),)]) for r in (good, bad)]
    summary = summarize(rows)
    assert summary["mean_first_solution_nodes"] == 2
    assert summary["first_solution_sample_count"] == 1
    assert summary["mean_censored_first_solution_nodes"] == 51
    assert summarize([rows[1]])["mean_first_solution_nodes"] is None
    old = summarize_v1([good, bad], Grammar.uniform(language), [((1,),)])
    assert old["mean_first_solution_nodes"] == 2


def test_shuffle_is_reproducible_and_never_self_assigned():
    a = derangement(24, random.Random(8))
    assert a == derangement(24, random.Random(8))
    assert sorted(a) == list(range(24))
    assert all(i != j for i, j in enumerate(a))


def test_metadata_and_ground_truth_cannot_change_recognition_or_search():
    torch.manual_seed(7)
    grammar = Grammar.uniform(make_language())
    ios = (Example(((1, 2),), ((2, 1),)),)
    a = Task("contains_flipH_template", ios, chain("flipH"))
    b = Task("misleading_rotate90", ios, chain("rotate90"))
    assert encode_task(a) == encode_task(b)
    model = RecognitionModel(list(grammar.language.primitives), len(encode_task(a)[0]), encode_task)
    ga, gb = model.contextual_grammar(a, grammar), model.contextual_grammar(b, grammar)
    assert ga.log_probabilities == gb.log_probabilities
    ra, rb = search(a, ga, top_k=1), search(b, gb, top_k=1)
    assert ra.frontier.solutions == rb.frontier.solutions
    assert ra.enumerated_nodes == rb.enumerated_nodes


def test_split_rejects_training_program_and_canonical_equivalents():
    language = make_language()
    p = chain("rotate90", "trim")
    probes = [diverse_grid(random.Random(s)) for s in range(12)]
    split = ProgramSplit(language, [p], probes)
    assert not split.accept(p)
    assert not split.accept(chain("trim", "rotate90"))
    novel = chain("border", "rotate90", "trim")
    assert split.accept(novel)
    assert not split.accept(novel)


def test_search_distinguishes_limit_from_success():
    grammar = Grammar.uniform(make_language())
    task = Task("impossible", (Example(((1,),), ((9,),)),))
    limited = search(task, grammar, max_nodes=1)
    assert limited.termination_reason == "max_nodes" and limited.budget_exhausted
    limited = search(task, grammar, max_nodes=100, max_states=1)
    assert limited.termination_reason == "max_states" and limited.budget_exhausted
    successful = search(Task("id", (Example(((1,),), ((1,),)),)), grammar, top_k=1, max_nodes=1)
    assert successful.termination_reason == "frontier_complete" and not successful.budget_exhausted
    for options in ({"max_size": 0}, {"max_states": 0}):
        with pytest.raises(ValueError):
            list(enumerate_programs(grammar, **options))


def test_branching_enumerator_matches_independent_exhaustive_oracle():
    number = Type("Number")
    language = Language(number, number, {
        "inc": Primitive("inc", FunctionType((number,), number), lambda a: a+1),
        "add": Primitive("add", FunctionType((number, number), number), lambda a, b: a+b),
        "zero": Primitive("zero", FunctionType((), number), lambda: 0)})
    grammar = Grammar.from_logits(language, {"inc": .3, "add": .6, "zero": -.5})

    @lru_cache(None)
    def exact_size(size):
        values = [INPUT, Program("zero")] if size == 1 else []
        if size > 1:
            values.extend(Program("inc", (p,)) for p in exact_size(size-1))
        for left in range(1, size-1):
            values.extend(Program("add", (a, b)) for a in exact_size(left) for b in exact_size(size-1-left))
        return tuple(values)

    oracle = [p for size in range(1, 6) for p in exact_size(size)]
    enumerated = list(enumerate_programs(grammar, max_size=5))
    assert len(enumerated) == len(set(enumerated)) == len(oracle)
    assert set(enumerated) == set(oracle)
    costs = [-grammar.log_prior(p) for p in enumerated]
    assert all(a <= b+1e-12 for a, b in zip(costs, costs[1:]))
    task = Task("double", (Example(2, 4), Example(3, 6)))
    expected = sorted((grammar.log_prior(p) for p in oracle if task.accepts(language, p)), reverse=True)[:3]
    actual = search(task, grammar, top_k=3, max_size=5)
    assert [s.log_prior for s in actual.frontier.solutions] == pytest.approx(expected)
