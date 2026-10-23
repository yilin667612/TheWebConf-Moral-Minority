"""Survey Figure 6: means and participant-bootstrap 95% confidence intervals.

The main figure separates (a) certainty, (b) three discussion-level items,
and (c) C1/C2 first, with three comment-level metrics in each.
Colors identify treatments; circles/triangles identify reported alignment.

Resamples whole participant rows within the four treatment-by-alignment groups.
The same bootstrap indices are used for all outcomes, preserving C1/C2
dependence. Intervals are pointwise percentile CIs, not multiplicity-adjusted.
They describe these observed post-exposure subgroups and selected scenarios;
they do not identify causal treatment effects within alignment strata or
uncertainty over a population of new scenarios. No p-values are calculated.

Use --wide for the compact three-panel row; --publish updates the manuscript
figure. The three-item mean remains in the summary and legacy preview panels
as a supplementary result. The previous boxplot PDFs are left untouched.
"""

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
from pypdf import PdfReader
from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from fig6_survey_alignment_boxplots import (
    ROOT, GROUPS, METRICS as LEGACY_METRICS, COMMENT_METRICS, INK,
    label, single_metric, comment_panel,
)

DISCUSSION_ITEMS = [
    ("perspective_broadening_1", ("Multiple", "sides"),
     "The discussion made me consider more than one side of the situation."),
    ("perspective_broadening_2", ("New", "considerations"),
     "The discussion made me think about considerations that had not initially occurred to me."),
    ("perspective_broadening_3", ("Alternative", "judgments"),
     "The discussion made me think about why someone might reach a different conclusion."),
]
METRICS = LEGACY_METRICS + [item[0] for item in DISCUSSION_ITEMS]


def marker(c, x, y, color, minority, radius=3.2):
    c.setFillColor(HexColor(color))
    c.setStrokeColor(HexColor("#FFFFFF"))
    c.setLineWidth(.5)
    if minority:
        # Equilateral triangle centered at its centroid.
        path = c.beginPath()
        path.moveTo(x, y + radius * 1.25)
        path.lineTo(x + radius * 1.08, y - radius * .625)
        path.lineTo(x - radius * 1.08, y - radius * .625)
        path.close()
        c.drawPath(path, fill=1, stroke=1)
    else:
        c.circle(x, y, radius, fill=1, stroke=1)


def draw_estimate(c, center, width, sy, values, stats, group, seed):
    del width, values, seed  # Shared layout signature; no raw dots or jitter.
    color, minority = group[-2:]
    c.setStrokeColor(HexColor(color))
    c.setLineWidth(1)
    c.line(center, sy(stats["ci_low"]), center, sy(stats["ci_high"]))
    for bound in ("ci_low", "ci_high"):
        c.line(center - 2.8, sy(stats[bound]), center + 2.8, sy(stats[bound]))
    marker(c, center, sy(stats["mean"]), color, minority)


