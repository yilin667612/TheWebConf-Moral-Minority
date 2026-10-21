# Exploratory MM vs Mm comparisons within reported judgment alignment.
# All 16 two-sided Welch p-values are unadjusted; groups are post-exposure.
args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args)==2)
d <- read.csv(args[1], stringsAsFactors=FALSE, na.strings='')
stopifnot(nrow(d)==80, length(unique(d$participant_id))==80,
          all(table(d$treatment)==40),
          all(d$majority_aligned_judgment == (d$judgment_direction==d$majority_judgment)))
metrics <- c('certainty_1_4','comment1_influence','comment2_influence',
             'comment1_agreement','comment2_agreement','comment1_reflection',
             'comment2_reflection','perspective_broadening_mean')
result <- do.call(rbind,lapply(c(1,0),function(a) {
  s <- d[d$majority_aligned_judgment==a,]
  do.call(rbind,lapply(metrics,function(v) {
    mm <- s[s$treatment=='majority_majority',v]
    mixed <- s[s$treatment=='majority_minority',v]
    stopifnot(!anyNA(mm),!anyNA(mixed))
    z <- t.test(mixed,mm,alternative='two.sided',var.equal=FALSE)
    data.frame(alignment=if(a==1) 'majority' else 'minority',metric=v,
               n_MM=length(mm),n_Mm=length(mixed),mean_MM=mean(mm),mean_Mm=mean(mixed),
               difference_Mm_minus_MM=mean(mixed)-mean(mm),
               t=unname(z$statistic),df=unname(z$parameter),p=z$p.value,
               ci95_low=z$conf.int[1],ci95_high=z$conf.int[2])
  }))
}))
stopifnot(nrow(result)==16)
write.csv(result,args[2],row.names=FALSE)
print(result[,c('alignment','metric','p')],digits=9,row.names=FALSE)
