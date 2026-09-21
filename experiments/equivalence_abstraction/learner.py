"""Execute the frozen Phase 2 function with only its compressor factory replaced.

An isolated globals dictionary avoids process-wide monkeypatching. The Wake,
recognition, RNG, budgets, checkpoint and resume code is literally the same code
object, not a copied/reimplemented loop.
"""
from types import FunctionType
from experiments.full_dreamcoder import learner as frozen
from .compressor import make_compressor

ARMS = ('B0', 'B1', 'B2', 'B3')
_globals = dict(frozen.run_condition.__globals__, METHODS=ARMS, make_compressor=make_compressor)
run_condition = FunctionType(frozen.run_condition.__code__, _globals,
                             'run_condition', frozen.run_condition.__defaults__, frozen.run_condition.__closure__)
