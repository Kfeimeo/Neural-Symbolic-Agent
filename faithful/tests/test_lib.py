"""Library interface tests: kernel process management, Python evaluator, Domain
contract, Stitch wrapper and the dependency-injected EC driver."""
import copy
import json
import math
import random
import pytest
import torch
from faithful.lib import (ast, Kernel, KernelError, KernelProcessError, executable_path, operations,
                          Interpreter, EvaluationError, curry, Domain, Primitive,
                          OriginalCompressor, VersionSpaceCompressor, StitchCompressor, NoCompression, accounting,
                          StitchOptions, LEAF_COST, ExploreCompress, ECConfig, SearchConfig, DreamConfig, RecognitionConfig)
from faithful.lib import stitch
from faithful.lib.ec import generic_wake, kernel_io_wake, uses_kernel_io
from faithful.lib.domains import ListDomain, ArithmeticDomain, list_tasks, arithmetic_tasks, GridDomain, smoke_domain
from faithful.lib.domains.grid import REQUEST as GRID_REQUEST
from faithful.lib.ast import primitive as P, abstraction as L, application as A, index as I, invented, parse_program, show_program

@pytest.fixture(scope="module")
def kernel():
    with Kernel() as k: yield k

# ---- ast ---------------------------------------------------------------------------------

def test_program_text_roundtrip():
    text = "(lambda (map (lambda (+ $0 1)) (#(lambda (map (lambda (- 0 $0)) $0)) $0)))"
    p = parse_program(text)
    assert parse_program(show_program(p)) == p
    assert ast.leaves(p) == 6 and ast.leaves(p["abstraction"]["application"][1]["application"][0]["invented"]) == 5
    assert ast.arity(ast.arrows(ast.base("a"), ast.base("b"), ast.base("c"))) == 2
    assert ast.primitives_used(p) == {"map", "+", "1", "-", "0"}

# ---- evaluator -------------------------------------------------------------------------------

def test_python_interpreter_higher_order_and_errors():
    prims = {"map": curry(lambda f, xs: [f(x) for x in xs], 2), "+": curry(lambda a, b: a + b, 2), "1": 1, "boom": lambda x: 1 / 0}
    p = parse_program("(lambda (map (lambda (+ $0 1)) $0))")
    assert Interpreter(prims).evaluate(p, [[1, 2]]) == [2, 3]
    assert Interpreter(prims).evaluate(L(L(A(I(1), I(0)))), [lambda x: x * 2, 4]) == 8  # closure as argument
    with pytest.raises(EvaluationError, match="ZeroDivisionError"): Interpreter(prims).evaluate(P("boom"), [1])
    with pytest.raises(EvaluationError, match="No evaluator"): Interpreter(prims).evaluate(P("missing"), [])
    with pytest.raises(EvaluationError, match="Unbound"): Interpreter(prims).evaluate(L(I(3)), [1])
    with pytest.raises(EvaluationError, match="function"): Interpreter(prims).evaluate(P("map"), [])
    with pytest.raises(EvaluationError, match="budget"): Interpreter(prims, max_steps=3).evaluate(p, [[1, 2]])

def test_python_and_haskell_semantics_agree(kernel):
    d = ListDomain(names=("map", "+", "-", "0", "1"))
    p = parse_program("(lambda (map (lambda (- 0 (+ $0 1))) $0))")
    xs = [[], [1, -2, 3]]
    python = d.evaluate_batch(p, [[x] for x in xs])
    # the official_domain target has Haskell semantics for the same tutorial DSL
    if executable_path("official_domain"):
        with Kernel(target="official_domain") as k:
            assert k.evaluate_batch(p, [[x] for x in xs]) == python
    assert python == [[], [-2, 1, -4]]

# ---- kernel ------------------------------------------------------------------------------------

def test_kernel_discovery_and_protocol(kernel):
    assert executable_path("versionspace") == kernel.executable
    assert {"compress", "compression_objective", "vs_compress"} <= operations("versionspace")
    assert "vs_compress" not in operations("core") and kernel.supports("vs_compress")
    assert kernel.beta(A(L(I(0)), P("zero"))) == P("zero")
    with pytest.raises(KernelError, match="Unknown operation"): kernel.call("no_such_operation")
    with pytest.raises(KernelError): kernel.call("beta")  # malformed request is an error, not a result

