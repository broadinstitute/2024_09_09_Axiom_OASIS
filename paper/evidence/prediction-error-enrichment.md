# Prediction-model-error enrichment evidence

Targets: `ENRICH-001` and `ENRICH-002`.

The input commit was `b1a17f4a2a61dd4bb7a4c6ac2a4905355dc4f0ea`.
This audit used the camera-ready PDF and transcription, committed notebook code and stored outputs, the two committed `err_*_targets.csv` files, current base prediction Parquets, committed metadata and target annotations, and the existing clean-reproduction verifier evidence.
No notebook, regression pipeline, or scientific workflow was executed.
Read-only calculations used temporary code under `/tmp` and did not write a current enrichment artifact.
The separate prediction-discrepancy enrichment files belong to the next batch and were not assessed here.

## Source layers

The camera-ready text is the acceptance baseline.
It says 138 MT wells better predicted by Cell Painting were enriched in 480 molecular targets, including cell-cycle, PI3K-Akt, MAPK, and p53 signals, while 304 wells better predicted by the technical baseline had no significant target enrichment.

The committed historical enrichment layer is `err_higher_targets.csv` at SHA-256 `b8ec5c0897781734134989fd4cdaa77bad226c7227cb26d4f908389cf06b74cc` and `err_lower_targets.csv` at SHA-256 `2e21fe1892178f652b7c6ab4eaddeab7a0a8e50476a8e6bbbf6d11151a1f827e`.
The historical notebook output in commit `e2979d6fcb9118b15a6ac88381958b37dc378407` records 304 Higher, 138 Lower, and 12,734 Normal wells.

The current base layer uses the CellProfiler, CP-CNN, and DINO `mad_featselect` prediction Parquets read by the committed notebook.
Their SHA-256 values are `3e95b205fd1094dfc74a9e0127e49abc54d727cf047a74c5b808135251e9cf30`, `fab95880575141ed4b8660a7f3f1c8389d784c0f0b21349b6e0732694897e5`, and `176493398d0399dc280d2e59ef651306ea149ea4936e640b4522c8953352c215`.
The stored current notebook output committed in `70e67f0483e0fecb9e6a5dc21928ee93f9c49050` and an independent read-only reconstruction both give 292 Higher, 134 Lower, and 12,750 Normal wells.

The target expansion uses `metadata.parquet` at SHA-256 `92c2a3c4d305d5a8c17efe467ceb1cde6a6c5505e51d395f1d0300882277f8ff` and `cg_motive.parquet` at SHA-256 `6706a0dc762c2560d96ccde1a3307e4397d2a6173839baecf0f1a9e8e9845957`.
The filtered CellProfiler prediction is a separate sensitivity layer that no notebook reads and was not substituted for the base layer.

## Group selection and direction

For every prediction row, the notebook defines signed residual as `Predicted - Observed`.
It averages that signed residual by `(Metadata_Plate, Metadata_Well, Model_type, Metadata_Compound, Metadata_Log10Conc)` and then pivots `Model_type`.
The aggregation key omits the assay variable, so LDH and MT residuals are inadvertently combined along with repeated appearances and the three morphology representations.
Of the 13,176 physical well-exposure keys, 13,170 have both assay labels and six have only one assay label in the current predictions.

The notebook then defines `Diff_error = Baseline residual - Morphology residual`.
It calculates the sample standard deviation of `Diff_error` across the eligible universe and selects Higher above `2.58 * SD`, Lower below `-2.58 * SD`, and Normal otherwise.
The current standard deviation is 0.031089156199550442 and the current threshold magnitude is 0.08021002299484015.
The universe contains 13,176 unique non-DMSO `(compound, concentration, well, plate)` IDs.

The notebook sends Higher IDs to `err_higher_targets.csv` and labels them `Better predicted by Cell Painting`.
It sends Lower IDs to `err_lower_targets.csv` and labels them `Better predicted by technical baseline`.
These are the repository's explicit filename and display-label mappings and were not reversed to match the paper.

The mapping is not a valid comparison of prediction errors because it thresholds a difference of signed residuals rather than a difference of absolute or squared residuals.
The `2.58 * SD` rule is also not a formal significance test, despite the notebook comment equating it to a p-value of 0.01.
The repository therefore proves how the labels were assigned but does not prove that either selected group is genuinely better predicted by the named model.

Replacing only CellProfiler with the filtered alternative previously gave 289 Higher and 131 Lower wells.
The base and filtered Higher sets overlap on 247 wells with Jaccard similarity 0.740, while the lower-MT and lower-cell-count distribution shifts remain in the same direction.
This sensitivity does not resolve the label or count inconsistency and was not chosen for its agreement with the paper.

## Enrichment contract

