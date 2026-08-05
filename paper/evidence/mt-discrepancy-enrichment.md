# MT prediction-discrepancy enrichment

This note resolves `ENRICH-003` and `ENRICH-004` from the camera-ready paper, committed notebook state, committed MT target CSVs, and a read-only audit of the current prediction inputs.
It does not resolve the mechanistic hypotheses in `INTERPRETATION-001`.

## Source layers and provenance

The camera-ready results define 261 wells with morphology-predicted MT higher than observed and 131 underpredicted wells, reported as 2.0% and 1.0% of samples.
An earlier target ledger named notebook `2_1_predict_continuous_assays.ipynb` as producer, but cell 16 of `2_2_outlier_enrichment_analysis.ipynb` writes `mtt_higher_targets.csv` and `mtt_lower_targets.csv`.
The ledger now names notebook 2.2 directly.
The two CSVs were committed at `220c08a`, while the notebook later received path-only changes at `e473821` without regenerated stored outputs.
The current reproduction retains the functionally determined `Metadata_Compound` grouping key, removes the unused read of deleted `refchemdb_oasis.parquet`, and samples actual DMSO wells from the DINO profile substrate for its exploratory cluster control.
Every enrichment call continues to use the `cg_motive.parquet` target library.
A clean isolated execution now completes without error and regenerates both 8,858-row CSVs.

## Discrepancy-group contract

Notebook 2.2 reads the ignored current pipeline output `1_snakemake/outputs/cellprofiler/mad_featselect/classifier_results/axiom_continuous_predictions.parquet` and filters `Model_type == "Morphology"`.
It joins the verified Zenodo metadata on plate and well, then averages predicted MT, observed MT, and cell count by perturbation, assay variable, well, and plate.
`Metadata_Perturbation` encodes compound and concentration, so the resulting sample grain is one compound-concentration exposure well identified by perturbation, well, and plate.
It filters the assay variable to `Metadata_mtt_ridge_norm`, leaving 13,176 stored MT rows and 13,176 unique `Unique_ID` values.
The signed residual is `Predicted - Observed`.
`Higher` requires a residual greater than `2.58 * SD`, `Lower` requires a residual less than `-2.58 * SD`, and all other rows are `Normal`.
The SD is the sample standard deviation of all 13,176 signed MT residuals, rather than a per-compound or robust estimate.
The historical SD and numerical threshold were not printed in stored output and cannot be recovered exactly from the committed CSVs.
The `2.58 * SD` rule is a descriptive residual cutoff and is not treated here as a formal p-value.
Higher therefore means that morphology predicts a larger normalized MT value than was observed, while Lower means that morphology predicts a smaller normalized MT value than was observed.

Stored output reports 261 Higher, 131 Lower, and 12,784 Normal rows, which sum exactly to 13,176.
Those counts are 1.9809%, 0.9942%, and 97.0249%, agreeing with the camera-ready 2.0% and 1.0% after rounding.

A clean current-code reconstruction used that ignored pipeline-output prediction Parquet and the notebook's exact plate-well metadata join while retaining `Metadata_Compound`, which is uniquely determined for every existing group.
It retained 13,176 MT rows, had sample SD 0.07567157318680068 and threshold 0.19523265882194576, and selected 262 Higher, 142 Lower, and 12,772 Normal rows.
Those current counts are 1.9885%, 1.0777%, and 96.9338%, so the current prediction layer does not reproduce the stored count membership scale exactly.
The historical full hit lists were not stored separately, so exact historical-versus-current membership identity cannot be measured from the CSV overlaps.
The current reconstruction is kept separate from the historical stored output and is not substituted for it.

## CSV and enrichment contract

