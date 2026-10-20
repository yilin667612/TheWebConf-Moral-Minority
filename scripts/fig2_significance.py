"""Add post-cluster Wald comparisons to the user-designed Figure 2.

Uses all available post/group means, preserving the displayed estimand even
when a post lacks one side. Cluster influence scores retain majority/minority
dependence within a post. Nine two-sided, asymptotic Wald tests receive Holm
correction jointly. These observational contrasts are not causal effects.
The original user artwork is backed up once; reruns always use that backup.
Run with bundled Python (numpy, pypdf, reportlab); no scipy required.
"""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import numpy as np
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'figures/fig2.pdf'
BACKUP = ROOT / 'figures/alternatives/fig2_before_significance.pdf'
OUT = ROOT / 'output/fig2_significance'
SOURCE = ROOT.parent / 'minority-voices-aita/output/reception_full_min200_20261002/posts.jsonl'
METRICS = {'mean_score': ('score_sum', 'score_n'),
           'mean_reply': ('reply_sum', 'n'), 'mean_depth': ('depth_sum', 'n')}

def comparisons(community='AITA'):
    database = {'AITA': 'reddit', 'AITAH': 'aitah'}[community]
    reference = json.loads((ROOT / 'scripts/data/fig2_reception_post_equal.json').read_text())
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert digest == reference['source_sha256']
    rows = []
    with SOURCE.open() as stream:
        for line in stream:
            row = json.loads(line)
            if row['kind'] == 'post' and row['database'] == database:
                assert row['stored_verdicts'] >= 200 and row['rho'] != .5
                rows.append(row)
    assert len({r['post_id'] for r in rows}) == len(rows)
    results = []
    for metric, (num, den) in METRICS.items():
        for band, contrast in [('low', 'majority-minority'),
                               ('high', 'majority-minority'), ('high', 'blaming-defending')]:
            a, b = {}, {}
            for row in rows:
                if row['band'] != band:
                    continue
                for side, stats in row['stats'].items():
                    if not stats[den]:
                        continue
                    if contrast == 'majority-minority':
                        dest = a if side == 'majority' else b
                    elif side == 'minority':
                        dest = a if row['dominant'] == 'NA' else b
                    else:
                        continue
                    dest[row['post_id']] = stats[num] / stats[den]
            ma, mb = np.mean(list(a.values())), np.mean(list(b.values()))
            ids = sorted(a.keys() | b.keys())
            # OLS with two group indicators; CR1 sandwich variance of A-B.
            # Missing post/group cells contribute zero influence, not zero data.
            influence = np.array([(a[k]-ma)/len(a) if k in a else 0. for k in ids])
            influence -= np.array([(b[k]-mb)/len(b) if k in b else 0. for k in ids])
            g, n = len(ids), len(a) + len(b)
            se = math.sqrt(float(influence @ influence) * g/(g-1) * (n-1)/(n-2))
            delta = float(ma-mb)
            z = delta/se
            p = math.erfc(abs(z)/math.sqrt(2))
            results.append(dict(metric=metric, band=band, contrast=contrast,
                mean_a=float(ma), mean_b=float(mb), difference=delta, se=se,
                n_a=len(a), n_b=len(b), n_shared=len(a.keys() & b.keys()),
                n_clusters=g, z=z, p_raw=p,
                ci95_unadjusted=[delta-1.95996398454*se,delta+1.95996398454*se]))
    order = np.argsort([r['p_raw'] for r in results])
    running = 0.
    for rank, index in enumerate(order):
        r = results[index]
        running = max(running, min(1., (len(results)-rank)*r['p_raw']))
        r['p_holm'] = running
        r['indicator'] = '***' if running < .001 else '**' if running < .01 else '*' if running < .05 else ''
    return digest, results

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--community', choices=['AITA', 'AITAH'], default='AITA')
    args = parser.parse_args()
    target, backup, out = TARGET, BACKUP, OUT
    if args.community == 'AITAH':
        target = ROOT / 'figures/aitah_reception_agreement_direction_boxes_vertical.pdf'
        backup = ROOT / 'figures/alternatives/aitah_reception_before_significance.pdf'
        out = ROOT / 'output/aitah_reception_significance'
    digest, results = comparisons(args.community)
    out.mkdir(parents=True, exist_ok=True)
    backup.parent.mkdir(parents=True, exist_ok=True)
    original = (backup if backup.exists() else target).read_bytes()
    reader = PdfReader(io.BytesIO(original))
    page = reader.pages[0]
    assert tuple(map(float, page.mediabox)) == (0, 0, 742, 640), 'Inspect changed artwork before overlaying.'
    pdfmetrics.registerFont(TTFont('FigureSans', '/System/Library/Fonts/Supplemental/Arial.ttf'))
    buff = io.BytesIO()
    c = canvas.Canvas(buff, pagesize=(742,640))
    # Cover the old right-panel axis title only; preserve tick labels and plots.
    c.setFillColorRGB(1,1,1)
    c.rect(511,640-262,21,208,fill=1,stroke=0)
    c.saveState()
    c.translate(526,640-162)
    c.rotate(90)
    c.setFillColorRGB(55/255,71/255,79/255)
    c.setFont('FigureSans',13.5)
    c.drawCentredString(0,0,'Mean reply depth')
    c.restoreState()
    # Coordinates are in the verified user-edited artwork, measured from top.
    coords = [(71,96,44),(141,167,69),(201,227,119),
              (318,343,171),(389,414,65),(449,474,69),
              (565,591,177),(636,662,67),(696,721,53)]
    if args.community == 'AITAH':
        coords = [(73,98,101),(143,169,61),(202,228,149),
                  (319,344,152),(390,415,68),(450,475,60),
                  (566,592,147),(637,662,64),(696,721,54)]
    c.setStrokeColorRGB(55/255,71/255,79/255)
    c.setFillColorRGB(55/255,71/255,79/255)
    c.setLineWidth(.75)
    for result,(x1,x2,top) in zip(results,coords):
        if not result['indicator']:
            continue
        y=640-top
        path=c.beginPath(); path.moveTo(x1,y-3); path.lineTo(x1,y)
        path.lineTo(x2,y); path.lineTo(x2,y-3); c.drawPath(path)
        c.setFont('FigureSans',11)
        c.drawCentredString((x1+x2)/2,y+1,result['indicator'])
    c.save()
    page.merge_page(PdfReader(io.BytesIO(buff.getvalue())).pages[0])
    writer=PdfWriter(); writer.add_page(page)
    if not backup.exists():
        backup.write_bytes(original)
    with target.open('wb') as stream:
        writer.write(stream)
    report=dict(community=args.community, source=str(SOURCE), source_sha256=digest,
        artwork_sha256=hashlib.sha256(original).hexdigest(),
        method='Equal-post mean contrasts; CR1 post-cluster sandwich SE; two-sided asymptotic normal Wald p; Holm correction across all nine comparisons. All observed cells retained. No causal interpretation.',
        comparisons=results)
    (out/'significance.json').write_text(json.dumps(report,indent=2)+'\n')
    for r in results:
        print(r['metric'],r['band'],r['contrast'],f"difference={r['difference']:.5g} p_Holm={r['p_holm']:.5g}",r['indicator'] or 'not significant')

if __name__=='__main__':
    main()
