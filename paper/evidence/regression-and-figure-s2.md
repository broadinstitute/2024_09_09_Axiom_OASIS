# Regression and Figure S2 evidence

This note resolves TABLE-1, REGRESSION-001, REGRESSION-002, and SFIG-2 against the camera-ready sources and the repository state at `a001f114c8edd3223182787749c13d2f73c7d050`.
No notebook or scientific workflow was executed.
Small read-only calculations used the existing Parquets and wrote temporary code and output only under `/tmp`.
The intentionally unfixed `01_checkwelleffects.ipynb` was inspected only as historical provenance, and `2_1_predict_continuous_assays.ipynb` was not executed in place.

## Source layers

Camera-ready Table 1 and Figure S2 are the acceptance baselines.
The current base layer is the `mad_featselect` CellProfiler, CP-CNN, and DINO output set read by the committed regression notebook.
The stored-notebook layer is the rounded table and Figure S2 analysis output committed by `70e67f0` after the post-merge reproduction run.
The filtered alternative is `cellprofiler/mad_featselect_filt`, which is kept separate because no notebook reads it.

The current output Parquets are under the ignored `1_snakemake/outputs/` tree, so their hashes are needed to identify the exact local evidence substrate.
The base metric hashes are `0776ae960579a13086af037cdf5939121498b601eb003a86a49133de6fd64929`, `e37819d3a1d8895c769a71380f8bd3802a939c87656556a7cfa1ef443dbb2ae6`, and `573ea48fd4d1d875b7fd8da3495ec04c716751a66fb24c5ca29c2f65eb664750` for CellProfiler, CP-CNN, and DINO.
The corresponding prediction hashes are `3e95b205fd1094dfc74a9e0127e49abc54d727cf047a74c5b808135251e9cf30`, `fab95880575141ed4b8660a7f3f1c8389d784c0f0b21349b6e0732694897e5`, and `176493398d0399dc280d2e59ef651306ea149ea4936e640b4522c8953352c215`.
The filtered CellProfiler metric and prediction hashes are `bc29d5fa207b6dcd1bdef1e12fae59853cf3ebaa5f7ea53fc7f60cb0271fab92` and `fb254d3ecc76a50620343aac898183fc960c040369f1666bc2bab635a81212a8`.
The CellProfiler and DINO profile hashes used for Figure S2 are `b88726ed99b16092702bfbbe9dec88a7eb9c776451d18a2aba24097c537a9216` and `c70500d4b8c12a28650b40ed4d2ef636201c546237fd9d99babb4bdf252ff6b1`.

## TABLE-1

Each current metrics file has exactly 60 unique `(Variable, Model_type, Split)` rows from two assay labels, three model labels, and ten splits numbered 0 through 9.
The exact assay labels are `Metadata_ldh_ridge_norm` and `Metadata_mtt_ridge_norm`, and the exact model labels are `Baseline`, `Mean_predictor`, and `Morphology`.
These map without ambiguity to the camera-ready technical, mean-predictor, and representation-specific rows, while the replicate rows are recomputed from the paired DINO-profile metadata using the committed notebook code.

Each cell below is camera-ready mean (standard deviation), followed by the current base value from the same ten-split aggregation.

| Assay | Input features | R2 | RMSE | MAE |
| --- | --- | --- | --- | --- |
| LDH | Mean predictor baseline | -0.002 (0.0020); -0.002046 (0.001966) | 0.1 (0.011); 0.100922 (0.010558) | 0.061 (0.0030); 0.060572 (0.002960) |
| LDH | Technical baseline | 0.65 (0.044); 0.645670 (0.043684) | 0.06 (0.0049); 0.059701 (0.004904) | 0.035 (0.00078); 0.034699 (0.000784) |
| LDH | Replicate baseline | 0.45 (0.062); 0.451423 (0.061536) | 0.08 (0.0025); 0.079643 (0.002483) | 0.053 (0.0017); 0.052872 (0.001652) |
| LDH | CellProfiler | 0.65 (0.051); 0.658492 (0.048101) | 0.059 (0.0026); 0.058437 (0.003032) | 0.039 (0.00085); 0.039268 (0.001124) |
| LDH | CP-CNN | 0.66 (0.053); 0.663890 (0.058681) | 0.058 (0.0025); 0.057782 (0.001916) | 0.039 (0.0010); 0.039108 (0.000788) |
| LDH | DINO | 0.66 (0.052); 0.652671 (0.059281) | 0.059 (0.0030); 0.059007 (0.002521) | 0.04 (0.0011); 0.039977 (0.000898) |
| MT | Mean predictor baseline | -0.0019 (0.0017); -0.001910 (0.001721) | 0.17 (0.014); 0.170990 (0.014188) | 0.092 (0.0044); 0.091856 (0.004399) |
| MT | Technical baseline | 0.70 (0.055); 0.698458 (0.055239) | 0.093 (0.0050); 0.092923 (0.005003) | 0.048 (0.0014); 0.048279 (0.001425) |
| MT | Replicate baseline | 0.88 (0.020); 0.884299 (0.019805) | 0.06 (0.0052); 0.059793 (0.005229) | 0.032 (0.0013); 0.031677 (0.001333) |
| MT | CellProfiler | 0.79 (0.039); 0.789236 (0.034939) | 0.077 (0.0034); 0.077746 (0.002750) | 0.042 (0.0013); 0.041764 (0.001107) |
| MT | CP-CNN | 0.79 (0.040); 0.792594 (0.038143) | 0.077 (0.0032); 0.077059 (0.003211) | 0.042 (0.0011); 0.041684 (0.001154) |
| MT | DINO | 0.79 (0.039); 0.789814 (0.036985) | 0.078 (0.0031); 0.077952 (0.002942) | 0.042 (0.0013); 0.042041 (0.001140) |

