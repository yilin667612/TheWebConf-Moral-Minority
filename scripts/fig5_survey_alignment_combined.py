"""Paper-style combined survey panels, both split by reported alignment.

Use --publish to replace the manuscript Figure 6 PDF.
Run with bundled Python; Rscript computes all 16 unadjusted Welch tests.
The figure shows means and exploratory, unadjusted significance asterisks.
All groups are defined after exposure.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
from decimal import Decimal, ROUND_HALF_UP
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, default=ROOT.parent/'minority-voices-aita/output/80_participants_merged_analysis.csv')
p.add_argument('--out', type=Path, default=ROOT/'output/pdf/fig5_alignment_combined')
p.add_argument('--publish', action='store_true', help='Replace figures/survey_results_panels.pdf')
args = p.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
with args.source.open(newline='', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
assert len(rows) == len({r['participant_id'] for r in rows}) == 80
assert all(r['majority_aligned_judgment'] == str(int(r['judgment_direction']==r['majority_judgment'])) for r in rows)
conditions = [('MM','majority_majority','#5770DB'),('Mm','majority_minority','#A65BA6')]
# Keep source/test keys unchanged; use descriptive condition names in the paper.
condition_labels = {'MM': 'Two Majority', 'Mm': 'Majority + Minority'}
alignments = [('majority','1',-1),('minority','0',1)]
metrics = ['certainty_1_4','comment1_influence','comment2_influence',
           'comment1_agreement','comment2_agreement','comment1_reflection',
           'comment2_reflection','perspective_broadening_mean']
cells = {}
for alignment, code, _ in alignments:
    for name, treatment, _ in conditions:
        sample = [r for r in rows if r['treatment']==treatment and r['majority_aligned_judgment']==code]
        for metric in metrics:
            values = [float(r[metric]) for r in sample]
            assert all(1 <= v <= (4 if metric=='certainty_1_4' else 7 if metric=='perspective_broadening_mean' else 5) for v in values)
            cells[alignment,name,metric] = dict(n=len(values),mean=statistics.mean(values))
for name,treatment,_ in conditions:
    for metric in metrics:
        parts = [cells[a,name,metric] for a,_,_ in alignments]
        assert sum(s['n'] for s in parts)==40
        pooled = statistics.mean(float(r[metric]) for r in rows if r['treatment']==treatment)
        assert abs(sum(s['n']*s['mean'] for s in parts)/40-pooled)<1e-12
rscript = shutil.which('Rscript') or '/usr/local/bin/Rscript'
test_file=args.out/'alignment_tests.csv'
subprocess.run([rscript,str(ROOT/'scripts/fig5_survey_alignment_tests.R'),str(args.source),str(test_file)],check=True)
with test_file.open(newline='') as f:
    tests=list(csv.DictReader(f))
assert len(tests)==16
p_values = {(t['alignment'],t['metric']):float(t['p']) for t in tests}
for test in tests:
    for condition,_,_ in conditions:
        s=cells[test['alignment'],condition,test['metric']]
        assert s['n']==int(test['n_'+condition])
        assert abs(s['mean']-float(test['mean_'+condition]))<1e-12
pdf = args.out/'survey_alignment_combined.pdf'
c = canvas.Canvas(str(pdf),pagesize=(240,210))
c.setTitle('Survey responses by reported judgment alignment')
INK='#37474F'
def text(x,y,s,size=6.1,align='left',color=INK,bold=False):
    c.setFillColor(HexColor(color)); c.setFont('Helvetica-Bold' if bold else 'Helvetica',size)
    {'left':c.drawString,'center':c.drawCentredString,'right':c.drawRightString}[align](x,y,s)
def number(v):
    return str(Decimal(str(v)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
CENTER, WIDTH = 150, 78
BAR_HEIGHT, PAIR_OFFSET = 4.0, 2.5
def xp(v,upper,side):
    return CENTER+side*(v-1)/(upper-1)*WIDTH
def guides(y0,y1,upper,ticks=False,tick_values=None):
    c.setLineWidth(.3); c.setStrokeColor(HexColor('#E3E7EB'))
    for side in [-1,1]:
        for tick in (tick_values if tick_values is not None else range(1,upper+1)):
            x=xp(tick,upper,side)
            if tick!=1: c.line(x,y0,x,y1)
            if ticks: text(x+side*2.8 if tick==1 else x,y0-8,str(tick),5.8,'center')
    c.setStrokeColor(HexColor(INK)); c.setDash(1.4,1.4)
    c.line(CENTER,y0-2,CENTER,y1+1); c.setDash()
def bars(metric,y,upper):
    for alignment,_,side in alignments:
        for dy,(name,_,color) in zip([PAIR_OFFSET,-PAIR_OFFSET],conditions):
            s=cells[alignment,name,metric]; value=s['mean']
            end=xp(value,upper,side)
            c.setFillColor(HexColor(color))
            c.rect(min(CENTER,end),y+dy-BAR_HEIGHT/2,abs(end-CENTER),BAR_HEIGHT,fill=1,stroke=0)
            text(end+side*2,y+dy-1.8,number(value),5.2,'right' if side<0 else 'left')
        # One marker per between-condition comparison, centered between the paired bars.
        p_value = p_values[alignment,metric]
        stars = '***' if p_value < .001 else '**' if p_value < .01 else '*' if p_value < .05 else ''
        if stars:
            # Bracket spans the two bar centers and opens toward the bars.
            bracket_x = 69.5 if side < 0 else 230.5
            cap_x = bracket_x - side * .6
            c.setStrokeColor(HexColor(INK)); c.setLineWidth(.45)
            c.line(bracket_x,y-PAIR_OFFSET,bracket_x,y+PAIR_OFFSET)
            for dy in [-PAIR_OFFSET,PAIR_OFFSET]:
                c.line(bracket_x,y+dy,cap_x,y+dy)
            text(65 if side < 0 else 235.5,y-2.2,stars,6,'center')
for y,(name,_,color) in zip([196,187],conditions):
    c.setFillColor(HexColor(color)); c.rect(2,y,5,5,fill=1,stroke=0)
    text(10,y,condition_labels[name],6.1)
for x,(alignment,_,_) in zip([110,190],alignments):
    text(x,196,'Agrees with '+alignment,6,'center')
    mm=cells[alignment,'MM','certainty_1_4']['n']
    mixed=cells[alignment,'Mm','certainty_1_4']['n']
    text(x,187,f'n = {mm} / {mixed}',5.2,'center')
# Extend the alignment divider through both group headings and sample sizes.
c.setStrokeColor(HexColor(INK)); c.setLineWidth(.3); c.setDash(1.4,1.4)
c.line(CENTER,182,CENTER,202); c.setDash()
text(2,169.5,'Judgment',6.1)
text(2,162.5,'certainty',6.1)
guides(161,175,4,True)
bars('certainty_1_4',168,4)
text(150,146,'Mean certainty',6.1,'center')
text(2,136.5,'Range of moral',6.1); text(2,129.5,'considerations',6.1)
guides(128,141,7,ticks=True,tick_values=[1,3,5,7])
bars('perspective_broadening_mean',135,7)
text(150,113,'Mean rating',6.1,'center')

# All six 1-5 rows share a continuous grid and one set of bottom ticks.
# Pair centers are 13 points apart; each pair has a one-point edge gap.
guides(26,104,5,ticks=True,tick_values=[1,3,5])
groups=[('Influence',None,'comment1_influence','comment2_influence',98,85),
        ('Agreement',None,'comment1_agreement','comment2_agreement',72,59),
        ('New moral','considerations','comment1_reflection','comment2_reflection',46,33)]
for title,line2,m1,m2,y1,y2 in groups:
    midpoint = (y1+y2)/2
    text(2,midpoint+(1.5 if line2 else -2),title,6.1)
    if line2: text(2,midpoint-5.5,line2,6.1)
    for metric,y,clabel in [(m1,y1,'C1'),(m2,y2,'C2')]:
        text(56,y-2,clabel,5.8,'right'); bars(metric,y,5)
text(150,11,'Mean rating',6.1,'center')
c.save()
(args.out/'summary.json').write_text(json.dumps(dict(
    source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
    condition_labels=condition_labels,
    cells=[dict(alignment=k[0],condition=k[1],metric=k[2],**v) for k,v in cells.items()],
    tests=tests,
    caveat='Post-exposure alignment; exploratory subgroup comparisons. Asterisks use unadjusted two-sided Welch p-values: * < .05, ** < .01, *** < .001.'),indent=2)+'\n')
poppler=Path('/Users/minjeongshin/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm')
if poppler.exists():
    fonts=args.out/'fontconfig.xml'
    fonts.write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig><dir>/System/Library/Fonts/Supplemental</dir><cachedir>/tmp/survey-font-cache</cachedir><alias><family>Helvetica</family><prefer><family>Arial</family></prefer></alias></fontconfig>')
    subprocess.run([str(poppler),'-scale-to','1800','-png','-singlefile',str(pdf),str(pdf.with_suffix(''))],check=True,env={**os.environ,'FONTCONFIG_FILE':str(fonts)})
print(pdf)
if args.publish:
    target=ROOT/'figures/survey_results_panels.pdf'
    shutil.copyfile(pdf,target)
    print(target)
