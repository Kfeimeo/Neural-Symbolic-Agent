"""Continue the authorized full study after the already-running subset finishes.

Uses ordinary local subprocesses, not scheduled automations. Records failures and
never marks the study complete while required cells are absent. Run from root.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import psutil

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent


def status(stage, **details):
    record = {'stage': stage, 'pid': os.getpid(), 'time': datetime.datetime.now().isoformat(), **details}
    temp = OUT/'execution_status.partial'
    temp.write_text(json.dumps(record, indent=2), encoding='utf8')
    os.replace(temp, OUT/'execution_status.json')
    print(json.dumps(record), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wait-pids', type=int, nargs='*', default=[])
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    processes = []
    for pid in args.wait_pids:
        try:
            processes.append(psutil.Process(pid))
        except psutil.NoSuchProcess:
            pass
    status('waiting_for_existing_subset', waiting_pids=[p.pid for p in processes])
    while any(p.is_running() for p in processes):
        time.sleep(15)
    needed = [OUT/'runs/seed_101/medium'/f'{arm}_t1'/'complete.json' for arm in ('B0', 'B1', 'B2', 'B3')]
    if not all(p.exists() for p in needed):
        raise RuntimeError('Subset process ended without all four training completion records')
    commands = [
        [sys.executable, '-m', 'experiments.equivalence_abstraction.run', 'all', '--workers', str(args.workers)],
        [sys.executable, '-m', 'results.equivalence_abstraction.replay_metrics'],
        [sys.executable, '-m', 'results.equivalence_abstraction.build_report'],
    ]
    for command in commands:
        status('running', command=command, log='full_study.log')
        with (OUT/'full_study.log').open('a', encoding='utf8') as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    report = json.loads((OUT/'analysis.json').read_text())
    if not report['complete']:
        raise RuntimeError(f"Required records still missing: {len(report['missing'])}")
    status('complete', report='PHASE3_REPORT.md')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        status('failed', error=f'{type(exc).__name__}: {exc}')
        raise
