"""Static figures for PHASE2_REPORT.md, drawn from results/full_dreamcoder/*.json only.

Same conventions as the Phase 1 figures: fixed categorical colours per arm (never
cycled), one axis per panel, regimes as small multiples.  Full-DC reuses B's hue
family with a distinct colour so that the recognition contrast is visible.
"""
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from benchmarks.latent_abstraction import generator as bench
from experiments.abstraction_learning.evaluation import BUDGETS
from experiments.abstraction_learning.figures import setup, INK, INK2, SURFACE
from .run import RESULTS, ROUNDS, ARM

FIGURES = RESULTS / 'figures'
REGIMES = bench.REGIMES
COLOR = {'A0': '#8a8983', 'A': '#2a78d6', 'B': '#eb6834', ARM: '#8e1b8b', f'{ARM}_rec': '#c23b9e', f'{ARM}_shuffle': '#d9a3cf', f'{ARM}_pool': '#5c0f5a',
         f'{ARM}_t2': '#b06bb0', f'{ARM}_t3': '#c98fc8', 'B_wake10000': '#f2a27e', 'O': '#008300', 'O_uniform': '#4a3aa7', 'PWS_B': '#a0522d', 'PW_D': '#c9a100'}
STYLE = {f'{ARM}_rec': '--', f'{ARM}_shuffle': ':', 'B_wake10000': '--', 'PWS_B': '-.', f'{ARM}_t2': ':', f'{ARM}_t3': ':'}
MAX = str(max(BUDGETS))


def read(name):
    return json.loads((RESULTS / name).read_text(encoding='utf8'))


def value(m):
    return None if m is None or m.get('mean') is None else m['mean']


def error(m):
    return 0. if m is None or m.get('std') is None else m['std']


def cells_index(cells):
    return {(c['regime'], c['label'], c['iteration']): c for c in cells['cells']}


def final(label):
    if label in ('A0', 'O_uniform'):
        return 0
    if label.startswith('PW'):
        return 1
    return ROUNDS


