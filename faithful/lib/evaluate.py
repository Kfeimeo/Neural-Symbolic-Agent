"""Python execution semantics for protocol v1 programs.

The Haskell kernel only evaluates its built-in Grid/test primitives. A domain
written in Python supplies ``{name: implementation}`` and this interpreter runs
the untyped λ-calculus over it: de Bruijn indices, application, abstraction and
``invented`` bodies, exactly as ``haskell/Evaluation.hs`` does for Haskell values.

Implementations are either constants or callables. Callables are called one
argument at a time (curried); :func:`curry` adapts an n-ary Python function.
Functions passed *into* primitives (``map`` etc.) are plain one-argument
callables, so a primitive like ``map`` is simply ``curry(lambda f, xs: [f(x) for x in xs], 2)``.
"""
from __future__ import annotations
from typing import Any, Callable, Mapping, Optional, Sequence

class EvaluationError(Exception):
    """Raised for unbound variables, missing primitives, non-function application,
    domain errors raised by primitives, or an exceeded step budget."""

def curry(function: Callable, arity: int) -> Any:
    """Turn an n-ary Python function into the curried form the evaluator expects."""
    if arity <= 0: return function()
    if arity == 1: return function
    def take(*collected):
        if len(collected) == arity: return function(*collected)
        return lambda x: take(*collected, x)
    return take

class _Closure:
    __slots__ = ("body", "env", "interpreter")
    def __init__(self, body, env, interpreter):
        self.body, self.env, self.interpreter = body, env, interpreter
    def __call__(self, x):
        return self.interpreter.run(self.body, [x, *self.env])
    def __repr__(self): return "<closure>"

class Interpreter:
    """Evaluate programs over ``primitives``; ``max_steps`` bounds reductions per call."""
    def __init__(self, primitives: Mapping[str, Any], max_steps: Optional[int] = 100_000):
        self.primitives = dict(primitives)
        self.max_steps = max_steps
        self._steps = 0

    def run(self, program: dict, env: Sequence[Any] = ()) -> Any:
        self._steps += 1
        if self.max_steps is not None and self._steps > self.max_steps:
            raise EvaluationError("Evaluation step budget exceeded")
        if "application" in program:
            f, x = program["application"]
            vf = self.run(f, env); vx = self.run(x, env)
            if not callable(vf): raise EvaluationError("Applying a non-function")
            try:
                return vf(vx)
            except EvaluationError: raise
            except Exception as e:  # domain error inside a primitive
                raise EvaluationError(f"{type(e).__name__}: {e}") from e
        if "abstraction" in program: return _Closure(program["abstraction"], list(env), self)
        if "index" in program:
            i = program["index"]
            if 0 <= i < len(env): return env[i]
            raise EvaluationError("Unbound variable")
        if "invented" in program: return self.run(program["invented"], [])
        if "primitive" in program:
            name = program["primitive"]
            if name not in self.primitives: raise EvaluationError(f"No evaluator for {name}")
            return self.primitives[name]
        raise EvaluationError(f"Malformed program node: {list(program)}")

    def evaluate(self, program: dict, inputs: Sequence[Any]) -> Any:
        """Apply ``program`` to ``inputs`` in order; the result must be data, not a function."""
        self._steps = 0
        value = self.run(program, [])
        for x in inputs:
            if not callable(value): raise EvaluationError("Applying a non-function")
            try: value = value(x)
            except EvaluationError: raise
            except Exception as e: raise EvaluationError(f"{type(e).__name__}: {e}") from e
        if callable(value): raise EvaluationError("Result is a function")
        return value

def evaluate(program: dict, primitives: Mapping[str, Any], inputs: Sequence[Any], max_steps: Optional[int] = 100_000) -> Any:
    return Interpreter(primitives, max_steps).evaluate(program, inputs)
