"""Figure 8: all-agreement fixed-post certainty profiles and post-FE trends.

prepare: read immutable annotation/metadata inputs, including middle agreement;
Retain posts with scored comments of the given group in every first-day decile.
Majority is pooled across post judgment directions; blaming/defending are minority groups.
plot: use the same cached post-stage means for profiles and FE coefficients.
PDF only in figures/. Optional PNG preview must be outside figures/.
"""
import argparse,hashlib,io,json,os,subprocess,tempfile
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT.parent/'minority-voices-aita/output/certainty_analysis_2026-09-22/full_period_18h/manifest.json'
KEYS=['subreddit','post_id']
GROUPS=['subreddit','direction']
SIDES={'NTA':'NA','NAH':'NA','YTA':'YA','ESH':'YA'}
SEED=20261007

def digest(p):
    with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def holm(p):
    p=np.asarray(p); order=np.argsort(p);out=np.empty(len(p))
    out[order]=np.minimum(1,np.maximum.accumulate(p[order]*np.arange(len(p),0,-1)))
    return out

def prepare(a):
    m=json.loads(a.source_manifest.read_text())
    for key in ['source','metadata']:assert digest(m[key])==m[key+'_sha256'],key
    d=pd.read_csv(m['source'],usecols=['com_id','post_id','subreddit','label','Certainty','created_utc'])
    assert not d.duplicated(['subreddit','com_id']).any()
    meta=pd.read_json(m['metadata']).rename(columns={'community':'subreddit','YA_share':'rho','created_utc':'post_time'})
    d=d.merge(meta,on=KEYS,how='left',validate='many_to_one')
    assert d.rho.notna().all() and d.YANA_total.ge(200).all()
    d['band']=np.select([(d.rho<=.2)|(d.rho>=.8),d.rho.between(.4,.6)],['high','low'],default='middle')
    if a.band=='high':d=d[d.band.eq('high')].copy()
    d['direction']=np.where(d.rho<.5,'Blame',np.where(d.rho>.5,'Defend','Tie'))
    frame=d[KEYS+['band','direction','rho','YANA_total']].drop_duplicates()
    assert not frame.duplicated(KEYS).any()
    source_rows=len(d)
    ct=pd.to_datetime(d.created_utc,format='mixed',utc=True)
    elapsed=(ct-pd.to_datetime(d.post_time,format='mixed',utc=True)).dt.total_seconds()
    assert elapsed.notna().all() and elapsed.ge(0).all()
    d['comment_time']=ct
    d=d[d.direction.ne('Tie') & d.label.isin(SIDES) & elapsed.lt(86400)].copy()
    d=d.sort_values(KEYS+['comment_time','com_id'])
    g=d.groupby(KEYS,sort=False)
    d['stage']=(10*g.cumcount()//g.com_id.transform('size')).astype(int)
    is_minority=((d.direction=='Blame') & d.label.isin(['YTA','ESH']))|((d.direction=='Defend') & d.label.isin(['NTA','NAH']))
    d.loc[~is_minority,'direction']='Majority'
    scored=d[d.Certainty.isin([1,2,3,4])]
    v=scored.groupby(GROUPS+['post_id','band','stage']).agg(certainty=('Certainty','mean'),n_comments=('com_id','size')).reset_index()
    assert int(v.n_comments.sum())==len(scored)
    cohort_keys=GROUPS+['post_id']
    complete=v.groupby(cohort_keys).stage.nunique().eq(10)
    keep=complete[complete].reset_index()[cohort_keys]
    v=v.merge(keep,on=cohort_keys,validate='many_to_one')
    assert not v.duplicated(cohort_keys+['stage']).any()
    assert v.groupby(cohort_keys).stage.nunique().eq(10).all()
    # Match the existing high/low fixed sample exactly before adding middle posts.
    if a.legacy_values and a.legacy_values.exists():
        old=pd.read_csv(a.legacy_values)
        if a.band=='high':old=old[old.band.eq('high')]
        old=old.set_index(KEYS+['stage']).sort_index()
        same=v[v.band.isin(['high','low']) & v.direction.ne('Majority')].set_index(KEYS+['stage']).sort_index()
        assert old.index.equals(same.index)
        assert np.allclose(old.certainty,same.certainty) and np.array_equal(old.n_comments,same.n_comments)
    rows=[];trends=[];counts=[];slopes_all=[]
    rng=np.random.default_rng(SEED)
    x=np.arange(10)/9;xc=x-x.mean();sxx=xc@xc
    # Preserve the original minority bootstrap RNG streams exactly.
    order=[(c,d) for c in ['AITA','AITAH'] for d in ['Blame','Defend']]+[(c,'Majority') for c in ['AITA','AITAH']]
    for group in order:
        part=v[(v.subreddit==group[0]) & (v.direction==group[1])]
        community,direction=group
        matrix=part.pivot(index='post_id',columns='stage',values='certainty').reindex(columns=range(10))
        y=matrix.to_numpy();n=len(y)
        assert n>=2 and np.isfinite(y).all()
        point=y.mean(axis=0)
        weights=rng.multinomial(n,np.full(n,1/n),size=a.profile_reps)
        boot=weights@y/n;cis=np.quantile(boot,[.025,.975],axis=0)
        cn=part.groupby('stage').n_comments.sum()
        for s in range(10):rows.append(dict(subreddit=community,direction=direction,stage=s,
            progress_mid=(s+.5)/10,value=point[s],ci_low=cis[0,s],ci_high=cis[1,s],n_posts=n,n_comments=int(cn[s])))
        slopes=(y-y.mean(axis=1,keepdims=True))@xc/sxx
        beta=slopes.mean();se=slopes.std(ddof=1)/np.sqrt(n)
        # Within-transformed FE normal equation and clustered sandwich checks.
        residual=y-y.mean(axis=1,keepdims=True)-beta*xc
        beta_within=np.sum((y-y.mean(axis=1,keepdims=True))*xc)/(n*sxx)
        sandwich=n/(n-1)*np.sum((residual@xc)**2)/(n*sxx)**2
        assert np.isclose(beta,beta_within,atol=1e-12) and np.isclose(se,np.sqrt(sandwich),atol=1e-12)
        # Independent explicit post-dummy OLS validation on a deterministic subset.
        ys=y[:min(n,40)];ns=len(ys)
        design=np.column_stack([np.repeat(np.eye(ns),10,axis=0),np.tile(x,ns)])
        assert np.isclose(np.linalg.lstsq(design,ys.ravel(),rcond=None)[0][-1],slopes[:ns].mean(),atol=1e-11)
        boots=[]
        for first in range(0,a.trend_reps,1000):
            w=rng.multinomial(n,np.full(n,1/n),size=min(1000,a.trend_reps-first))
            boots.append(w@slopes/n)
        lo,hi=np.quantile(np.concatenate(boots),[.025,.975])
        trends.append(dict(subreddit=community,direction=direction,n_posts=n,n_comments=int(part.n_comments.sum()),
            beta=beta,cluster_se=se,t_stat=beta/se,df=n-1,ci_low=lo,ci_high=hi,
            first=point[0],last=point[-1],positive_post_slope_fraction=float(np.mean(slopes>0))))
        eligible=frame[(frame.subreddit==community)&(frame.direction.ne('Tie') if direction=='Majority' else frame.direction.eq(direction))]
        counts.append(dict(subreddit=community,direction=direction,annotation_posts=len(eligible),
            fixed_posts=n,scored_comments=int(part.n_comments.sum()),
            **{band+'_posts':int(part[part.band==band].post_id.nunique()) for band in ['high','middle','low']}))
        slopes_all.extend(dict(subreddit=community,direction=direction,post_id=p,slope=s) for p,s in zip(matrix.index,slopes))
    t=pd.DataFrame(trends)
    expr='t<-c('+','.join(map(str,t.t_stat))+');df<-c('+','.join(map(str,t.df))+');write.table(data.frame(p=2*pt(-abs(t),df),critical=qt(.975,df)),row.names=FALSE,col.names=FALSE,sep=",")'
    result=subprocess.run([str(a.rscript),'--vanilla','-e',expr],capture_output=True,text=True,check=True)
    tails=pd.read_csv(io.StringIO(result.stdout),header=None,names=['p','critical'])
    assert len(tails)==6 and tails.p.between(0,1).all()
    t['p_two_sided']=tails.p;t['p_holm_6']=holm(t.p_two_sided)
    t['t_ci_low']=t.beta-tails.critical*t.cluster_se;t['t_ci_high']=t.beta+tails.critical*t.cluster_se
    a.data.mkdir(parents=True,exist_ok=True)
    frame.to_csv(a.data/'annotation_posts.csv',index=False)
    v.to_csv(a.data/'post_stage_values.csv',index=False)
    pd.DataFrame(rows).to_csv(a.data/'stage_summary.csv',index=False)
    pd.DataFrame(counts).to_csv(a.data/'curve_counts.csv',index=False)
    t.to_csv(a.data/'linear_trends.csv',index=False)
    pd.DataFrame(slopes_all).to_csv(a.data/'post_slopes.csv',index=False)
    provenance=dict(source=m['source'],source_sha256=m['source_sha256'],metadata=m['metadata'],metadata_sha256=m['metadata_sha256'],
        agreement_band=a.band,annotation_posts=len(frame),annotation_comments=source_rows,tie_posts=int(frame.direction.eq('Tie').sum()),
        annotation_counts=frame.groupby(['subreddit','band']).size().reset_index(name='posts').to_dict('records'),
        plotted_unique_posts=len(keep[KEYS].drop_duplicates()),plotted_group_memberships=len(keep),plotted_comments=int(v.n_comments.sum()),seed=SEED,
        profile_reps=a.profile_reps,trend_reps=a.trend_reps,
        window='0 <= elapsed hours < 24; relative rank among retained verdict comments within this window',
        cohort=('High agreement (rho <= .2 or rho >= .8)' if a.band=='high' else 'All agreement levels, including middle')+'; exact ties excluded; group-specific scored certainty present in all ten stages',
        weighting='Equal post weight within each community/direction; no comment pooling or sampling-fraction reweighting',
        model='mean_certainty[p,s] = post_intercept[p] + beta*(stage/9) + error[p,s]',
        coefficient='Fitted first-to-last-stage change (5% to 95% sequence position), not per-hour change',
        intervals='Pointwise 95% whole-post percentile bootstrap, unadjusted; trend p-values are two-sided cluster-t G-1 df, Holm across six groups',
        top_level='Inherited from annotation-source provenance; source lacks parent IDs and author IDs',
        validation='High/low fixed post-stage cells reproduce previous Figure 5; within-transformed FE and post-slope coefficients agree; sandwich SE and explicit dummy OLS subset checked',
        limitations=['Selected persistent-expression posts per group, not all annotated posts.',
            'Combined annotation archive has unequal agreement-band sampling; describes this sample, not community population.',
            'Different authors may contribute across stages; not within-person change or causal influence.',
            'Linear trend is exploratory and does not imply monotonic increase.',
            'Individual-group significance is not a cross-group slope-difference test.'],
        output_sha256={p.name:digest(p) for p in a.data.glob('*.csv')})
    (a.data/'manifest.json').write_text(json.dumps(provenance,indent=2)+'\n')
    report=f'{a.band} agreement fixed-post certainty\n\n'+pd.DataFrame(counts).to_string(index=False)+'\n\n'+t.to_string(index=False)+'\n'
    (a.data/'report.txt').write_text(report);print(report)

def plot(a):
    os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'moral_minority_mpl'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import PercentFormatter,MultipleLocator,FormatStrFormatter
    m=json.loads((a.data/'manifest.json').read_text())
    for name,value in m['output_sha256'].items():assert digest(a.data/name)==value,name
    s=pd.read_csv(a.data/'stage_summary.csv');t=pd.read_csv(a.data/'linear_trends.csv')
    ink='#37474F';colors={'Majority':'#5770DB','Blame':'#FC8D61','Defend':'#66C2A5'};markers={'Majority':'D','Blame':'o','Defend':'s'}
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'text.color':ink,'axes.labelcolor':ink,
        'axes.edgecolor':ink,'xtick.color':ink,'ytick.color':ink,'pdf.fonttype':42,'axes.unicode_minus':False})
    communities=[a.community] if a.community else ['AITA','AITAH']
    single=len(communities)==1
    compact=a.width<7
    fig,axes=plt.subplots(len(communities),2,figsize=(a.width,2.6 if single else 4.4),squeeze=False,gridspec_kw={'width_ratios':[1.15,1]},sharex='col')
    fig.subplots_adjust(left=.105 if compact else (.08 if single else .12),right=.98,bottom=.25 if compact else (.21 if single else .12),top=.84 if single else .9,wspace=.1 if compact else .08,hspace=.12)
    low=max(1,np.floor((s.ci_low.min()-.025)*20)/20);high=min(4,np.ceil((s.ci_high.max()+.025)*20)/20)
    if a.community=='AITA' and m.get('agreement_band')=='high':
        low,high=3.2,3.9
    xmin=min(-.04,float(t.ci_low.min())-.035);xmax=max(.12,float(t.ci_high.max())+.035)
    for row,community in enumerate(communities):
        left,right=axes[row]
        for direction,ypos in [('Majority',2),('Blame',1),('Defend',0)]:
            v=s[(s.subreddit==community)&(s.direction==direction)].sort_values('stage')
            r=t[(t.subreddit==community)&(t.direction==direction)].iloc[0]
            left.fill_between(v.progress_mid,v.ci_low,v.ci_high,color=colors[direction],alpha=.20,lw=0)
            left.plot(v.progress_mid,v.value,color=colors[direction],marker=markers[direction],ms=3.5,lw=1.7)
            right.errorbar(r.beta,ypos,xerr=[[r.beta-r.ci_low],[r.ci_high-r.beta]],fmt=markers[direction],
                color=colors[direction],ms=6,elinewidth=1.8,capsize=3,markeredgecolor=ink,markeredgewidth=.5)
            # Keep stars in the chart; thresholds are given in the caption.
            stars='***' if r.p_holm_6<.001 else '**' if r.p_holm_6<.01 else '*' if r.p_holm_6<.05 else ''
            suffix=f' {stars}' if stars else ''
            right.text(r.beta,ypos+.47,f'{r.beta:+.3f}{suffix}',
                       ha='center',va='bottom',fontsize=9)
            right.text(r.beta,ypos+.22,f'[{r.ci_low:.3f}, {r.ci_high:.3f}]',
                       ha='center',va='bottom',fontsize=9)
        part=t[t.subreddit==community]
        ns=[int(part[part.direction==d].n_comments.iloc[0]) for d in colors]
        position=left.get_position()
        if not single:
            fig.text(.023,(position.y0+position.y1)/2,community,rotation=90,
                     ha='center',va='center',fontweight='bold',fontsize=10)
        left.text(.98,.04,'n = '+' / '.join(f'{n:,}' for n in ns),transform=left.transAxes,ha='right',fontsize=8)
        left.set(xlim=(0,1),ylim=(low,high),ylabel='Mean certainty')
        left.xaxis.set_major_locator(MultipleLocator(.25 if compact else .2));left.xaxis.set_major_formatter(PercentFormatter(1,decimals=0))
        left.yaxis.set_major_locator(MultipleLocator(.2 if high-low>.7 else .1));left.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
        right.set(xlim=(xmin,xmax),ylim=(-.43,2.78),yticks=[])
        right.xaxis.set_major_locator(MultipleLocator(.1 if compact else .05));right.xaxis.set_major_formatter(FormatStrFormatter('%.2f'))
        right.axvline(0,color='#7C8C93',ls='--',lw=1)
        right.tick_params(axis='y',length=0,pad=6,labelsize=9)
        for ax in [left,right]:
            ax.spines[['top','right']].set_visible(False)
            ax.tick_params(axis='x',labelsize=9)
            ax.grid(axis='y' if ax is left else 'x',color='#E2E7EA',lw=.7)
            ax.set_axisbelow(True)
        right.spines['left'].set_visible(False)
    axes[-1,0].set_xlabel('Comment-sequence position (first 24 h)',fontsize=9,labelpad=5)
    axes[-1,1].set_xlabel('Estimated linear change',fontsize=9,labelpad=5)
    fig.legend(handles=[Line2D([],[],color=colors[d],marker=markers[d],lw=1.8,label={'Majority':'Majority','Blame':'Blaming','Defend':'Defending'}[d]) for d in colors],
        loc='upper center',bbox_to_anchor=(.52,.99),ncol=3,frameon=False,fontsize=10)
    a.pdf.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(a.pdf,metadata={'Title':m.get('agreement_band','all')+' agreement certainty profiles and post fixed-effects trends'})
    if a.preview:
        assert 'figures' not in a.preview.resolve().parts,'PNG previews must stay outside figures/'
        a.preview.parent.mkdir(parents=True,exist_ok=True);fig.savefig(a.preview,dpi=240)
    plt.close(fig);print(a.pdf)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['prepare','plot'])
    p.add_argument('--source-manifest',type=Path,default=MANIFEST)
    p.add_argument('--legacy-values',type=Path,default=ROOT/'scripts/data/fig5_certainty_progress/fixed/post_stage_values.csv')
    p.add_argument('--data',type=Path,default=ROOT/'scripts/data/fig8_all_groups/fixed')
    p.add_argument('--pdf',type=Path,default=ROOT/'figures/NOT_USED/certainty_progress_all_agreement_post_fe.pdf')
    p.add_argument('--preview',type=Path)
    p.add_argument('--community',choices=['AITA','AITAH'])
    p.add_argument('--width',type=float,default=8.2)
    p.add_argument('--band',choices=['all','high'],default='all')
    p.add_argument('--profile-reps',type=int,default=2000);p.add_argument('--trend-reps',type=int,default=20000)
    p.add_argument('--rscript',type=Path,default=Path('/usr/local/bin/Rscript'))
    a=p.parse_args();prepare(a) if a.mode=='prepare' else plot(a)
