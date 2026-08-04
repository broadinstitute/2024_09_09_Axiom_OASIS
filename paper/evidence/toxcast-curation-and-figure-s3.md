# ToxCast curation and Figure S3

Targets: `TOXCAST-001`, `TOXCAST-002`, `TOXCAST-003`, `METHOD-TOXCAST`, and `SFIG-3`.

The input commit was signed commit `6081dd364648f73c26f948199d5a5afa1ae9ea1d`.
This audit used camera-ready main-page 7 and STAR Methods pages e3-e4, published supplemental Figure S3, the six pinned ToxCast Parquets, the pinned OASIS annotation CSV, the current exposure metadata, committed code and stored outputs in notebooks `3B_extract_invitrodb.ipynb` and `3_1_toxcast_endpoints.ipynb`, and the compiled-metric context in `REPRODUCING.md`.
No notebook or scientific workflow was executed.
All scratch calculations were read-only and wrote only under `/tmp`.

## Compound overlap and identifier semantics

The tested-library denominator is 1,085 unique non-DMSO compound names in `metadata.parquet`.
The pinned `v5_oasis_03Sept2024_simple.csv` mapping has 1,494 rows and 1,477 unique, non-missing, one-to-one `(OASIS_ID, DTXSID)` pairs.
Sixteen exact pair groups are repeated and account for 17 excess mapping rows, but no OASIS ID maps to multiple DTXSIDs and no DTXSID maps to multiple OASIS IDs after exact deduplication.

Notebook `3B_extract_invitrodb.ipynb` selects the full mapping without deduplication, renames `DTXSID` to `dsstox_substance_id`, and inner-joins ToxCast chemicals on that EPA DTXSID.
Notebook `3_1_toxcast_endpoints.ipynb` then unions the distinct `OASIS_ID` values present in the three binary matrices.
The cell-based and cytotoxicity matrices have the same 963-ID set, and the 371 cell-free IDs are a subset.
The sorted 963-ID union, serialized one ID per line with a terminal newline, has SHA-256 `5e52764163aebbde6682d6ccda67136f918fa1600470566c704e39b73545c5c7`.
This exactly reproduces the stored notebook output of 963, and `963 / 1,085 = 88.755760%`, which rounds to the published 89%.

The implementation does not intersect that 963-ID union with the tested-compound metadata.
The tested metadata has 119 compound names with a missing OASIS ID, 966 names with at least one OASIS ID, and 967 distinct non-missing IDs because Vasopressin has `OASIS679` and `OASIS1751`.
Only 670 tested OASIS IDs, representing 670 tested names, intersect the pinned 963-ID ToxCast union.
There are 293 ToxCast-union IDs absent from the tested metadata and 297 tested IDs absent from the ToxCast union.
The current pinned tested-ID intersection is therefore `670 / 1,085 = 61.751152%`, not 89%.

The reported 963 is a distinct OASIS-ID-grained union, not a raw-row count and not a tested-library intersection.
Missing tested identifiers cannot enter an ID join.
Repeated mapping and assay rows remain in the info Parquets, which contain 3,477, 295, and 305 exact duplicate rows for cell-based, cell-free, and cytotoxicity data, but compound-endpoint majority aggregation and pivoting collapse the binary outputs to one value per OASIS ID and endpoint.
This is an identifier-join and universe-definition deviation in the pinned repository, independent of any invitrodb release drift.
No behavior of a newer invitrodb release was inferred.

## Pinned endpoint contracts

Endpoint hashes below are SHA-256 values of sorted endpoint keys serialized one per line with a terminal newline.

| Category | Info contract | Binary contract | Binary missingness and support | Endpoint hash |
| --- | --- | --- | --- | --- |
| Cell-based | 144,203 rows x 31 columns; 963 IDs; 292 endpoints; 1,680 missing raw AC50s and 93,101 missing matched cytotoxicity AC50s | 963 rows x 293 columns; 292 endpoint columns | 174,093 null, 107,103 observed of 281,196 cells; minimum 5 positive and 7 negative | `6be7d8b85dbd9be85a4c71938c95827455aa8bb0a3c9ab1f67e4d336af44eac1` |
| Cell-free | 4,032 rows x 27 columns; 359 IDs; 72 endpoints; 10 missing AC50s | 371 rows x 73 columns; 72 endpoint columns and 12 all-null ID rows | 23,627 null, 3,085 observed of 26,712 cells; minimum 5 positive and 5 negative | `3ff042d1a15806550011113255baf86a7d16ec4c204975f777ded38d99f0d830` |
| Cytotoxicity | 19,380 rows x 10 columns; 963 IDs; 48 source categories; 15,958 missing consensus AC50s | 963 rows x 39 columns; 38 retained endpoint columns | 17,745 null, 18,849 observed of 36,594 cells; minimum 5 positive and 12 negative | `dd72c42de0a3e6748dbf757fe592ac9f7cfa45fe1ae30caf42dd548d65855102` |

