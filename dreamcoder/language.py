from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Type:
    name: str


@dataclass(frozen=True)
class FunctionType:
    arguments: tuple[Type, ...]
    result: Type


@dataclass(frozen=True)
class Program:
    name: str
    arguments: tuple[Program, ...] = ()

    def __str__(self) -> str:
        return self.name if not self.arguments else f"{self.name}({', '.join(map(str, self.arguments))})"

    def symbols(self) -> list[str]:
        return ([] if self.name == "$input" else [self.name]) + [
            s for child in self.arguments for s in child.symbols()]

    @property
    def size(self) -> int:
        return 1 + sum(child.size for child in self.arguments)


INPUT = Program("$input")


@dataclass(frozen=True)
class Primitive:
    name: str
    signature: FunctionType
    implementation: Callable[..., Any]
    definition: Program | None = None


@dataclass
class Language:
    input_type: Type
    output_type: Type
    primitives: dict[str, Primitive]

    def infer(self, program: Program) -> Type:
        if program.name == "$input":
            if program.arguments:
                raise TypeError("Input cannot have arguments")
            return self.input_type
        primitive = self.primitives[program.name]
        actual = tuple(self.infer(child) for child in program.arguments)
        if actual != primitive.signature.arguments:
            raise TypeError(f"{program}: expected {primitive.signature.arguments}, got {actual}")
        return primitive.signature.result

    def evaluate(self, program: Program, value: Any) -> Any:
        self.infer(program)
        return self._evaluate(program, value)

    def _evaluate(self, program: Program, value: Any) -> Any:
        if program.name == "$input":
            return value
        return self.primitives[program.name].implementation(
            *(self._evaluate(child, value) for child in program.arguments))

    def expand(self, program: Program) -> Program:
        if program.name == "$input":
            return program
        children = tuple(self.expand(c) for c in program.arguments)
        definition = self.primitives[program.name].definition
        if definition is None:
            return Program(program.name, children)
        def substitute(p: Program) -> Program:
            return children[0] if p.name == "$input" else Program(p.name, tuple(substitute(c) for c in p.arguments))
        return self.expand(substitute(definition))