def trajectory(cell, key, labels, title, filename, ylabel, regimes=REGIMES, reference=None):
    regimes = [r for r in regimes if any((r, l, ROUNDS) in cell for l in labels)]
    fig, axes = setup(1, len(regimes), width=4 * len(regimes))
    for ax, regime in zip(axes.flat, regimes):
        for l in labels:
            pts = [cell.get((regime, l, it)) for it in range(1, ROUNDS + 1)]
            if all(p is None for p in pts):
                continue
            xs = [it for it, p in zip(range(1, ROUNDS + 1), pts) if p and value(p['metrics'].get(key)) is not None]
            ys = [value(p['metrics'][key]) for p in pts if p and value(p['metrics'].get(key)) is not None]
            es = [error(p['metrics'][key]) for p in pts if p and value(p['metrics'].get(key)) is not None]
            ax.errorbar(xs, ys, yerr=es, color=COLOR.get(l, INK2), linestyle=STYLE.get(l, '-'), linewidth=1.8, marker='o', markersize=4, capsize=2, label=l)
        if reference:
            for l, style in reference:
                c = cell.get((regime, l, final(l)))
                if c and value(c['metrics'].get(key)) is not None:
                    ax.axhline(value(c['metrics'][key]), color=COLOR.get(l, INK2), linestyle=style, linewidth=1.2, label=l)
        ax.set_title(f'reuse = {regime}', color=INK, fontsize=10)
        ax.set_xlabel('EC iteration', color=INK2, fontsize=9)
        ax.set_ylabel(ylabel, color=INK2, fontsize=9)
        ax.set_xticks(range(1, ROUNDS + 1))
    axes.flat[0].legend(fontsize=7, frameon=False)
    fig.suptitle(title, color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / filename, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def exposure_figure(cell, gaps):
    regimes = [r for r in REGIMES if r != 'zero']
    fig, axes = setup(1, len(regimes), width=4 * len(regimes))
    perfect = gaps['perfect_er2']
    for ax, regime in zip(axes.flat, regimes):
        for l in ['B', ARM, f'{ARM}_pool']:
            for key, style in [('er2', '-'), ('er1', '--')]:
                pts = [cell.get((regime, l, it)) for it in range(1, ROUNDS + 1)]
                if all(p is None for p in pts):
                    continue
                xs = [it for it, p in zip(range(1, ROUNDS + 1), pts) if p]
                ys = [value(p['metrics'][key]) for p in pts if p]
                ax.plot(xs, ys, color=COLOR[l], linestyle=style, linewidth=1.8, marker='o' if key == 'er2' else 's', markersize=4, label=f'{l} {key.upper().replace("ER", "ER@")}')
        if perfect.get(regime) is not None:
            ax.axhline(perfect[regime], color=INK, linestyle=':', linewidth=1.2, label='perfect Wake ER@2')
        c = cell.get((regime, 'PWS_B', 1))
        if c and value(c['metrics'].get('er2')) is not None:
            ax.axhline(value(c['metrics']['er2']), color=COLOR['PWS_B'], linestyle='-.', linewidth=1.2, label='PWS_B ER@2')
        ax.set_ylim(-0.02, 1.02)
        ax.set_title(f'reuse = {regime}', color=INK, fontsize=10)
        ax.set_xlabel('EC iteration', color=INK2, fontsize=9)
        ax.set_ylabel('exposure recall', color=INK2, fontsize=9)
        ax.set_xticks(range(1, ROUNDS + 1))
    axes.flat[0].legend(fontsize=7, frameon=False)
    fig.suptitle('Latent exposure in Wake frontiers: ER@1 (dashed) and ER@2 (solid), recognition OFF (B) versus ON (FullDC)', color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / 'exposure_by_iteration.png', dpi=150, facecolor=SURFACE)
    plt.close(fig)


def solve_curves(cell):
    fig, axes = setup(1, len(REGIMES), width=4 * len(REGIMES))
    for ax, regime in zip(axes.flat, REGIMES):
        for l in ['A0', 'B', ARM, f'{ARM}_rec', f'{ARM}_shuffle', 'PWS_B', 'O']:
            c = cell.get((regime, l, final(l)))
            if not c:
                continue
            ys = [value(c['curve'][str(n)]) for n in BUDGETS]
            es = [error(c['curve'][str(n)]) for n in BUDGETS]
            ax.errorbar(BUDGETS, ys, yerr=es, color=COLOR.get(l, INK2), linestyle=STYLE.get(l, '-'), linewidth=1.8, marker='o', markersize=4, capsize=2, label=l)
        ax.set_xscale('log')
        ax.set_ylim(-0.02, 0.7)
        ax.set_title(f'reuse = {regime}', color=INK, fontsize=10)
        ax.set_xlabel('candidate budget B (log)', color=INK2, fontsize=9)
        ax.set_ylabel('S(B) = P(r_t <= B)', color=INK2, fontsize=9)
    axes.flat[0].legend(fontsize=7, frameon=False)
    fig.suptitle('Held-out solve curves (final libraries; unsolved tasks have r > 10000)', color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / 'heldout_solve_curves.png', dpi=150, facecolor=SURFACE)
    plt.close(fig)


def rank_ecdf(cells):
    """Fine-grained S(B): empirical CDF of held-out first-solution ranks pooled over instances."""
    fig, axes = setup(1, len(REGIMES), width=4 * len(REGIMES))
    per = {}
    for c in cells['cells']:
        if c['iteration'] != final(c['label']):
            continue
        per[(c['regime'], c['label'])] = c
    for ax, regime in zip(axes.flat, REGIMES):
        for l in ['B', ARM, f'{ARM}_rec', 'O']:
            c = per.get((regime, l))
            if not c or 'ranks' not in c:
                continue
            ranks = sorted(c['ranks'])
            n = c['rank_task_count']
            xs, ys = [1], [0]
            for i, r in enumerate(ranks, 1):
                xs += [r, r]
                ys += [ys[-1], i / n]
            xs.append(max(BUDGETS))
            ys.append(ys[-1])
            ax.plot(xs, ys, color=COLOR.get(l, INK2), linestyle=STYLE.get(l, '-'), linewidth=1.6, label=l)
        ax.set_xscale('log')
        ax.set_xlim(1, max(BUDGETS))
        ax.set_ylim(-0.02, 0.7)
        ax.set_title(f'reuse = {regime}', color=INK, fontsize=10)
        ax.set_xlabel('first-solution rank r (log)', color=INK2, fontsize=9)
        ax.set_ylabel('fraction of held-out tasks solved', color=INK2, fontsize=9)
    axes.flat[0].legend(fontsize=7, frameon=False)
    fig.suptitle('Empirical S(B) from first-solution ranks (pooled over instances)', color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / 'rank_ecdf.png', dpi=150, facecolor=SURFACE)
    plt.close(fig)


def chain_figure(chain):
    rows = [r for r in chain['cohorts'] if r['regime'] != 'zero' and r['d_er2'] is not None]
    pairs = [('d_training_solve', 'd_er2', 'Δ training solve rate', 'Δ ER@2'), ('d_er2', 'd_recall', 'Δ ER@2', 'Δ behavioural recall'),
             ('d_recall', 'd_solve_library', 'Δ behavioural recall', 'Δ held-out solve (library)'), ('d_recall', 'd_solve_recognition', 'Δ behavioural recall', 'Δ held-out solve (recognition)')]
    fig, axes = setup(1, len(pairs), width=4 * len(pairs))
    marker = {'low': 'v', 'medium': 'o', 'high': '^'}
    for ax, (x, y, xl, yl) in zip(axes.flat, pairs):
        for r in rows:
            if r[x] is None or r[y] is None:
                continue
            ax.scatter(r[x], r[y], color=COLOR[ARM], marker=marker[r['regime']], s=45, edgecolor=INK, linewidth=0.5, label=r['regime'])
        ax.axhline(0, color=INK2, linewidth=0.8)
        ax.axvline(0, color=INK2, linewidth=0.8)
        ax.set_xlabel(xl, color=INK2, fontsize=9)
        ax.set_ylabel(yl, color=INK2, fontsize=9)
        stat = chain['correlations_over_reuse_cohorts'].get(f'{x}_vs_{y}')
        if stat and stat['spearman'] is not None:
            ax.set_title(f"Spearman ρ = {stat['spearman']:.2f} (n = {stat['n']})", color=INK, fontsize=9)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    seen = {}
    for h, l in zip(handles, labels):
        seen.setdefault(l, h)
    axes.flat[0].legend(seen.values(), seen.keys(), fontsize=7, frameon=False)
    fig.suptitle('Causal chain per cohort: FullDC minus B (instance x reuse cohorts)', color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / 'chain.png', dpi=150, facecolor=SURFACE)
    plt.close(fig)


def recovery_by_support_figure(per_latent):
    rows = [r for r in per_latent['recovery_by_support'] if r['label'] in ('B', ARM, 'B_wake10000', 'PWS_B')]
    regimes = [r for r in REGIMES if any(x['regime'] == r for x in rows)]
    fig, axes = setup(1, len(regimes), width=4 * len(regimes))
    for ax, regime in zip(axes.flat, regimes):
        labels = [l for l in ('B', ARM, 'B_wake10000', 'PWS_B') if any(x['regime'] == regime and x['label'] == l for x in rows)]
        width = 0.35
        for i, l in enumerate(labels):
            r = next(x for x in rows if x['regime'] == regime and x['label'] == l)
            for j, (key, nkey, hatch) in enumerate([('p_recovered_ge2', 'n_ge2', ''), ('p_recovered_lt2', 'n_lt2', '//')]):
                v = r[key] or 0.
                ax.bar(i + (j - 0.5) * width, v, width, color=COLOR.get(l, INK2), hatch=hatch, edgecolor=INK, linewidth=0.5)
                ax.text(i + (j - 0.5) * width, v + 0.02, f"{r['recovered_ge2' if j == 0 else 'recovered_lt2']}/{r[nkey]}", ha='center', fontsize=7, color=INK)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=8)
        ax.set_ylim(0, 1.15)
        ax.set_ylabel('P(recovered)', color=INK2, fontsize=9)
        ax.set_title(f'reuse = {regime}  (solid: support >= 2, hatched: support < 2)', color=INK, fontsize=9)
    fig.suptitle('Behavioural recovery conditional on frontier support (latents pooled over instances)', color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURES / 'recovery_by_support.png', dpi=150, facecolor=SURFACE)
    plt.close(fig)


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    cells = read('cells.json')
    cell = cells_index(cells)
    gaps = read('gap_closure.json')
    chain = read('chain.json')
    per_latent = read('per_latent.json')
    trajectory(cell, 'training_solve_rate', ['B', ARM, f'{ARM}_pool', 'B_wake10000', 'O'], 'Training solve rate by EC iteration (solved persistent frontiers / 56)',
               'training_solve_by_iteration.png', 'training solve rate', reference=[('O', ':')])
    exposure_figure(cell, gaps)
    trajectory(cell, 'recall', ['B', ARM, f'{ARM}_pool', 'B_wake10000'], 'Behavioural abstraction recall by EC iteration', 'recall_by_iteration.png', 'behavioural recall',
               regimes=[r for r in REGIMES if r != 'zero'], reference=[('PWS_B', '-.'), ('PW_D', ':')])
    trajectory(cell, f'solve_{MAX}', ['B', ARM, f'{ARM}_rec', f'{ARM}_pool', 'B_wake10000', 'A'], 'Held-out solve rate at 10000 candidates by EC iteration',
               'heldout_by_iteration.png', 'solve rate @10000', reference=[('O', ':'), ('PWS_B', '-.')])
    solve_curves(cell)
    rank_ecdf(cells)
    chain_figure(chain)
    recovery_by_support_figure(per_latent)
    print(f'figures written to {FIGURES}')


if __name__ == '__main__':
    main()
