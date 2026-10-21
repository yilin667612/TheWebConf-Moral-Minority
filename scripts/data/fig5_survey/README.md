# Survey Figure 5

Run `python3 scripts/fig5_survey_panels.py` from the paper root with
ReportLab and pypdf installed and `Rscript` available. The script calls
`scripts/fig5_survey_certainty_tests.R` and regenerates
`figures/survey_results_panels.pdf`.

The participant-level CSV is deliberately not included in this repository.
The expected local input is
`../minority-voices-aita/output/80_participants_merged_analysis.csv`.
R reads the literal judgment label `NA` as text, not a missing value.

The source PDF here preserves the original lower-panel vector artwork.
The builder removes its certainty panel and bottom axis title and resizes
mean and p-value labels. Full-sample values are audited against the CSV.

Certainty comparisons are two-sided Welch tests within reported judgment
alignment, with Holm correction across the two comparisons. Grouping uses
the single judgment measured after exposure, not a baseline. Confidence
intervals are unadjusted; the analyses do not establish within-person
change or causal subgroup effects. Aggregate tests and input hashes are
saved in the ignored `output/fig5_survey_final/` directory.
