"""Primitive registry shared by ML, DSA and invented abstractions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Union

from .types import Arrow, Type


class EvalError(Exception):
    """Raised by primitive implementations on undefined inputs (e.g. argmin of
    an empty set).  The evaluator turns it into the ERR observation."""


@dataclass(frozen=True)
class Primitive:
    name: str
    signature: Union[Type, Arrow]   # Type for constants, Arrow for functions
    implementation: Callable[..., Any]
    layer: str = "ml"               # "ml" | "dsa" | "invented"
    description: str = ""

    @property
    def arguments(self) -> tuple:
        return self.signature.arguments if isinstance(self.signature, Arrow) else ()

    @property
    def result(self) -> Type:
        return self.signature.result if isinstance(self.signature, Arrow) else self.signature


def constant(name: str, typ: Type, value: Any, layer: str = "ml", description: str = "") -> Primitive:
    return Primitive(name, typ, lambda: value, layer, description)


def function(name: str, args: tuple, result: Type, impl: Callable[..., Any], layer: str = "ml",
             description: str = "") -> Primitive:
    return Primitive(name, Arrow(tuple(args), result), impl, layer, description)
