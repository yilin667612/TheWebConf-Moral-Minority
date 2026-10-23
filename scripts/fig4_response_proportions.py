"""Standalone former Figure 3(b); unchanged rounded pair-weighted estimates."""
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/moral_minority_mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'scripts/data/aita_high_agreement_overview/overview_values.json').read_text())
colors={'Majority':'#5770DB','Blaming':'#FC8D61','Defending':'#66C2A5'}
ink='#37474F'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'pdf.fonttype':42,
    'text.color':ink,'axes.labelcolor':ink,'axes.edgecolor':ink,'xtick.color':ink,'ytick.color':ink})
fig,ax=plt.subplots(figsize=(4.5,2.4))
for j,(group,color) in enumerate(colors.items()):
    row=data['response'][j]; start=0
    for key,hatch in [('support',None),('challenge','///'),('other',None)]:
        value=row[key] if key!='other' else 100-row['support']-row['challenge']
        ax.barh(2-j,value,left=start,height=.55,
            color=color if key=='support' else ('white' if key=='challenge' else '#E4E7E9'),
            edgecolor=color if key!='other' else '#A8B0B5',hatch=hatch,linewidth=.8)
        if key!='other':
            ax.text(start+value/2,2-j,('≈' if j==0 else '')+f'{value:.1f}',ha='center',va='center',fontsize=9,
                bbox=dict(facecolor='white',edgecolor='none',alpha=.85,pad=.7) if hatch else None)
        start+=value
ax.set(xlim=(0,100),ylim=(-.6,2.6),xticks=[0,25,50,75,100],yticks=[2,1,0],yticklabels=list(colors))
ax.xaxis.set_major_formatter(PercentFormatter(100,decimals=0))
ax.spines[['top','right']].set_visible(False)
ax.tick_params(axis='y',length=0)
ax.legend(handles=[Patch(facecolor='#A8B0B5',label='Support'),Patch(facecolor='white',edgecolor=ink,hatch='///',label='Challenge'),Patch(facecolor='#E4E7E9',edgecolor='#A8B0B5',label='Other')],
    loc='upper center',bbox_to_anchor=(.5,1.25),ncol=3,frameon=False,fontsize=9,handlelength=1.1,columnspacing=.8)
fig.subplots_adjust(left=.24,right=.93,bottom=.16,top=.79)
fig.savefig(ROOT/'figures/NOT_USED/aita_response_proportions.pdf')
plt.close(fig)
