"""The unified ``Domain`` interface.

A domain delivers four things to the Explore–Compress driver:

1. **DSL** — primitives with types and execution semantics (:attr:`Domain.primitives`,
   :meth:`Domain.grammar`, :attr:`Domain.evaluator`).
2. **Likelihood** — :meth:`Domain.log_likelihood`; the default is deterministic
   I/O matching (``0`` when every example is reproduced, ``-inf`` otherwise).
3. **Task features** — :meth:`Domain.features` returning a fixed-size tensor of
   :attr:`Domain.feature_dim` for the recognition network.
4. **Dreams** — :meth:`Domain.dream` turning a program sampled from the current
   library into a training task (``None`` rejects the draw).

Execution semantics may live in Python (:class:`PythonEvaluator`, the default,
built from each primitive's ``implementation``) or in a Haskell executable
(:class:`KernelEvaluator`, used by the Grid domain and by anything built like
``domains/DomainMain.hs``). The driver passes the kernel explicitly; domains hold
no process handles.
"""
from __future__ import annotations
import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional, Sequence

from . import ast
from .evaluate import EvaluationError, Interpreter, curry

# ---- data ----------------------------------------------------------------------

@dataclass(frozen=True)
class Primitive:
    """A DSL symbol. ``implementation`` is a constant or an n-ary Python callable
    (``arity`` is read off the type and the callable is curried automatically); it
    may be ``None`` when the domain evaluates through a kernel executable."""
    name: str
    type: ast.Type
    implementation: Any = None
    log_weight: float = 0.
    curried: bool = False   # set when ``implementation`` already takes one argument at a time

    @property
    def arity(self) -> int:
        return ast.arity(self.type)

    def production(self) -> dict:
        return ast.production(ast.primitive(self.name), self.type, self.log_weight)

    def value(self) -> Any:
        """Runtime value for the Python interpreter."""
        if self.implementation is None:
            raise EvaluationError(f"Primitive {self.name!r} has no Python implementation")
        if self.curried or self.arity == 0 or not callable(self.implementation):
            return self.implementation
        return curry(self.implementation, self.arity)

@dataclass
class Task:
    """Only I/O examples: ``examples`` is a list of ``(inputs, output)`` where
    ``inputs`` is the argument list. There is deliberately no ground-truth field."""
    name: str
    examples: list[tuple[list, Any]]
    request: ast.Type
    metadata: dict = field(default_factory=dict)

    @property
    def inputs(self) -> list[list]:
        return [list(xs) for xs, _ in self.examples]

    @property
    def outputs(self) -> list[Any]:
        return [y for _, y in self.examples]

    def wire(self) -> dict:
        """Kernel ``search_tasks`` representation."""
        return {"name": self.name, "examples": [{"inputs": xs, "output": y} for xs, y in self.examples]}

# ---- execution ---------------------------------------------------------------------

class Evaluator(ABC):
    """Runs a program on several input sets; failures become ``None``."""
    @abstractmethod
    def evaluate_batch(self, program: ast.Program, input_sets: Sequence[Sequence[Any]], kernel=None) -> list[Any]: ...

    def evaluate(self, program: ast.Program, inputs: Sequence[Any], kernel=None) -> Any:
        value, = self.evaluate_batch(program, [inputs], kernel)
        if value is None: raise EvaluationError("Evaluation failed")
        return value

class PythonEvaluator(Evaluator):
    def __init__(self, primitives: Iterable[Primitive], max_steps: Optional[int] = 100_000):
        self.values = {p.name: p.value() for p in primitives if p.implementation is not None}
        self.max_steps = max_steps

    def evaluate_batch(self, program, input_sets, kernel=None):
        interpreter = Interpreter(self.values, self.max_steps)
        out = []
        for inputs in input_sets:
            try: out.append(interpreter.evaluate(program, inputs))
            except (EvaluationError, RecursionError): out.append(None)
        return out

class KernelEvaluator(Evaluator):
    """Delegates to the kernel's ``evaluate_batch`` (Haskell-side primitive semantics)."""
    def evaluate_batch(self, program, input_sets, kernel=None):
        if kernel is None: raise EvaluationError("KernelEvaluator needs a kernel")
        return kernel.call("evaluate_batch", program=program, input_sets=[list(xs) for xs in input_sets])["values"]

# ---- the interface ---------------------------------------------------------------------

