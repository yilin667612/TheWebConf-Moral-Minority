"""Recreate the survey procedure as an editable vector figure.

Preserves the structure and content of figures/survey_procedure.png while
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
W, H = 990, 725
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
    box(x, top, 355, 48, color=color, weight=4, radius=9)
    c.setFillColor(HexColor(color))
    c.circle(x+36, H-top-24, 11, fill=1, stroke=0)
    text(x+64, top+33, label, 29, color=color)

box(6, 9, 978, 405, color=INK, weight=4.5, radius=15)
text(39, 64, '1  Read an AITA post and two comments', 38, 'Helvetica-Bold')
box(45, 96, 900, 84)
text(80, 147, 'AITA for not waiting for my always-late friend?', 32, 'Helvetica-Bold')
box(45, 192, 426, 210)
box(519, 192, 426, 210)
text(258, 243, 'Highly Scored', 33, 'Helvetica-Bold', align='center')
text(732, 243, 'Balanced', 33, 'Helvetica-Bold', align='center')
comment(80, 270, 'NA comment', BLUE)
comment(80, 333, 'NA comment', BLUE)
comment(555, 270, 'NA comment', BLUE)
comment(555, 333, 'YA comment', RED)
text(495, 332, 'or', 28, 'Helvetica-Oblique', '#555555', 'center')

c.setFillColor(HexColor('#8E8E8E'))
arrow = c.beginPath()
arrow.moveTo(473, H-414)
arrow.lineTo(517, H-414)
arrow.lineTo(495, H-443)
arrow.close()
c.drawPath(arrow, fill=1, stroke=0)

box(6, 445, 978, 272, color=INK, weight=4.5, radius=15)
text(39, 499, '2  What is your judgment?', 38, 'Helvetica-Bold')
scale_colors = ['#98102D', '#C3193F', '#E35779', '#F3A4B7',
                '#B0C6F1', '#6C91DF', '#2859C4', '#1E408E']
for x, color in zip([162, 251, 340, 429, 558, 647, 736, 828], scale_colors):
    c.setFillColor(HexColor(color))
    c.circle(x, H-552, 21, fill=1, stroke=0)
c.setStrokeColor(HexColor('#8E8E8E'))
c.setLineWidth(3.5)
c.line(495, H-521, 495, H-584)
text(141, 605, 'Definitely YA', 30, 'Helvetica-Bold', '#C3193F')
text(667, 605, 'Definitely NA', 30, 'Helvetica-Bold', '#2859C4')
box(75, 627, 840, 66, color='#9E9E9E', radius=8)
text(105, 669, 'Explain your judgment', 30, 'Helvetica-Oblique', '#8E8E8E')
c.save()
print(pdf)
if args.publish:
    target = ROOT/'figures/survey_procedure.pdf'
    shutil.copyfile(pdf, target)
    print(target)