The notebook retains unique unknown-direction `(target, OASIS_ID)` annotations, keeps targets annotated to at least three OASIS IDs, and expands each retained target to the metadata's physical well-exposure IDs.
Each output has the eight columns `target_set`, `overlap_size`, `target_set_size`, `hit_list_size`, `universe_size`, `p_value`, `overlap_hits`, and `fdr`.
Both historical files and the reconstructed current layers contain 8,858 unique `target_set` keys with identical target-set sizes.
The expanded target-set sizes range from 14 to 5,895 eligible wells, with median 47, and every row uses universe size 13,176.

For each target set, the one-sided overrepresentation p-value is `hypergeom.sf(x - 1, M, n, N)`.
Here `M` is the 13,176-well universe, `n` is the target-set well count, `N` is the selected hit-list size, and `x` is the overlap well count.
Benjamini-Hochberg correction is applied once across all 8,858 target-set p-values with `multipletests(method = "fdr_bh", is_sorted = False)`.
Recalculation of the committed p-values agrees within `1.12e-16`, and recalculation of the committed FDR values agrees within `8.09e-15`.
Serialized `overlap_hits` order and row order among tied FDR values are ignored in every comparison.

| Layer | Notebook group and label | Hit-list size | Target sets with FDR below 0.05 | Minimum p-value | Minimum FDR |
| --- | --- | ---: | ---: | ---: | ---: |
| Committed `err_higher` | Higher, Cell Painting label | 304 | 178 | 8.93308e-27 | 7.91292e-23 |
| Current `err_higher` | Higher, Cell Painting label | 292 | 839 | 1.42726e-27 | 1.26427e-23 |
| Committed `err_lower` | Lower, technical-baseline label | 138 | 0 | 1.13771e-4 | 1.0 |
| Current `err_lower` | Lower, technical-baseline label | 134 | 0 | 2.57451e-3 | 1.0 |

## Historical-to-current drift

The Higher hit-list size decreases by 12 wells, or 3.95%, and the Lower hit-list size decreases by four wells, or 2.90%.
The committed CSVs do not preserve the complete historical hit lists outside target overlaps, so full selected-list membership overlap cannot be reconstructed.
The union of annotated overlap hits contains 255 historical and 248 current Higher IDs, with 201 shared and Jaccard similarity 0.6656.
The corresponding Lower union contains 107 historical and 100 current IDs, with 86 shared and Jaccard similarity 0.7107.

For Higher, 6,885 of 8,858 overlap sizes and 5,914 semantic overlap-hit sets are exact, while 5,072 p-values and 6,962 FDR values are exact.
Higher mean and maximum absolute p-value drift are 0.05182 and 0.85777, and mean and maximum absolute FDR drift are 0.11907 and 0.99094.
The significant-target sets share 177 keys, with one historical-only key and 662 current-only keys.

For Lower, 7,552 of 8,858 overlap sizes and 7,404 semantic overlap-hit sets are exact, while 5,645 p-values and all 8,858 FDR values are exact.
Lower mean and maximum absolute p-value drift are 0.06197 and 0.92253, while FDR drift is exactly zero because every adjusted value is 1.0 in both layers.
Neither Lower layer has a significant target set.

The existing clean-reproduction evidence identifies this as regression-selection drift independent of POD fitting and notes that the XGBoost regressor lacks an explicit seed.
The repository does not establish the cause, so no mechanism is assigned here.

## Paper mapping and decisions

The camera-ready counts are swapped relative to the notebook and CSV mapping.
The paper assigns 138 to the enriched Cell Painting-better group, while the code assigns the Cell Painting label to historical Higher with 304 wells and current Higher with 292 wells.
The paper assigns 304 to the no-enrichment technical-better group, while the code assigns the technical-baseline label to historical Lower with 138 wells and current Lower with 134 wells.

The qualitative enrichment direction remains aligned between prose and code labels: the group labeled Cell Painting is enriched and the group labeled technical baseline has no significant enrichment.
No repository layer simultaneously supports the paper's group labels, counts, and enrichment summaries, and the signed-residual selector prevents independently validating the literal better-predicted direction.

For `ENRICH-001`, neither the committed 178 nor current 839 significant target-set count reproduces the published 480.
No KEGG or other pathway-membership substrate is present in the repository, and the exact pathway counts and FDR values occur only in the paper sources.
The cell-cycle, PI3K-Akt, MAPK, and p53 interpretation therefore cannot be assessed from repository evidence.
Decision: `blocked` because the target-specific 480-target and major-pathway acceptance rule lacks both numerical and pathway support.

For `ENRICH-002`, the no-enrichment conclusion holds exactly in both Lower layers, but those code-labeled technical-baseline groups contain 138 and 134 wells rather than about 304.
The 304 historical and 292 current count scale belongs to Higher, which the code labels Cell Painting and which has significant enrichment.
Decision: `blocked` because count-scale agreement and the no-enrichment conclusion never occur in the same code-labeled source layer.

These results are overrepresentation associations conditional on a selected hit list.
They do not establish a causal or mechanistic explanation for assay behavior.
