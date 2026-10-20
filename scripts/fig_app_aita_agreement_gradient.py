"""Appendix: AITA score/reply/depth over 0.05-wide final YA-share bins.

Each dot is a mean of within-post/side means (equal-post, not pooled).
Reuses the Figure 2 high/low cache, adding independently retrieved middle
posts. Exact ties excluded; absent minority cells remain missing, not zero.
PNG previews stay outside figures/. Source hashes and counts are exported.
"""
import argparse, collections, gzip, hashlib, json, math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np

METRICS={'mean_score':('score_sum','score_n','Mean comment score'),
         'mean_reply':('reply_sum','n','Mean direct-reply count'),
         'mean_depth':('depth_sum','n','Mean reply depth')}
COLORS={'majority':'#5770DB','minority':'#DB5F57'}
INK='#37474f'

def read(path):
    op=gzip.open if path.suffix=='.gz' else open
    with op(path,'rt') as f:return [json.loads(line) for line in f if line.strip()]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cache',type=Path)
    ap.add_argument('--additional',type=Path)
    ap.add_argument('--reference',type=Path)
    ap.add_argument('--summary',type=Path,help='Render the saved summary without archive access or recomputation.')
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--replicates',type=int,default=2000)
    args=ap.parse_args()
    if args.summary:
        args.output.mkdir(parents=True,exist_ok=True)
        draw(json.loads(args.summary.read_text()),args.output)
        return
    if not all([args.cache,args.additional,args.reference]):
        ap.error('Supply --summary or all of --cache, --additional, --reference.')
    records=read(args.cache); added=read(args.additional)
    assert any(r['kind']=='complete' and r['database']=='reddit' for r in records)
    assert any(r['kind']=='complete' for r in added)
    manifest=next(r for r in added if r['kind']=='manifest')
    posts=[r for r in records+added if r['kind']=='post' and r['database']=='reddit']
    assert len(posts)==manifest['full_non_tied_posts']
    assert len({p['post_id'] for p in posts})==len(posts)
    ref=json.loads(args.reference.read_text())['communities']['AITA']['groups']
    # Existing Figure 2 estimates must be reproduced unchanged.
    for key,g in ref.items():
        band,side=key.split('|')
        rows=[p['stats'][side] for p in posts if p['band']==band and side in p['stats']]
        for metric,(num,den,_) in METRICS.items():
            vals=[s[num]/s[den] for s in rows if s[den]>0]
            assert math.isclose(np.mean(vals),g[metric],rel_tol=1e-11),(key,metric)
    bins=collections.defaultdict(list)
    counts=collections.Counter()
    for p in posts:
        assert 0<=p['rho']<=1 and p['rho']!=.5 and p['stored_verdicts']>=200
        # Decimal representation avoids binary boundary artifacts at .15, .3, etc.
        from decimal import Decimal, ROUND_FLOOR
        b=min(19,int((Decimal(str(p['rho']))/Decimal('0.05')).to_integral_value(rounding=ROUND_FLOOR)))
        counts[b]+=1
        for side,s in p['stats'].items():
            for metric,(num,den,_) in METRICS.items():
                if s[den]>0:bins[(b,side,metric)].append(s[num]/s[den])
    rng=np.random.default_rng(20261008); cells=[]
    for b in range(20):
        for side in COLORS:
            for metric in METRICS:
                a=np.array(bins[(b,side,metric)])
                assert len(a)>0,(b,side,metric)
                boot=[]
                for start in range(0,args.replicates,100):
                    idx=rng.integers(len(a),size=(min(100,args.replicates-start),len(a)))
                    boot.extend(a[idx].mean(axis=1))
                lo,hi=np.quantile(boot,[.025,.975])
                cells.append(dict(bin=b,x=(b+.5)/20,side=side,metric=metric,n_posts=len(a),
                                  mean=float(a.mean()),ci_low=float(lo),ci_high=float(hi)))
    args.output.mkdir(parents=True,exist_ok=True)
    summary=dict(community='AITA',weighting='equal-post within each bin/side/metric',
        n_posts=len(posts),n_comments=sum(s['n'] for p in posts for s in p['stats'].values()),
        posts_per_bin=dict(counts),manifest=manifest,seed=20261008,bootstrap_replicates=args.replicates,
        binning='[left,right), last bin closed; width 0.05; exact ties excluded',
        sources=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (args.cache,args.additional)],
        note='Frozen high/low cache plus newly retrieved middle posts; nontransactional archive. Pointwise intervals, not a monotonicity or causal test.',cells=cells)
    (args.output/'gradient_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with gzip.open(args.output/'aita_gradient_post_statistics.jsonl.gz','wt') as f:
        for p in posts:f.write(json.dumps(p,separators=(',',':'))+'\n')
    draw(summary,args.output)
    print(json.dumps({k:summary[k] for k in ['n_posts','n_comments','posts_per_bin']},indent=2))
    for metric in METRICS:
        print(metric)
        for b in [0,8,9,10,11,19]:
            vals={c['side']:round(c['mean'],4) for c in cells if c['metric']==metric and c['bin']==b}
            print(b,vals)

def draw(summary,output):
    cells=summary['cells']
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'pdf.fonttype':42,
        'text.color':INK,'axes.labelcolor':INK,'axes.edgecolor':INK,
        'xtick.color':INK,'ytick.color':INK})
    fig,axes=plt.subplots(1,3,figsize=(7.4,2.65),sharex=True)
    for ax,(metric,(_,_,ylabel)) in zip(axes,METRICS.items()):
        for lo,hi in [(0,.2),(.8,1)]:ax.axvspan(lo,hi,color='#E9EDEF',zorder=0)
        ax.axvspan(.4,.6,color='#F4F5F6',zorder=0)
        ax.axvline(.5,color='#AEB8BF',lw=.7,zorder=1)
        for side,color in COLORS.items():
            c=[c for c in cells if c['metric']==metric and c['side']==side]
            x=[v['x'] for v in c];y=[v['mean'] for v in c]
            ax.fill_between(x,[v['ci_low'] for v in c],[v['ci_high'] for v in c],color=color,alpha=.14,lw=0)
            ax.plot(x,y,color=color,lw=1.6,marker='o',markersize=3.2,label=side.title())
        if metric=='mean_score':ax.axhline(0,color=INK,lw=.7)
        else:ax.set_ylim(bottom=0)
        ax.set_xlim(0,1);ax.set_xticks([0,.5,1],['0','0.5','1'])
        ax.set_ylabel(ylabel,labelpad=4,color=INK)
        ax.yaxis.set_major_locator(MaxNLocator(4))
        ax.tick_params(colors=INK,labelsize=10)
        ax.spines[['top','right']].set_visible(False)
        for k in ['left','bottom']:ax.spines[k].set_color(INK)
    fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',ncol=2,frameon=False,bbox_to_anchor=(.52,1.02))
    fig.supxlabel('Final YA share',y=.025,color=INK,fontsize=9)
    fig.subplots_adjust(left=.085,right=.99,bottom=.16,top=.90,wspace=.58)
    stem=output/'aita_reception_by_ya_share_post_equal'
    fig.savefig(stem.with_suffix('.pdf'),bbox_inches='tight',pad_inches=.025)
    fig.savefig(stem.with_suffix('.png'),dpi=200,bbox_inches='tight',pad_inches=.025)
    plt.close(fig)

if __name__=='__main__':main()
