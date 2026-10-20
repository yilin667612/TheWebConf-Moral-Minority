"""Figure 7 trial: three hourly post-equal mean curves in two panels.

Uses the verified 24-hour summary unchanged. Low agreement combines both
judgment sides within each post. No median, percentile band, smoothing,
or uncertainty interval is shown. Archive-wide reception is grouped by
comment arrival, not a within-comment trajectory or equal follow-up.
"""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

ROOT = Path(__file__).resolve().parents[1]
INK = '#37474F'
GROUPS = [('majority', 'High agreement · Majority', '#5770DB', 'o'),
          ('minority', 'High agreement · Minority', '#DB5F57', 's'),
          ('low', 'Low agreement', '#8D99A8', '^')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', type=Path, default=ROOT/'scripts/data/fig3_arrival_post_equal.json')
    parser.add_argument('--output', type=Path, default=ROOT/'output/fig7_arrival_overlay')
    args = parser.parse_args()
    data = json.loads(args.summary.read_text())
    assert data['weighting'].startswith('equal-post')
    community = data['communities']['AITA']
    assert community['manifest']['arrival_hours'] == [0, 24]
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
        'pdf.fonttype': 42, 'text.color': INK, 'axes.labelcolor': INK,
        'axes.edgecolor': INK, 'xtick.color': INK, 'ytick.color': INK})
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 3.45))
    specs = [('score', 'Mean comment score', 1, (-60, 1600), [-10, -1, 0, 1, 10, 100, 1000]),
             ('reply', 'Mean reply count', .01, (0, 4), [0, .01, .1, 1])]
    for ax, (metric, label, threshold, limits, ticks) in zip(axes, specs):
        for side, name, color, marker in GROUPS:
            points = community['series'][side]
            assert [p['hour'] for p in points] == list(range(24))
            means = [p[metric]['mean'] for p in points]
            assert all(limits[0] <= y <= limits[1] for y in means), 'Clipped mean'
            ax.plot([p['hour']+.5 for p in points], means, color=color,
                    marker=marker, markersize=3.1, linewidth=1.8, label=name,
                    zorder=3 if side != 'low' else 2)
        ax.set_yscale('symlog', linthresh=threshold, linscale=1)
        ax.set_ylim(limits)
        ax.yaxis.set_major_locator(FixedLocator(ticks))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:g}'))
        ax.yaxis.set_minor_locator(NullLocator())
        ax.set_xlim(0, 24)
        ax.set_xticks([0, 6, 12, 18, 24])
        ax.set_ylabel(label, fontsize=10.5, labelpad=3)
        ax.tick_params(labelsize=10, length=3, pad=3)
        ax.spines[['top', 'right']].set_visible(False)
        ax.axhline(0, color=INK, linewidth=.65)
        ax.grid(axis='y', color='#DCE2E7', linewidth=.55, alpha=.7)
        ax.set_axisbelow(True)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(.52, 1),
               ncol=3, frameon=False, fontsize=10, handlelength=1.5,
               columnspacing=1.1, handletextpad=.4)
    fig.supxlabel('Comment arrival time since post (hours)', fontsize=10.5, y=.015)
    fig.subplots_adjust(left=.085, right=.99, bottom=.17, top=.86, wspace=.28)
    args.output.mkdir(parents=True, exist_ok=True)
    stem = args.output/'aita_arrival_reception_overlay'
    fig.savefig(stem.with_suffix('.pdf'), bbox_inches='tight', pad_inches=.04)
    fig.savefig(stem.with_suffix('.png'), dpi=220, bbox_inches='tight', pad_inches=.04)
    plt.close(fig)
    stem.with_suffix('.json').write_text(json.dumps(dict(
        summary=str(args.summary), summary_sha256=hashlib.sha256(args.summary.read_bytes()).hexdigest(),
        source_sha256=data['source_sha256'], community='AITA',
        method=__doc__, series=community['series']), indent=2)+'\n')
    print(stem.with_suffix('.pdf'))


if __name__ == '__main__':
    main()