Each committed CSV has 8,858 rows and exactly six columns: `target_set`, `p_value`, `fdr`, `overlap_size`, `target_set_size`, and `overlap_hits`.
Each has 8,858 unique `target_set` keys, finite p-values and FDR values in [0, 1], and valid nonnegative overlap and target-set sizes.
The target library retains unique `target` and `OASIS_ID` pairs from `cg_motive.parquet` with `interaction_type == "unknown_direction"`, keeps targets annotated to at least three OASIS compounds before the metadata join, and expands those annotations to exposure-well `Unique_ID` values.
Consequently, `target_set_size` and `overlap_size` count exposure wells rather than unique compounds, and `overlap_hits` lists exposure-well identifiers rather than a compound-only list.
The nominal eligible universe is every unique MT `Unique_ID`, or 13,176 exposure wells, and the historical hit-list sizes are 261 Higher and 131 Lower.
For every target set, the notebook computes the one-sided upper-tail hypergeometric probability `hypergeom.sf(overlap_size - 1, 13176, target_set_size, hit_list_size)`.
It applies Benjamini-Hochberg correction jointly across all 8,858 p-values and calls target sets significant at FDR below 0.05.
All stored p-values and FDR values reproduce this procedure exactly with maximum numerical difference 0.

The implementation does not intersect target-library members with the MT universe before calculating `target_set_size`.
Against the current 13,176 MT keys, 1,007 of 11,182 target-library exposure IDs lie outside that universe, so the stored probabilities reproduce the committed implementation rather than an ideal universe-restricted test.
The CSVs omit `hit_list_size` and `universe_size`, so 261, 131, and 13,176 are recoverable only from proven notebook variables and stored output.
The notebook serializes a Python set with `",".join(overlap)`, making textual `overlap_hits` order nondeterministic across processes.
This audit decoded sample identifiers by their well and plate suffixes and compared overlaps as unordered sets, finding exact agreement between every decoded overlap count and the target library.

### Regenerated candidate validation

The semantic verifier now includes both regenerated MT CSVs.
It requires the exact six-column schema, 8,858 unique and reference-matched target-set keys, exact reference-matched `target_set_size` values, valid overlap membership and bounds, finite probabilities in [0, 1], and FDR values that reproduce Benjamini-Hochberg correction of the reported p-values.
Hit membership, overlap size, p-value, FDR, and significant-set drift remain diagnostic because the current 262/142 discrepancy groups differ from the historical 261/131 groups.
All 8,858 target-set sizes reproduce exactly in both files.
The Higher rerun has 7,218 exact overlap-size rows, 6,620 exact p-value rows, 8,594 exact FDR rows, and 71 significant target sets rather than 147.
The Lower rerun has 6,099 exact overlap-size rows, 5,537 exact p-value rows, 7,362 exact FDR rows, and 143 significant target sets rather than 107.

### Committed reference enrichment

The committed higher CSV contains exactly 147 significant target sets.
Their FDR values range from 1.5816846329335925e-06 to 0.04859910648923281, target-set sizes range from 15 to 5,895 exposure wells, and overlaps range from 5 to 165 wells.
Its five lowest-FDR rows are KDR (FDR 1.58168e-06, 29/365), FLT4 (2.29668e-06, 19/167), CYP3A4 (2.29668e-06, 165/5,895), CYP2C8 (2.29668e-06, 82/2,140), and CYP3A5 (5.90692e-06, 85/2,333).

The committed lower CSV contains 107 significant target sets.
Their FDR values range from 1.5518654039272212e-06 to 0.048787574030544074, target-set sizes range from 28 to 5,895 exposure wells, and overlaps range from 4 to 83 wells.
Its five lowest-FDR rows are MAPK9 (FDR 1.55187e-06, 11/75), PSMB5 (1.71524e-06, 9/46), ABL1 (1.71524e-06, 19/321), FLT3 (6.74935e-05, 13/182), and RND3 (8.16835e-05, 9/74).

## ENRICH-003 direct support

The paper's six named CYP target sets are all significant in the higher CSV.