The 292 and 72 info endpoint-key sets exactly equal their binary column-key sets.
Their counts and hashes reproduce the published cell-based and cell-free contracts.
The cytotoxicity info key set contains 28 cell-type and 20 tissue categories, for 48 total, with hash `5e4ae4cad194074b1c4289ccc42311ee8a8b8b62254350d2cbac8ae2b7fe9b40`.
The minimum-class-support filter retains only 23 cell-type and 15 tissue categories, for the 38-key binary hash above.

The ten source categories excluded for fewer than five positives are `cell_type__HUVEC` (2 positive, 19 negative), `cell_type__IMR90_(neural_crest_cells_differentiated_from_iPSC)` (3, 12), `cell_type__SBAD2_(peripheral_neurons_differentiated_from_iPSC)` (2, 13), `cell_type__hNPC` (4, 37), `cell_type__iPSC` (3, 18), `tissue__brain` (4, 37), `tissue__embryo` (3, 12), `tissue__iPS-derived_endothelial_cells` (3, 18), `tissue__peripheral_nervous_system` (2, 13), and `tissue__umbilical_vein-derived_endothelial_cells` (2, 19).
The paper's 48 therefore describes consensus source categories before the stated final class-support rule, while the classification-ready binary contains 38.

Current compiled metrics contain 7,209 cell-based rows over 267 labels, 1,431 cell-free rows over 53 labels, and 918 cytotoxicity rows over 34 labels after profile intersection and downstream eligibility.
`REPRODUCING.md` records exact regenerated row and semantic-key sets for those metrics and bit-exact core values for the 2,709 `AggType == "all"` cell-based and cytotoxicity rows.
Those downstream subsets independently validate stable label consumption but do not turn 38 classification-ready cytotoxicity keys into 48.

## Curation rule trace

The committed extraction notebook implements these rules upstream of the six Parquets.

- It makes a positive call only when `hitcall > 0.9`, so equality at 0.9 is inactive.
- It joins chemicals by EPA DTXSID and carries the matched OASIS ID into every output.
- It selects human cell and cell-free formats, excludes whole embryos, follow-up assay names, names containing `TRANS` or `EcoTox`, `_ch1` and `_ch2` components, named real-time viability channels, background reporters, and background-control endpoints.
- It represents the closest-to-44-hour choice through explicit removal of `CLD_6hr`, `CLD_24hr`, `APR_HepG2_1hr`, and `APR_HepG2_72hr`, rather than a general nearest-time calculation.
- The pinned retained data have one time point per endpoint and contain no `_ch1`, `_ch2`, background-reporter, or background-control endpoint.
- It aggregates viability rows by compound and `cell_short_name` and separately by compound and tissue.
- A consensus cytotoxicity call is positive when `nhit / ntested >= 0.2`, and its AC50 is the median AC50 among positive component calls.
- Specific cell-based rows use a cell-level match when present and tissue fallback otherwise; the pinned info file has 107,843 cell-level rows and 36,360 tissue-fallback rows.
- A specific endpoint is inactivated only when its AC50 is strictly greater than half the matched consensus cytotoxicity AC50; no pinned positive row is exactly equal to the half-AC50 boundary.
- Duplicate compound-endpoint groups use `sum > floor(count / 2)`, so even ties are inactive.
- The cell-based, cell-free, and cytotoxicity inputs contain 23,644, 388, and 287 duplicate compound-endpoint groups; 716 cell-based and 21 cell-free groups are even ties, and no cytotoxicity group is tied.
- Endpoint retention counts observed zeros and ones and requires at least five of each, ignoring null matrix cells.

The paper's general rule that any positive specific-endpoint AC50 above 100 uM is reset inactive is not implemented for cell-based or cell-free endpoints.
The code applies the 100 uM ceiling only to consensus cytotoxicity AC50s before generating the cytotoxicity binary.
The pinned cell-based info contains 555 positive raw rows above 100 uM, of which 138 remain positive after the implemented cytotoxicity comparison.
Applying the stated 100 uM rule before majority aggregation would reduce the final cell-based positive count from 8,400 to 8,332 and remove `ATG_FoxA2_CIS` from the endpoint set, reducing 292 endpoints to 291.
The cell-free info has two positive rows stored as 100.00000000000001 uM for `CCTE_GLTED_hIYD`; applying the strict rule changes the final binary call for `OASIS1388`, while `OASIS1513` remains positive by majority because it has two additional positive rows below 100 uM.

