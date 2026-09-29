from __future__ import annotations

from dataclasses import dataclass, field

from ..ml.ast import Term


@dataclass(frozen=True)
class Solution:
    program: Term
    cost: int                 # search cost (weighted) at which it was found
    description_length: int   # uniform L(p | library)
    order: int                # evaluated-program index at which it was found
    expanded_states: int      # expanded states at the moment it was found


@dataclass
class Frontier:
    capacity: int
    solutions: list[Solution] = field(default_factory=list)

    def add(self, s: Solution) -> bool:
        if any(x.program == s.program for x in self.solutions):
            return False
        self.solutions.append(s)
        return True

    @property
    def full(self) -> bool:
        return len(self.solutions) >= self.capacity

    @property
    def best(self) -> Solution | None:
        return min(self.solutions, key=lambda s: (s.description_length, s.order)) if self.solutions else None

    def programs(self) -> list[Term]:
        return [s.program for s in self.solutions]