| Target set | FDR | Overlap / target-set wells |
| --- | ---: | ---: |
| CYP3A4 | 2.29668e-06 | 165 / 5,895 |
| CYP2C8 | 2.29668e-06 | 82 / 2,140 |
| CYP3A5 | 5.90692e-06 | 85 / 2,333 |
| CYP2B6 | 6.48857e-05 | 61 / 1,535 |
| CYP3A7 | 9.43990e-05 | 59 / 1,486 |
| CYP3A43 | 3.05151e-04 | 27 / 456 |

The paper's four named xenobiotic transporter target sets are also significant.

| Target set | FDR | Overlap / target-set wells |
| --- | ---: | ---: |
| ABCB1 | 2.47243e-05 | 121 / 3,965 |
| ABCG2 | 2.47243e-05 | 67 / 1,713 |
| SLCO1B1 | 0.00563663 | 44 / 1,207 |
| SLCO1B3 | 0.0433023 | 30 / 810 |

Six serotonergic receptor sets are significant: HTR4, HTR2C, HTR2B, HTR6, HTR1F, and HTR1E, with FDR values from 0.00689964 to 0.0436271 and overlaps from 24 to 32 wells.
Aripiprazole, cisapride, clomipramine, domperidone, paliperidone, risperidone, and tamsulosin occur directly in significant HTR overlaps.
Amoxapine and apomorphine occur in no significant higher overlap, and no `DRD*`, `ADRA*`, or `ADRB*` target set is significant.
The committed artifacts therefore directly support serotonergic receptor enrichment and seven of nine named examples, while the dopaminergic and adrenergic wording remains a pharmacological interpretation in paper prose rather than a significant target-set result.

Decision: `reproduced-with-deviation` because the exact historical group scale, 147 significant target sets, CYP class, serotonergic receptor class, and all four transporter targets are supported, while current counts drift slightly and direct significant-set support is absent for the dopaminergic and adrenergic labels and two named compounds.
The result remains an association between annotated targets and discrepancy wells and does not establish a causal metabolic mechanism.

## ENRICH-004 direct support

Proteasome-related target sets dominate the lower enrichment, with 18 significant `PSM*` keys.
PSMB5 is the second-ranked row at FDR 1.71524e-06 with 9 of 46 target-set wells overlapping, and both bortezomib and ixazomib occur directly in that overlap.
Additional significant examples include PSMA6, PSMA8, and PSMD1 at FDR 3.72677e-04; PSMB3, PSMB11, and PSMD2 at 0.00237351; and PSMA2, PSMA4, PSMA5, PSMB1, PSMB2, PSMB6, PSMB7, and PSMB9 at 0.00659124.
Bortezomib occurs in 111 lower target-set overlaps, while ixazomib occurs in eight and is significant for PSMB5, CYP3A4, and CYP2D6.
Carfilzomib occurs in no lower CSV overlap, so its claimed historical exposure membership cannot be verified from the repository artifact.
In the separate current selector, bortezomib has five Lower wells, ixazomib has three, and all 16 carfilzomib wells are Normal.

Xenobiotic metabolism has direct target-set support from CYP3A4 (FDR 0.00339245, 83/5,895), CYP2D6 (0.0161719, 44/2,614), and CYP1A1 (0.0212361, 26/1,242).
The repository contains no pathway or process mapping that links significant target keys to bile acid synthesis, general cell stress, or apoptosis.
Significant rows such as ERN1, ATF4, NUPR1, TNFRSF10A, FASLG, BAK1, and TNFSF10 are reported only as target-set associations here and are not promoted to process evidence by inference from their gene names.
The bile acid synthesis, general cell stress, and apoptosis labels therefore remain camera-ready prose interpretations rather than repository-mapped enrichment results.

Decision: `reproduced-with-deviation` because the exact historical 131-well group scale and the major distinct proteasome and xenobiotic-metabolism signals are directly supported, preserving the qualitative conclusion of biologically structured underprediction.
The deviations are current selector drift to 142 Lower wells, absence of carfilzomib from the historical overlap artifact, lack of repository process mappings for three prose labels, and the unenforced target-set universe restriction.
These associations do not establish proteasome inhibition or any other mechanism as the cause of the MT prediction discrepancy.