The notebook's re-expression of the cell-based majority calculation exactly equals the committed 292-column binary with zero keyed value differences.
Before cytotoxicity filtering it has 17,110 positives, and afterward it has 8,400 positives.
Both percentages use the full `963 x 292 = 281,196` rectangular matrix, including 174,093 null cells, so they are `17,110 / 281,196 = 6.084724%` and `8,400 / 281,196 = 2.987240%`, which round to the published 6.1% and 3.0%.
The reduction is `8,710 / 17,110 = 50.905903%`, which rounds to 51%.
Among the 107,103 observed compound-endpoint cells, the corresponding fractions are 15.975276% and 7.842918%.
The published totals therefore reproduce the stored implementation, but their denominator includes unmeasured null cells and their calculation omits the separately stated 100 uM rule.

Notebook `3B_extract_invitrodb.ipynb` contains the upstream SQL extraction and curation code, while notebook `3_1_toxcast_endpoints.ipynb` reads the pre-curated Parquets and re-expresses only summaries and selected binary logic.
The raw invitrodb v4.1 database is not committed, and `3A_download_invitrodb.sh` is documented as non-functional and requiring an approximately 100 GB external MySQL import.
The repository therefore has code provenance and pinned outputs, but it does not have an executable repository-only derivation from raw invitrodb to those outputs.

## Endpoint composition

The composition notebook first reduces each info file to one unique metadata row per retained endpoint.
The cell-based denominator is all 292 metadata rows, and the cell-free denominator is all 72 metadata rows; none of the selected composition fields is missing.

| Published summary | Pinned numerator / denominator | Exact pinned percentage |
| --- | ---: | ---: |
| Cell-based liver | 151 / 292 | 51.712329% |
| Cell-based vascular | 63 / 292 | 21.575342% |
| Cell-based kidney | 35 / 292 | 11.986301% |
| Cell-free binding | 37 / 72 | 51.388889% |
| Cell-free enzymatic activity | 35 / 72 | 48.611111% |
| Cell-free GPCR family | 21 / 72 | 29.166667% |
| Cell-free CYP family | 11 / 72 | 15.277778% |
| Cell-free nuclear-receptor family | 10 / 72 | 13.888889% |

The six cell-based target-type counts are protein 135, RNA 96, pathway 33, cellular 15, molecular messenger 12, and DNA 1.
The paper's 84% individual-molecule summary is `(protein + RNA + molecular messenger + DNA) = 244 / 292 = 83.561644%`, leaving pathway plus cellular as `48 / 292 = 16.438356%`.

The reported 36 cell-based families and their 19%, 18%, and 11% leaders come from all 292 endpoint metadata rows: nuclear receptor `56 / 292 = 19.178082%`, DNA binding `54 / 292 = 18.493151%`, and cytokine `32 / 292 = 10.958904%`.
That denominator does not match the paper's wording about only individual mRNA and protein targets.
Restricting to the 244 individual-molecule rows gives 34 families and leaders DNA binding `43 / 244 = 17.622951%`, nuclear receptor `38 / 244 = 15.573770%`, and cytokine `32 / 244 = 13.114754%`.
The cell-free file has 11 families over all 72 endpoints.

The published endpoint-overlap and activity medians reproduce exactly from non-null binary calls: 346 compounds and 20.683488% active over the 38 retained cytotoxicity endpoints, 306 and 7.116136% over 292 cell-based endpoints, and 33 and 41.342952% over 72 cell-free endpoints.
These round to the published 346, 306, and 33 compounds and 21%, 7%, and 41% active, with zero difference at displayed precision and unchanged rankings.
Using all 48 pre-support cytotoxicity source categories instead gives medians of 135 compounds and 19.259259% active.
The camera-ready cytotoxicity medians therefore depend on the unreported 38-endpoint post-support subset even though the preceding count is 48.

## Figure S3 provenance and qualitative result

Panel A in the published supplemental PDF matches the extraction code's human-cell selection, viability split, cell and tissue consensus, 20% rule, median positive AC50, cell-preferred tissue fallback, half-consensus-AC50 inactivation, and five-positive/five-negative retention flow.
The hit-call threshold and 100 uM handling come from STAR Methods and code rather than the panel itself, with the specific-endpoint 100 uM deviation described above.

