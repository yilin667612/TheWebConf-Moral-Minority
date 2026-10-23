"""Participant-level boxplot redesign of survey Figure 6 (draft, no publish).

Three panels: judgment certainty, range of moral considerations, and comment
ratings. Each uses reported judgment alignment x assigned treatment (4 groups).
Comment 1 and comment 2 remain separate repeated measures, never pooled as
independent participants. Alignment is measured after exposure.

Boxes: linear-interpolated quartiles; median line; 1.5-IQR Tukey whiskers.
All observations are drawn, jittered horizontally only. Diamonds mark means.
No inferential tests are added or changed by this visualization script.
Run with bundled Python (numpy, reportlab, pypdf); Poppler renders previews.
"""

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess

import numpy as np
from pypdf import PdfReader
from reportlab.lib.colors import HexColor, Color
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
INK = "#37474F"
BLUE, PINK = "#5770DB", "#C6538C"
GROUPS = [
    ("majority", "1", "MM", "majority_majority", "Highly Scored", BLUE, False),
    ("majority", "1", "Mm", "majority_minority", "Balanced", PINK, False),
    ("minority", "0", "MM", "majority_majority", "Highly Scored", BLUE, True),
    ("minority", "0", "Mm", "majority_minority", "Balanced", PINK, True),
]
METRICS = ["certainty_1_4", "perspective_broadening_mean",
           "comment1_influence", "comment2_influence",
           "comment1_agreement", "comment2_agreement",
           "comment1_reflection", "comment2_reflection"]
COMMENT_METRICS = [
    ("Influence", "comment1_influence", "comment2_influence"),
    ("Agreement", "comment1_agreement", "comment2_agreement"),
    ("New moral considerations", "comment1_reflection", "comment2_reflection"),
]


def lighten(hex_color, amount):
    color = HexColor(hex_color)
    return Color(*(v * (1 - amount) + amount for v in (color.red, color.green, color.blue)))


def label(c, x, y, text, size=8, align="left", bold=False):
    c.setFillColor(HexColor(INK))
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    {"left": c.drawString, "center": c.drawCentredString,
     "right": c.drawRightString}[align](x, y, text)


def box_fill(c, x, y, w, h, color, hatched):
    """Same treatment hue, with pale diagonal hatching for minority alignment."""
    c.setFillColor(lighten(color, .88 if hatched else .66))
    c.setStrokeColor(HexColor(color))
    c.setLineWidth(.8)
    c.rect(x, y, w, h, stroke=1, fill=1)
    if hatched and h > 0:
        c.saveState()
        clip = c.beginPath()
        clip.rect(x, y, w, h)
        c.clipPath(clip, stroke=0, fill=0)
        c.setStrokeColor(lighten(color, .45))
        c.setLineWidth(.32)
        for offset in np.arange(-h, w + 5, 4):
            c.line(x + offset, y, x + offset + h, y + h)
        c.restoreState()


