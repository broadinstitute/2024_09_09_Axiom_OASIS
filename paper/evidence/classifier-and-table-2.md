# Classifier and Table 2 evidence

Targets: `TABLE-2` and `CLASSIFIER-001`.

The input commit was `904331a8f3b6bb00f167f2149d5764b3871d6b1d`.
This check used the camera-ready PDF and transcription, the committed compiled Axiom metrics, current base-scenario prediction Parquets, stored notebook code, classifier code, and existing reproduction evidence.
No notebook, classifier, or scientific workflow was executed.
Read-only calculations used temporary files under `/tmp`.
AUROC and PRAUC are unitless, so all denominators below are compound samples rather than physical units.

## Source layers and semantics

Camera-ready Table 2 is the acceptance baseline.
The committed `compiled_axiom_metrics.parquet` has SHA-256 `9993bf115589d63e673cab729273cab8f0c93b776012f9f07c74b5629edf5247` and contains 81 unique, non-null `(Metadata_AggType, Metadata_Label, Model_type, Feat_type)` keys.
Its exact labels are aggregation types `all`, `allpod`, and `allpodcc`; assays `LDH`, `MTT`, and `cell_count`; models `Actual`, `Cellcount_baseline`, and `Random_baseline`; and features `cellprofiler`, `cpcnn`, and `dino`.
The paper's MT label maps to the artifact's `MTT`, and active and inactive classes map to `y_actual` values 1 and 0.

The current base prediction hashes are `238dd2091319bab9bb2bd8208a843a8135e3ad976fc6552acca9c2082b7d0910` for CellProfiler, `97a0affbe155bcc430e60ac5f6c7529c6bee4278e2a1f80d5e3a1e49e7a8b062` for CP-CNN, and `179a125c3aff895fc9c87f34e9ceaaf97a691ff0f42ddf0c45ec4a01f8c8f305` for DINO.
The notebook reads these three `mad_featselect` base paths and groups all out-of-fold rows by aggregation, assay, and model before calculating metrics.
The single published baseline rows trace to the `Feat_type = cellprofiler` compiled rows, and the same fixed mapping is used for the current comparison rather than choosing a layer after seeing its agreement.
The other representation-specific baselines were also checked and are summarized below.

`aggregate_profiles.py` calls `pycytominer.aggregate` by `Metadata_OASIS_ID`, whose default operation is the median, and the `all` layer uses every available non-DMSO profile without concentration filtering.
The nominal design has two replicates at eight concentrations, while the current CellProfiler keyed substrate has 959 IDs with 13-16 available profiles and eight IDs with 28-48 profiles; 966 of 967 IDs cover eight concentrations and one covers seven.
CellProfiler and CP-CNN each produce 967 keyed consensus samples representing 966 unique compound names, while DINO produces 966 keyed samples representing 966 names.
The original assay-curve layer has 1,085 unique tested compound names, but 119 rows lack an OASIS ID and therefore cannot join to the classifier profiles.
Vasopressin maps to both `OASIS679` and `OASIS1751` in CellProfiler and CP-CNN and lands in folds 3 and 5, while the DINO substrate lacks `OASIS1751`.
The implementation is therefore compound-level by OASIS ID, with one duplicated chemical name crossing folds in two representations.

| Representation | OASIS-ID samples | Unique compound names | LDH inactive / active | MT inactive / active | Validation-fold sizes |
| --- | ---: | ---: | ---: | ---: | --- |
| CellProfiler | 967 | 966 | 840 / 127 | 589 / 378 | 194, 194, 193, 193, 193 |
| CP-CNN | 967 | 966 | 840 / 127 | 588 / 379 | 194, 194, 193, 193, 193 |
| DINO current base | 966 | 966 | 839 / 127 | 587 / 379 | 194, 193, 193, 193, 193 |

Across all current representation layers, the cell-count baselines range from 0.727169 to 0.730446 AUROC and 0.418538 to 0.419418 PRAUC for LDH, and from 0.684483 to 0.688951 AUROC and 0.636031 to 0.639079 PRAUC for MT.
The representation-specific random baselines range from 0.491760 to 0.550712 AUROC and 0.130230 to 0.159136 PRAUC for LDH, and from 0.494790 to 0.529954 AUROC and 0.389637 to 0.403397 PRAUC for MT.

`classify.py` uses `StratifiedKFold(n_splits=5)` without fold shuffling and emits each OASIS-ID sample once as out-of-fold validation data.
The random baseline first shuffles labels with seed 42, and the cell-count baseline retains only `Cell_Count`.
`3_2_0_assay_metrics.ipynb` computes AUROC with `roc_auc_score` and computes PRAUC as trapezoidal `auc(recall, precision)` after `precision_recall_curve`.
It omits `k_fold` from the grouping key, so metrics are calculated from pooled out-of-fold predictions rather than averaged fold metrics.
An explicit diagnostic average of the five fold-specific metrics differed from the pooled values by as much as 0.02123, confirming that these are distinct estimands.

