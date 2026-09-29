"""Convenience: baseline + TSL (+ ablations) + comparison in one command.

    python -m arc_tsl.experiments.run_all --tasks 10 --out results/arc_tsl/smoke --workers 4
"""
from __future__ import annotations

import sys

from . import compare, run_baseline, run_tsl


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    run_baseline.main(argv)
    run_tsl.main(argv)
    out = "results/arc_tsl/latest"
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]
    compare.main(["--out", out])


if __name__ == "__main__":
    main()
