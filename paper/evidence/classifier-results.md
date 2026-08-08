# Classifier-results evidence

Targets: `FIG-3AB`, `FIG-3C`, `FILTER-001`, `FILTER-002`, `FIG-4A`, `REPRESENTATION-001`, `FIG-4B`, `SFIG-4`, `CONCLUSION-002`, and `CONCLUSION-003`.

The input commit was signed commit `00ea45a429a7f54db120079febc07d3c8d9c4c75`.
This audit used camera-ready main Sections 3.2 through 3.2.2 and Figures 3 and 4, camera-ready supplemental Figure S4, all four committed compiled metric Parquets, the current base and separately named filtered CellProfiler prediction Parquets, current CP-CNN and DINO prediction Parquets, stored code and outputs in notebooks `3_2_1_compare_endpoint_types.ipynb`, `3_2_2_compare_concs_reps.ipynb`, and `3_2_3_compare_endpoints_detail.ipynb`, the classifier implementation, `paper/verification/compiled_results.py`, `paper/REPRODUCING.md`, and the prior ToxCast and classifier evidence notes.
No notebook, classifier, POD fit, Snakemake rule, or scientific workflow was executed.
Read-only scratch calculations wrote only under `/tmp`.
Published JPEGs were used only to inspect labels, distributions, and directions, not as pixel baselines.

## Metric contract and endpoint universes

All four compiled metric files have the same eight scientific columns: `Metadata_AggType`, `Metadata_Label`, `Model_type`, `AUROC`, `PRAUC`, `Metadata_Count_0`, `Metadata_Count_1`, and `Feat_type`.
The unique semantic key is `(Metadata_AggType, Metadata_Label, Model_type, Feat_type)`, with no duplicate or null keys.
The exact labels are aggregation types `all`, `allpod`, and `allpodcc`; models `Actual`, `Cellcount_baseline`, and `Random_baseline`; and representations `cellprofiler`, `cpcnn`, and `dino`.
The Axiom assay label `MTT` is the paper's MT assay.
AUROC and PRAUC are unitless and are computed from pooled out-of-fold predictions, while the class-count columns give compound-sample denominators.

| Outcome | SHA-256 | Rows | Modeled labels | Compound-sample range |
| --- | --- | ---: | ---: | ---: |
| Axiom | `9993bf115589d63e673cab729273cab8f0c93b776012f9f07c74b5629edf5247` | 81 | 3 | 966-967 |
| ToxCast cytotoxicity | `0e776953b44df52f01eef1d035aad64930893a021758d1c8d2c920d9cca2cbd0` | 918 | 34 | 13-667 |
| ToxCast cell-based | `92737df23e2500a692c1b8424afa841b5f264d4fbcf1db54b1da46fc1d5356c1` | 7,209 | 267 | 10-652 |
| ToxCast cell-free | `f9821cc893c10f0460428ff2b72ba803dce612d03d60611bf00fb0b64da32352` | 1,431 | 53 | 11-131 |