At the notebook's two-significant-figure rule, 32 of 36 means and 19 of 36 standard deviations agree with the camera-ready values.
The four rounded mean mismatches are LDH CellProfiler R2, LDH CellProfiler RMSE, LDH DINO R2, and MT CellProfiler RMSE.
The largest absolute differences are 0.008492 for an R2 mean, 0.007281 for an R2 standard deviation, 0.000990 for an RMSE mean, 0.000650 for an RMSE standard deviation, 0.000428 for an MAE mean, and 0.000274 for an MAE standard deviation.
The stored notebook reports the current base values after two-significant-figure rounding rather than the camera-ready morphology values where those layers differ.

The filtered CellProfiler alternative gives LDH R2, RMSE, and MAE of 0.655643 (0.044240), 0.058723 (0.003018), and 0.039363 (0.001221).
It gives MT R2, RMSE, and MAE of 0.789440 (0.034268), 0.077735 (0.003110), and 0.041710 (0.001232).
This alternative does not remove the camera-ready rounding deviations and was not selected as a substitute for the notebook substrate.

Decision: `reproduced-with-deviation`.
The schemas, labels, split count, metric scale, and conclusions reproduce, while 21 of 72 reported mean or standard-deviation entries drift at camera-ready rounding.

## REGRESSION-001

The committed notebook contains plots and descriptive aggregation but no formal test for Table 1 model differences.
The audit therefore used two-sided paired t-tests across the ten common split indices and reports them as an explicit check rather than as undocumented paper provenance.

The three morphology representations remain practically similar.
Across their means, the largest ranges are 0.01122 R2, 0.001225 RMSE, and 0.000869 MAE for LDH, and 0.003358 R2, 0.000893 RMSE, and 0.000357 MAE for MT.
All MT representation comparisons are non-significant with p-values at or above 0.184.
All LDH R2 and RMSE comparisons are non-significant with p-values at or above 0.0861.
LDH MAE is a narrow statistical exception in the unadjusted paired tests: DINO differs from CellProfiler by 0.000709 with p = 0.00393 and from CP-CNN by 0.000869 with p = 0.000292, while CellProfiler and CP-CNN do not differ with p = 0.451.
Both DINO comparisons remain significant after Bonferroni correction within the three LDH MAE comparisons, and the CP-CNN comparison also remains significant after correction across all 18 representation tests.
The significant LDH MAE differences are at most 2.2% of the approximately 0.04 MAE and do not overturn practical similarity.

For MT, all three morphology representations beat the technical baseline in the favorable direction on every metric.
Their mean improvements are 0.0908 to 0.0941 for R2, 0.0150 to 0.0159 lower RMSE, and 0.00624 to 0.00659 lower MAE.
The paired p-value ranges are `1.47e-6` to `2.10e-6` for R2, `3.16e-7` to `8.38e-7` for RMSE, and `1.36e-9` to `9.28e-9` for MAE.

For LDH, the morphology R2 advantages of 0.0070 to 0.0182 have p-values from 0.256 to 0.626, and the RMSE reductions of 0.000695 to 0.001920 have p-values from 0.222 to 0.598.
Morphology MAE is instead 0.00441 to 0.00528 higher than the technical baseline with p-values from `1.10e-8` to `3.15e-8`.
Metric ordering therefore supports Cell Painting over the technical baseline for MT, while LDH has no R2 or RMSE advantage and formally favors the technical baseline on MAE.

Decision: `reproduced-with-deviation`.
The paper's practical representation-similarity and MT-versus-LDH baseline conclusions hold, with a small but formally significant LDH MAE representation difference that the camera-ready statement does not expose.

## REGRESSION-002

The current model R2 mean is 0.655181 after pooling technical baseline, CellProfiler, CP-CNN, and DINO across ten splits.
The current replicate R2 mean is 0.451423, giving an exact mean difference of 0.2037579853.

