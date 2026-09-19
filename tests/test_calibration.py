import random
from dataclasses import replace

import pytest

from dreamcoder.abstraction import RepeatedSubprogramCompressor
from dreamcoder.audit.benchmark import fingerprint, io_hash
from dreamcoder.audit.controlled import ControlledConfig, generate, private_record
from dreamcoder.audit.curves import search_curves
from dreamcoder.audit.distribution import abstraction_metrics, overlap, profile, rewrite_for_measurement, typed_search_growth
from dreamcoder.domains.grid import make_language
from dreamcoder.domains.grid.canonical import canonical
from dreamcoder.grammar import Grammar
from dreamcoder.language import INPUT, FunctionType, Language, Primitive, Program, Type
from dreamcoder.search import search
from dreamcoder.tasks import Example, Task


@pytest.fixture(scope="module")
def benchmark():
    return generate()


def test_controlled_split_and_hidden_boundary(benchmark):
    language = make_language()
    assert len(benchmark.latents) == 4
    assert len(benchmark.training) == 96 and len(benchmark.testing) == 60
    for task in benchmark.learner_training()+benchmark.learner_testing():
        assert task.ground_truth is None
        assert task.name.startswith(("train_", "test_"))
    for task in benchmark.training+benchmark.testing:
        assert set(task.ground_truth.symbols()) <= set(language.primitives)
    split = overlap([t.ground_truth for t in benchmark.training], [t.ground_truth for t in benchmark.testing], language, benchmark.split_probes)
    assert split["full_program_overlap"] == split["canonical_program_overlap"] == split["behavioral_probe_overlap"] == 0
    assert split["shared_nontrivial_subtree_count"] > 0
    assert not {io_hash(t) for t in benchmark.training} & {io_hash(t) for t in benchmark.testing}


def test_independent_reuse_control_preserves_hidden_programs(benchmark):
    other = generate(replace(benchmark.config, low_reuse=1, high_reuse=2))
    assert benchmark.latents == other.latents
    assert [t.ground_truth for t in benchmark.testing] == [t.ground_truth for t in other.testing]
    assert len(other.training) == 18
    cells = {(m["reuse"], m["difficulty"], m["complexity_extra"], m["recipe"])
             for n, m in benchmark.metadata.items() if n.startswith("test_") and m["recipe"] not in ("anchor", "hard_tail")}
    assert len(cells) == 2*2*2*3


def test_generator_reproducible_without_search(benchmark):
    assert private_record(benchmark) == private_record(generate(benchmark.config))


def test_prefix_curves_equal_independent_searches():
    number = Type("Number")
    language = Language(number, number, {
        "inc": Primitive("inc", FunctionType((number,), number), lambda x: x+1),
        "add": Primitive("add", FunctionType((number, number), number), lambda x, y: x+y),
        "zero": Primitive("zero", FunctionType((), number), lambda: 0)})
    grammar = Grammar.from_logits(language, {"inc": 1, "add": 0, "zero": -.5})
    tasks = [Task("increment", (Example(2, 3), Example(3, 4))),
             Task("double", (Example(2, 4), Example(3, 6))),
             Task("impossible", (Example(0, -100),))]
    budgets = (1, 5, 10, 30)
    for state_limit in (1, 25, 10000):
        curves = search_curves(tasks, grammar, budgets, max_size=5, max_states=state_limit)
        for task, curve in zip(tasks, curves):
            for n in budgets:
                direct = search(task, grammar, top_k=3, max_nodes=n, max_size=5, max_states=state_limit)
                cached = curve[n]
                assert cached.frontier.solutions == direct.frontier.solutions
                for field in ("enumerated_nodes", "expanded_states", "first_solution_nodes", "budget_exhausted", "termination_reason"):
                    assert getattr(cached, field) == getattr(direct, field)


def test_parameterized_rewriting_is_only_capacity_metric():
    language = make_language()
    body = Program("rotate90", (Program("trim", (INPUT,)),))
    p = Program("rotate90", (Program("trim", (Program("invert", (INPUT,)),)),))
    assert rewrite_for_measurement(p, {"macro": body}, parameterized=False) == p
    compact = rewrite_for_measurement(p, {"macro": body})
    assert compact == Program("macro", (Program("invert", (INPUT,)),))
    assert compact.size < p.size
    score = abstraction_metrics({"macro": body}, {"F0": body, "F1": Program("invert", (body,))}, language, [((0,1,2),)])
    assert score["alpha_precision"] == score["canonical_precision"] == 1
    assert score["alpha_recall"] == .5


def test_repeated_full_programs_do_not_imply_proper_fragments():
    language = make_language()
    ps = [Program(n, (Program("trim", (INPUT,)),)) for n in ("rotate90", "flipH", "invert") for _ in range(12)]
    p = profile(ps, language)
    assert p["unique_raw_programs"] == 3
    assert p["recurring_proper_fragment_count"] == 0
    assert p["primitive_frequency"]["trim"] == 36
    growth = typed_search_growth(language)
    assert int(growth[-1]["grid_programs_at_most_depth"]) > int(growth[2]["grid_programs_at_most_depth"])


def test_compressor_does_not_overwrite_existing_named_primitive():
    language = make_language()
    prior = language.primitives["identity"]
    language.primitives["learned_0"] = Primitive("learned_0", prior.signature, prior.implementation)
    p = Program("rotate90", (Program("trim", (INPUT,)),))
    result = RepeatedSubprogramCompressor().compress(Grammar.uniform(language), [p]*12)
    assert result.added == ["learned_1"]
    assert result.grammar.language.primitives["learned_0"] is language.primitives["learned_0"]
