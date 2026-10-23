# Survey Figure 6

Run `python3 scripts/fig6_survey_alignment_dotwhisker.py --wide --publish`
from the paper root with the bundled Python (NumPy, ReportLab, pypdf).
This replaces `figures/survey_results_panels.pdf` with a three-panel row of
means and pointwise 95% participant-bootstrap confidence intervals.
The compact row is 516 by 140 pt, with 5.2-pt two-decimal mean labels placed
outside their confidence intervals to avoid data marks and other labels.
Bold C1/C2 headings sit inside the top-left corner of each region. Panel (c)
uses the short display label `New considerations` for the reflection items.
Panels (b) and (c) space the four group estimates 8 pt apart, with item centers
42 pt apart (within C1/C2 for panel c). Panel (c) has 274 pt of plotting width,
retaining the overall figure width and font sizes.
Omit `--publish` to generate a preview only. The builder imports shared layout
helpers from `scripts/fig6_survey_alignment_boxplots.py`.

Panel (b) reports `perspective_broadening_1`, `_2`, and `_3` separately:
considering multiple sides, new considerations, and why someone might reach
an alternative judgment. Each item retains all four treatment/alignment
groups, with means and pointwise 95% CIs. The existing
`perspective_broadening_mean` is verified as the unweighted three-item mean
for every participant and retained only as a supplementary score. No item
responses are missing. The main manuscript describes item-level differences
without new significance tests; the largest observed gap across all 80
readers concerns considering alternative judgments. This is not a test of
differences in treatment effects across items or a claim about every subgroup.

The participant-level CSV is deliberately not included in this repository.
The expected local input is
`../minority-voices-aita/output/80_participants_merged_analysis.csv`.
R reads the literal judgment label `NA` as text, not a missing value.

The previous bar and boxplot builders preserve earlier designs. The published
figure has no asterisks: circles/triangles show majority/minority alignment;
blue/magenta show Highly Scored/Balanced. Condition names are display labels;
the source treatment values and statistical output keys remain unchanged.
Highly Scored displays two majority comments; Balanced displays one majority
and one minority comment. Group counts are 30/31 for majority alignment and
10/9 for minority alignment, in Highly Scored/Balanced order.
The exact-p-value appendix table is temporarily
omitted from the manuscript; its component and computed CSV are retained.
Subgroup means and sample sizes are audited against the existing R results.

Existing hypothesis tests use two-sided Welch tests with unadjusted p-values and are
interpreted as exploratory given the multiple comparisons. Certainty
comparisons group readers by the single reported judgment measured after
exposure, not a baseline. Confidence intervals are also unadjusted; the
analyses do not establish within-person change or causal subgroup effects.
The 20,000 bootstrap resamples (seed 20261023) draw whole participant rows
within condition-by-alignment groups, preserving dependence across outcomes.
The percentile intervals do not resample scenarios and are conditional on the
selected stimuli. Means, intervals, input hash, and previews are saved in
`output/pdf/fig6_alignment_dotwhisker/`. Existing Welch tests are retained in
`output/pdf/fig5_alignment_combined/alignment_tests.csv`.
`components/tab_survey_alignment_tests.tex` reports every p-value, rounded
to three decimals (values below .001 are reported as <.001).

The procedure diagram is generated with bundled Python:
`python3 scripts/fig_survey_procedure.py --publish`.
Its editable source preserves the previous diagram's structure and content,
with the same descriptive condition names used in the results figure.
