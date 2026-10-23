"""Recreate the survey procedure as an editable vector figure.

Preserves the structure and content of figures/NOT_USED/survey_procedure.png while
using the paper's descriptive condition names. Run with bundled Python.
"""
import argparse
from pathlib import Path
import shutil

from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, default=ROOT/'output/pdf/survey_procedure')
parser.add_argument('--publish', action='store_true')
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
pdf = args.out/'survey_procedure.pdf'
W, H = 990, 445
c = canvas.Canvas(str(pdf), pagesize=(W, H))
c.setTitle('Survey procedure: Highly Scored and Balanced')
INK, GRAY = '#242424', '#BDBDBD'
BLUE, RED = '#5770DB', '#DB5F57'
FONT_DIR = Path('/System/Library/Fonts/Supplemental')
FONT_MAP = {'Helvetica': 'Arial', 'Helvetica-Bold': 'Arial-Bold',
            'Helvetica-Oblique': 'Arial-Italic'}
for name, filename in [('Arial', 'Arial.ttf'), ('Arial-Bold', 'Arial Bold.ttf'),
                       ('Arial-Italic', 'Arial Italic.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(FONT_DIR/filename)))

def text(x, baseline, value, size, font='Helvetica', color=INK, align='left'):
    c.setFillColor(HexColor(color))
    c.setFont(FONT_MAP.get(font, font), size)
    {'left': c.drawString, 'center': c.drawCentredString}[align](x, H-baseline, value)

def box(x, top, width, height, color=GRAY, weight=3.5, radius=13):
    c.setStrokeColor(HexColor(color))
    c.setLineWidth(weight)
    c.roundRect(x, H-top-height, width, height, radius, fill=0, stroke=1)

def comment(x, top, label, color):
    box(x, top, 355, 39, color=color, weight=3, radius=7)
    c.setFillColor(HexColor(color))
    c.circle(x+29, H-top-19.5, 8, fill=1, stroke=0)
    text(x+51, top+26, label, 21, color=color)

# Compact spacing preserves the original sequence and condition structure.
box(4, 6, 982, 258, color=INK, weight=2, radius=12)
text(30, 38, '1  Read an AITA post and two comments', 28, 'Helvetica-Bold')
box(37, 49, 916, 47, weight=2.5, radius=8)
text(63, 80, 'AITA for not waiting for my always-late friend?', 24, 'Helvetica-Bold')
box(37, 104, 434, 150, weight=2.5, radius=9)
box(519, 104, 434, 150, weight=2.5, radius=9)
text(254, 134, 'Highly Scored', 25, 'Helvetica-Bold', align='center')
text(736, 134, 'Balanced', 25, 'Helvetica-Bold', align='center')
comment(77, 146, 'NA comment', BLUE)
comment(77, 198, 'NA comment', BLUE)
comment(558, 146, 'NA comment', BLUE)
comment(558, 198, 'YA comment', RED)
text(495, 187, 'or', 21, 'Helvetica-Oblique', '#555555', 'center')

c.setFillColor(HexColor('#8E8E8E'))
arrow = c.beginPath()
arrow.moveTo(480, H-266)
arrow.lineTo(510, H-266)
arrow.lineTo(495, H-281)
arrow.close()
c.drawPath(arrow, fill=1, stroke=0)

box(4, 284, 982, 155, color=INK, weight=2, radius=12)
text(30, 316, '2  What is your judgment?', 28, 'Helvetica-Bold')
scale_colors = ['#98102D', '#C3193F', '#E35779', '#F3A4B7',
                '#B0C6F1', '#6C91DF', '#2859C4', '#1E408E']
for x, color in zip([162, 251, 340, 429, 558, 647, 736, 828], scale_colors):
    c.setFillColor(HexColor(color))
    c.circle(x, H-345, 14, fill=1, stroke=0)
c.setStrokeColor(HexColor('#8E8E8E'))
c.setLineWidth(2.5)
c.line(495, H-326, 495, H-364)
text(141, 382, 'Definitely YA', 23, 'Helvetica-Bold', '#C3193F')
text(667, 382, 'Definitely NA', 23, 'Helvetica-Bold', '#2859C4')
box(66, 392, 858, 31, color='#9E9E9E', weight=2.5, radius=6)
text(90, 414, 'Explain your judgment', 22, 'Helvetica-Oblique', '#8E8E8E')
c.save()
print(pdf)
if args.publish:
    target = ROOT/'figures/survey_procedure.pdf'
    shutil.copyfile(pdf, target)
    print(target)