The camera-ready Figure 3 and Figure 4 captions instead report two paired MT/LDH assays, 48 ToxCast cytotoxicity source categories, 292 cell-based endpoints, and 72 cell-free endpoints.
The prior curation audit showed that the 48 source cytotoxicity categories become 38 binary endpoints after the stated five-positive/five-negative source filter.
After intersection with available profiles, five-fold classification requires at least five positives and five negatives and retains 34 of 38 cytotoxicity endpoints, 267 of 292 cell-based endpoints, and 53 of 72 cell-free endpoints.
The four additional cytotoxicity exclusions are `cell_type__LUHMES` with 12 negative and 3 positive samples, `cell_type__hNC` with 11 and 4, `tissue__H9-derived_embryonic_neural_crest_stem_cells` with 11 and 4, and `tissue__central_nervous_system` with 12 and 3.
The 25 cell-based exclusions each have only two to four positives after profile intersection.
They are `ATG_AP_2_CIS`, `ATG_NRF1_CIS`, `ATG_Sox_CIS`, `ATG_TGFb_CIS`, `BSK_3C_Thrombomodulin`, `BSK_MyoF_ACTA1`, `BSK_MyoF_CollagenIV`, `BSK_MyoF_PAI1`, `BSK_MyoF_TIMP1`, `BSK_MyoF_VCAM1`, `CCTE_Deisenroth_DEVTOX_RUES2-GLR_Endo_Bra`, `CLD_HMGCS2_48hr`, `IUF_NPC1b_proliferation_BrdU_72hr`, `LTEA_HepaRG_BCL2L11`, `LTEA_HepaRG_CCND2`, `LTEA_HepaRG_CFLAR`, `LTEA_HepaRG_GSTM3`, `LTEA_HepaRG_HIF1A`, `LTEA_HepaRG_LDH_cytotoxicity`, `LTEA_HepaRG_SDHB`, `LTEA_HepaRG_XBP1`, `TOX21_TSHR_HTRF_Antagonist_ratio`, `TOX21_TSHR_wt_Agonist_HTRF_ratio`, `TOX21_VDR_BLA_Antagonist_ratio`, and `VALA_TUBHUV_Antagonist_TubuleLength`.
The 19 cell-free exclusions fail five-fold support in either the positive or negative class.
They are `NVS_ADME_hCYP2A6`, `NVS_ADME_hCYP2J2`, `NVS_ADME_hCYP4F12`, `NVS_ENZ_hAurA`, `NVS_ENZ_hMMP13`, `NVS_ENZ_hPDE5`, `NVS_ENZ_hPTEN`, `NVS_ENZ_hPTPN11`, `NVS_ENZ_hTie2`, `NVS_ENZ_hVEGFR2`, `NVS_GPCR_hAdra2C`, `NVS_GPCR_hAdrb1`, `NVS_GPCR_hAdrb2`, `NVS_GPCR_hM1`, `NVS_GPCR_hM2`, `NVS_GPCR_hM3`, `NVS_GPCR_hNPY1`, `NVS_GPCR_hNPY2`, and `NVS_NR_hPPARa`.
No endpoint distribution or comparison below substitutes a caption count for its actual modeled denominator.

The corrected `3_2_1` formal-model cell first selects `Metadata_AggType == "all"`, CellProfiler, and at least 100 compound samples.
It receives 9 Axiom rows over three labels, 69 ToxCast cytotoxicity rows over 23 labels, 696 cell-based rows over 232 labels, and six cell-free rows over only `NVS_NR_hER` and `NVS_NR_hPPARg`.
The Axiom formal model includes `cell_count` as a third predicted endpoint even though the Figure 3 caption and facet label specify only MT and LDH.

## Figure 3A and Figure 3B distributions

The table uses the committed CellProfiler `Actual` model at `Metadata_AggType == "all"` and excludes Axiom `cell_count` so that the paired-assay universe is exactly MT and LDH.
Quartiles use the standard linear interpolation implemented by pandas.

| Endpoint type | n | Compound samples, min / median / max | AUROC median [Q1, Q3], range | PRAUC median [Q1, Q3], range |
| --- | ---: | ---: | --- | --- |
| Paired MT/LDH | 2 | 967 / 967 / 967 | 0.901547 [0.886123, 0.916972], 0.870698-0.932396 | 0.805566 [0.786937, 0.824196], 0.768307-0.842826 |
| ToxCast cytotoxicity | 34 | 13 / 595 / 667 | 0.737210 [0.657039, 0.776169], 0.241071-0.916601 | 0.477455 [0.389099, 0.635675], 0.189841-0.686364 |
| ToxCast cell-based | 267 | 10 / 202 / 652 | 0.607226 [0.508917, 0.685389], 0.223891-0.921235 | 0.144840 [0.077417, 0.241917], 0.009342-0.850000 |
| ToxCast cell-free | 53 | 11 / 26 / 131 | 0.532086 [0.404830, 0.631579], 0.210702-0.971429 | 0.454015 [0.336925, 0.695904], 0.107341-0.981818 |

Paired MT/LDH has the highest AUROC and PRAUC.
ToxCast cytotoxicity is next by AUROC, ToxCast cell-based performance is lower but above both baselines in aggregate, and cell-free AUROC is near 0.5.
Absolute cell-free PRAUC is not low because the median active fraction is approximately 41%, so predictability must be judged against its matched random baseline rather than by comparing raw PRAUC across endpoint types.

## Figure 3C baseline comparisons and formal tests

Every effect below is `Actual - baseline` on the exact matched `(endpoint type, Metadata_Label)` key.
The p-values are two-sided `scipy.stats.ttest_rel` tests over those paired keys, matching the Figure 3 caption's stated paired t-test procedure.
They are unadjusted because the caption specifies p-values and does not define a multiplicity family.