def test_kernel_timeout_kills_and_restarts():
    d = GridDomain()
    k = Kernel(timeout=0.01)
    with pytest.raises(KernelProcessError, match="timed out"):
        k.call("enumerate_budget", grammar=d.grammar(), search_grammar=d.grammar(), request=d.request,
               upper_bound=100, maximum_depth=14, max_size=33, limit=100000, max_states=5_000_000)
    assert not k.alive and k.last_failure
    k.timeout = None
    assert k.beta(P("zero")) == P("zero") and k.alive   # transparent restart
    k.close(); assert not k.alive
    k2 = Kernel(restart=False); k2.kill(); k2.last_failure = "killed"
    with pytest.raises(KernelProcessError, match="restart disabled"): k2.beta(P("zero"))

def test_kernel_thread_safety(kernel):
    import threading
    out = []
    def work(n):
        for _ in range(20): out.append(kernel.beta(A(L(I(0)), P(f"p{n}")))["primitive"] == f"p{n}")
    threads = [threading.Thread(target=work, args=(n,)) for n in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(out) == 80 and all(out)

# ---- domain -------------------------------------------------------------------------------------

class Tiny(Domain):
    name, request, feature_dim = "tiny", ast.arrow(ast.base("int"), ast.base("int")), 2
    primitives = [Primitive("incr", ast.arrow(ast.base("int"), ast.base("int")), lambda n: n + 1),
                  Primitive("double", ast.arrow(ast.base("int"), ast.base("int")), lambda n: n * 2)]
    def features(self, task): return torch.tensor([float(len(task.examples)), float(task.outputs[0])])

def test_domain_contract(kernel):
    d = Tiny()
    g = d.grammar(); assert [p["program"]["primitive"] for p in g["productions"]] == ["incr", "double"]
    t = d.unary_task("add2", [(0, 2), (5, 7)])
    good, bad = L(A(P("incr"), A(P("incr"), I(0)))), L(A(P("double"), I(0)))
    assert d.log_likelihood(t, good, d.evaluate_batch(good, t.inputs)) == 0.
    assert d.log_likelihood(t, bad, d.evaluate_batch(bad, t.inputs)) == -math.inf
    assert d.solves(t, good) and not d.solves(t, bad)
    assert d.features(t).shape == (2,)
    dream = d.dream(good, d.request, [t], random.Random(0))
    assert dream is not None and dream.examples == [([0], 2), ([5], 7)] and dream.metadata["dream"]
    assert d.dream(P("incr"), d.request, [t], random.Random(0)) is not None  # η-short program still applies
    assert d.dream(L(P("incr")), d.request, [t], random.Random(0)) is None    # result is a function -> rejected
    assert kernel.infer(g, good) == d.request

class SoftTiny(Tiny):
    def log_likelihood(self, task, program, outputs):
        return sum(-5. for y, (_, e) in zip(outputs, task.examples) if y != e)

def test_custom_likelihood_changes_wake_selection(kernel):
    d = SoftTiny(); t = d.unary_task("add2", [(0, 2), (5, 7)])
    assert uses_kernel_io(d) is False and uses_kernel_io(GridDomain()) is True
    ec = ExploreCompress(d, kernel, NoCompression(), ECConfig(search=SearchConfig(limit=50, top_k=3), recognition=RecognitionConfig(enabled=False), dream=DreamConfig(enabled=False)))
    f, trace = ec.wake(t)
    assert trace.solutions == 50 and len(f["entries"]) == 3   # every candidate has finite likelihood
    assert f["entries"][0]["log_likelihood"] == 0.             # the exact solution still ranks first
    assert any(e["log_likelihood"] < 0 for e in f["entries"])

# ---- stitch ----------------------------------------------------------------------------------------

def test_stitch_encoding_roundtrip():
    atoms = stitch.Atoms()
    p = L(A(invented(L(A(P("flipH"), I(0)))), A(P("+"), I(0), P("$weird name"))))
    s = stitch.encode(p, atoms)
    assert s == "(lam (inv_0 (+ $0 prim_2)))"
    assert stitch.decode(s, atoms) == p
    assert stitch.decode("(lam (#0 $0))", atoms, 1) == L(L(A(I(1), I(0))))
    assert stitch.decode("(f #1 (lam (#0 $0)))", _atoms_with("f"), 2) == L(L(A(P("f"), I(0), L(A(I(2), I(0))))))

def _atoms_with(*names):
    a = stitch.Atoms()
    for n in names: a.symbol(P(n))
    return a

def grid_fixture(copies=8):
    p = L(A(P("flipH"), A(P("rotate90"), A(P("flipH"), I(0)))))
    return [ast.frontier(GRID_REQUEST, [ast.entry(copy.deepcopy(p), 0.)]) for _ in range(copies)]

def test_stitch_wrapper_exposes_backend(kernel):
    programs = [f["entries"][0]["program"] for f in grid_fixture()]
    r = stitch.compress(programs, 2, tasks=range(len(programs)), options=StitchOptions(max_arity=1, no_curried_metavars=True))
    assert r.abstractions and r.abstractions[0].arity == 0 and r.abstractions[0].utility > 0
    assert r.json["abstractions"][0]["name"] == "fn_0" and len(r.rewritten) == len(programs)
    for before, after in zip(programs, r.rewritten): assert kernel.beta(before) == kernel.beta(after)
    again = stitch.rewrite(programs, r.abstractions, options=StitchOptions())
    assert [kernel.beta(x) for x in again] == [kernel.beta(x) for x in programs]
    assert StitchOptions(max_arity=3, cost_var=0, extra={"follow": "x"}).kwargs() == {"max_arity": 3, "threads": 1, "silent": True, "cost_var": 0, "follow": "x"}
    assert stitch.backend_version() in (None, "0.1.29")

@pytest.mark.parametrize("compressor", [
    OriginalCompressor(arity=1, iterations=3),
    VersionSpaceCompressor(iterations=3, arity=1),
    StitchCompressor(iterations=3),
    StitchCompressor(iterations=3, rewrite="kernel"),
    StitchCompressor(iterations=3, rewrite="stitch"),
    StitchCompressor(iterations=3, gate="mdl", options=StitchOptions(max_arity=1, **LEAF_COST)),
    StitchCompressor(iterations=3, mode="batch"),
    StitchCompressor(iterations=3, strip_request_lambdas=False, options=StitchOptions(max_arity=1, **LEAF_COST), gate="mdl"),
])
def test_compressors_share_contract(kernel, compressor):
    d = GridDomain(); g = d.grammar()
    fs = grid_fixture() + [ast.frontier(GRID_REQUEST)]      # one unsolved frontier passes through
    before = ast.digest([fs, g])
    r = compressor.compress(kernel, g, fs)
    assert ast.digest([fs, g]) == before, "inputs mutated"
    assert r.inventions, compressor.name
    assert len(r.frontiers) == len(fs) and r.frontiers[-1] == fs[-1]
    assert r.statistics["backend"] == compressor.name
    xs = [[[0, 1, 2], [3, 0, 1]], [[1]], [[1, 0], [2, 3], [0, 1]]]
    for a, b in zip(fs[:-1], r.frontiers[:-1]):
        p, q = a["entries"][0]["program"], b["entries"][0]["program"]
        assert kernel.beta(p) == kernel.beta(q)
        assert kernel.evaluate_batch(p, [[x] for x in xs]) == kernel.evaluate_batch(q, [[x] for x in xs])
        kernel.score(r.grammar, GRID_REQUEST, q)              # rewritten programs are scorable (η-long, typed)
        assert ast.leaves(q) < ast.leaves(p)
    for p in r.inventions:
        assert kernel.infer(r.grammar, p["program"]) == p["type"]
    assert accounting(kernel, r.grammar, r.frontiers)["mdl"] < accounting(kernel, g, fs)["mdl"]
    assert all(h["after"] > h["before"] for h in r.history)

def test_stitch_rejects_ill_typed_and_records_attempts(kernel):
    d = ListDomain(); g = d.grammar()
    # three tasks with no shared structure beyond map: Stitch proposes nothing useful under η-long constraints
    ec = ExploreCompress(d, kernel, NoCompression(), ECConfig(search=SearchConfig(limit=300), recognition=RecognitionConfig(enabled=False), dream=DreamConfig(enabled=False)))
    train, _ = list_tasks(d); ec.run(train)
    r = StitchCompressor().compress(kernel, g, ec.history[-1].frontiers)
    assert r.statistics["attempts"] and "rejection" in r.statistics["attempts"][-1]
    assert r.statistics["options"]["no_curried_metavars"] is True

# ---- driver ------------------------------------------------------------------------------------------

def test_explore_compress_python_domain(kernel, tmp_path):
    d = ArithmeticDomain(); train, test = arithmetic_tasks(d)
    cfg = ECConfig(rounds=2, seed=3, output=tmp_path, search=SearchConfig(limit=200, max_states=20000),
                   dream=DreamConfig(draws=5), recognition=RecognitionConfig(steps=5))
    ec = ExploreCompress(d, kernel, StitchCompressor(), cfg)
    history = ec.run(train, rounds=1)
    kept = copy.deepcopy(ec.frontiers)
    history = ec.run(train, rounds=1)                       # continues: frontiers, grammar and model persist
    assert [h.solved for h in history] == [3, 3] and ec.model is not None and history[1].round == 1
    assert set(kept) == set(ec.frontiers) == {t.name for t in train} and all(ec.frontiers[n]["entries"] for n in kept)
    assert all(h.dream["draws"] == 5 and h.dream["accepted"] + h.dream["rejected"] == 5 for h in history)
    assert all(len(h.recognition_losses) == 5 for h in history)
    assert (tmp_path / "history.json").exists() and (tmp_path / "recognition_1.pt").exists()
    saved = json.loads((tmp_path / "config.json").read_text()); assert saved["domain"] == "arithmetic" and saved["compressor"] == "stitch"
    held = ec.solve(test)
    assert len(held) == 1 and held[0][0]["request"] == d.request
    # recognition search grammar carries per-context weights and the driver reloads checkpoints
    sg = ec.search_grammar(test[0]); assert "contexts" in sg and len(sg["contexts"]["root"]) == len(ec.grammar["productions"]) + 1
    fresh = ExploreCompress(d, kernel, NoCompression(), cfg); fresh.load_recognition(tmp_path / "recognition_1.pt")
    assert fresh.grammar == ec.grammar

def test_explore_compress_kernel_domain_matches_frozen_demo(kernel):
    """The frozen ``faithful.python.ec.demo`` configuration through the library."""
    d = smoke_domain(); assert uses_kernel_io(d)
    xs = [[[0, 1, 2], [2, 3, 0]], [[1, 0], [3, 2], [0, 3]]]
    tasks = [d.unary_task("color-complement", [(x, [[0 if c == 0 else 4 - c for c in row] for row in x]) for x in xs]),
             d.unary_task("horizontal-reflection", [(x, [list(reversed(row)) for row in x]) for x in xs])]
    cfg = ECConfig(rounds=1, seed=7, search=SearchConfig(upper_bound=4.5, maximum_depth=7, limit=1000, max_size=1000, max_states=60000),
                   recognition=RecognitionConfig(steps=5))
    ec = ExploreCompress(d, kernel, OriginalCompressor(arity=0), cfg)
    h = ec.run(tasks)
    assert h[0].solved == 2 and h[0].traces[0].first_solution is not None
    # generic wake (Python-side filtering through the kernel evaluator) agrees with the kernel's own I/O filter
    g = d.grammar()
    a, _ = kernel_io_wake(ec, tasks[1], g, g); b, _ = generic_wake(ec, tasks[1], g, g)
    assert [e["program"] for e in a["entries"]] == [e["program"] for e in b["entries"]]
