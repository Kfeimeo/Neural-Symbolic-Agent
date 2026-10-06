"""Faithful DreamCoder as a library.

Typical use::

    from faithful.lib import Domain, Primitive, Kernel, ExploreCompress, ECConfig, StitchCompressor, ast

    class MyDomain(Domain):
        name, request, feature_dim = "mine", ast.arrow(ast.base("int"), ast.base("int")), 8
        primitives = [Primitive("incr", ast.arrow(ast.base("int"), ast.base("int")), lambda n: n + 1)]
        def features(self, task): ...

    domain = MyDomain()
    with Kernel() as kernel:
        ec = ExploreCompress(domain, kernel, StitchCompressor(), ECConfig(rounds=3))
        history = ec.run([domain.unary_task("add2", [(0, 2), (3, 5)])])

The symbolic core stays in Haskell (``Kernel``); execution semantics, likelihood,
features and dreams come from the ``Domain``; compression is pluggable.
"""
from . import ast
from .ast import (base, arrow, arrows, variable, primitive, index, application, abstraction, abstractions, invented,
                  show_program, parse_program, show_type, grammar, frontier, entry, production)
from .kernel import (Kernel, KernelOptions, KernelError, KernelProcessError, KernelBuildError, KernelTarget,
                     TARGETS, DEFAULT_TARGET, build, ensure_executable, executable_path, register_target, operations)
from .evaluate import Interpreter, EvaluationError, curry, evaluate
from .domain import Domain, FunctionalDomain, Primitive, Task, Evaluator, PythonEvaluator, KernelEvaluator
from .compression import (Compressor, CompressionResult, OriginalCompressor, VersionSpaceCompressor, StitchCompressor,
                          NoCompression, make_compressor, accounting)
from .stitch import StitchOptions, LEAF_COST
from .ec import ExploreCompress, ECConfig, SearchConfig, DreamConfig, RecognitionConfig, RoundRecord, WakeTrace, explore_compress

__all__ = [n for n in dir() if not n.startswith("_")]