The heatmap code selects categories using info-row counts strictly greater than 800, fills existing null consensus AC50 values with 100 uM, pivots with `first`, drops any compound lacking one of the selected categories, and clusters rows and columns with Euclidean distance and average linkage.
Although 24 of 28 cell categories and 16 of 20 tissue categories contain duplicate info rows, selection by unique OASIS-compound count yields the same retained categories.
The selected duplicate groups have no discordant filled AC50 values, so the `first` aggregation does not change values.
The viridis scale is linear from 0 to 100 uM, with lower darker values indicating cytotoxicity at a lower concentration.
Values above 100 uM have already been nulled in the upstream consensus step before the heatmap fills nulls with 100.

The 12 plotted cell categories are `cell_type__HepG2`, `cell_type__HCT116`, `cell_type__HEK293T`, `cell_type__MDA-kb2`, `cell_type__VM7`, `cell_type__HeLa`, `cell_type__MCF7`, `cell_type__ERR-HEK293T`, `cell_type__HEK293`, `cell_type__ME-180`, `cell_type__PGC/ERR_HEK293T`, and `cell_type__PR-UAS-bla-HEK293T`.
They contain 958, 957, 957, 957, 957, 943, 934, 862, 862, 862, 862, and 862 unique OASIS IDs, respectively.
The six plotted tissue categories are `tissue__breast`, `tissue__liver`, `tissue__cervix`, `tissue__kidney`, `tissue__intestinal`, and `tissue__colon`, with 958, 958, 957, 957, 934, and 862 unique IDs.
The cell pivot has 958 IDs by 12 categories and the tissue pivot has 959 IDs by six categories before complete-case filtering.
Both heatmaps cluster the same 839 complete OASIS IDs.
These plotted subsets are separate from the 28 cell-type and 20 tissue source categories used to form all 48 consensus source readouts.

Across the 839 complete compounds, cell-category pairwise Spearman correlations have median 0.561 and range 0.338-0.878, while binary active/inactive agreement has median 86.9% and range 76.5%-95.7%.
There are 513 compounds inactive in all 12 cells, 23 active in all 12, and 303 active in only a subset, spanning 166 binary patterns.
Tissue-category Spearman correlations have median 0.534 and range 0.265-0.722, while binary agreement has median 88.0% and range 79.4%-90.9%.
There are 599 compounds inactive in all six tissues, 13 active in all six, and 227 active in only a subset, spanning 35 binary patterns.
This quantitatively supports broad cross-category agreement together with substantial cell- and tissue-selective structure.
A diagnostic four-cluster cut of the same Euclidean-average row linkage contains a 79-compound cell cluster with median AC50 28.41 uM and median activity in 10 of 12 cells, and a 59-compound tissue cluster with median AC50 28.19 uM and median activity in five of six tissues, alongside large predominantly inactive clusters.
The cut is a scratch summary rather than an acceptance baseline for exact cluster order.

The published image itself is lettered A for the flow, B for the cell heatmap, and C for the tissue heatmap.
The main text's Figure S3A, S3B, and S3C references agree with those image labels.
The supplemental legend instead calls the cell and tissue heatmaps C and D, including a nonexistent panel D.
This source-label inconsistency is retained rather than silently corrected.
Exact pixels, dendrogram order, and the JPEG navigation copy were not used as acceptance baselines.

## Decisions and conclusion impact

`TOXCAST-001` is reproduced with deviation because 963 and 89% reproduce exactly, but the numerator is a full annotation-ID union rather than a tested-library intersection.
`TOXCAST-002` is reproduced with deviation because the 48, 292, and 72 source metadata counts are exact, but final minimum-support binaries contain 38, 292, and 72 endpoints and the stated 100 uM rule would change the cell-based endpoint set.
`METHOD-TOXCAST` is reproduced with deviation because the principal thresholds, consensus, matching, confounding, majority, and support rules are traced, while the general 100 uM rule is not applied to specific endpoints and raw invitrodb regeneration is unavailable repository-only.
`TOXCAST-003` is reproduced with deviation because every displayed composition and median value and every ranking match, while the cell-family wording uses all 292 endpoints and the cytotoxicity medians use 38 rather than all 48 source categories.
`SFIG-3` is reproduced with deviation because the code, category coverage, scale, clustering conventions, and broad selective-cluster result agree, while the supplemental legend misletters the actual B and C heatmaps as C and D.

The tissue, function, family, overlap-median, active-fraction, heatmap concordance, and selective-pattern interpretations remain intact.
The 963-compound coverage statement is not supported as a tested-library overlap by the pinned repository, and the published endpoint-count wording obscures which cytotoxicity subset contributes to downstream summaries and models.