def legend(c, width, y, cells):
    for i, group in enumerate(GROUPS):
        alignment, _, condition, _, treatment_label, color, minority = group
        x, yy = 15 + width / 2 * (i // 2), y - i % 2 * 13
        marker(c, x + 5.5, yy + 2.5, color, minority, 3)
        n = cells[alignment, condition, METRICS[0]]["n"]
        label(c, x + 16, yy,
              f"Agrees with {alignment}: {treatment_label} (n = {n})", 7.3)


def wide_figure(path, cells):
    """Paper-width row: one certainty outcome, three discussion items, six ratings."""
    c = canvas.Canvas(str(path), pagesize=(516, 140))
    c.setTitle("Survey responses: Highly Scored and Balanced")
    c.setSubject("Means and pointwise 95% whole-participant bootstrap confidence intervals")
    legend_labels = []
    for group in GROUPS:
        alignment, _, condition, _, treatment, _, _ = group
        n = cells[alignment, condition, METRICS[0]]["n"]
        legend_labels.append(f"Agrees with {alignment}: {treatment} (n = {n})")
    # Center the complete two-column legend using its actual marker/text bounds.
    legend_left = -2.75
    legend_right = max(258 * (i // 2) + 7 + stringWidth(text, "Helvetica", 6.8)
                       for i, text in enumerate(legend_labels))
    legend_start = (516 - (legend_right - legend_left)) / 2 - legend_left
    for i, group in enumerate(GROUPS):
        color, minority = group[-2:]
        x, yy = legend_start + 258 * (i // 2), 133 - 10 * (i % 2)
        marker(c, x, yy + 2, color, minority, 2.5)
        label(c, x + 7, yy, legend_labels[i], 6.8)

    def panel_axes(x, width, upper):
        y, height = 16, 86
        sy = lambda value: y + (value - .8) / (upper - .6) * height
        ticks = [1, 3, 5, 7] if upper == 7 else range(1, upper + 1)
        for value in ticks:
            yy = sy(value)
            c.setStrokeColor(HexColor("#E4E8EB"))
            c.setLineWidth(.3)
            c.line(x, yy, x + width, yy)
            label(c, x - 4, yy - 2.1, str(value), 6.5, "right")
        c.setStrokeColor(HexColor(INK))
        c.setLineWidth(.5)
        c.line(x, y, x, y + height)
        return sy

    def point(x, sy, metric, group, annotations):
        stats = cells[group[0], group[2], metric]
        color, minority = group[-2:]
        c.setStrokeColor(HexColor(color))
        c.setLineWidth(.7)
        c.line(x, sy(stats["ci_low"]), x, sy(stats["ci_high"]))
        for bound in ("ci_low", "ci_high"):
            c.line(x - 1.6, sy(stats[bound]), x + 1.6, sy(stats[bound]))
        marker(c, x, sy(stats["mean"]), color, minority, 2.25)
        annotations.append(dict(x=x, mean=stats["mean"],
                                mean_y=sy(stats["mean"]),
                                low=sy(stats["ci_low"]), high=sy(stats["ci_high"])))

    def annotate_means(annotations, left, width):
        """Place values outside their CI, avoiding other labels and data marks."""
        size = 5.2
        # Preserve the established label positions while shrinking the text.
        layout_size = 5.8
        obstacles, occupied = [], []
        for item in annotations:
            x, low, high, mean_y = item["x"], item["low"], item["high"], item["mean_y"]
            obstacles.extend([
                (x - .45, low, x + .45, high),
                (x - 2, low - .6, x + 2, low + .6),
                (x - 2, high - .6, x + 2, high + .6),
                (x - 2.9, mean_y - 2.9, x + 2.9, mean_y + 3.4),
            ])

        def overlaps(a, b):
            return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]

        for i, item in enumerate(annotations):
            value = f"{item['mean']:.2f}"
            half_width = stringWidth(value, "Helvetica", layout_size) / 2
            # Alternating above/below keeps closely spaced treatment pairs legible.
            preferred = ("above", "below") if i % 2 == 0 else ("below", "above")
            candidates = []
            for extra in range(0, 35, 2):
                for side in preferred:
                    baseline = (item["high"] + 3 + extra if side == "above"
                                else item["low"] - 6.8 - extra)
                    box = (item["x"] - half_width - .2, baseline - 1.4,
                           item["x"] + half_width + .2, baseline + 4.6)
                    if (box[0] >= left and box[2] <= left + width and
                            box[1] >= 17 and box[3] <= 101 and
                            not any(overlaps(box, b) for b in obstacles + occupied)):
                        candidates.append((baseline, box))
                if candidates:
                    break
            assert candidates, f"No unobstructed mean label position for {value} at {item['x']}"
            baseline, box = candidates[0]
            occupied.append(box)
            c.setFillColor(HexColor("#FFFFFF"))
            c.rect(box[0], box[1], box[2] - box[0], box[3] - box[1], fill=1, stroke=0)
            label(c, item["x"], baseline, value, size, "center")

    x, width = 16, 60
    label(c, x - 10, 111, "(a) Judgment certainty", 7.1)
    sy = panel_axes(x, width, 4)
    annotations = []
    for fraction, group in zip([.16, .34, .66, .84], GROUPS):
        point(x + width * fraction, sy, METRICS[0], group, annotations)
    annotate_means(annotations, x, width)
    for fraction, alignment in ((1 / 6, "Majority"), (5 / 6, "Minority")):
        label(c, x + width * fraction, 9, "Agrees with", 6.5, "center")
        label(c, x + width * fraction, 2, alignment, 6.5, "center")

    # Keep paper width fixed, using tighter panel gaps to give (c) more room.
    dot_spacing = 8.0
    x, width = 90, 126
    item_spacing = width / len(DISCUSSION_ITEMS)
    label(c, x, 111, "(b) Discussion-level considerations", 7.1)
    sy = panel_axes(x, width, 7)
    annotations = []
    for m, (metric, lines, _) in enumerate(DISCUSSION_ITEMS):
        center = x + item_spacing * (m + .5)
        for i, group in enumerate(GROUPS):
            point(center + (i - 1.5) * dot_spacing, sy, metric, group, annotations)
        for j, text in enumerate(lines):
            label(c, center, 9 - j * 7, text, 6.4, "center")
    annotate_means(annotations, x, width)

    x, width = 233, 274
    label(c, x, 111, "(c) Comment-level ratings", 7.1)
    sy = panel_axes(x, width, 5)
    gap, region = 12, (width - 12) / 2
    c.setStrokeColor(HexColor("#BFC8CE"))
    c.setLineWidth(.4)
    c.setDash(1.8, 2.4)
    c.line(x + width / 2, 1, x + width / 2, 102)
    c.setDash()
    annotations = []
    for j in range(2):
        left = x + j * (region + gap)
        # Put the subgroup heading inside the plotting area, over an empty corner.
        c.setFillColor(HexColor("#FFFFFF"))
        c.rect(left + 2, 92, 13, 9, fill=1, stroke=0)
        label(c, left + 4, 94, f"C{j + 1}", 7, bold=True)
        for m, (name, metric1, metric2) in enumerate(COMMENT_METRICS):
            # Match (b)'s between-item spacing as well as its within-item dots.
            center = left + region / 2 + (m - 1) * item_spacing
            metric = (metric1, metric2)[j]
            for i, group in enumerate(GROUPS):
                point(center + (i - 1.5) * dot_spacing, sy, metric, group, annotations)
            if name == "New moral considerations":
                label(c, center, 9, "New", 6.4, "center")
                label(c, center, 2, "considerations", 6.4, "center")
            else:
                label(c, center, 9, name, 6.4, "center")
    annotate_means(annotations, x, width)
    c.save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT.parent /
                        "minority-voices-aita/output/80_participants_merged_analysis.csv")
    parser.add_argument("--out", type=Path, default=ROOT / "output/pdf/fig6_alignment_dotwhisker")
    parser.add_argument("--baseline", type=Path, default=ROOT /
                        "output/pdf/fig5_alignment_combined/summary.json")
    parser.add_argument("--resamples", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20261023)
    parser.add_argument("--wide", action="store_true", help="Render a compact single-row paper figure")
    parser.add_argument("--publish", action="store_true", help="Publish the wide figure to figures/survey_results_panels.pdf")
    args = parser.parse_args()
    assert args.resamples >= 1000
    assert not args.publish or args.wide, "Use --wide when publishing the manuscript figure"
    rows = list(csv.DictReader(args.source.open(newline="", encoding="utf-8-sig")))
    assert len(rows) == len({r["participant_id"] for r in rows}) == 80
    assert all(r["majority_aligned_judgment"] ==
               str(int(r["judgment_direction"] == r["majority_judgment"])) for r in rows)
    assert all(abs(float(r["perspective_broadening_mean"]) -
                   sum(float(r[item[0]]) for item in DISCUSSION_ITEMS) / 3) < 1e-12
               for r in rows), "The retained composite must equal the three-item mean"
    samples, cells = {}, {}
    for group, group_seed in zip(GROUPS, np.random.SeedSequence(args.seed).spawn(4)):
        alignment, code, condition, treatment = group[:4]
        selected = [r for r in rows if r["treatment"] == treatment
                    and r["majority_aligned_judgment"] == code]
        matrix = np.array([[float(r[metric]) for metric in METRICS] for r in selected])
        upper = np.array([4, 7, 5, 5, 5, 5, 5, 5, 7, 7, 7])
        assert np.all(np.isfinite(matrix)) and np.all((matrix >= 1) & (matrix <= upper))
        n = len(matrix)
        indices = np.random.default_rng(group_seed).integers(n, size=(args.resamples, n))
        bootstrap_means = matrix[indices].mean(axis=1)
        low, high = np.quantile(bootstrap_means, [.025, .975], axis=0, method="linear")
        for m, metric in enumerate(METRICS):
            key = (alignment, condition, metric)
            samples[key] = matrix[:, m].tolist()
            cells[key] = dict(n=n, mean=float(matrix[:, m].mean()),
                              ci_low=float(low[m]), ci_high=float(high[m]))
            assert 1 <= low[m] <= cells[key]["mean"] <= high[m] <= upper[m]
    assert [cells[g[0], g[2], METRICS[0]]["n"] for g in GROUPS] == [30, 31, 10, 9]
    source_hash = hashlib.sha256(args.source.read_bytes()).hexdigest()
    baseline = json.loads(args.baseline.read_text())
    assert source_hash == baseline["source_sha256"]
    for old in baseline["cells"]:
        new = cells[old["alignment"], old["condition"], old["metric"]]
        assert new["n"] == old["n"] and abs(new["mean"] - old["mean"]) < 1e-12

    args.out.mkdir(parents=True, exist_ok=True)
    outputs = []
    if args.wide:
        path = args.out / "survey_alignment_dotwhisker_wide.pdf"
        wide_figure(path, cells)
        outputs.append(path)
    else:
        render_preview_panels(args.out, samples, cells, outputs)

    overall_items = []
    for metric, _, wording in DISCUSSION_ITEMS:
        means = {treatment: float(np.mean([float(r[metric]) for r in rows
                                          if r["treatment"] == treatment]))
                 for treatment in ("majority_majority", "majority_minority")}
        overall_items.append(dict(metric=metric, wording=wording,
                                  highly_scored_mean=means["majority_majority"],
                                  balanced_mean=means["majority_minority"],
                                  balanced_minus_highly_scored=
                                  means["majority_minority"] - means["majority_majority"]))
    summary = dict(source=str(args.source), source_sha256=source_hash,
                   baseline_means_and_counts_verified=True,
                   composite_verified_as_unweighted_three_item_mean=True,
                   main_discussion_metrics=[item[0] for item in DISCUSSION_ITEMS],
                   supplementary_composite="perspective_broadening_mean",
                   overall_discussion_items=overall_items,
                   resamples=args.resamples, seed=args.seed,
                   resampling="Whole participant rows, within treatment x reported alignment; shared indices across outcomes",
                   interval="Pointwise 95% percentile bootstrap confidence interval of the mean; no multiplicity adjustment",
                   scope="Descriptive post-exposure subgroups for the selected scenarios; not causal subgroup treatment effects",
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
        pdf = PdfReader(path)
        assert len(pdf.pages) == 1
        extracted = pdf.pages[0].extract_text()
        assert all(t in extracted for t in ("Highly Scored", "Balanced",
                                             "Agrees with majority", "Agrees with minority"))
        subprocess.run([str(poppler), "-scale-to", "2400", "-png", "-singlefile",
                        str(path), str(path.with_suffix(""))], check=True,
                       env={**os.environ, "FONTCONFIG_FILE": str(fontconfig.resolve())})
        print(path)
    if args.publish:
        target = ROOT / "figures/survey_results_panels.pdf"
        shutil.copyfile(outputs[0], target)
        print(target)
    print(f"All 32 legacy means/counts match; 12 item-level group means added; "
          f"{args.resamples:,} whole-participant bootstrap resamples per group.")


def render_preview_panels(out, samples, cells, outputs):
    path = out / "survey_alignment_dotwhisker.pdf"
    c = canvas.Canvas(str(path), pagesize=(540, 360))
    c.setTitle("Survey means and 95% participant-bootstrap confidence intervals")
    c.setSubject("Reported judgment alignment after exposure; pointwise percentile intervals")
    legend(c, 540, 347, cells)
    single_metric(c, (28, 205, 228, 101), METRICS[0], 4,
                  "(a) Judgment certainty", samples, cells, draw_estimate)
    single_metric(c, (296, 205, 228, 101), METRICS[1], 7,
                  "(b) Range of moral considerations", samples, cells, draw_estimate)
    comment_panel(c, (28, 33, 496, 119), "(c) Comment-level ratings",
                  samples, cells, draw_estimate)
    c.save()
    outputs.append(path)

    for name, metric, upper, title in (
        ("survey_judgment_certainty_dotwhisker", METRICS[0], 4, "(a) Judgment certainty"),
        ("survey_moral_range_dotwhisker", METRICS[1], 7, "(b) Range of moral considerations"),
    ):
        path = out / f"{name}.pdf"
        c = canvas.Canvas(str(path), pagesize=(540, 217))
        c.setTitle(title[4:] + ": means and 95% participant-bootstrap CIs")
        legend(c, 540, 204, cells)
        single_metric(c, (28, 24, 496, 138), metric, upper, title, samples, cells, draw_estimate)
        c.save()
        outputs.append(path)
    path = out / "survey_comment_ratings_dotwhisker.pdf"
    c = canvas.Canvas(str(path), pagesize=(540, 245))
    c.setTitle("Comment-level means and 95% participant-bootstrap CIs")
    legend(c, 540, 232, cells)
    comment_panel(c, (28, 33, 496, 145), "(c) Comment-level ratings",
                  samples, cells, draw_estimate)
    c.save()
    outputs.append(path)

if __name__ == "__main__":
    main()
