# Exploratory conditional comparisons with unadjusted p-values.
# Alignment uses the single reported judgment, measured after exposure.
# Run: Rscript scripts/fig5_survey_certainty_tests.R [source.csv] [output_dir]
args <- commandArgs(trailingOnly=TRUE)
source <- if(length(args)>0) args[1] else '../minority-voices-aita/output/80_participants_merged_analysis.csv'
out <- if(length(args)>1) args[2] else 'output/fig5_survey_final'
dir.create(out, recursive=TRUE, showWarnings=FALSE)
# NA is a substantive judgment label, not a missing-value marker.
d <- read.csv(source, stringsAsFactors=FALSE, na.strings='')
stopifnot(nrow(d)==80, length(unique(d$participant_id))==80,
          all(table(d$treatment)==40), !anyNA(d$certainty_1_4),
          all(d$certainty_1_4 %in% 1:4),
          all(d$majority_aligned_judgment == (d$judgment_direction==d$majority_judgment)))
tests <- lapply(c(1,0), function(a) {
  s <- d[d$majority_aligned_judgment==a,]
  mm <- s$certainty_1_4[s$treatment=='majority_majority']
  mixed <- s$certainty_1_4[s$treatment=='majority_minority']
  test <- t.test(mixed, mm, alternative='two.sided', var.equal=FALSE)
  pooled_sd <- sqrt(((length(mm)-1)*var(mm)+(length(mixed)-1)*var(mixed))/(length(mm)+length(mixed)-2))
  df_g <- length(mm)+length(mixed)-2
  J <- exp(lgamma(df_g/2)-log(sqrt(df_g/2))-lgamma((df_g-1)/2))
  data.frame(alignment=if(a==1) 'majority' else 'minority',
             n_MM=length(mm), n_Mm=length(mixed), mean_MM=mean(mm), mean_Mm=mean(mixed),
             sd_MM=sd(mm), sd_Mm=sd(mixed), difference_Mm_minus_MM=mean(mixed)-mean(mm),
             t=unname(test$statistic), df=unname(test$parameter), p=test$p.value,
             ci95_low=test$conf.int[1], ci95_high=test$conf.int[2],
             hedges_g=J*(mean(mixed)-mean(mm))/pooled_sd)
})
result <- do.call(rbind, tests)
write.csv(result, file.path(out,'certainty_tests.csv'), row.names=FALSE)
print(result, digits=7, row.names=FALSE)
# Audit the pre-existing full-sample values, without changing their test family.
measures <- c('certainty_1_4','comment1_influence','comment2_influence',
              'comment1_agreement','comment2_agreement','comment1_reflection',
              'comment2_reflection','perspective_broadening_mean')
stopifnot(all(measures %in% names(d)))
audit <- do.call(rbind,lapply(measures,function(v) {
  mm <- d[d$treatment=='majority_majority',v]
  mixed <- d[d$treatment=='majority_minority',v]
  stopifnot(length(mm)==40,length(mixed)==40,!anyNA(mm),!anyNA(mixed))
  test <- t.test(mixed,mm)
  data.frame(measure=v,mean_MM=mean(mm),mean_Mm=mean(mixed),p=test$p.value)
}))
write.csv(audit,file.path(out,'full_sample_audit.csv'),row.names=FALSE)
print(audit,digits=7,row.names=FALSE)
capture.output(sessionInfo(),file=file.path(out,'R_session.txt'))
