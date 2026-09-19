from dataclasses import dataclass
from typing import Any

from .language import Language, Program


@dataclass(frozen=True)
class Example:
    input: Any
    output: Any


@dataclass(frozen=True)
class Task:
    name: str
    examples: tuple[Example, ...]
    ground_truth: Program | None = None

    def accepts(self, language: Language, program: Program) -> bool:
        try:
            return all(language.evaluate(program, e.input) == e.output for e in self.examples)
        except (ValueError, IndexError, ZeroDivisionError):
            return False
