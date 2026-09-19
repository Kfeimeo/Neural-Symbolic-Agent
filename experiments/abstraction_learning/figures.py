"""Static figures for PHASE1_REPORT.md, drawn from the aggregated result files only.

Colours follow a fixed categorical assignment per arm (never cycled); wake-budget
and perfect-Wake variants reuse their base arm's hue with a different line style
or hatch.  One axis per panel; regimes are small multiples.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from benchmarks.latent_abstraction import generator as bench

ROOT = bench.ROOT
RESULTS = ROOT / 'results'
FIGURES = RESULTS / 'abstraction_learning' / 'figures'
REGIMES = bench.REGIMES
SURFACE, INK, INK2, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#e6e5e1'
COLOR = {'A': '#2a78d6', 'B': '#eb6834', 'C': '#1baf7a', 'D': '#eda100', 'E': '#e87ba4', 'O': '#008300', 'O_uniform': '#4a3aa7', 'A0': '#8a8983'}
STYLE = {'': '-', '_wake10000': '--', '_wake30000': ':'}
from .evaluation import BUDGETS
MAX = str(max(BUDGETS))


def base_arm(arm):
    arm = arm.replace('PW_', '')
    return arm.split('_wake')[0]


def color(arm):
    return COLOR[base_arm(arm)]


def style(arm):
    return STYLE['_wake' + arm.split('_wake')[1]] if '_wake' in arm else ('--' if arm.startswith('PW_') else '-')


def read(name):
    return json.loads((RESULTS / name).read_text(encoding='utf8'))


def setup(nrows, ncols, width=12, height=3.2):
    fig, axes = plt.subplots(nrows, ncols, figsize=(width, height * nrows), squeeze=False, facecolor=SURFACE)
    for ax in axes.flat:
        ax.set_facecolor(SURFACE)
        ax.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ['top', 'right']:
            ax.spines[side].set_visible(False)
        for side in ['left', 'bottom']:
            ax.spines[side].set_color(INK2)
        ax.tick_params(colors=INK2, labelsize=8)
    return fig, axes


def value(m):
    return None if m is None or m.get('mean') is None else m['mean']


def error(m):
    return 0. if m is None or m.get('std') is None else m['std']


def recall_by_iteration(recovery):
    curves = recovery['recall_by_iteration']
    regimes = [r for r in REGIMES if curves.get(r)]
    fig, axes = setup(1, len(regimes), width=4 * len(regimes))
    for ax, regime in zip(axes.flat, regimes):
        for arm in ['B', 'C', 'D', 'E', 'B_wake10000', 'B_wake30000', 'D_wake10000', 'D_wake30000']:
            pts = curves[regime].get(arm)
            if not pts:
                continue
            xs = [p['iteration'] for p in pts]
            ys = [value(p['behavioral_recall']) for p in pts]
            es = [error(p['behavioral_recall']) for p in pts]
            ax.errorbar(xs, ys, yerr=es, color=color(arm), linestyle=style(arm), linewidth=1.8, marker='o', markersize=4, capsize=2, label=arm)
        ax.set_title(f'reuse = {regime}', color=INK, fontsize=10)
        ax.set_xlabel('EC iteration', color=INK2, fontsize=9)
        ax.set_ylim(-0.02, 1.02)
    axes[0, 0].set_ylabel('behavioural recall of active latents', color=INK2, fontsize=9)
    axes[0, -1].legend(fontsize=7, frameon=False)
    fig.suptitle('Experiment 3: abstraction recovery by EC iteration (mean ± SD over instances)', color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / 'recall_by_iteration.png', dpi=150)
    plt.close(fig)


def solve_rate_by_depth(solve):
    cells = {(c['regime'], c['arm'], c['iteration']): c for c in solve['cells']}
    rounds = solve['rounds']
    fig, axes = setup(1, 4, width=16)
    for ax, regime in zip(axes.flat, REGIMES):
        for arm in ['A0', 'A', 'B', 'C', 'D', 'E', 'O', 'O_uniform']:
            it = 0 if arm in ('A0', 'O_uniform') else rounds
            c = cells.get((regime, arm, it))
            if not c:
                continue
            depths = sorted(c['by_depth'], key=int)
            ys = [value(c['by_depth'][d].get(MAX)) for d in depths]
            ax.plot([int(d) for d in depths], ys, color=color(arm), linestyle=style(arm), linewidth=1.8, marker='o', markersize=4, label=arm)
        ax.set_title(f'reuse = {regime}', color=INK, fontsize=10)
        ax.set_xlabel('operator-tree depth d', color=INK2, fontsize=9)
        ax.set_ylim(-0.02, 1.02)
    axes[0, 0].set_ylabel(f'held-out solve rate at {MAX} candidates', color=INK2, fontsize=9)
    axes[0, -1].legend(fontsize=7, frameon=False)
    fig.suptitle('Experiment 2: solve rate by complexity (final iteration)', color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / 'solve_rate_by_depth.png', dpi=150)
    plt.close(fig)


def solve_curves(solve):
    cells = {(c['regime'], c['arm'], c['iteration']): c for c in solve['cells']}
    rounds = solve['rounds']
    fig, axes = setup(1, 4, width=16)
    for ax, regime in zip(axes.flat, REGIMES):
        for arm in ['A0', 'A', 'B', 'C', 'D', 'E', 'O', 'O_uniform']:
            it = 0 if arm in ('A0', 'O_uniform') else rounds
            c = cells.get((regime, arm, it))
            if not c:
                continue
            xs = [n for n in BUDGETS if value(c['solve_rate'][str(n)]) is not None]
            ys = [value(c['solve_rate'][str(n)]) for n in xs]
            es = [error(c['solve_rate'][str(n)]) for n in xs]
            ax.errorbar(xs, ys, yerr=es, color=color(arm), linestyle=style(arm), linewidth=1.8, marker='o', markersize=4, capsize=2, label=arm)
        ax.set_xscale('log')
        ax.set_title(f'reuse = {regime}', color=INK, fontsize=10)
        ax.set_xlabel('candidate budget', color=INK2, fontsize=9)
        ax.set_ylim(-0.02, 1.02)
    axes[0, 0].set_ylabel('held-out solve rate', color=INK2, fontsize=9)
    axes[0, -1].legend(fontsize=7, frameon=False)
    fig.suptitle('Experiments 1 and 5: solve curves at the final iteration (mean ± SD over instances)', color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / 'solve_curves.png', dpi=150)
    plt.close(fig)


def compression_vs_generalization(compression):
    markers = {'B': 'o', 'C': 's', 'D': '^', 'E': 'D'}
    fig, axes = setup(2, 4, width=16, height=3.4)
    for j, regime in enumerate(REGIMES):
        for i, (key, label) in enumerate([('cumulative_delta_mdl', 'cumulative ΔMDL (training corpus)'), ('mean_delta_L', 'mean ΔL of held-out programs')]):
            ax = axes[i, j]
            for c in compression['cells']:
                arm = c['arm']
                if c['regime'] != regime or base_arm(arm) not in markers or arm.startswith('PW_') or c['iteration'] == 0:
                    continue
                x, y = value(c[key]), value(c['solve_rate_10000'])
                if x is None or y is None:
                    continue
                ax.scatter([x], [y], color=COLOR['A'], marker=markers[base_arm(arm)], s=28, alpha=0.8, edgecolors=SURFACE, linewidths=0.8,
                           label=base_arm(arm) if c['iteration'] == 1 and '_wake' not in arm else None)
            ax.set_xlabel(label, color=INK2, fontsize=8)
            if j == 0:
                ax.set_ylabel('solve rate at 10000', color=INK2, fontsize=9)
            if i == 0:
                ax.set_title(f'reuse = {regime}', color=INK, fontsize=10)
            r = compression['correlations'].get(regime, {})
            k = 'cumulative_delta_mdl_vs_solve_rate' if key == 'cumulative_delta_mdl' else 'mean_delta_L_vs_solve_rate'
            rho = r.get(k, {}).get('spearman')
            ax.text(0.02, 0.95, f'Spearman ρ = {rho:.2f}' if rho is not None else 'ρ n/a', transform=ax.transAxes, fontsize=8, color=INK2, va='top')
    handles, labels = axes[0, 0].get_legend_handles_labels()
    if handles:
        axes[0, -1].legend(handles, labels, fontsize=7, frameon=False, title='arm (marker)', title_fontsize=7)
    fig.suptitle('Experiment 4: compression versus generalisation (one point per arm x instance x iteration)', color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / 'compression_vs_generalization.png', dpi=150)
    plt.close(fig)


def oracle_gap(solve):
    cells = {(c['regime'], c['arm'], c['iteration']): c for c in solve['cells']}
    rounds = solve['rounds']
    arms = ['A0', 'A', 'B', 'C', 'D', 'E', 'PW_B', 'PW_C', 'PW_D', 'PW_E', 'O', 'O_uniform']
    fig, axes = setup(1, 4, width=16, height=3.6)
    for ax, regime in zip(axes.flat, REGIMES):
        ys, labels = [], []
        for k, arm in enumerate(arms):
            it = 0 if arm in ('A0', 'O_uniform') else 1 if arm.startswith('PW_') else rounds
            c = cells.get((regime, arm, it))
            if not c:
                continue
            m = c['solve_rate'][MAX]
            ax.errorbar([value(m)], [len(labels)], xerr=[error(m)], color=color(arm), fmt='o' if not arm.startswith('PW_') else 'D', markersize=6, capsize=2)
            labels.append(arm)
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=8, color=INK)
        ax.invert_yaxis()
        ax.set_xlim(-0.02, 1.02)
        ax.set_title(f'reuse = {regime}', color=INK, fontsize=10)
        ax.set_xlabel(f'held-out solve rate at {MAX}', color=INK2, fontsize=9)
    fig.suptitle('Experiment 5: oracle gap (final iteration; diamonds = perfect-Wake diagnostic)', color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / 'oracle_gap.png', dpi=150)
    plt.close(fig)


def training_solved(compression):
    cells = {(c['regime'], c['arm'], c['iteration']): c for c in compression['cells']}
    rounds = max(c['iteration'] for c in compression['cells'])
    fig, axes = setup(1, 4, width=16)
    for ax, regime in zip(axes.flat, REGIMES):
        for arm in ['A', 'B', 'C', 'D', 'E', 'O']:
            pts = [cells.get((regime, arm, it)) for it in range(1, rounds + 1)]
            if all(p is None for p in pts):
                continue
            xs = [it for it, p in zip(range(1, rounds + 1), pts) if p]
            ys = [value(p['training_solved']) for p in pts if p]
            ax.plot(xs, ys, color=color(arm), linestyle=style(arm), linewidth=1.8, marker='o', markersize=4, label=arm)
        ax.set_title(f'reuse = {regime}', color=INK, fontsize=10)
        ax.set_xlabel('EC iteration', color=INK2, fontsize=9)
        ax.set_ylim(0, 56)
    axes[0, 0].set_ylabel('training tasks solved (of 56)', color=INK2, fontsize=9)
    axes[0, -1].legend(fontsize=7, frameon=False)
    fig.suptitle('Training-set bootstrapping by EC iteration', color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / 'training_solved.png', dpi=150)
    plt.close(fig)


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    solve, recovery, compression = read('solve_curves.json'), read('abstraction_recovery.json'), read('compression_results.json')
    recall_by_iteration(recovery)
    solve_rate_by_depth(solve)
    solve_curves(solve)
    compression_vs_generalization(compression)
    oracle_gap(solve)
    training_solved(compression)
    print(f'figures written to {FIGURES}')


if __name__ == '__main__':
    main()
