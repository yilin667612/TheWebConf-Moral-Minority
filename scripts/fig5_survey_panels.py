"""Compact Figure 5: conditional certainty means + original remaining panels.

Run bundled Python from the paper root. R supplies Welch tests and Holm
adjustment across the two certainty comparisons. Alignment is defined by
the single reported judgment, measured after exposure, not a baseline.
The lower panel is preserved vector artwork from the original Figure 5.
"""
import csv
import hashlib
import io
import json
import re
from pathlib import Path
import subprocess
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, FloatObject, TextStringObject

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'output/fig5_survey_final'
SOURCE = ROOT.parent/'minority-voices-aita/output/80_participants_merged_analysis.csv'
ORIGINAL = ROOT/'scripts/data/fig5_survey/survey_results_bars_original.pdf'
TARGET = ROOT/'figures/survey_results_panels.pdf'
OUT.mkdir(parents=True, exist_ok=True)
subprocess.run(['Rscript', str(ROOT/'scripts/fig5_survey_certainty_tests.R'),
                str(SOURCE), str(OUT)], check=True, cwd=ROOT)
with (OUT/'certainty_tests.csv').open() as f:
    stats = {r['alignment']: r for r in csv.DictReader(f)}

# Independent Python check of means, n, and Welch t against R.
with SOURCE.open(newline='', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
import statistics
for alignment, code in [('majority','1'),('minority','0')]:
    s = stats[alignment]
    values = []
    for condition, name in [('majority_majority','MM'),('majority_minority','Mm')]:
        v = [float(r['certainty_1_4']) for r in rows
             if r['treatment']==condition and r['majority_aligned_judgment']==code]
        assert len(v)==int(s['n_'+name])
        assert abs(statistics.mean(v)-float(s['mean_'+name]))<1e-12
        values.append(v)
    a,b = values
    t = (statistics.mean(b)-statistics.mean(a))/(statistics.variance(a)/len(a)+statistics.variance(b)/len(b))**.5
    assert abs(t-float(s['t']))<1e-12

buf = io.BytesIO()
c = canvas.Canvas(buf, pagesize=(240,199))
ink = '#37474F'
def text(x,y,value,size=6.1,align='left',color=ink):
    c.setFillColor(HexColor(color))
    # Match the preserved lower panel's font, type sizes, and ink color.
    c.setFont('Helvetica',size)
    {'left':c.drawString,'center':c.drawCentredString,'right':c.drawRightString}[align](x,y,value)
colors = [('MM','#5770DB'),('Mm','#DB5F57')]
for x,(label,color) in zip([66,139],colors):
    c.setFillColor(HexColor(color))
    c.rect(x,189,5,5,stroke=0,fill=1)
    text(x+8,189,label+' (n = 40)',7)
text(2,177,'(a)',6.3)
text(87,177,'Agrees with majority',6.3,'center')
text(183,177,'Agrees with minority',6.3,'center')
def xp(value,side):
    return 135+side*(value-1)*30
for side in [-1,1]:
    for tick in [1,2,3,4]:
        c.setStrokeColor(HexColor('#E3E7EB'))
        c.setLineWidth(.3)
        if tick!=1:
            c.line(xp(tick,side),151,xp(tick,side),171)
        tick_x=xp(tick,side)+(side*2.8 if tick==1 else 0)
        text(tick_x,145,str(tick),6.1,'center')
for y,(name,color) in zip([165,156],colors):
    text(9,y-2.2,name,6.3)
    for alignment,side in [('majority',-1),('minority',1)]:
        s = stats[alignment]
        mean = float(s['mean_'+name])
        left = xp(mean,side) if side==-1 else xp(1,side)
        c.setFillColor(HexColor(color))
        c.rect(left,y-2.6,(mean-1)*30,5.2,stroke=0,fill=1)
        text(xp(mean,side)+side*2,y-1.85,f'{mean:.2f}',5.2,
             'right' if side==-1 else 'left')
        text(xp(1,side)+side*2.8,y-1.8,'n = '+s['n_'+name],5.0,
             'right' if side==-1 else 'left','#FFFFFF')

# The two 1 labels share one baseline and flank a central dashed divider.
c.setStrokeColor(HexColor(ink))
c.setLineWidth(.4)
c.setDash(1.5,1.5)
c.line(135,141,135,172)
c.setDash()

# Brackets denote MM vs Mm within one reported-judgment alignment.
for alignment,side in [('majority',-1),('minority',1)]:
    p = float(stats[alignment]['p_holm'])
    stars = '***' if p<.001 else '**' if p<.01 else '*' if p<.05 else ''
    if stars:
        x = 38 if side==-1 else 233
        c.setStrokeColor(HexColor(ink))
        c.setLineWidth(.5)
        c.lines([(x,156,x,165),(x,156,x-side*2,156),(x,165,x-side*2,165)])
        text(x+side*6,158.5,stars,6.1,'center')
text(135,134,'Mean certainty (1-4)',6.3,'center')
text(2,126,'(b)',6.3)
c.save()

page = PdfReader(buf).pages[0]
source_writer = PdfWriter(clone_from=ORIGINAL)
base = source_writer.pages[0]
assert tuple(map(float,base.mediabox))==(0,0,240,166)
# Match panel (a)'s numeric type size without changing panel (b)'s values,
# bars, axis labels, or measure labels. Each source text run has its own Tf.
stream = ContentStream(base.get_contents(), base.pdf)
font_index = matrix_index = None
resized = 0
removed_mean_title = 0
for index, (operands, operator) in enumerate(stream.operations):
    if operator == b'Tf':
        font_index = index
    elif operator == b'Tm':
        matrix_index = index
    elif operator == b'Tj' and str(operands[0]) == 'Mean':
        operands[0] = TextStringObject('')
        removed_mean_title += 1
    elif operator == b'Tj' and re.fullmatch(r'(?:\d+\.\d{2}|p [=<] \.\d{3})', str(operands[0])):
        matrix = stream.operations[matrix_index][0]
        if float(matrix[5]) < 126:
            font = stream.operations[font_index][0]
            old_size = float(font[1])
            font[1] = FloatObject(5.2)
            matrix[5] = FloatObject(float(matrix[5])+(old_size-5.2)*.35)
            resized += 1
assert resized == 21, f'Expected 14 means and 7 p-values, got {resized}'
assert removed_mean_title == 1
base.replace_contents(stream)
base.cropbox.lower_left=(0,0)
base.cropbox.upper_right=(240,126)
base.trimbox.lower_left=(0,0)
base.trimbox.upper_right=(240,126)
page.merge_page(base)
# Remove the bottom margin formerly occupied by the Mean axis title.
page.mediabox.lower_left = (0,10)
page.cropbox.lower_left = (0,10)
writer=PdfWriter()
writer.add_page(page)
writer.add_metadata({'/Title':'Survey responses: certainty and comment ratings'})
with TARGET.open('wb') as f:
    writer.write(f)
(OUT/'manifest.json').write_text(json.dumps(dict(
    source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    original_artwork_sha256=hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),
    method='Two-sided Welch tests, Holm across two certainty comparisons. Unadjusted 95% difference CIs. B retains verified original full-sample unadjusted tests.',
    caveat='Single reported judgment after exposure. Conditional groups are not randomized; neither within-person change nor causal effect modification is identified.',
    original_artwork=str(ORIGINAL),output=str(TARGET)),indent=2)+'\n')
print(TARGET)
