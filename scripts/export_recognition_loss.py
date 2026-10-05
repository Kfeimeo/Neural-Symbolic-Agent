"""Export per-step recognition loss curves from Phase 2/3 training records.

Usage:
  python scripts/export_recognition_loss.py RES/results_equivalence_abstraction_2
  python scripts/export_recognition_loss.py results/equivalence_abstraction --output analysis/loss_curves
"""
import argparse
import csv
import gzip
import json
import os
import tempfile
from pathlib import Path

import matplotlib
os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'phase3-matplotlib-cache'))
Path(os.environ['MPLCONFIGDIR']).mkdir(parents=True, exist_ok=True)
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def read_json(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return json.load(f)


def smooth(values, window):
    if window <= 1 or len(values) < 2:
        return np.asarray(values, dtype=float)
    window = min(window, len(values))
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(np.asarray(values, dtype=float), kernel, mode='same')


def plot_curve(losses, path, title, window):
    x = np.arange(1, len(losses) + 1)
    fig, ax = plt.subplots(figsize=(9, 4.8), constrained_layout=True)
    ax.plot(x, losses, color='#8aa0b8', linewidth=.7, alpha=.5, label='per-step loss')
    if window > 1 and len(losses) >= window:
        ax.plot(x, smooth(losses, window), color='#c7473a', linewidth=1.8,
                label=f'{window}-step moving average')
    ax.set(title=title, xlabel='Optimizer step', ylabel='Bias-optimal loss')
    ax.grid(True, alpha=.22)
    ax.legend(frameon=False)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('results', type=Path, help='Phase 2 or Phase 3 result directory')
    ap.add_argument('--output', type=Path, help='Export root (default: <results>/loss_curves)')
    ap.add_argument('--smooth', type=int, default=25, help='Moving-average window; 0 disables smoothing')
    args = ap.parse_args()
    if args.smooth < 0:
        ap.error('--smooth must be >= 0')
    source = args.results.resolve()
    target = (args.output or source / 'loss_curves').resolve()
    if source == target or source in target.parents:
        pass  # The default output is intentionally inside results; scans are restricted to runs/.
    run_files = sorted((source / 'runs').glob('seed_*/*/*_t*/round_*.json.gz'))
    if not run_files:
        # Phase 2's FullDC paths use arm directories without the _tN suffix.
        run_files = sorted((source / 'runs').glob('seed_*/*/*/round_*.json.gz'))
    if not run_files:
        raise SystemExit(f'No round_*.json.gz files found under {source / "runs"}')

    grouped = {}
    for path in run_files:
        record = read_json(path)
        losses = record.get('recognition', {}).get('losses', [])
        if not losses:
            continue
        rel = path.parent.relative_to(source / 'runs')
        run_key = str(rel)
        out_dir = target / rel
        out_dir.mkdir(parents=True, exist_ok=True)
        iteration = record.get('iteration')
        if iteration is None:
            iteration = int(path.name.removesuffix('.json.gz').split('_')[-1])
        plot_curve(losses, out_dir / f'round_{iteration}.png',
                   f'{run_key} — recognition training, round {iteration}', args.smooth)
        grouped.setdefault(run_key, []).append((iteration, path, record, losses, out_dir))

    for run_key, rounds in sorted(grouped.items()):
        rounds.sort(key=lambda row: row[0])
        out_dir = rounds[0][4]
        fig, axes = plt.subplots(3, 2, figsize=(13, 10), constrained_layout=True, sharex=False)
        for ax, (iteration, _, record, losses, _) in zip(axes.flat, rounds):
            x = np.arange(1, len(losses) + 1)
            ax.plot(x, losses, color='#8aa0b8', linewidth=.55, alpha=.45)
            if args.smooth > 1 and len(losses) >= args.smooth:
                ax.plot(x, smooth(losses, args.smooth), color='#c7473a', linewidth=1.5)
            ax.set_title(f'Round {iteration} · {len(losses)} steps')
            ax.set_xlabel('Optimizer step')
            ax.set_ylabel('Loss')
            ax.grid(True, alpha=.2)
        for ax in axes.flat[len(rounds):]:
            ax.set_visible(False)
        fig.suptitle(f'{run_key} — recognition loss')
        fig.savefig(out_dir / 'all_rounds.png', dpi=150)
        plt.close(fig)

        with (out_dir / 'losses.csv').open('w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['round', 'step', 'loss'])
            for iteration, _, _, losses, _ in rounds:
                writer.writerows((iteration, i, value) for i, value in enumerate(losses, 1))
        summary = []
        for iteration, path, record, losses, _ in rounds:
            summary.append({'round': iteration, 'steps': len(losses), 'loss_first': losses[0],
                            'loss_last': losses[-1], 'loss_mean': float(np.mean(losses)),
                            'loss_first_50_mean': float(np.mean(losses[:50])),
                            'loss_last_50_mean': float(np.mean(losses[-50:])),
                            'record': str(path.relative_to(source))})
        (out_dir / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')

    print(f'Exported {sum(len(v) for v in grouped.values())} round curves across {len(grouped)} runs to {target}')


if __name__ == '__main__':
    main()