| Endpoint type | n | AUROC vs random, mean diff (p) | AUROC vs cell count, mean diff (p) | PRAUC vs random, mean diff (p) | PRAUC vs cell count, mean diff (p) |
| --- | ---: | --- | --- | --- | --- |
| Paired MT/LDH | 2 | 0.398578 (0.05302) | 0.191848 (0.03349) | 0.538687 (0.10817) | 0.276758 (0.16420) |
| ToxCast cytotoxicity | 34 | 0.240708 (4.02e-11) | 0.151719 (6.02e-10) | 0.239111 (1.58e-11) | 0.160264 (8.96e-11) |
| ToxCast cell-based | 267 | 0.107903 (1.23e-21) | 0.094356 (1.74e-19) | 0.053321 (1.97e-15) | 0.049795 (1.30e-15) |
| ToxCast cell-free | 53 | 0.021021 (0.52341) | 0.059622 (0.02687) | -0.001233 (0.96462) | 0.048514 (0.06960) |

The main inference is supported directly: cytotoxicity and cell-based morphology models improve over random for both metrics, while cell-free models do not improve over random and their mean effects are 0.021 AUROC and -0.001 PRAUC.
The small cell-free AUROC advantage over cell count does not establish predictability above random and is not a practical counterexample.
The two paired Axiom endpoints provide large effects but are too few for stable direct t-test inference; their strong metric ordering is independently established by Table 2 and the prior classifier evidence.

The notebook does not implement the caption's direct paired t-tests.
It fits `metric ~ Model_type` random-intercept mixed models by endpoint label and then applies Tukey HSD to fitted values.
All four AUROC models converge, and the first three PRAUC models converge.
The six-row, two-endpoint cell-free PRAUC model reports `converged=False`, so its post-hoc p-values are invalid and are not interpreted.
For the converged groups, the stored morphology-versus-random and morphology-versus-cell-count Tukey p-values are 5.76e-6 and 3.54e-4 for Axiom AUROC, 3.13e-4 and 0.01083 for Axiom PRAUC, at most 2.07e-14 and 2.81e-8 for ToxCast cytotoxicity, and approximately 3.22e-13 for both morphology contrasts in both cell-based metrics.
The converged six-row cell-free AUROC fit returns effectively zero post-hoc p-values, but its two-endpoint result conflicts with the full 53-endpoint paired tests and the paper's own no-predictability conclusion.
Figure 3C also mixes full-universe mean effects with p-values resembling the narrower formal-model output and, for the Axiom row, includes the third `cell_count` endpoint despite the stated n of two.
These inferential and denominator deviations do not overturn the baseline ordering or the paper's main conclusion.

## Concentration-strategy mapping

The paper's all-concentration profiles map to artifact `Metadata_AggType == "all"`.
The paper's profiles after the morphology POD, called `all_morph` in STAR Methods, map to `allpod`; the code retains concentrations with `Metadata_Log10Conc > Metadata_POD` and falls back to all profiles when no post-POD aggregate exists.
The paper's profiles after the morphology POD and before the cytotoxicity or cell-count POD, called `all_morph_cytotox` in STAR Methods, map to `allpodcc`; the code retains `Metadata_Log10Conc > Metadata_POD` and `< Metadata_ccPOD`, then falls back first to the minimum post-morphology-POD concentration and finally to all profiles.
The artifact labels, rather than the manuscript aliases, are used in every key comparison.

## Figure 4A and supplemental Figure S4A

The distribution table gives the committed and current CellProfiler `Actual` medians as `compiled / current`, with the committed min-max range in parentheses.
All comparisons use all 2, 34, 267, or 53 modeled endpoint keys, respectively.

