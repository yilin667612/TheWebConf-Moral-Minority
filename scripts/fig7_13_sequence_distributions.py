"""Candidate replacements for Figures 7 (AITA) and 13 (AITAH).

Uses complete post-level exports from fig7_sequence_reception.py. First-day
judgment comments define ten equal-count stages BEFORE alignment is split.
Default: fixed posts within each group/metric, with valid means at all stages.
Ribbons are percentiles of post means, not uncertainty intervals. Outcomes
remain last recorded scores and archive-wide direct-reply counts.
Does not modify the manuscript or overwrite arrival-hour figures.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator, PercentFormatter

ROOT = Path(__file__).resolve().parents[1]
GROUPS = [('majority', 'High agreement\nMajority', '#5770DB'),
          ('minority', 'High agreement\nMinority', '#DB5F57'),
          ('low', 'Low agreement\nAll judgments', '#8D99A8')]

def build(source, output, selection):
    records = [json.loads(line) for line in source.read_text().splitlines()]
    manifest = records[0]
    assert manifest['kind'] == 'manifest' and records[-1]['kind'] == 'complete'
    posts = records[1:-1]
    assert len(posts) == manifest['posts'] == records[-1]['posts']
    assert len({p['post_id'] for p in posts}) == len(posts)
    assert all(p['kind'] == 'post' for p in posts)
    assert manifest['stages'] == 10 and manifest['first_day_hours'] == 24
    summaries = {}
    for group, _, _ in GROUPS:
        summaries[group] = {}
        for metric, numerator, denominator in [('score', 'score_sum', 'score_n'),
                                                ('reply', 'reply_sum', 'n')]:
            rows = []
            for post in posts:
                cells = [post['cells'].get(f'{group}|{i}', {}) for i in range(10)]
                values = [c[numerator]/c[denominator] if c.get(denominator, 0) else np.nan for c in cells]
                valid = np.isfinite(values)
                if valid.all() if selection == 'fixed' else valid.any():
                    rows.append(values)
            matrix = np.asarray(rows)
            assert matrix.ndim == 2 and matrix.shape[1] == 10
            n = np.isfinite(matrix).sum(axis=0)
            assert (n > 0).all()
            percentiles = np.nanpercentile(matrix, [10,25,50,75,90], axis=0)
            summaries[group][metric] = dict(n_posts=n.tolist(), mean=np.nanmean(matrix, axis=0).tolist(),
                **dict(zip(['p10','p25','median','p75','p90'], percentiles.tolist())))
    ink = '#37474F'
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':10,
        'pdf.fonttype':42, 'text.color':ink, 'axes.labelcolor':ink,
        'axes.edgecolor':ink, 'xtick.color':ink, 'ytick.color':ink})
    fig, axes = plt.subplots(2,3,figsize=(9.4,4.1),sharex=True,sharey='row')
    xs = (np.arange(10)+.5)/10
    for col,(group,title,color) in enumerate(GROUPS):
        axes[0,col].set_title(title,fontsize=10.5,pad=7)
        for row,metric in enumerate(['score','reply']):
            ax = axes[row,col]
            d = summaries[group][metric]
            ax.fill_between(xs,d['p10'],d['p90'],color=color,alpha=.12,lw=0)
            ax.fill_between(xs,d['p25'],d['p75'],color=color,alpha=.28,lw=0)
            ax.plot(xs,d['mean'],color=color,lw=1.8,marker='o',ms=3.2)
            ax.plot(xs,d['median'],color=color,lw=1.3,ls='--')
            ax.set_yscale('symlog',linthresh=1 if metric=='score' else .01)
            ax.yaxis.set_major_locator(FixedLocator([-100,-10,-1,0,1,10,100,1000]
                                                    if metric=='score' else [0,.01,.1,1,10]))
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v,_:f'{v:g}'))
            ax.yaxis.set_minor_locator(NullLocator())
            ax.set_xlim(0,1)
            ax.set_xticks([0,.25,.5,.75,1])
            ax.xaxis.set_major_formatter(PercentFormatter(1,decimals=0))
            ax.axhline(0,color=ink,lw=.7)
            ax.grid(color='#DCE2E7',lw=.55,alpha=.7)
            ax.set_axisbelow(True)
            ax.spines[['top','right']].set_visible(False)
            ax.tick_params(labelsize=9.5,length=3,pad=2)
    # Fit each row to the plotted means and percentile bands, not individual outliers.
    for row,metric in enumerate(['score','reply']):
        bounds = [v for g,_,_ in GROUPS for k in ['p10','p90','mean'] for v in summaries[g][metric][k]]
        lo,hi = min(0,min(bounds)),max(bounds)
        axes[row,0].set_ylim(lo*1.25 if lo<0 else -.0015, max(hi*1.3,1))
    axes[0,0].set_ylabel('Mean comment score',fontsize=9.5,labelpad=3)
    axes[1,0].set_ylabel('Mean reply count',fontsize=9.5,labelpad=3)
    fig.legend(handles=[Line2D([],[],color=ink,marker='o',lw=1.8,ms=4,label='Mean'),
        Line2D([],[],color=ink,ls='--',lw=1.3,label='Median'),
        Patch(facecolor=ink,alpha=.28,label='25–75%'),
        Patch(facecolor=ink,alpha=.12,label='10–90%')],loc='upper center',
        bbox_to_anchor=(.53,1.01),ncol=4,frameon=False,fontsize=10.5)
    fig.supxlabel('Comment-sequence position (first 24 h)',fontsize=10.5,y=.015)
    fig.subplots_adjust(left=.09,right=.99,bottom=.13,top=.79,wspace=.13,hspace=.15)
    output.mkdir(parents=True,exist_ok=True)
    stem = output/f"{manifest['community'].lower()}_sequence_reception_distributions_{selection}"
    fig.savefig(stem.with_suffix('.pdf'),bbox_inches='tight',pad_inches=.04)
    fig.savefig(stem.with_suffix('.png'),dpi=200,bbox_inches='tight',pad_inches=.04)
    plt.close(fig)
    result = dict(manifest=manifest,selection=selection,summary=summaries,
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),method=__doc__)
    stem.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    print(stem.with_suffix('.pdf'))
    print({g:{m:d['n_posts'] for m,d in stats.items()} for g,stats in summaries.items()})

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'output/fig7_13_sequence')
    parser.add_argument('--selection',choices=['fixed','available'],default='fixed')
    args = parser.parse_args()
    build(args.source,args.output,args.selection)