The Table 2 caption says performance was pooled across 10 train-test splits.
The implementation and STAR Methods instead specify five compound-level stratified folds, so the caption has the correct pooling concept but the wrong split count.
This is a source and provenance inconsistency, and the completed `METHOD-CLASSIFIER` decision is unchanged.

## TABLE-2

Each cell below is the camera-ready value, the committed compiled value, and the value reconstructed from current base predictions.

| Assay | Input features | AUROC camera / compiled / current | PRAUC camera / compiled / current |
| --- | --- | --- | --- |
| LDH | Cell count baseline | 0.73 / 0.730446 / 0.730446 | 0.42 / 0.418538 / 0.418538 |
| LDH | Random baseline | 0.50 / 0.500544 / 0.500544 | 0.14 / 0.137195 / 0.137195 |
| LDH | CellProfiler | 0.93 / 0.932396 / 0.932396 | 0.77 / 0.768307 / 0.768307 |
| LDH | CP-CNN | 0.93 / 0.925928 / 0.925928 | 0.72 / 0.721698 / 0.721698 |
| LDH | DINO | 0.94 / 0.939551 / 0.939551 | 0.77 / 0.769632 / 0.769632 |
| MT | Cell count baseline | 0.69 / 0.688951 / 0.688951 | 0.64 / 0.639079 / 0.639079 |
| MT | Random baseline | 0.51 / 0.505394 / 0.505394 | 0.40 / 0.396563 / 0.396563 |
| MT | CellProfiler | 0.87 / 0.870698 / 0.870698 | 0.84 / 0.842826 / 0.842826 |
| MT | CP-CNN | 0.86 / 0.858888 / 0.858888 | 0.83 / 0.834197 / 0.834197 |
| MT | DINO | 0.87 / 0.875945 / 0.871935 | 0.84 / 0.837959 / 0.832443 |

Nineteen of 20 committed entries and 19 of 20 current entries match the camera-ready values at two-decimal rounding.
The committed mismatch is DINO MT AUROC, which rounds to 0.88 rather than 0.87, and its largest absolute camera-ready deviation is 0.005945.
The current mismatch is DINO MT PRAUC, which rounds to 0.83 rather than 0.84, and its largest absolute camera-ready deviation is 0.007557.
The maximum compiled PRAUC deviation is 0.004197, and the maximum current AUROC deviation is 0.004606.

All mapped compiled and current values are identical except the two DINO MT metrics.
The committed DINO MT row has 588 inactive and 378 active samples, while the current DINO prediction layer has 587 inactive and 379 active samples.
Current direct evidence identifies Clodinafop-propargyl as an active DINO call produced by an order-sensitive assay fit, as documented in `activity-and-figure-2a.md`.
The one-active-sample count change and resulting retraining are consistent with that repository-evidenced call drift, but the absent historical predictions prevent proving which historical label changed or assigning the entire numerical difference to one mechanism.

Decision: `reproduced-with-deviation`.
The schema, semantic mappings, class scale, 19-of-20 rounded agreement, and performance conclusions reproduce, while one rounded entry in each computational layer and the five-fold versus 10-split provenance inconsistency remain explicit deviations.

## CLASSIFIER-001

The current LDH mean across CellProfiler, CP-CNN, and DINO is 0.932625 AUROC and 0.753212 PRAUC.
These values remain near the paper's approximately 0.93 and 0.75 claim.

Every morphology representation exceeds its own cell-count and random baselines for both AUROC and PRAUC in both assays.
The smallest morphology advantage over the cell-count baseline is 0.172305 AUROC and 0.194682 PRAUC, and every random-baseline margin is larger.
This is direct metric ordering only.
Neither Table 2 nor `3_2_0_assay_metrics.ipynb` implements a formal statistical test for these pairwise claims, so no significance claim is made here.

Representation-to-representation ranges remain small: 0.013623 AUROC and 0.047934 PRAUC for LDH, and 0.013047 AUROC and 0.010382 PRAUC for MT.
The localized DINO MT drift changes no ordering and does not alter the paper's conclusion that morphology predicts paired cytotoxicity and outperforms both baselines.

The filtered CellProfiler scenario was inspected only as a separate alternative layer and was not substituted for the notebook's base scenario.
Its SHA-256 is `03e558a37439e6763f403fdb8c617d3bd10b60d3e63d8fdd130b3ed1bea44482`, and its morphology values are 0.930906 AUROC and 0.762049 PRAUC for LDH and 0.870029 AUROC and 0.842454 PRAUC for MT.
It preserves the conclusion but is excluded from the Table 2 comparison.

Decision: `reproduced-with-deviation`.
The claimed magnitudes, representation similarity, and all baseline orderings hold, while the source split-count inconsistency, one duplicated chemical name across ID-level folds, and localized DINO MT numerical drift are retained as deviations.