| Endpoint type | Strategy | AUROC median compiled / current (compiled range) | PRAUC median compiled / current (compiled range) |
| --- | --- | --- | --- |
| Paired MT/LDH | `all` | 0.901547 / 0.901547 (0.870698-0.932396) | 0.805566 / 0.805566 (0.768307-0.842826) |
| Paired MT/LDH | `allpod` | 0.900340 / 0.899277 (0.853343-0.947338) | 0.813218 / 0.815481 (0.812533-0.813903) |
| Paired MT/LDH | `allpodcc` | 0.775366 / 0.779561 (0.747478-0.803254) | 0.440856 / 0.457960 (0.236630-0.645083) |
| ToxCast cytotoxicity | `all` | 0.737210 / 0.737210 (0.241071-0.916601) | 0.477455 / 0.477455 (0.189841-0.686364) |
| ToxCast cytotoxicity | `allpod` | 0.740779 / 0.743593 (0.463235-0.946429) | 0.493067 / 0.512173 (0.176122-0.967033) |
| ToxCast cytotoxicity | `allpodcc` | 0.650000 / 0.661887 (0.523693-0.719562) | 0.315550 / 0.311496 (0.073972-0.799531) |
| ToxCast cell-based | `all` | 0.607226 / 0.607226 (0.223891-0.921235) | 0.144840 / 0.144840 (0.009342-0.850000) |
| ToxCast cell-based | `allpod` | 0.609748 / 0.619550 (0.239287-0.988095) | 0.137900 / 0.133216 (0.009801-0.991071) |
| ToxCast cell-based | `allpodcc` | 0.616146 / 0.610714 (0.190476-0.939901) | 0.135466 / 0.133610 (0.005542-0.811303) |
| ToxCast cell-free | `all` | 0.532086 / 0.532086 (0.210702-0.971429) | 0.454015 / 0.454015 (0.107341-0.981818) |
| ToxCast cell-free | `allpod` | 0.510490 / 0.528571 (0.047619-0.821429) | 0.533136 / 0.542443 (0.105251-0.906807) |
| ToxCast cell-free | `allpodcc` | 0.534759 / 0.516043 (0.125000-0.858974) | 0.515150 / 0.457677 (0.113890-0.889411) |

The next table reports direct paired mean effects for `all -> allpod` and `allpod -> allpodcc` as `compiled / current`.
The final column is the committed notebook's mixed-model fitted-value effect and Tukey HSD adjusted p-value.
The notebook controls the three strategy contrasts within each endpoint type and metric by Tukey family-wise error, not by the paper's unspecified FDR procedure.

| Endpoint type | Metric | n | Direct mean effect compiled / current | Notebook effect (Tukey p-adj) |
| --- | --- | ---: | --- | --- |
| Paired MT/LDH | AUROC, `all -> allpod` | 2 | -0.001207 / -0.002270 | 0.0034 (0.9547) |
| Paired MT/LDH | PRAUC, `all -> allpod` | 2 | 0.007651 / 0.009915 | 0.0284 (0.5658) |
| ToxCast cytotoxicity | AUROC, `all -> allpod` | 34 | 0.038562 / 0.037393 | 0.0380 (5.39e-8) |
| ToxCast cytotoxicity | PRAUC, `all -> allpod` | 34 | 0.059863 / 0.053636 | 0.0583 (0.1128) |
| ToxCast cell-based | AUROC, `all -> allpod` | 267 | 0.019421 / 0.020284 | 0.0126 (0.0685) |
| ToxCast cell-based | PRAUC, `all -> allpod` | 267 | -0.005875 / -0.005417 | -0.0091 (0.6735) |
| ToxCast cell-free | AUROC, `all -> allpod` | 53 | -0.024817 / -0.007108 | -0.0096 (0.8723) |
| ToxCast cell-free | PRAUC, `all -> allpod` | 53 | -0.006125 / 0.009313 | 0.0009 (0.9997) |
| Paired MT/LDH | AUROC, `allpod -> allpodcc` | 2 | -0.124974 / -0.119716 | -0.1440 (4.20e-5) |
| Paired MT/LDH | PRAUC, `allpod -> allpodcc` | 2 | -0.372361 / -0.357521 | -0.4240 (9.63e-6) |
| ToxCast cytotoxicity | AUROC, `allpod -> allpodcc` | 34 | -0.088586 / -0.090794 | -0.0870 (2.43e-14) |
| ToxCast cytotoxicity | PRAUC, `allpod -> allpodcc` | 34 | -0.167164 / -0.165180 | -0.1659 (3.01e-7) |
| ToxCast cell-based | AUROC, `allpod -> allpodcc` | 267 | -0.007970 / -0.010462 | -0.0016 (0.9579) |
| ToxCast cell-based | PRAUC, `allpod -> allpodcc` | 267 | -0.006597 / -0.007442 | -0.0029 (0.9612) |
| ToxCast cell-free | AUROC, `allpod -> allpodcc` | 53 | 0.013429 / -0.006094 | -0.0033 (0.9838) |
| ToxCast cell-free | PRAUC, `allpod -> allpodcc` | 53 | 0.005152 / -0.016502 | -0.0072 (0.9794) |

