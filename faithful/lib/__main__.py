"""``python -m faithful.lib build [target ...]`` / ``python -m faithful.lib info``."""
import argparse
import sys
from .kernel import TARGETS, DEFAULT_TARGET, build, executable_path, build_dir, operations

def main(argv=None):
    parser = argparse.ArgumentParser(prog="faithful.lib")
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="compile kernel executables with ghc")
    b.add_argument("targets", nargs="*", default=[DEFAULT_TARGET], choices=list(TARGETS) + ["all"])
    b.add_argument("-O", dest="optimisation", default="-O1")
    sub.add_parser("info", help="show targets, executables and served operations")
    args = parser.parse_args(argv)
    if args.command == "build":
        targets = list(TARGETS) if "all" in args.targets else args.targets
        for t in targets:
            print(f"[{t}] -> {build(t, optimisation=args.optimisation)}", flush=True)
    else:
        print(f"build directory: {build_dir()}")
        for key, t in TARGETS.items():
            exe = executable_path(key)
            print(f"{key:16} {t.name:22} {'built ' + str(exe) if exe else 'missing'}")
            print(f"{'':16} operations: {', '.join(sorted(operations(key)))}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