class Domain(ABC):
    """Subclass and set :attr:`name`, :attr:`request`, :attr:`primitives`,
    :attr:`feature_dim`; implement :meth:`features`. Override the rest as needed."""
    name: str = "domain"
    request: ast.Type                        # default request type for tasks and dreams
    primitives: Sequence[Primitive] = ()
    log_variable: float = 0.
    feature_dim: int = 0
    evaluator: Optional[Evaluator] = None    # defaults to a PythonEvaluator over ``primitives``

    def __init__(self):
        if self.evaluator is None:
            self.evaluator = PythonEvaluator(self.primitives)

    # 1. DSL ---------------------------------------------------------------------------
    def grammar(self) -> ast.Grammar:
        """Initial library: one production per primitive, uniform unless weighted."""
        return ast.grammar((p.production() for p in self.primitives), self.log_variable)

    def evaluate_batch(self, program: ast.Program, input_sets: Sequence[Sequence[Any]], kernel=None) -> list[Any]:
        return self.evaluator.evaluate_batch(program, input_sets, kernel)

    def evaluate(self, program: ast.Program, inputs: Sequence[Any], kernel=None) -> Any:
        return self.evaluator.evaluate(program, inputs, kernel)

    # 2. likelihood ------------------------------------------------------------------------
    def outputs_equal(self, predicted: Any, expected: Any) -> bool:
        return predicted == expected

    def log_likelihood(self, task: Task, program: ast.Program, outputs: Sequence[Any]) -> float:
        """``outputs[i]`` is the program's value on ``task.examples[i]`` (``None`` on failure).
        Deterministic default: ``0.0`` if every example matches, else ``-inf``."""
        for predicted, (_, expected) in zip(outputs, task.examples):
            if predicted is None or not self.outputs_equal(predicted, expected): return -math.inf
        return 0.

    def score(self, task: Task, program: ast.Program, kernel=None) -> float:
        return self.log_likelihood(task, program, self.evaluate_batch(program, task.inputs, kernel))

    def solves(self, task: Task, program: ast.Program, kernel=None) -> bool:
        return self.score(task, program, kernel) > -math.inf

    # 3. features ----------------------------------------------------------------------------
    @abstractmethod
    def features(self, task: Task):
        """A ``torch.Tensor`` of shape ``(feature_dim,)``."""

    # 4. dreams -------------------------------------------------------------------------------
    def dream_inputs(self, request: ast.Type, tasks: Sequence[Task], rng: random.Random) -> list[list]:
        """Input sets for a dreamed task; default reuses a random training task's inputs."""
        candidates = [t for t in tasks if t.request == request] or list(tasks)
        if not candidates: raise ValueError("No tasks to draw dream inputs from")
        return rng.choice(candidates).inputs

    def dream(self, program: ast.Program, request: ast.Type, tasks: Sequence[Task], rng: random.Random,
              kernel=None, name: str = "dream") -> Optional[Task]:
        """Turn a sampled program into a task, or ``None`` to reject the draw."""
        inputs = self.dream_inputs(request, tasks, rng)
        outputs = self.evaluate_batch(program, inputs, kernel)
        if any(y is None for y in outputs): return None
        return Task(name, [(list(xs), y) for xs, y in zip(inputs, outputs)], request, {"dream": True})

    # helpers ------------------------------------------------------------------------------------
    def task(self, name: str, examples: Iterable[tuple[list, Any]], request: Optional[ast.Type] = None, **metadata) -> Task:
        return Task(name, [(list(xs), y) for xs, y in examples], request or self.request, dict(metadata))

    def unary_task(self, name: str, pairs: Iterable[tuple[Any, Any]], request: Optional[ast.Type] = None, **metadata) -> Task:
        return self.task(name, (([x], y) for x, y in pairs), request, **metadata)

class FunctionalDomain(Domain):
    """Assemble a domain from plain values/callables without subclassing."""
    def __init__(self, name: str, request: ast.Type, primitives: Sequence[Primitive], feature_dim: int,
                 features: Callable[[Task], Any], log_likelihood: Optional[Callable[[Task, ast.Program, Sequence[Any]], float]] = None,
                 dream: Optional[Callable[..., Optional[Task]]] = None, evaluator: Optional[Evaluator] = None,
                 log_variable: float = 0.):
        self.name, self.request, self.primitives, self.feature_dim = name, request, list(primitives), feature_dim
        self.log_variable, self.evaluator = log_variable, evaluator
        self._features, self._log_likelihood, self._dream = features, log_likelihood, dream
        super().__init__()
    def features(self, task): return self._features(task)
    def log_likelihood(self, task, program, outputs):
        return self._log_likelihood(task, program, outputs) if self._log_likelihood else super().log_likelihood(task, program, outputs)
    def dream(self, program, request, tasks, rng, kernel=None, name="dream"):
        return self._dream(program, request, tasks, rng, kernel, name) if self._dream else super().dream(program, request, tasks, rng, kernel, name)
