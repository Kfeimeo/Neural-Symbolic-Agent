"""Finish the current long-running experiment after its prerequisite workers.

This is a one-shot local process pipeline, not a scheduled/recurring task.
It fails if a prerequisite exits without the required completion records.
"""
import argparse
import subprocess
import sys
import time
import psutil
from .kernel import ROOT
from .controlled_run import OUT, REGIMES, SEEDS, verify
from .toy import save


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--training-pid', type=int, required=True)
    p.add_argument('--partial-pid', type=int, required=True)
    p.add_argument('--workers', type=int, default=8)
    args = p.parse_args()
    verify(OUT)
    def alive(pid, phase):
        try:
            command = psutil.Process(pid).cmdline()
            return 'faithful.python.controlled_run' in command and phase in command
        except (psutil.NoSuchProcess, psutil.AccessDenied): return False
    markers = [OUT/'runs'/r/str(s)/label/'complete.json' for r in REGIMES for s in SEEDS for label in ['B', 'C', 'D', 'E']]
    previous = -1
    while True:
        count = sum(path.exists() for path in markers)
        if count != previous: print(f'completed training conditions {count}/{len(markers)}', flush=True); previous = count
        if count == len(markers): break
        if not alive(args.training_pid, 'train'): raise RuntimeError('Training exited before all conditions completed')
        time.sleep(5)
    print('Waiting for the already-running partial evaluation to close', flush=True)
    while alive(args.partial_pid, 'available'): time.sleep(5)
    for module, extra in [('controlled_run', ['evaluate', '--workers', str(args.workers)]), ('controlled_audit', [])]:
        subprocess.run([sys.executable, '-u', '-m', 'faithful.python.'+module, *extra], cwd=ROOT, check=True)
    test = subprocess.run([sys.executable, '-m', 'pytest', 'faithful/tests', '-q'], cwd=ROOT, capture_output=True, text=True)
    save(OUT/'validation.json', {'command': 'python -m pytest faithful/tests -q', 'returncode': test.returncode, 'stdout': test.stdout, 'stderr': test.stderr})
    print(test.stdout, flush=True)
    if test.returncode: raise RuntimeError('Final regression suite failed; report not marked complete')
    for module in ['controlled_provenance', 'controlled_report']:
        subprocess.run([sys.executable, '-u', '-m', 'faithful.python.'+module], cwd=ROOT, check=True)
    print('Frozen experiment, reports, tests and checksums complete.', flush=True)


if __name__ == '__main__': main()