The model metrics use ten repeated 80/20 compound-group splits over 966 OASIS-linked compounds.
CellProfiler and CP-CNN each start from 14,769 exposure rows, while DINO starts from 14,619 because the representation-specific profile tables retain different rows.
Each model split holds out 194 compounds and evaluates 2,930 to 2,990 rows, depending on representation, split, and assay missingness.
The replicate calculation uses a separate 1,085-compound, 8,679 compound-concentration-group universe because the notebook does not apply the model's OASIS-ID filter.
Each replicate split holds out 217 compounds and retains 1,532 to 1,562 paired LDH groups after missing-value removal.

The comparison matching the paper's pooled wording is a two-sided equal-variance independent t-test of 40 model-split R2 values against ten replicate-split R2 values.
It gives `t = 10.8059118362`, `df = 48`, and `p = 1.88446103266e-14`.
The result remains clearly significant and the effect remains near 0.20, although the current p-value is 1.88-fold above the literal camera-ready bound of `1e-14`.
The split-number labels should not be treated as paired across model and replicate results because their compound universes differ.

Decision: `reproduced-with-deviation`.
The acceptance rule is satisfied, while the exact p-value threshold and the distinct model-versus-replicate split universes are recorded explicitly.

## SFIG-2

The camera-ready figure, supplemental PDF, committed notebook code, stored notebook output, and current Parquets agree on the panel variables, labels, and directions.
Exact pixels and clustering order were not used as acceptance baselines.

Panels A-C use all retained CellProfiler-profile rows from `assayworks_prod_27`, including controls, and aggregate 6,320 rows from 17 plates into all 384 row A-P and column 1-24 well positions.
The historical notebook computes the mean cell count and median normalized LDH and MT per well despite the caption's compact wording.
Relative to rows F-K and columns 7-18, the outer rows A and P or columns 1 and 24 have 32.36 fewer cells on average, normalized LDH higher by 0.14334, and normalized MT higher by 0.17180.
These directions and the patchy cell-count field reproduce the published edge-high LDH and MT and lower-edge-count patterns.

Panels D and E use the current base predictions after averaging signed prediction residuals over repeated appearances and the three morphology representations.
The notebook omits assay variable from this aggregation, so the selection combines LDH and MT residuals before plotting MT and cell count.
It calls wells above `2.58 * SD` of `Baseline residual - Morphology residual` "Better predicted by Cell Painting", although this is a signed-residual threshold rather than a formal significance test on absolute prediction error.

The current base and stored-notebook layers contain 13,176 eligible non-DMSO wells, with 292 in the Cell Painting-better group, 134 in the technical-better group, and 12,750 normal.
The camera-ready Figure S2 legend gives no group count, while the associated camera-ready results text reports 138 wells and the historical committed enrichment table used 304 before the post-merge run produced 292.
The existing reproduction evidence states that this regression-selection drift is independent of POD fitting, that `regression.py` seeds the split generator but not XGBoost, and that the exact mechanism remains unresolved.

The Cell Painting-better group retains the published distribution shifts.
Its MT median is 0.6272 versus 0.9956 for all samples, and its interquartile range is 0.3460 to 0.8001 versus 0.9502 to 1.0000.
Its cell-count median is 664.5 versus 785 for all samples, and its interquartile range is 498.25 to 765.25 versus 704 to 846.

Replacing only CellProfiler with the filtered alternative gives 289 Cell Painting-better wells and 131 technical-better wells.
The base and filtered Cell Painting-better sets overlap on 247 wells, with Jaccard similarity 0.740, and the filtered group preserves the lower-MT and lower-cell-count shifts.
This alternative is reported as a separate sensitivity layer and is not used to choose a better match to the paper.

Panel F uses the 292 current base wells and all 4,432 DINO features, with cell counts from 2 to 1,133.
The first DINO principal component has absolute Pearson correlation 0.875 with cell count.
Mean cosine similarity is 0.529 within the same cell-count quartile and 0.341 across different quartiles, while the lowest-count quartile has mean within-group similarity 0.640 versus 0.259 to other wells.
These values reproduce the dominant cell-count-linked block structure without requiring the camera-ready dendrogram order.

Decision: `reproduced-with-deviation`.
All six panels reproduce their scientific directions and major patterns, while the regression-derived sample count drifts and the notebook's "significantly better" label overstates its signed-residual threshold.

## Method reconciliation and cause

Table 1, `regression.py`, and the current metrics all use ten repeated 80/20 compound-group splits with `random_state = 42`.
STAR Methods separately says that all supervised scenarios used five-fold cross-validation.
This is the already documented METHOD-REGRESSION inconsistency, and no method target or acceptance contract was changed here.

The small Table 1 drift and the larger Figure S2 membership drift sit at the documented post-merge regression-output boundary.
The original regression environment is not pinned, the pre-fix prediction writer corrupted identifier columns, and the current XGBoost regressor has no explicit seed.
Existing evidence does not isolate one of these facts as the mechanism, so the exact cause remains unresolved rather than being attributed speculatively.
The paper's practical conclusions are unchanged.
