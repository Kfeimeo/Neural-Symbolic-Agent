"""Term evaluation by compilation to Python closures.

``ERR`` is the observation of an undefined computation.  Function values are
``Closure`` objects.
"""
from __future__ import annotations

from typing import Any, Callable

from ..ml.ast import Abs, App, Hole, Prim, Term, Var
from ..ml.primitives import EvalError
from .grammar import Library


class _Err:
    __slots__ = ()

    def __repr__(self):
        return "ERR"

    def __bool__(self):
        return False


ERR = _Err()

_CAUGHT = (EvalError, ValueError, IndexError, ZeroDivisionError, KeyError, TypeError, ArithmeticError,
           RecursionError)


class Closure:
    __slots__ = ("fn", "term", "env")

    def __init__(self, fn: Callable[[Any], Any], term: Term, env: tuple):
        self.fn, self.term, self.env = fn, term, env

    def __call__(self, x):
        return self.fn(x)

    def __repr__(self):
        return f"<closure {self.term}>"


def compile_term(t: Term, library: Library) -> Callable[[tuple], Any]:
    if isinstance(t, Var):
        i = t.index
        return lambda env: env[i]
    if isinstance(t, Prim):
        if t.name in library.abstractions:
            return compile_term(library.abstractions[t.name].body, library)
        value = library.primitives[t.name].implementation()
        return lambda env: value
    if isinstance(t, App):
        fns = [compile_term(a, library) for a in t.args]
        if t.name in library.abstractions:
            body_fn = compile_term(library.abstractions[t.name].body, library)
            def run_invented(env, fns=fns, body_fn=body_fn):
                args = [f(env) for f in fns]
                args.reverse()  # parameter 0 is the outermost lambda => highest index
                return body_fn(tuple(args))
            return run_invented
        impl = library.primitives[t.name].implementation
        def run(env, fns=fns, impl=impl):
            return impl(*[f(env) for f in fns])
        return run
    if isinstance(t, Abs):
        body_fn = compile_term(t.body, library)
        body = t
        def make(env, body_fn=body_fn, body=body):
            return Closure(lambda x: body_fn((x,) + env), body, env)
        return make
    if isinstance(t, Hole):
        raise ValueError("cannot evaluate a pattern with holes")
    raise TypeError(t)


def evaluate(t: Term, library: Library, env: tuple = ()) -> Any:
    """Evaluate; returns ERR on any undefined computation."""
    try:
        return compile_term(t, library)(env)
    except _CAUGHT:
        return ERR


def safe_call(fn: Callable, *args):
    try:
        return fn(*args)
    except _CAUGHT:
        return ERR
