"""Vertical alternative: low agreement left, high agreement right.

Blaming/defending are subsets of high-agreement minority, not new cohorts.
Reads frozen post summaries only; does not change main-paper references.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

ROOT=Path(__file__).resolve().parents[1]
COLORS={'Majority':'#5770DB','Minority':'#DB5F57','Blaming':'#FC8D61','Defending':'#66C2A5'}
INK='#37474F'
LAYOUT=[('low','Majority',0),('low','Minority',.8),
        ('high','Majority',2.25),('high','Minority',3.05),
        ('high','Blaming',4.15),('high','Defending',4.95)]
METRICS={'mean_score':('score_sum','score_n'),'mean_reply':('reply_sum','n'),'mean_depth':('depth_sum','n')}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--community',choices=['AITA','AITAH'],default='AITA')
    p.add_argument('--pdf-dir',type=Path,default=ROOT/'figures/alternatives')
    p.add_argument('--preview-dir',type=Path,default=ROOT/'output/fig2_agreement_direction_vertical')
    args=p.parse_args()
    community=args.community
    database={'AITA':'reddit','AITAH':'aitah'}[community]
    source=ROOT.parent/'minority-voices-aita/output/reception_full_min200_20261002/posts.jsonl'
    reference=json.loads((ROOT/'scripts/data/fig2_reception_post_equal.json').read_text())
    assert hashlib.sha256(source.read_bytes()).hexdigest()==reference['source_sha256']
    directional=json.loads((ROOT/'scripts/data/fig4_direction_post_equal.json').read_text())['communities'][community]['groups']
    values={(band,g,m):[] for band,g,_ in LAYOUT for m in METRICS}
    seen=set()
    with source.open() as f:
        for line in f:
            r=json.loads(line)
            if r['kind']!='post' or r['database']!=database: continue
            assert r['post_id'] not in seen
            seen.add(r['post_id'])
            assert r['stored_verdicts']>=200 and r['rho']!=.5
            for side,s in r['stats'].items():
                for m,(num,den) in METRICS.items():
                    if s[den]<=0: continue
                    values[(r['band'],side.title(),m)].append(s[num]/s[den])
                    if r['band']=='high' and side=='minority':
                        g='Blaming' if r['dominant']=='NA' else 'Defending'
                        values[('high',g,m)].append(s[num]/s[den])
    for (band,g,m),a in values.items():
        ref=directional[('NA' if g=='Blaming' else 'YA')+'|minority'] if g in ['Blaming','Defending'] else reference['communities'][community]['groups'][band+'|'+g.lower()]
        assert len(a)==ref['post_metric_counts'][m]
        assert np.isclose(np.mean(a),ref.get('metrics',ref)[m],rtol=1e-12)
    for m in METRICS:
        assert np.array_equal(np.sort(values[('high','Minority',m)]),np.sort(values[('high','Blaming',m)]+values[('high','Defending',m)]))
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'pdf.fonttype':42,
        'text.color':INK,'axes.labelcolor':INK,'axes.edgecolor':INK,'xtick.color':INK,'ytick.color':INK})
    fig,axes=plt.subplots(1,3,figsize=(8.2,3.65) if community=='AITA' else (8.2,8.2*298.0781/735.528654))
    specs=[('mean_score','Mean comment score',(-60,125),[-50,0,50,100]),
           ('mean_reply','Mean reply count',(-.1,2.5),[0,.5,1,1.5,2,2.5]),
           ('mean_depth','Mean reply depth',(-.15,3.5),[0,1,2,3])]
    if community=='AITAH':
        # Fit the displayed AITAH whiskers, with room for mean annotations.
        specs=[('mean_score','Mean comment score',(-16,55),[-10,0,20,40]),
               ('mean_reply','Mean reply count',(-.06,1.65),[0,.5,1,1.5]),
               ('mean_depth','Mean reply depth',(-.1,2.65),[0,1,2])]
    report={}
    for ax,(m,label,limits,ticks) in zip(axes,specs):
        ax.axvspan(4.15-.36,4.95+.36,color='#F0F2F4',zorder=0)
        if community=='AITAH':
            ax.axvline(1.525,color='#D4D9DD',lw=1,ls=(0,(3,3)),zorder=1)
        for j,(band,g,x) in enumerate(LAYOUT):
            a=np.asarray(values[(band,g,m)])
            q1,median,q3=np.quantile(a,[.25,.5,.75])
            within=a[(a>=q1-1.5*(q3-q1))&(a<=q3+1.5*(q3-q1))]
            assert limits[0]<=within.min() and within.max()<=limits[1]
            mean=float(a.mean())
            ax.boxplot([a],positions=[x],widths=.368,orientation='vertical',whis=1.5,
                showfliers=False,manage_ticks=False,patch_artist=True,
                boxprops=dict(facecolor=to_rgba(COLORS[g],.75),edgecolor='black',linewidth=1),
                whiskerprops=dict(color='black',linewidth=1),capprops=dict(color='black',linewidth=1),
                medianprops=dict(color='black',linewidth=1.3),zorder=2)
            ax.plot(x,mean,marker='D',ms=4.8,mfc='white',mec=INK,mew=.8,zorder=4)
            # Put mean labels above whiskers to keep every number clear of
            # box/median lines; the diamond still marks the mean's position.
            label_offset=17 if m=='mean_score' and g=='Blaming' else 5
            if community=='AITAH' and band=='low' and g=='Minority' and m!='mean_score':
                label_offset=17
            ax.annotate(f'{mean:.2f}',(x,float(within.max())),xytext=(0,label_offset),
                textcoords='offset points',ha='center',va='bottom',fontsize=9)
            report[band+'|'+g+'|'+m]=dict(n_posts=len(a),mean=mean,q1=q1,median=median,q3=q3,
                whisker_low=float(within.min()),whisker_high=float(within.max()))
        ax.set(xlim=(-.55,5.5),ylim=limits,yticks=ticks,xticks=[.4,3.6],
            xticklabels=['Low\nagreement','High\nagreement'])
        ax.set_ylabel(label,fontsize=10.5,labelpad=3)
        ax.tick_params(axis='x',length=0,pad=10,labelsize=10)
        ax.tick_params(axis='y',length=3,pad=2,labelsize=10)
        ax.spines[['top','right','bottom']].set_visible(False)
        ax.axhline(0,color=INK,lw=.7,zorder=1.8)
        ax.set_axisbelow(True)
        ax.grid(axis='y',color='#DCE2E7',linewidth=.55,alpha=.7)
    if community=='AITAH':
        # Match the custom legend hierarchy in the user-designed Figure 2.
        from matplotlib.patches import Rectangle
        for g,x,y in [('Majority',.16,.94),('Minority',.365,.94),
                      ('Blaming',.625,.972),('Defending',.625,.908)]:
            fig.add_artist(Rectangle((x-.035,y-.014),.026,.028,
                transform=fig.transFigure,facecolor=COLORS[g],edgecolor='none'))
            fig.text(x,y,'Minority (all)' if g=='Minority' else g,va='center',fontsize=11)
        fig.text(.565,.94,'{',fontsize=23,va='center',ha='center',color='black')
        fig.add_artist(Line2D([.835],[.94],transform=fig.transFigure,ls='',
            marker='D',mfc='white',mec=INK,ms=5))
        fig.text(.852,.94,'Mean',va='center',fontsize=11)
        fig.subplots_adjust(left=.075,right=.995,bottom=.1444,top=.8615,wspace=.30)
    else:
        handles=[Patch(facecolor=COLORS[g],label='Minority (all)' if g=='Minority' else g) for g in COLORS]
        handles.append(Line2D([],[],ls='',marker='D',mfc='white',mec=INK,ms=5,label='Mean'))
        fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.515,1),ncol=5,frameon=False,
            fontsize=11,handlelength=1.1,columnspacing=.9,handletextpad=.4)
        fig.subplots_adjust(left=.08,right=.994,bottom=.18,top=.82,wspace=.30)
    args.pdf_dir.mkdir(parents=True,exist_ok=True)
    args.preview_dir.mkdir(parents=True,exist_ok=True)
    stem=f'{community.lower()}_reception_agreement_direction_boxes_vertical'
    save_options=dict(bbox_inches='tight',pad_inches=.045) if community=='AITA' else {}
    fig.savefig(args.pdf_dir/f'{stem}.pdf',**save_options)
    fig.savefig(args.preview_dir/f'{stem}.png',dpi=220,**save_options)
    plt.close(fig)
    (args.preview_dir/f'{stem}_summary.json').write_text(json.dumps(dict(source=str(source),
        source_sha256=reference['source_sha256'],community=community,groups=report,
        method='Post-equal means. Boxes: IQR; whiskers: observed values within 1.5 IQR. Outliers hidden only. Means use all posts. Blaming/defending partition high-agreement minority.'),indent=2)+'\n')
    print('All six groups validated against frozen summaries. Saved vertical alternative.')

if __name__=='__main__': main()
