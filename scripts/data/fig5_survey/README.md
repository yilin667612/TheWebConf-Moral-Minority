# Survey Figure 5

Run `python3 scripts/fig5_survey_alignment_combined.py --publish` from the
paper root with ReportLab installed and `Rscript` available. This replaces
`figures/survey_results_panels.pdf` with means for all outcomes, split by
reported judgment alignment. Omit `--publish` to generate a preview only.
The script calls `scripts/fig5_survey_alignment_tests.R` for all 16 tests.

The participant-level CSV is deliberately not included in this repository.
The expected local input is
`../minority-voices-aita/output/80_participants_merged_analysis.csv`.
R reads the literal judgment label `NA` as text, not a missing value.

The source PDF and `fig5_survey_panels.py` preserve the older panel design;
they are not used by the current builder. The current figure shows asterisks
for unadjusted two-sided Welch p-values (* < .05, ** < .01, *** < .001),
outside each MM--Mm pair. The exact-p-value appendix table is temporarily
omitted from the manuscript; its component and computed CSV are retained.
Its subgroup means and sample sizes
are audited against the R results and reconcile with full-sample means.

All comparisons use two-sided Welch tests with unadjusted p-values and are
interpreted as exploratory given the multiple comparisons. Certainty
comparisons group readers by the single reported judgment measured after
exposure, not a baseline. Confidence intervals are also unadjusted; the
analyses do not establish within-person change or causal subgroup effects.
Aggregate tests (`alignment_tests.csv`), means, input hashes, and previews
are saved in the ignored `output/pdf/fig5_alignment_combined/` directory.
`components/tab_survey_alignment_tests.tex` reports every p-value, rounded
to three decimals (values below .001 are reported as <.001).