The published approximately 0.04 cytotoxicity and 0.02 cell-based AUROC effects reproduce as direct paired means of 0.038562 and 0.019421 in the committed layer and 0.037393 and 0.020284 in the current layer.
The effect magnitudes are small, and the cell-based median paired effects are only 0.009712 committed and 0.012507 current.
The camera-ready FDR values of less than 1e-14 and 0.002 do not reproduce from the committed notebook: its Tukey values are 5.39e-8 and 0.0685, and no committed code defines the paper's FDR family.
Other AUROC effects and every PRAUC effect show no consistent practical improvement.
The approximately 0.06 mean cytotoxicity PRAUC change is driven by a wide distribution whose committed and current median effects are -0.000063 and -0.015563, and the notebook Tukey p-value is 0.1128.

Excluding cytotoxic concentrations strongly worsens paired MT/LDH and ToxCast cytotoxicity performance in both computational layers and both metrics.
Cell-based changes are negative and at most 0.0105 in magnitude, while cell-free effects change sign across POD-derived layers and remain at most 0.0165 in magnitude.
This supports the published no-improvement conclusion and the directions in Figure 4A and supplemental Figure S4A.

## Current POD-derived drift

The official semantic verifier proves all 2,709 ToxCast cell-based and cytotoxicity rows at `AggType == "all"` are bit-exact.
This scratch audit also observed exact current agreement for all 477 cell-free `all` rows, without expanding the verifier's formal gate.
The key sets match for all 9,639 compiled and current metric rows, but `allpod` and `allpodcc` values drift because discrete POD selection changes which profiles are aggregated.

| Outcome and strategy | n | Mean absolute / maximum AUROC drift | Mean absolute / maximum PRAUC drift |
| --- | ---: | ---: | ---: |
| ToxCast cytotoxicity `allpod` | 306 | 0.02880 / 0.23117 | 0.02557 / 0.28115 |
| ToxCast cytotoxicity `allpodcc` | 306 | 0.03332 / 0.52679 | 0.02672 / 0.38379 |
| ToxCast cell-based `allpod` | 2,403 | 0.04794 / 0.53170 | 0.02028 / 0.47778 |
| ToxCast cell-based `allpodcc` | 2,403 | 0.05308 / 0.62778 | 0.02159 / 0.43269 |
| ToxCast cell-free `allpod` | 477 | 0.04261 / 0.68981 | 0.03352 / 0.46313 |
| ToxCast cell-free `allpodcc` | 477 | 0.04406 / 0.60909 | 0.03552 / 0.35142 |

Despite large endpoint-level tails, the group effects that carry the paper's conclusions drift little: cytotoxicity `all -> allpod` AUROC changes from 0.038562 to 0.037393, cell-based changes from 0.019421 to 0.020284, and cytotoxicity `allpod -> allpodcc` changes from -0.088586 to -0.090794.
The divergence is localized to POD-derived aggregation and must not be attributed to classifier instability.

## Figure 4B and supplemental Figure S4B

The representation distributions and direct paired summaries below use the committed metric Parquets and the analysis in `3_2_3_compare_endpoints_detail.ipynb`.
The mixed-model and Tukey statistics are stored in `3_2_2_compare_concs_reps.ipynb`, which evaluates both concentration strategies and representation contrasts.

The table uses matched `AggType == "all"`, `Model_type == "Actual"` keys.
All ToxCast values are bit-exact between the committed and current base layers, so one value represents both.

| Endpoint type | Representation | n | AUROC median, range | PRAUC median, range |
| --- | --- | ---: | --- | --- |
| Paired MT/LDH | CellProfiler | 2 | 0.901547, 0.870698-0.932396 | 0.805566, 0.768307-0.842826 |
| Paired MT/LDH | CP-CNN | 2 | 0.892408, 0.858888-0.925928 | 0.777947, 0.721698-0.834197 |
| Paired MT/LDH | DINO | 2 | 0.907748, 0.875945-0.939551 | 0.803796, 0.769632-0.837959 |
| ToxCast cytotoxicity | CellProfiler | 34 | 0.737210, 0.241071-0.916601 | 0.477455, 0.189841-0.686364 |
| ToxCast cytotoxicity | CP-CNN | 34 | 0.750482, 0.531863-0.844436 | 0.482249, 0.121017-0.755675 |
| ToxCast cytotoxicity | DINO | 34 | 0.745739, 0.232143-0.835596 | 0.450633, 0.052941-0.719705 |
| ToxCast cell-based | CellProfiler | 267 | 0.607226, 0.223891-0.921235 | 0.144840, 0.009342-0.850000 |
| ToxCast cell-based | CP-CNN | 267 | 0.597315, 0.261084-0.941071 | 0.143401, 0.008097-0.950000 |
| ToxCast cell-based | DINO | 267 | 0.619048, 0.082716-0.912371 | 0.158141, 0.008571-0.764923 |
| ToxCast cell-free | CellProfiler | 53 | 0.532086, 0.210702-0.971429 | 0.454015, 0.107341-0.981818 |
| ToxCast cell-free | CP-CNN | 53 | 0.522222, 0.138889-0.962500 | 0.487900, 0.133245-0.935676 |
| ToxCast cell-free | DINO | 53 | 0.515050, 0.208333-0.846154 | 0.475315, 0.158378-0.907097 |