def legend(c, width, y, cells):
    # Two columns, each containing the two treatments within one alignment.
    for i, group in enumerate(GROUPS):
        alignment, _, condition, _, treatment_label, color, hatched = group
        x = 15 + (width / 2) * (i // 2)
        yy = y - (i % 2) * 13
        box_fill(c, x, yy - 1, 11, 7, color, hatched)
        n = cells[alignment, condition, "certainty_1_4"]["n"]
        label(c, x + 16, yy,
              f"Agrees with {alignment}: {treatment_label} (n = {n})", 7.3)


def axes(c, x, y, width, height, upper):
    def sy(value):
        return y + (value - .8) / (upper - .6) * height
    c.setLineWidth(.35)
    for value in range(1, upper + 1):
        yy = sy(value)
        c.setStrokeColor(HexColor("#E4E8EB"))
        c.line(x, yy, x + width, yy)
        label(c, x - 6, yy - 2.7, str(value), 8, "right")
    c.setStrokeColor(HexColor(INK))
    c.setLineWidth(.6)
    c.line(x, y, x, y + height)
    return sy


def draw_box(c, center, width, sy, values, stats, group, seed):
    color, hatched = group[-2:]
    c.setStrokeColor(HexColor(color))
    c.setLineWidth(.7)
    c.line(center, sy(stats["whisker_low"]), center, sy(stats["whisker_high"]))
    for key in ("whisker_low", "whisker_high"):
        c.line(center - width * .25, sy(stats[key]),
               center + width * .25, sy(stats[key]))
    box_fill(c, center - width / 2, sy(stats["q1"]), width,
             sy(stats["q3"]) - sy(stats["q1"]), color, hatched)
    # All points are shown once, including outliers; no vertical jitter.
    rng = random.Random(seed)
    c.saveState()
    c.setFillColor(HexColor(color))
    c.setFillAlpha(.48)
    for value in values:
        dx = rng.uniform(-.36, .36) * width
        c.circle(center + dx, sy(value), 1.15, stroke=0, fill=1)
    c.restoreState()
    c.setStrokeColor(HexColor(INK))
    c.setLineWidth(.95)
    c.line(center - width / 2, sy(stats["median"]),
           center + width / 2, sy(stats["median"]))
    # White diamond with dark outline: mean, not the median.
    yy, radius = sy(stats["mean"]), 2.5
    diamond = c.beginPath()
    diamond.moveTo(center, yy + radius)
    diamond.lineTo(center + radius, yy)
    diamond.lineTo(center, yy - radius)
    diamond.lineTo(center - radius, yy)
    diamond.close()
    c.setFillColor(HexColor("#FFFFFF"))
    c.setLineWidth(.65)
    c.drawPath(diamond, fill=1, stroke=1)


def single_metric(c, frame, metric, upper, title, samples, cells, renderer=draw_box):
    x, y, width, height = frame
    label(c, x, y + height + 12, title, 9.3)
    sy = axes(c, x, y, width, height, upper)
    fractions = [.16, .34, .66, .84]
    for i, (fraction, group) in enumerate(zip(fractions, GROUPS)):
        key = (group[0], group[2], metric)
        renderer(c, x + fraction * width, width * .11, sy,
                 samples[key], cells[key], group, 157 + 29 * i)
    for fraction, alignment in ((.25, "majority"), (.75, "minority")):
        label(c, x + width * fraction, y - 14, "Agrees with " + alignment, 8, "center")


def comment_panel(c, frame, title, samples, cells, renderer=draw_box):
    x, y, width, height = frame
    label(c, x, y + height + 24, title, 9.3)
    sy = axes(c, x, y, width, height, 5)
    gap = 18
    region = (width - gap) / 2
    # Primary grouping is comment identity: C1 on the left, C2 on the right.
    # Within each, the three metrics use the same four alignment-treatment boxes.
    c.setStrokeColor(HexColor("#C8D0D5"))
    c.setLineWidth(.5)
    c.setDash(2, 3)
    c.line(x + width / 2, y - 24, x + width / 2, y + height + 13)
    c.setDash()
    for j in range(2):
        left = x + j * (region + gap)
        label(c, left + region / 2, y + height + 5, f"C{j + 1}", 9, "center", bold=True)
        for m, (name, metric1, metric2) in enumerate(COMMENT_METRICS):
            metric = (metric1, metric2)[j]
            center = left + region * (m + .5) / 3
            spacing = region / 3 * .185
            for i, group in enumerate(GROUPS):
                key = (group[0], group[2], metric)
                renderer(c, center + (i - 1.5) * spacing,
                         spacing * .75, sy, samples[key], cells[key], group,
                         503 + 83 * m + 17 * j + i)
            if name == "New moral considerations":
                label(c, center, y - 12, "New moral", 8, "center")
                label(c, center, y - 22, "considerations", 8, "center")
            else:
                label(c, center, y - 12, name, 8, "center")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT.parent /
                        "minority-voices-aita/output/80_participants_merged_analysis.csv")
    parser.add_argument("--out", type=Path, default=ROOT / "output/pdf/fig6_alignment_boxplots")
    parser.add_argument("--baseline", type=Path, default=ROOT /
                        "output/pdf/fig5_alignment_combined/summary.json")
    parser.add_argument("--comment-only", action="store_true",
                        help="Regenerate the combined figure and panel (c), leaving standalone (a)/(b) unchanged")
    args = parser.parse_args()
    rows = list(csv.DictReader(args.source.open(newline="", encoding="utf-8-sig")))
    assert len(rows) == len({r["participant_id"] for r in rows}) == 80
    assert all(r["majority_aligned_judgment"] ==
               str(int(r["judgment_direction"] == r["majority_judgment"])) for r in rows)
    samples, cells = {}, {}
    for group in GROUPS:
        alignment, code, condition, treatment = group[:4]
        selected = [r for r in rows if r["treatment"] == treatment
                    and r["majority_aligned_judgment"] == code]
        for metric in METRICS:
            values = [float(r[metric]) for r in selected]
            upper = 4 if metric == "certainty_1_4" else 7 if metric == "perspective_broadening_mean" else 5
            assert values and all(math.isfinite(v) and 1 <= v <= upper for v in values)
            q1, median, q3 = np.quantile(values, [.25, .5, .75], method="linear")
            iqr = q3 - q1
            inside = [v for v in values if q1 - 1.5 * iqr <= v <= q3 + 1.5 * iqr]
            key = (alignment, condition, metric)
            samples[key] = values
            cells[key] = dict(n=len(values), mean=float(np.mean(values)),
                              q1=float(q1), median=float(median), q3=float(q3),
                              whisker_low=min(inside), whisker_high=max(inside))
    assert [cells[g[0], g[2], "certainty_1_4"]["n"] for g in GROUPS] == [30, 31, 10, 9]
    source_hash = hashlib.sha256(args.source.read_bytes()).hexdigest()
    baseline_verified = False
    if args.baseline.exists():
        baseline = json.loads(args.baseline.read_text())
        assert source_hash == baseline["source_sha256"], "Source differs from existing Figure 6"
        for old in baseline["cells"]:
            new = cells[old["alignment"], old["condition"], old["metric"]]
            assert new["n"] == old["n"] and abs(new["mean"] - old["mean"]) < 1e-12
        baseline_verified = True

    args.out.mkdir(parents=True, exist_ok=True)
    outputs = []

    # Combined figure: two compact reader-level panels above one wide comment panel.
    path = args.out / "survey_alignment_boxplots.pdf"
    c = canvas.Canvas(str(path), pagesize=(540, 360))
    c.setTitle("Survey responses by reported judgment alignment: boxplots")
    legend(c, 540, 347, cells)
    single_metric(c, (28, 205, 228, 101), METRICS[0], 4,
                  "(a) Judgment certainty", samples, cells)
    single_metric(c, (296, 205, 228, 101), METRICS[1], 7,
                  "(b) Range of moral considerations", samples, cells)
    comment_panel(c, (28, 33, 496, 119), "(c) Comment-level ratings", samples, cells)
    c.save()
    outputs.append(path)

    # Independently usable panels retain exactly the same four-entry legend.
    for name, metric, upper, title in (
        ("survey_judgment_certainty_boxplot", METRICS[0], 4, "(a) Judgment certainty"),
        ("survey_moral_range_boxplot", METRICS[1], 7, "(b) Range of moral considerations"),
    ):
        if args.comment_only:
            continue
        path = args.out / f"{name}.pdf"
        c = canvas.Canvas(str(path), pagesize=(540, 217))
        c.setTitle(title[4:])
        legend(c, 540, 204, cells)
        single_metric(c, (28, 24, 496, 138), metric, upper, title, samples, cells)
        c.save()
        outputs.append(path)
    path = args.out / "survey_comment_ratings_boxplot.pdf"
    c = canvas.Canvas(str(path), pagesize=(540, 245))
    c.setTitle("Comment-level ratings by reported judgment alignment")
    legend(c, 540, 232, cells)
    comment_panel(c, (28, 33, 496, 145), "(c) Comment-level ratings", samples, cells)
    c.save()
    outputs.append(path)

    summary = dict(source=str(args.source), source_sha256=source_hash,
                   baseline_means_and_counts_verified=baseline_verified,
                   observation_unit="participant; C1/C2 retained separately",
                   groups="Reported judgment alignment after exposure x randomized treatment",
                   box_definition="Q1/Q3: linear quantiles; median line; Tukey 1.5-IQR whiskers",
                   markers="All participants: dots, horizontal-only seeded jitter; mean: white diamond",
                   tests="None added or changed; descriptive redesign",
                   cells=[dict(alignment=k[0], condition=k[1], metric=k[2], **v)
                          for k, v in cells.items()])
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    poppler = Path("/Users/minjeongshin/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm")
    fontconfig = args.out / "fontconfig.xml"
    fontconfig.write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd">'
                          '<fontconfig><dir>/System/Library/Fonts/Supplemental</dir>'
                          '<cachedir>/tmp/survey-font-cache</cachedir>'
                          '<alias><family>Helvetica</family><prefer><family>Arial</family>'
                          '</prefer></alias></fontconfig>')
    for path in outputs:
        document = PdfReader(path)
        assert len(document.pages) == 1
        extracted = document.pages[0].extract_text()
        assert all(t in extracted for t in ("Highly Scored", "Balanced",
                                             "Agrees with majority", "Agrees with minority"))
        subprocess.run([str(poppler), "-scale-to", "2100", "-png", "-singlefile",
                        str(path), str(path.with_suffix(""))], check=True,
                       env={**os.environ, "FONTCONFIG_FILE": str(fontconfig.resolve())})
        print(path)
    print("Verified 32 group-metric distributions; existing means/counts match:", baseline_verified)


if __name__ == "__main__":
    main()