On the 267 matched cell-based endpoints, DINO's AUROC median advantage is 0.022090 over CellProfiler and 0.015873 over CP-CNN, which supports the paper's approximately 0.02 median statement.
The paired mean advantages are smaller at 0.011882 and 0.010790.
The `3_2_2_compare_concs_reps.ipynb` mixed-model effects are the same 0.0119 and 0.0108, with Tukey p-values 0.0733 and 0.1154 rather than the camera-ready 2.7e-5 and 7.4e-6.
Direct paired t-test p-values are 0.1847 and 0.2105.
The magnitude claim and practical similarity hold, while the published significance claim does not reproduce from the committed statistical code.

All PRAUC representation contrasts in `3_2_2_compare_concs_reps.ipynb` are non-significant after Tukey adjustment.
The direct DINO cell-based PRAUC mean advantages are 0.012775 over CellProfiler and 0.011606 over CP-CNN, with unadjusted paired p-values 0.0313 and 0.0498, but the notebook Tukey values are 0.4726 and 0.5384 and the effects are small.
The one `3_2_2_compare_concs_reps.ipynb` AUROC exception is DINO below CP-CNN by 0.053944 on ToxCast cytotoxicity, with Tukey p = 0.0493; its median difference is 0.009763 in the opposite direction because endpoint-level changes are heterogeneous.
This is a statistical and estimand exception, not a broad practical advantage for any representation.
The ordering across assay types and the near-overlap of representation distributions in Figure 4B and supplemental Figure S4B remain intact.

The base CellProfiler scenario remains separate from `cellprofiler_filt`.
The latter changes only the CellProfiler feature-selection outlier threshold and is not read by any manuscript notebook.
Its current `all` AUROC medians are 0.900467 for paired MT/LDH, 0.732987 for ToxCast cytotoxicity, 0.605916 for cell-based, and 0.521390 for cell-free, all practically similar to the base medians.
It preserves the conclusions but was not substituted based on agreement.

## Decisions and conclusion impact

`FIG-3AB` is reproduced with deviation because the all-concentration distributions and practical assay-type ordering agree, while caption endpoint counts do not equal modeled counts and raw cell-free PRAUC must be interpreted relative to prevalence and baseline.
`FIG-3C` is reproduced with deviation because matched baseline effects support the main conclusion, while the panel mixes endpoint universes and statistical procedures and the cell-free PRAUC mixed model does not converge.
`FILTER-001` is reproduced with deviation because the published approximately 0.04 and 0.02 AUROC increases reproduce closely and remain small, while the published FDR values do not reproduce from the committed notebook.
`FILTER-002` is reproduced with deviation because both layers show large deterioration for cytotoxicity categories and no practical improvement for cell-based or cell-free endpoints, with explicit POD-derived numerical drift.
`FIG-4A` is reproduced with deviation because the distribution directions and all-concentration practical conclusion agree, while endpoint counts and filtered-strategy values drift.
`REPRESENTATION-001` is reproduced with deviation because the DINO cell-based median advantages remain approximately 0.02 and all three representations remain similar, while mean effects are approximately 0.011 and published p-values do not reproduce.
`FIG-4B` is reproduced with deviation because the representation distributions remain near-equivalent with the same assay-type ordering, while one small ToxCast cytotoxicity notebook contrast reaches Tukey p = 0.0493.
`SFIG-4` is reproduced with deviation because PRAUC shows no practical improvement from concentration filtering or representation choice, while POD-filtered values drift and small unadjusted representation tests differ from the notebook's multiplicity-controlled results.
`CONCLUSION-002` is reproduced with deviation for the exact modeled universes of 2, 34, 267, and 53 endpoints: morphology is above random for paired and ToxCast cytotoxicity and for targeted cell-based activity, while cell-free activity is not materially above random.
`CONCLUSION-003` is reproduced with deviation because representations remain practically similar and concentration filtering yields no practical improvement, despite localized statistical, provenance, and POD-drift exceptions.

None of these classifier associations is interpreted as a mechanistic or causal effect.
