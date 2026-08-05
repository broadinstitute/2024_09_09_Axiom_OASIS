# Tracked paper audit

This report is an archive-safe reanalysis of tracked sources, annotations, and compiled artifacts.
It is not a rerun of ignored scientific workflows and its figures are not publisher reproductions.
An execution outcome of `checked` means the declared checks passed against tracked inputs; it does not mean upstream workflows were regenerated.
Historical ledger status is retained for provenance and does not determine the execution outcome.

Mode: `tracked`.
Targets covered: 53.
Executed groups: sources_design, activity_pods, regression_enrichment, toxcast, classifier, external_image.
Validated tracked inputs: 60.
Ledger SHA-256: `795bcb88a56565ec032d5c2ca05054672994daa5978c39b997d23025b6156ce4`.

## Execution outcome counts

| Execution outcome | Count |
| --- | ---: |
| blocked | 3 |
| checked | 32 |
| documentary-only | 17 |
| out-of-scope | 1 |

## Historical ledger status counts

| Ledger status | Count |
| --- | ---: |
| blocked | 3 |
| reproduced | 7 |
| reproduced-with-deviation | 43 |

## Evidence coverage

| Evidence strength | Targets |
| --- | ---: |
| derived-artifact-reanalysis | 18 |
| documentary-trace | 17 |
| source-recomputation | 17 |
| unavailable | 1 |

[Open the evidence-coverage figure](evidence-coverage.svg).

## Sources, design, and Table S1

All 8 manifest sources passed SHA-256 and byte-count checks.
All 6 Office archives passed ZIP CRC checks.
Table S1 has 1085 rows, 966 stable IDs, and 119 blank IDs.

## Activity and PODs

The direction-aware cytotoxicity trace records 429 compounds and explicitly records that direction is absent from hit_summary.csv.

| Figure 2A compound | Published Table S2 POD (uM) |
| --- | ---: |
| Benzarone | 69.3371 |
| Tiratricol | 25.8604 |
| Tolcapone | 23.6063 |
| 2-Ethylanthracene-9,10-dione | 8.66085 |

Figure 2C has 156 published-SI five-series cases and 488 three-general cases.
The three-general CP-CNN ratios are 1.81811 over CellProfiler and 1.68649 over DINO.
The three-general CellProfiler-DINO paired-log10 p-value is 0.261389.
Figure 2D has 121 published-SI complete cases and preserves the morphology, MT, cell-count, LDH median ordering.

[Open the POD-summary figure](pod-summary.svg).

## Regression and enrichment

Regression and Figure S2 numerical acceptance was not rerun because the required prediction and metric Parquets are not tracked.
Their recipes validate the paper, producer notebook, implementation, and evidence trace explicitly.
The four tracked enrichment tables were directly recomputed with upper-tail hypergeometric tests and BH FDR.

| Enrichment artifact | Hit list | Significant sets | Maximum p error | Maximum FDR error |
| --- | ---: | ---: | ---: | ---: |
| err_higher_targets.csv | 304 | 178 | 1.11e-16 | 1.11e-16 |
| err_lower_targets.csv | 138 | 0 | 1.11e-16 | 0 |
| mtt_higher_targets.csv | 261 | 147 | 1.11e-16 | 1.11e-16 |
| mtt_lower_targets.csv | 131 | 107 | 1.11e-16 | 1.11e-16 |

MT-higher significant classes: {"cyp_prefix_count": 8, "htr_prefix_count": 6, "transporters_present": ["ABCB1", "ABCG2", "SLCO1B1", "SLCO1B3"]}.
MT-lower significant classes: {"cyp_prefix_count": 3, "psm_prefix_count": 18}.

[Open the enrichment-summary figure](enrichment-summary.svg).

## ToxCast and Table S5

The pinned binary annotation union contains 963 OASIS IDs; it is not a tested-library join.
Tracked evidence documents an actual tested-library intersection of 670 IDs (61.751152%).
Cell-based tissue composition: {"kidney": 35, "liver": 151, "vascular": 63}.
Cell-free assay composition: {"binding": 37, "enzymatic activity": 35}.
Cell-free target-family composition: {"cyp": 11, "gpcr": 21, "nuclear receptor": 10}.
Median compounds observed per endpoint: {"cellbased": 306, "cellfree": 33, "cytotox": 346}.
Median endpoint active fractions: {"cellbased": 0.071161355334425, "cellfree": 0.413429522752497, "cytotox": 0.206834880123743}.
The heatmap substrate has 12 cell categories, 6 tissue categories, and 839 complete compounds.
Table S5 has 12 nuclear-receptor assays and 0 source cytotoxicity hits.

[Open the ToxCast-summary figure](toxcast-summary.svg).

## Classifier metrics

Modeled endpoint counts: {"axiom": 2, "toxcast_cellbased": 267, "toxcast_cellfree": 53, "toxcast_cytotox": 34}.
All-concentration CellProfiler median AUROC and PRAUC: {"axiom": {"auroc": 0.90154710075502, "prauc": 0.805566469136103}, "toxcast_cellbased": {"auroc": 0.607226107226107, "prauc": 0.144839974879456}, "toxcast_cellfree": {"auroc": 0.532085561497326, "prauc": 0.454015201822219}, "toxcast_cytotox": {"auroc": 0.737210441587034, "prauc": 0.477454853975985}}.
DINO cell-based target effects: {"dino_vs_cellprofiler_cellbased_auroc": {"mean_difference": 0.0118822411673017, "median_difference": 0.0220902090209021}, "dino_vs_cpcnn_cellbased_auroc": {"mean_difference": 0.010790455248826, "median_difference": 0.0158730158730159}}.

| Family | Metric | allpodcc minus allpod mean | Median | Matched endpoints |
| --- | --- | ---: | ---: | ---: |
| axiom | auroc | -0.124974 | -0.124974 | 2 |
| axiom | prauc | -0.372361 | -0.372361 | 2 |
| toxcast_cellbased | auroc | -0.00797019 | -0.0047356 | 267 |
| toxcast_cellbased | prauc | -0.0065968 | -0.00425904 | 267 |
| toxcast_cellfree | auroc | 0.0134292 | 0.0266667 | 53 |
| toxcast_cellfree | prauc | 0.00515196 | -0.00237447 | 53 |
| toxcast_cytotox | auroc | -0.088586 | -0.0850192 | 34 |
| toxcast_cytotox | prauc | -0.167164 | -0.177995 | 34 |

[Open the classifier-summary figure](classifier-summary.svg).

## External image boundary

The raw source TIFF and image index are absent from the tracked audit, but the external producer and measured inventory-count deviation are documented.

## Generated figures

Each SVG is generated from this report and labeled as tracked-artifact reanalysis.

- [Evidence coverage](evidence-coverage.svg)
- [POD summary](pod-summary.svg)
- [Enrichment summary](enrichment-summary.svg)
- [ToxCast summary](toxcast-summary.svg)
- [Classifier summary](classifier-summary.svg)

## Targets

### DESIGN-001 - Tested compound design

Source: main:p2-p3:experimental-design.
Kind: claim.
Expected: 1085 compounds; eight concentrations from 0.01 to 100 uM; two biological replicates.
Full acceptance: exact: counts, range, and replicate design agree.
Producer: 1_snakemake/inputs/metadata/metadata.parquet.
Ledger evidence: evidence/experimental-design-and-figure-1.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `documentary-only`; availability: `documentary-only`; evidence strength: `documentary-trace`.
Declared deviation: Published design and 1085-compound library agree; post-QC metadata excludes three microscope plates, leaving Hycanthone at seven concentrations and 941 of 8679 compound-concentration groups with one retained row.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| DESIGN-001:01 - published compound, dose, and replicate design | True | True | true |

Validated inputs:
- `paper/paper.md`
- `paper/evidence/experimental-design-and-figure-1.md`

Limitations and deviations:
- Published design and 1085-compound library agree; post-QC metadata excludes three microscope plates, leaving Hycanthone at seven concentrations and 941 of 8679 compound-concentration groups with one retained row
- The required numerical substrate is not tracked; numerical acceptance was not rerun, and this recipe validates source, notebook, or code trace only.

### DESIGN-002 - Image representation feature counts

Source: main:p2-p3:experimental-design.
Kind: claim.
Expected: CellProfiler 5640; CP-CNN 672; DINO 4608.
Full acceptance: exact: representation names and feature counts agree.
Producer: 0_prepare_data; downloaded profile schemas.
Ledger evidence: evidence/experimental-design-and-figure-1.md.
Historical ledger status: `reproduced`.
Execution outcome: `documentary-only`; availability: `documentary-only`; evidence strength: `documentary-trace`.
Declared deviation: -.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| DESIGN-002:01 - published representation feature counts | True | True | true |

Validated inputs:
- `paper/paper.md`
- `paper/evidence/experimental-design-and-figure-1.md`

Limitations and deviations:
- The required numerical substrate is not tracked; numerical acceptance was not rerun, and this recipe validates source, notebook, or code trace only.

### DESIGN-003 - Assay and exposure design

Source: main:p2-p3:experimental-design.
Kind: claim.
Expected: 384-well plates; 44-hour exposure; Cell Painting, LDH, and MT readouts.
Full acceptance: exact: procedural constants and readout types agree.
Producer: paper methods; input metadata.
Ledger evidence: evidence/experimental-design-and-figure-1.md.
Historical ledger status: `reproduced`.
Execution outcome: `documentary-only`; availability: `documentary-only`; evidence strength: `documentary-trace`.
Declared deviation: -.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| DESIGN-003:01 - published assay and exposure constants | True | True | true |

Validated inputs:
- `paper/paper.md`
- `paper/evidence/experimental-design-and-figure-1.md`

Limitations and deviations:
- The required numerical substrate is not tracked; numerical acceptance was not rerun, and this recipe validates source, notebook, or code trace only.

### FIG-1 - Overview of the experimental design

Source: main:p3:figure-1.
Kind: figure.
Expected: The published workflow connects compound exposures to three measured assays and prediction outcomes.
Full acceptance: qualitative: same experimental stages, sample scale, assays, and intended outcomes; publisher layout need not match.
Producer: unknown.
Ledger evidence: evidence/experimental-design-and-figure-1.md.
Historical ledger status: `reproduced`.
Execution outcome: `documentary-only`; availability: `documentary-only`; evidence strength: `documentary-trace`.
Declared deviation: -.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| FIG-1:01 - Figure 1 workflow stages and outcomes | True | True | true |

Validated inputs:
- `paper/figures/figure-1.jpg`
- `paper/evidence/experimental-design-and-figure-1.md`

Limitations and deviations:
- The required numerical substrate is not tracked; numerical acceptance was not rerun, and this recipe validates source, notebook, or code trace only.

### ACTIVITY-001 - Activity counts in paired cytotoxicity-related assays

Source: main:p3:results-2.1.1.
Kind: claim.
Expected: MT 430 of 1085; cell count 221; LDH 144; 438 unique active compounds.
Full acceptance: exact: counts agree on the fixed published substrate.
Producer: 2_downstream_analysis/manuscript_notebooks/1_2_number_active_readouts.ipynb.
Ledger evidence: evidence/activity-and-figure-2a.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `source-recomputation`.
Declared deviation: CellProfiler Parquets reproduce 430/221/144 and 438 unique; the DINO count notebook yields 431/220/144 and 439, while published Table S2 has 429/220/147 and 437 unique.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| ACTIVITY-001:01 - published Table S2 activity counts | {"Cell count": 220, "LDH": 147, "MT": 429, "unique_compounds": 437} | {"Cell count": 220, "LDH": 147, "MT": 429, "unique_compounds": 437} | true |

Validated inputs:
- `paper/sources/table-s2.xlsx`
- `2_downstream_analysis/compiled_results/SI_tables/mt_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellcount_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/ldh_pods.csv`

Limitations and deviations:
- CellProfiler Parquets reproduce 430/221/144 and 438 unique; the DINO count notebook yields 431/220/144 and 439, while published Table S2 has 429/220/147 and 437 unique

### ACTIVITY-002 - Overall cytotoxic compound count

Source: main:p3:results-2.1.1.
Kind: claim.
Expected: 429 compounds are cytotoxic in at least one assay.
Full acceptance: exact: count and direction-aware definition agree.
Producer: 2_downstream_analysis/manuscript_notebooks/1_2_number_active_readouts.ipynb.
Ledger evidence: evidence/activity-and-figure-2a.md.
Historical ledger status: `reproduced`.
Execution outcome: `documentary-only`; availability: `documentary-only`; evidence strength: `documentary-trace`.
Declared deviation: -.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| ACTIVITY-002:01 - direction-aware cytotoxic compound count | 429 | 429 | true |
| ACTIVITY-002:02 - direction-aware definition trace | True | True | true |

Validated inputs:
- `2_downstream_analysis/compiled_results/SI_tables/hit_summary.csv`
- `paper/evidence/activity-and-figure-2a.md`

Limitations and deviations:
- The required numerical substrate is not tracked; numerical acceptance was not rerun, and this recipe validates source, notebook, or code trace only.

### ACTIVITY-003 - Compounds with increased MT readout

Source: main:p3:results-2.1.1.
Kind: claim.
Expected: Ten compounds increase MT; four have particularly strong responses.
Full acceptance: close: same small set and same four dominant responses; document borderline call differences.
Producer: 2_downstream_analysis/manuscript_notebooks/1_2_1_cmpds_increase_mt.ipynb.
Ledger evidence: evidence/activity-and-figure-2a.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `documentary-only`; availability: `documentary-only`; evidence strength: `documentary-trace`.
Declared deviation: CellProfiler reproduces ten and the same four dominant compounds; the DINO notebook adds Clodinafop-propargyl after an order-sensitive Exp2-to-Exp3 model change.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| ACTIVITY-003:01 - camera-ready increasing-MT call count | 10 | 10 | true |
| ACTIVITY-003:02 - increasing-MT count documentary trace | True | True | true |
| ACTIVITY-003:03 - four dominant increasing-MT compounds | ["Benzarone", "Tiratricol", "Tolcapone", "2-Ethylanthracene-9,10-dione"] | ["Benzarone", "Tiratricol", "Tolcapone", "2-Ethylanthracene-9,10-dione"] | true |
| ACTIVITY-003:04 - increasing-MT direction | increasing MT | increasing MT | true |

Validated inputs:
- `paper/evidence/activity-and-figure-2a.md`
- `2_downstream_analysis/compiled_results/SI_tables/mt_pods.csv`

Limitations and deviations:
- CellProfiler reproduces ten and the same four dominant compounds; the DINO notebook adds Clodinafop-propargyl after an order-sensitive Exp2-to-Exp3 model change
- The required numerical substrate is not tracked; numerical acceptance was not rerun, and this recipe validates source, notebook, or code trace only.

### FIG-2A - Strong MT-increasing concentration-response curves

Source: main:p4:figure-2a.
Kind: figure.
Expected: Four dominant MT-increasing compounds with POD markers.
Full acceptance: qualitative: same compounds, response direction, and approximate curve and POD locations.
Producer: 2_downstream_analysis/manuscript_notebooks/1_2_1_cmpds_increase_mt.ipynb.
Ledger evidence: evidence/activity-and-figure-2a.md.
Historical ledger status: `reproduced`.
Execution outcome: `checked`; availability: `available`; evidence strength: `source-recomputation`.
Declared deviation: -.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| FIG-2A:01 - Figure 2A four published compounds | ["Benzarone", "Tiratricol", "Tolcapone", "2-Ethylanthracene-9,10-dione"] | ["Benzarone", "Tiratricol", "Tolcapone", "2-Ethylanthracene-9,10-dione"] | true |
| FIG-2A:02 - Figure 2A Table S2 POD agreement | 4.4072791993698957e-07 | 1e-06 | true |

Validated inputs:
- `paper/sources/table-s2.xlsx`
- `2_downstream_analysis/compiled_results/SI_tables/mt_pods.csv`
- `paper/evidence/activity-and-figure-2a.md`

Limitations and deviations:
- None declared.

### BIOACTIVITY-001 - Morphological bioactivity frequency

Source: main:p5:results-2.1.2.
Kind: claim.
Expected: 34-59 percent active depending on representation and distance metric; CellProfiler global is the 34 percent outlier.
Full acceptance: close: same range, ordering, and outlier; small POD pass-call drift is acceptable.
Producer: 2_downstream_analysis/manuscript_notebooks/4_1_results_tables_SI.ipynb.
Ledger evidence: evidence/bioactivity-and-figure-2b-d.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `source-recomputation`.
Declared deviation: Current notebook-read data preserve 34-59 percent and ordering; published Table S3 has 169 CellProfiler-global calls (15.6 percent) versus the panel's 372 (34.3 percent) because of model/pass-call drift..

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| BIOACTIVITY-001:01 - all published-SI morphology count estimands | {"cellprofiler": {"categorical": 598, "general": 607, "global": 169}, "cpcnn": {"categorical": 0, "general": 539, "global": 539}, "dino": {"categorical": 626, "general": 644, "global": 545}} | {"cellprofiler": {"categorical": 598, "general": 607, "global": 169}, "cpcnn": {"categorical": 0, "general": 539, "global": 539}, "dino": {"categorical": 626, "general": 644, "global": 545}} | true |
| BIOACTIVITY-001:02 - CellProfiler-global published-SI fraction | [0.155760368663594, 0.0005] | 0.156 | true |
| BIOACTIVITY-001:03 - CellProfiler general published-SI count | 607 | 607 | true |
| BIOACTIVITY-001:04 - published-SI general morphology ordering over cytotoxic assays | True | True | true |

Validated inputs:
- `paper/sources/table-s3.xlsx`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_cellprofiler_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_cpcnn_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_dino_pods.csv`
- `paper/evidence/bioactivity-and-figure-2b-d.md`

Limitations and deviations:
- Current notebook-read data preserve 34-59 percent and ordering; published Table S3 has 169 CellProfiler-global calls (15.6 percent) versus the panel's 372 (34.3 percent) because of model/pass-call drift.

### FIG-2B - Active-compound counts and morphology POD distributions

Source: main:p4:figure-2b.
Kind: figure.
Expected: Representation and distance choices produce the published activity-count ordering and POD distributions.
Full acceptance: qualitative: same ordering, approximate proportions, and distribution shapes.
Producer: 2_downstream_analysis/manuscript_notebooks/1_3_compare_pods.ipynb.
Ledger evidence: evidence/bioactivity-and-figure-2b-d.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `source-recomputation`.
Declared deviation: Current counts differ by at most six and medians by 0.6 uM; published Table S3 loses 203 CellProfiler-global calls and shifts its median from 25.0 to 52.8 uM..

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| FIG-2B:01 - CellProfiler general active compounds | 607 | 607 | true |
| FIG-2B:02 - DINO general active compounds | 644 | 644 | true |

Validated inputs:
- `paper/sources/table-s3.xlsx`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_cellprofiler_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_cpcnn_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_dino_pods.csv`

Limitations and deviations:
- Current counts differ by at most six and medians by 0.6 uM; published Table S3 loses 203 CellProfiler-global calls and shifts its median from 25.0 to 52.8 uM.

### BIOACTIVITY-002 - Relative morphology POD sensitivity by representation

Source: main:p5:results-2.1.2.
Kind: claim.
Expected: CP-CNN PODs are about 2.0-fold higher than CellProfiler and 1.5-fold higher than DINO; CellProfiler and DINO are not significantly different.
Full acceptance: close: ratios remain near published magnitude and statistical conclusion is unchanged.
Producer: 2_downstream_analysis/manuscript_notebooks/1_3_compare_pods.ipynb.
Ledger evidence: evidence/bioactivity-and-figure-2b-d.md.
Historical ledger status: `blocked`.
Execution outcome: `blocked`; availability: `blocked`; evidence strength: `source-recomputation`.
Declared deviation: Ratios remain near 2.0 and 1.5, but CellProfiler-DINO is p=0.261 in published SI, p=0.034 on the current notebook path, and p=0.0545 with the filtered config; the absent historical extended matrix is excluded..

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| BIOACTIVITY-002:01 - three-general shared compounds | 488 | 488 | true |
| BIOACTIVITY-002:02 - CP-CNN over CellProfiler general POD ratio | [1.81811349465688, 5e-05] | 1.8181 | true |
| BIOACTIVITY-002:03 - CellProfiler-DINO null conclusion is substrate-dependent | 0.261389384315177 | 0.05 | true |

Validated inputs:
- `paper/sources/table-s3.xlsx`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_cellprofiler_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_cpcnn_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_dino_pods.csv`
- `paper/evidence/bioactivity-and-figure-2b-d.md`

Limitations and deviations:
- Ratios remain near 2.0 and 1.5, but CellProfiler-DINO is p=0.261 in published SI, p=0.034 on the current notebook path, and p=0.0545 with the filtered config; the absent historical extended matrix is excluded.

### FIG-2C - POD comparison across representations

Source: main:p4:figure-2c.
Kind: figure.
Expected: Published paired comparison for 342 compounds with PODs in all representations.
Full acceptance: qualitative: same paired universe at useful resolution, same ordering, and similar spread; document row drift.
Producer: 2_downstream_analysis/manuscript_notebooks/1_3_compare_pods.ipynb.
Ledger evidence: evidence/bioactivity-and-figure-2b-d.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `source-recomputation`.
Declared deviation: Five-series complete counts are 342 camera-ready, 156 published SI, 341 current notebook-read, 330 current filtered, and 408 stored; current notebook-read distributions and ordering agree closely..

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| FIG-2C:01 - camera-ready five-series count trace | 342 | 342 | true |
| FIG-2C:02 - published-SI five-series complete cases | 156 | 156 | true |
| FIG-2C:03 - published-SI count deviation from camera-ready | 186 | 186 | true |
| FIG-2C:04 - five-series median ordering preserved | True | True | true |
| FIG-2C:05 - tracked-SI five-series finite POD summaries and median order | {"finite_nonempty": true, "median_order": ["cellprofiler_categorical", "dino_categorical", "dino_global", "cpcnn_global", "cellprofiler_global"], "series_count": 5} | {"finite_nonempty": true, "median_order": ["cellprofiler_categorical", "dino_categorical", "dino_global", "cpcnn_global", "cellprofiler_global"], "series_count": 5} | true |

Validated inputs:
- `paper/sources/table-s3.xlsx`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_cellprofiler_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_cpcnn_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_dino_pods.csv`
- `paper/evidence/bioactivity-and-figure-2b-d.md`

Limitations and deviations:
- Five-series complete counts are 342 camera-ready, 156 published SI, 341 current notebook-read, 330 current filtered, and 408 stored; current notebook-read distributions and ordering agree closely.

### BIOACTIVITY-003 - Assay sensitivity ordering and fold differences

Source: main:p5:results-2.1.3.
Kind: claim.
Expected: Morphology > MT > cell count > LDH; among 121 compounds morphology POD is 1.8-fold, 3.9-fold, and 7.0-fold lower respectively.
Full acceptance: close: ordering is preserved, shared-compound count is similar, and fold differences remain broadly comparable.
Producer: 2_downstream_analysis/manuscript_notebooks/1_3_compare_pods.ipynb.
Ledger evidence: evidence/bioactivity-and-figure-2b-d.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `source-recomputation`.
Declared deviation: Ordering holds; published 121-compound folds are 1.79, 4.28, and 8.15, while current direction-aware 131-compound folds are 1.68, 3.87, and 7.41..

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| BIOACTIVITY-003:01 - assay median sensitivity ordering | [5.05543414478975, 8.95705965699234, 23.8188547870137, 40.5354608552776] | Morphology < MT < cell count < LDH | true |
| BIOACTIVITY-003:02 - published-SI complete cases | 121 | 121 | true |

Validated inputs:
- `paper/sources/table-s2.xlsx`
- `paper/sources/table-s3.xlsx`
- `paper/sources/table-s4.xlsx`
- `2_downstream_analysis/compiled_results/SI_tables/mt_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellcount_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/ldh_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_cellprofiler_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_cpcnn_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_dino_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/hit_summary.csv`

Limitations and deviations:
- Ordering holds; published 121-compound folds are 1.79, 4.28, and 8.15, while current direction-aware 131-compound folds are 1.68, 3.87, and 7.41.

### FIG-2D - POD comparison across morphology and cytotoxicity assays

Source: main:p4:figure-2d.
Kind: figure.
Expected: Published paired comparison for 121 compounds with all four PODs.
Full acceptance: qualitative: same sensitivity ordering and similar paired distributions; exact plotted points are not required.
Producer: 2_downstream_analysis/manuscript_notebooks/1_3_compare_pods.ipynb.
Ledger evidence: evidence/bioactivity-and-figure-2b-d.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `source-recomputation`.
Declared deviation: Published Table S4 has 121 complete hits after a null-ID join excludes 15 rows; current direction-aware data have 131 and preserve distributions, paired ordering, and significance..

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| FIG-2D:01 - published-SI four-assay complete cases | 121 | 121 | true |
| FIG-2D:02 - MT fold ratio versus morphology | 1.78550470485347 | 1.78550470485347 | true |

Validated inputs:
- `paper/sources/table-s2.xlsx`
- `paper/sources/table-s3.xlsx`
- `paper/sources/table-s4.xlsx`
- `2_downstream_analysis/compiled_results/SI_tables/mt_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellcount_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/ldh_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_cellprofiler_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_cpcnn_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_dino_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/hit_summary.csv`

Limitations and deviations:
- Published Table S4 has 121 complete hits after a null-ID join excludes 15 rows; current direction-aware data have 131 and preserve distributions, paired ordering, and significance.

### TABLE-1 - Regression prediction of paired LDH and MT readouts

Source: main:p5:table-1.
Kind: table.
Expected: Published R2, RMSE, and MAE means and standard deviations across six input-feature or baseline rows per assay.
Full acceptance: close: schemas and labels are exact; rounded metrics are close and preserve comparison conclusions.
Producer: 2_downstream_analysis/manuscript_notebooks/2_1_predict_continuous_assays.ipynb.
Ledger evidence: evidence/regression-and-figure-s2.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `documentary-only`; availability: `documentary-only`; evidence strength: `documentary-trace`.
Declared deviation: Schemas, labels, and ten splits agree; 51 of 72 mean or SD entries match at two significant figures, with maximum absolute mean drift 0.00849 R2, 0.000990 RMSE, and 0.000428 MAE.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| TABLE-1:01 - Table 1 documentary schema and value trace | True | True | true |
| TABLE-1:02 - Table 1 numerical acceptance rerun | False | False | true |

Validated inputs:
- `paper/paper.md`
- `1_snakemake/classifier/regression.py`
- `2_downstream_analysis/manuscript_notebooks/2_1_predict_continuous_assays.ipynb`
- `paper/evidence/regression-and-figure-s2.md`

Limitations and deviations:
- Schemas, labels, and ten splits agree; 51 of 72 mean or SD entries match at two significant figures, with maximum absolute mean drift 0.00849 R2, 0.000990 RMSE, and 0.000428 MAE
- The required numerical substrate is not tracked; numerical acceptance was not rerun, and this recipe validates source, notebook, or code trace only.

### REGRESSION-001 - Relative regression performance across representations and baselines

Source: main:p5-p6:results-2.2.1.
Kind: claim.
Expected: Representations perform similarly; Cell Painting beats the technical baseline for MT but not LDH.
Full acceptance: qualitative: significance and performance ordering conclusions agree.
Producer: 2_downstream_analysis/manuscript_notebooks/2_1_predict_continuous_assays.ipynb.
Ledger evidence: evidence/regression-and-figure-s2.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `documentary-only`; availability: `documentary-only`; evidence strength: `documentary-trace`.
Declared deviation: Practical similarity and MT-versus-LDH ordering hold; LDH MAE has small significant DINO differences and formally favors the technical baseline.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| REGRESSION-001:01 - regression comparison documentary trace | True | True | true |
| REGRESSION-001:02 - regression numerical acceptance rerun | False | False | true |

Validated inputs:
- `1_snakemake/classifier/regression.py`
- `2_downstream_analysis/manuscript_notebooks/2_1_predict_continuous_assays.ipynb`
- `paper/evidence/regression-and-figure-s2.md`

Limitations and deviations:
- Practical similarity and MT-versus-LDH ordering hold; LDH MAE has small significant DINO differences and formally favors the technical baseline
- The required numerical substrate is not tracked; numerical acceptance was not rerun, and this recipe validates source, notebook, or code trace only.

### REGRESSION-002 - LDH model versus replicate performance

Source: main:p5:results-2.2.1.
Kind: claim.
Expected: Cell Painting or technical baseline R2 exceeds replicate R2 by mean 0.20 with p < 1e-14.
Full acceptance: close: effect remains positive and near 0.20 with a clearly significant result.
Producer: 2_downstream_analysis/manuscript_notebooks/2_1_predict_continuous_assays.ipynb.
Ledger evidence: evidence/regression-and-figure-s2.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `documentary-only`; availability: `documentary-only`; evidence strength: `documentary-trace`.
Declared deviation: Current pooled effect is 0.203758 with two-sided equal-variance independent t-test p = 1.88446e-14; distinct 966-compound model and 1,085-compound replicate split universes are documented.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| REGRESSION-002:01 - LDH replicate comparison documentary trace | True | True | true |
| REGRESSION-002:02 - regression numerical acceptance rerun | False | False | true |

Validated inputs:
- `paper/paper.md`
- `2_downstream_analysis/manuscript_notebooks/2_1_predict_continuous_assays.ipynb`
- `paper/evidence/regression-and-figure-s2.md`

Limitations and deviations:
- Current pooled effect is 0.203758 with two-sided equal-variance independent t-test p = 1.88446e-14; distinct 966-compound model and 1,085-compound replicate split universes are documented
- The required numerical substrate is not tracked; numerical acceptance was not rerun, and this recipe validates source, notebook, or code trace only.

### TABLE-2 - Binary LDH and MT classifier performance

Source: main:p6:table-2.
Kind: table.
Expected: Published AUROC and PRAUC values for cell count, random, CellProfiler, CP-CNN, and DINO rows.
Full acceptance: close: keys and labels are exact; rounded metrics are close and all main performance conclusions agree.
Producer: 2_downstream_analysis/manuscript_notebooks/3_2_0_assay_metrics.ipynb.
Ledger evidence: evidence/classifier-and-table-2.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `derived-artifact-reanalysis`.
Declared deviation: Both compiled and current layers match 19 of 20 entries at two decimals; compiled DINO MT AUROC is 0.875945 and current DINO MT PRAUC is 0.832443; the caption says ten splits while code pools five folds.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| TABLE-2:01 - Table 2 row count | 10 | 10 | true |
| TABLE-2:02 - Table 2 conclusion gates | True | True | true |

Validated inputs:
- `2_downstream_analysis/compiled_results/compiled_axiom_metrics.parquet`

Limitations and deviations:
- Both compiled and current layers match 19 of 20 entries at two decimals; compiled DINO MT AUROC is 0.875945 and current DINO MT PRAUC is 0.832443; the caption says ten splits while code pools five folds
- Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated.

### CLASSIFIER-001 - Paired LDH classifier performance

Source: main:p6:results-2.2.2.
Kind: claim.
Expected: Mean AUROC about 0.93 and PRAUC about 0.75; Cell Painting beats baselines.
Full acceptance: close: values remain near published magnitude and Cell Painting still beats both baselines.
Producer: 2_downstream_analysis/manuscript_notebooks/3_2_0_assay_metrics.ipynb.
Ledger evidence: evidence/classifier-and-table-2.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `derived-artifact-reanalysis`.
Declared deviation: Current LDH morphology means are 0.932625 AUROC and 0.753212 PRAUC and all representations beat both baselines; split-count, keyed-universe, and localized DINO MT deviations are documented.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| CLASSIFIER-001:01 - LDH morphology mean AUROC | [0.932625056254142, 5e-07] | 0.932625 | true |
| CLASSIFIER-001:02 - LDH morphology mean PRAUC | [0.753212139721954, 5e-07] | 0.753212 | true |
| CLASSIFIER-001:03 - LDH representations beat both baselines | True | True | true |

Validated inputs:
- `2_downstream_analysis/compiled_results/compiled_axiom_metrics.parquet`

Limitations and deviations:
- Current LDH morphology means are 0.932625 AUROC and 0.753212 PRAUC and all representations beat both baselines; split-count, keyed-universe, and localized DINO MT deviations are documented
- Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated.

### ENRICH-001 - Targets among wells better predicted by Cell Painting

Source: main:p6:results-2.3.
Kind: claim.
Expected: About 138 wells and 480 enriched targets, including cell cycle, PI3K-Akt, MAPK, and p53 signals.
Full acceptance: close: comparable hit-list scale and the same major pathway interpretation; exact hits and FDR values may drift.
Producer: 2_downstream_analysis/manuscript_notebooks/2_1_predict_continuous_assays.ipynb.
Ledger evidence: evidence/prediction-error-enrichment.md.
Historical ledger status: `blocked`.
Execution outcome: `blocked`; availability: `blocked`; evidence strength: `derived-artifact-reanalysis`.
Declared deviation: Code maps the Cell Painting label to 304 historical and 292 current Higher wells with 178 and 839 significant target sets; the 480 result and pathway mapping are absent, and signed residuals do not establish better prediction.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| ENRICH-001:01 - historical higher hit-list size | 304 | 304 | true |
| ENRICH-001:02 - stored higher significant sets | 178 | 178 | true |
| ENRICH-001:03 - literal 480-target acceptance available | False | False | true |

Validated inputs:
- `2_downstream_analysis/compiled_results/err_higher_targets.csv`
- `paper/evidence/prediction-error-enrichment.md`

Limitations and deviations:
- Code maps the Cell Painting label to 304 historical and 292 current Higher wells with 178 and 839 significant target sets; the 480 result and pathway mapping are absent, and signed residuals do not establish better prediction
- Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated.

### ENRICH-002 - Targets among wells better predicted by the technical baseline

Source: main:p6:results-2.3.
Kind: claim.
Expected: About 304 wells with no significantly enriched targets.
Full acceptance: close: hit-list scale is comparable and the no-enrichment conclusion holds.
Producer: 2_downstream_analysis/manuscript_notebooks/2_1_predict_continuous_assays.ipynb.
Ledger evidence: evidence/prediction-error-enrichment.md.
Historical ledger status: `blocked`.
Execution outcome: `blocked`; availability: `blocked`; evidence strength: `derived-artifact-reanalysis`.
Declared deviation: No enrichment holds for the 138 historical and 134 current Lower wells labeled technical baseline, while the 304 and 292 Higher wells are labeled Cell Painting and enriched; no source layer satisfies both acceptance conditions.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| ENRICH-002:01 - stored lower hit-list size | 138 | 138 | true |
| ENRICH-002:02 - stored lower significant sets | 0 | 0 | true |
| ENRICH-002:03 - literal 304-well acceptance available | False | False | true |

Validated inputs:
- `2_downstream_analysis/compiled_results/err_lower_targets.csv`
- `paper/evidence/prediction-error-enrichment.md`

Limitations and deviations:
- No enrichment holds for the 138 historical and 134 current Lower wells labeled technical baseline, while the 304 and 292 Higher wells are labeled Cell Painting and enriched; no source layer satisfies both acceptance conditions
- Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated.

### ENRICH-003 - Higher morphology-predicted than observed MT cases

Source: main:p6-p7:results-2.3.
Kind: claim.
Expected: 261 wells enriched for 147 proteins, including CYPs, neurotransmitter receptors, and xenobiotic transporters.
Full acceptance: qualitative: similar discrepancy group and the same broad biological target classes; individual members may differ.
Producer: 2_downstream_analysis/manuscript_notebooks/2_2_outlier_enrichment_analysis.ipynb.
Ledger evidence: evidence/mt-discrepancy-enrichment.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `derived-artifact-reanalysis`.
Declared deviation: The current rerun selects 262 wells and 71 significant sets, retaining six named CYPs and three named transporters but no significant HTR set; all 8858 target definitions reproduce exactly.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| ENRICH-003:01 - MT higher hit-list size | 261 | 261 | true |
| ENRICH-003:02 - MT higher significant sets | 147 | 147 | true |
| ENRICH-003:03 - MT higher named target classes | {"cyp_prefix_count": 8, "htr_prefix_count": 6, "transporters_present": ["ABCB1", "ABCG2", "SLCO1B1", "SLCO1B3"]} | {"cyp_prefix_count": 8, "htr_prefix_count": 6, "transporters_present": ["ABCB1", "ABCG2", "SLCO1B1", "SLCO1B3"]} | true |

Validated inputs:
- `2_downstream_analysis/compiled_results/mtt_higher_targets.csv`
- `paper/evidence/mt-discrepancy-enrichment.md`

Limitations and deviations:
- The current rerun selects 262 wells and 71 significant sets, retaining six named CYPs and three named transporters but no significant HTR set; all 8858 target definitions reproduce exactly
- Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated.

### ENRICH-004 - Lower morphology-predicted than observed MT cases

Source: main:p6-p7:results-2.3.
Kind: claim.
Expected: 131 wells enriched for proteasome inhibition, xenobiotic metabolism, bile acid synthesis, cell stress, and apoptosis.
Full acceptance: qualitative: similar discrepancy group and the same broad biological processes.
Producer: 2_downstream_analysis/manuscript_notebooks/2_2_outlier_enrichment_analysis.ipynb.
Ledger evidence: evidence/mt-discrepancy-enrichment.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `derived-artifact-reanalysis`.
Declared deviation: The current rerun selects 142 wells and 143 significant sets, retaining 15 proteasome and two CYP sets; carfilzomib and three process mappings remain unsupported.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| ENRICH-004:01 - MT lower hit-list size | 131 | 131 | true |
| ENRICH-004:02 - MT lower significant sets | 107 | 107 | true |
| ENRICH-004:03 - MT lower named target classes | {"cyp_prefix_count": 3, "psm_prefix_count": 18} | {"cyp_prefix_count": 3, "psm_prefix_count": 18} | true |

Validated inputs:
- `2_downstream_analysis/compiled_results/mtt_lower_targets.csv`
- `paper/evidence/mt-discrepancy-enrichment.md`

Limitations and deviations:
- The current rerun selects 142 wells and 143 significant sets, retaining 15 proteasome and two CYP sets; carfilzomib and three process mappings remain unsupported
- Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated.

### TOXCAST-001 - OASIS and ToxCast overlap

Source: main:p7:results-3.
Kind: claim.
Expected: 963 tested compounds, or 89 percent, overlap ToxCast.
Full acceptance: close: same overlap definition and count within ordinary source-version drift.
Producer: 2_downstream_analysis/manuscript_notebooks/3_1_toxcast_endpoints.ipynb.
Ledger evidence: evidence/toxcast-curation-and-figure-s3.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `source-recomputation`.
Declared deviation: The stored 963-ID union gives 88.755760 percent of 1085, but it is not intersected with tested metadata; only 670 tested IDs overlap the pinned ToxCast union.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| TOXCAST-001:01 - stored ToxCast annotation-ID union, not tested overlap | 963 | 963 | true |
| TOXCAST-001:02 - stored annotation-union/library-denominator arithmetic, not tested overlap | [0.887557603686636, 0.005] | 0.89 | true |
| TOXCAST-001:03 - documented tested-library intersection IDs | 670 | 670 | true |
| TOXCAST-001:04 - documented tested-library intersection percentage | [61.7511520737327, 5e-07] | 61.751152 | true |
| TOXCAST-001:05 - 963 is an annotation union rather than a tested-library join | True | True | true |

Validated inputs:
- `1_snakemake/inputs/annotations/toxcast_cellbased_binary.parquet`
- `1_snakemake/inputs/annotations/toxcast_cellbased_info.parquet`
- `1_snakemake/inputs/annotations/toxcast_cellfree_binary.parquet`
- `1_snakemake/inputs/annotations/toxcast_cellfree_info.parquet`
- `1_snakemake/inputs/annotations/toxcast_cytotox_binary.parquet`
- `1_snakemake/inputs/annotations/toxcast_cytotox_info.parquet`
- `paper/evidence/toxcast-curation-and-figure-s3.md`

Limitations and deviations:
- The stored 963-ID union gives 88.755760 percent of 1085, but it is not intersected with tested metadata; only 670 tested IDs overlap the pinned ToxCast union

### TOXCAST-002 - Curated ToxCast endpoint counts

Source: main:p7:results-3.1.
Kind: claim.
Expected: 48 cytotoxicity, 292 non-cytotoxicity cell-based, and 72 cell-free endpoints.
Full acceptance: exact: endpoint category keys and counts agree for the pinned input.
Producer: 2_downstream_analysis/manuscript_notebooks/3_1_toxcast_endpoints.ipynb.
Ledger evidence: evidence/toxcast-curation-and-figure-s3.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `source-recomputation`.
Declared deviation: Source metadata have 48, 292, and 72 exact keys, but class support retains 38 cytotoxicity keys and enforcing the stated 100 uM rule would reduce cell-based endpoints to 291.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| TOXCAST-002:01 - ToxCast source endpoint counts | {"cellbased": 292, "cellfree": 72, "cytotox": 48} | {"cellbased": 292, "cellfree": 72, "cytotox": 48} | true |
| TOXCAST-002:02 - classification-ready binary endpoint counts | {"cellbased": 292, "cellfree": 72, "cytotox": 38} | {"cellbased": 292, "cellfree": 72, "cytotox": 38} | true |

Validated inputs:
- `1_snakemake/inputs/annotations/toxcast_cellbased_binary.parquet`
- `1_snakemake/inputs/annotations/toxcast_cellbased_info.parquet`
- `1_snakemake/inputs/annotations/toxcast_cellfree_binary.parquet`
- `1_snakemake/inputs/annotations/toxcast_cellfree_info.parquet`
- `1_snakemake/inputs/annotations/toxcast_cytotox_binary.parquet`
- `1_snakemake/inputs/annotations/toxcast_cytotox_info.parquet`

Limitations and deviations:
- Source metadata have 48, 292, and 72 exact keys, but class support retains 38 cytotoxicity keys and enforcing the stated 100 uM rule would reduce cell-based endpoints to 291

### TOXCAST-003 - ToxCast endpoint composition and activity summaries

Source: main:p7:results-3.1.
Kind: claim.
Expected: Published tissue, target-family, overlap, and active-fraction summaries for cell-based and cell-free endpoints.
Full acceptance: close: proportions and rankings remain broadly comparable; record source-version changes.
Producer: 2_downstream_analysis/manuscript_notebooks/3_1_toxcast_endpoints.ipynb.
Ledger evidence: evidence/toxcast-curation-and-figure-s3.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `source-recomputation`.
Declared deviation: All displayed values and rankings match; family percentages use all 292 cell-based endpoints and cytotoxicity medians use the 38 post-support endpoints rather than all 48 source categories.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| TOXCAST-003:01 - cell-based tissue composition | {"kidney": 35, "liver": 151, "vascular": 63} | {"kidney": 35, "liver": 151, "vascular": 63} | true |
| TOXCAST-003:02 - cell-free assay composition | {"binding": 37, "enzymatic activity": 35} | {"binding": 37, "enzymatic activity": 35} | true |
| TOXCAST-003:03 - cell-free target-family composition | {"cyp": 11, "gpcr": 21, "nuclear receptor": 10} | {"cyp": 11, "gpcr": 21, "nuclear receptor": 10} | true |
| TOXCAST-003:04 - median compounds tested per endpoint | {"cellbased": 306, "cellfree": 33, "cytotox": 346} | {"cellbased": 306, "cellfree": 33, "cytotox": 346} | true |
| TOXCAST-003:05 - median endpoint active fractions | {"cellbased": 0.071161355334425, "cellfree": 0.413429522752497, "cytotox": 0.206834880123743} | {"cellbased": 0.0711613553, "cellfree": 0.4134295228, "cytotox": 0.2068348801} | true |

Validated inputs:
- `1_snakemake/inputs/annotations/toxcast_cellbased_binary.parquet`
- `1_snakemake/inputs/annotations/toxcast_cellbased_info.parquet`
- `1_snakemake/inputs/annotations/toxcast_cellfree_binary.parquet`
- `1_snakemake/inputs/annotations/toxcast_cellfree_info.parquet`
- `1_snakemake/inputs/annotations/toxcast_cytotox_binary.parquet`
- `1_snakemake/inputs/annotations/toxcast_cytotox_info.parquet`

Limitations and deviations:
- All displayed values and rankings match; family percentages use all 292 cell-based endpoints and cytotoxicity medians use the 38 post-support endpoints rather than all 48 source categories

### FIG-3AB - AUROC and PRAUC distributions across assay types

Source: main:p8:figure-3a-b.
Kind: figure.
Expected: Paired MT and LDH perform best, followed by ToxCast cytotoxicity and cell-based assays, with cell-free assays near random.
Full acceptance: qualitative: same assay-type ordering and broadly similar distributions; no pixel match required.
Producer: 2_downstream_analysis/manuscript_notebooks/3_2_1_compare_endpoint_types.ipynb.
Ledger evidence: evidence/classifier-results.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `derived-artifact-reanalysis`.
Declared deviation: Ordering and distributions agree, but caption counts 48/292/72 are source counts rather than the 34/267/53 modeled endpoint counts.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| FIG-3AB:01 - classifier modeled endpoint distributions | {"axiom": 2, "toxcast_cellbased": 267, "toxcast_cellfree": 53, "toxcast_cytotox": 34} | {"axiom": 2, "toxcast_cellbased": 267, "toxcast_cellfree": 53, "toxcast_cytotox": 34} | true |
| FIG-3AB:02 - all-concentration CellProfiler distribution summaries | {"axiom": {"auroc": 0.90154710075502, "prauc": 0.805566469136103}, "toxcast_cellbased": {"auroc": 0.607226107226107, "prauc": 0.144839974879456}, "toxcast_cellfree": {"auroc": 0.532085561497326, "prauc": 0.454015201822219}, "toxcast_cytotox": {"auroc": 0.737210441587034, "prauc": 0.477454853975985}} | {"axiom": {"auroc": 0.901547, "prauc": 0.805566}, "toxcast_cellbased": {"auroc": 0.607226, "prauc": 0.14484}, "toxcast_cellfree": {"auroc": 0.532086, "prauc": 0.454015}, "toxcast_cytotox": {"auroc": 0.73721, "prauc": 0.477455}} | true |

Validated inputs:
- `2_downstream_analysis/compiled_results/compiled_axiom_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellbased_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellfree_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cytotox_metrics.parquet`

Limitations and deviations:
- Ordering and distributions agree, but caption counts 48/292/72 are source counts rather than the 34/267/53 modeled endpoint counts
- Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated.

### FIG-3C - Classifier differences from random and cell-count baselines

Source: main:p8:figure-3c.
Kind: figure.
Expected: Morphology improves cytotoxicity and cell-based prediction over random; cell-free prediction does not materially improve.
Full acceptance: qualitative: effect directions and main significance conclusions agree.
Producer: 2_downstream_analysis/manuscript_notebooks/3_2_1_compare_endpoint_types.ipynb.
Ledger evidence: evidence/classifier-results.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `derived-artifact-reanalysis`.
Declared deviation: Matched effects support the conclusion, but the panel mixes endpoint universes and tests and the six-row cell-free PRAUC mixed model does not converge.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| FIG-3C:01 - cell-based versus cell-free baseline conclusion | True | True | true |

Validated inputs:
- `2_downstream_analysis/compiled_results/compiled_axiom_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellbased_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellfree_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cytotox_metrics.parquet`

Limitations and deviations:
- Matched effects support the conclusion, but the panel mixes endpoint universes and tests and the six-row cell-free PRAUC mixed model does not converge
- Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated.

### FILTER-001 - Filtering to bioactive concentrations

Source: main:p7:results-3.2.1.
Kind: claim.
Expected: AUROC increases about 0.04 for ToxCast cytotoxicity and 0.02 for cell-based assays; other AUROC and all PRAUC comparisons show no material improvement.
Full acceptance: close: small improvements remain small and the overall no-practical-improvement conclusion holds.
Producer: 2_downstream_analysis/manuscript_notebooks/3_2_2_compare_concs_reps.ipynb.
Ledger evidence: evidence/classifier-results.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `derived-artifact-reanalysis`.
Declared deviation: Compiled/current AUROC effects are 0.0386/0.0374 and 0.0194/0.0203, but the published FDR values do not reproduce from the committed notebook.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| FILTER-001:01 - allpod versus all effects remain small | True | True | true |

Validated inputs:
- `2_downstream_analysis/compiled_results/compiled_axiom_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellbased_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellfree_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cytotox_metrics.parquet`

Limitations and deviations:
- Compiled/current AUROC effects are 0.0386/0.0374 and 0.0194/0.0203, but the published FDR values do not reproduce from the committed notebook
- Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated.

### FILTER-002 - Filtering out cytotoxic concentrations

Source: main:p7:results-3.2.1.
Kind: claim.
Expected: Performance worsens for cytotoxicity categories and does not improve cell-based or cell-free prediction.
Full acceptance: qualitative: effect directions and no-improvement conclusion agree.
Producer: 2_downstream_analysis/manuscript_notebooks/3_2_2_compare_concs_reps.ipynb.
Ledger evidence: evidence/classifier-results.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `derived-artifact-reanalysis`.
Declared deviation: Cytotoxicity performance worsens and other effects remain negligible, with expected numerical drift in POD-derived strategies.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| FILTER-002:01 - Axiom allpodcc minus allpod mean AUROC | -0.124974386867459 | -0.124974386867459 | true |
| FILTER-002:02 - Axiom allpodcc minus allpod mean PRAUC | -0.372361412793057 | -0.372361412793057 | true |
| FILTER-002:03 - allpodcc minus allpod mean AUROC | {"toxcast_cellbased": -0.00797018904098499, "toxcast_cellfree": 0.0134291664332844, "toxcast_cytotox": -0.0885859686562654} | {"toxcast_cellbased": -0.007970189, "toxcast_cellfree": 0.0134291664, "toxcast_cytotox": -0.0885859687} | true |
| FILTER-002:04 - allpodcc minus allpod mean PRAUC | {"toxcast_cellbased": -0.00659679632924061, "toxcast_cellfree": 0.00515195738908095, "toxcast_cytotox": -0.167163560277532} | {"toxcast_cellbased": -0.0065967963, "toxcast_cellfree": 0.0051519574, "toxcast_cytotox": -0.1671635603} | true |
| FILTER-002:05 - Axiom and cytotoxic effects are negative while cell-based and cell-free effects remain below 0.02 | True | True | true |

Validated inputs:
- `2_downstream_analysis/compiled_results/compiled_axiom_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellbased_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellfree_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cytotox_metrics.parquet`

Limitations and deviations:
- Cytotoxicity performance worsens and other effects remain negligible, with expected numerical drift in POD-derived strategies
- Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated.

### FIG-4A - Classifier AUROC across concentration consensus strategies

Source: main:p9:figure-4a.
Kind: figure.
Expected: All-concentration profiles perform as well as or better than filtered alternatives overall.
Full acceptance: qualitative: same practical conclusion and similar assay-type patterns.
Producer: 2_downstream_analysis/manuscript_notebooks/3_2_2_compare_concs_reps.ipynb.
Ledger evidence: evidence/classifier-results.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `derived-artifact-reanalysis`.
Declared deviation: Distribution directions and the practical conclusion agree, but modeled endpoint counts differ from captions and POD-filtered values drift.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| FIG-4A:01 - all-concentration strategy conclusion | True | True | true |

Validated inputs:
- `2_downstream_analysis/compiled_results/compiled_axiom_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellbased_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellfree_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cytotox_metrics.parquet`

Limitations and deviations:
- Distribution directions and the practical conclusion agree, but modeled endpoint counts differ from captions and POD-filtered values drift
- Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated.

### REPRESENTATION-001 - Alternative image representations

Source: main:p7:results-3.2.2.
Kind: claim.
Expected: Representations perform similarly; DINO cell-based AUROC is about 0.02 higher than CellProfiler and CP-CNN.
Full acceptance: close: performance remains similar overall and any DINO advantage stays small.
Producer: 2_downstream_analysis/manuscript_notebooks/3_2_3_compare_endpoints_detail.ipynb; 2_downstream_analysis/manuscript_notebooks/3_2_2_compare_concs_reps.ipynb.
Ledger evidence: evidence/classifier-results.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `derived-artifact-reanalysis`.
Declared deviation: DINO median advantages are 0.0221 and 0.0159, but mean effects are about 0.011 and published p-values do not reproduce.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| REPRESENTATION-001:01 - DINO versus CP-CNN cell-based AUROC effects | {"mean_difference": 0.010790455248826, "median_difference": 0.0158730158730159} | {"mean_difference": 0.01079046, "median_difference": 0.01587302} | true |
| REPRESENTATION-001:02 - DINO versus CellProfiler median cell-based AUROC | 0.0220902090209021 | 0.02209021 | true |

Validated inputs:
- `2_downstream_analysis/compiled_results/compiled_axiom_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellbased_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellfree_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cytotox_metrics.parquet`

Limitations and deviations:
- DINO median advantages are 0.0221 and 0.0159, but mean effects are about 0.011 and published p-values do not reproduce
- Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated.

### FIG-4B - Classifier AUROC across CellProfiler, CP-CNN, and DINO

Source: main:p9:figure-4b.
Kind: figure.
Expected: Published representation distributions are very similar within assay types.
Full acceptance: qualitative: same near-equivalence and assay-type ordering; no pixel match required.
Producer: 2_downstream_analysis/manuscript_notebooks/3_2_3_compare_endpoints_detail.ipynb; 2_downstream_analysis/manuscript_notebooks/3_2_2_compare_concs_reps.ipynb.
Ledger evidence: evidence/classifier-results.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `derived-artifact-reanalysis`.
Declared deviation: Near-equivalence and ordering agree, with one small ToxCast cytotoxicity Tukey contrast at p = 0.0493.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| FIG-4B:01 - representation effects remain practically small | True | True | true |

Validated inputs:
- `2_downstream_analysis/compiled_results/compiled_axiom_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellbased_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellfree_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cytotox_metrics.parquet`

Limitations and deviations:
- Near-equivalence and ordering agree, with one small ToxCast cytotoxicity Tukey contrast at p = 0.0493
- Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated.

### SFIG-1 - Representative Cell Painting image

Source: supp:p2:figure-s1.
Kind: figure.
Expected: Plate 41002889, well L12, site 6; representative of 191754 images including 43641 DMSO controls.
Full acceptance: close: plate, well, site, DMSO identity, and five-channel content agree exactly; inventory drift is acceptable only when measured directly from the current joined index and tied to a documented missing selection rule.
Producer: paper/render_sfig1.py; 2_downstream_analysis/other_notebooks/Plot_images.ipynb.
Ledger evidence: evidence/figure-s1.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `out-of-scope`; availability: `out-of-scope`; evidence strength: `unavailable`.
Declared deviation: The exact DMSO field and five channels resolve and render; the current joined index has 318828 fields including 72519 DMSO fields, while the published counts imply an undocumented nine-site selection rule.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| SFIG-1:01 - tracked navigation image identity trace | True | True | true |
| SFIG-1:02 - external source-image reproduction documented | True | True | true |
| SFIG-1:03 - external source image available | False | False | true |

Validated inputs:
- `paper/figures/figure-s1.jpg`
- `paper/paper.md`
- `paper/evidence/figure-s1.md`
- `paper/render_sfig1.py`

Limitations and deviations:
- The exact DMSO field and five channels resolve and render; the current joined index has 318828 fields including 72519 DMSO fields, while the published counts imply an undocumented nine-site selection rule
- The raw source image is external and excluded from tracked-only execution.

### SFIG-2 - Technical factors and paired-assay prediction diagnostics

Source: supp:p3:figure-s2.
Kind: figure.
Expected: Well-position effects, normalized readout distributions, and DINO similarity clustergram support the technical-factor interpretation.
Full acceptance: qualitative: same major spatial and cell-count patterns; exact clustering order is not required.
Producer: 2_downstream_analysis/manuscript_notebooks/2_1_predict_continuous_assays.ipynb; 2_downstream_analysis/other_notebooks/01_checkwelleffects.ipynb.
Ledger evidence: evidence/regression-and-figure-s2.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `documentary-only`; availability: `documentary-only`; evidence strength: `documentary-trace`.
Declared deviation: All panel directions and major patterns hold; current base selects 292 versus camera-ready text n = 138, and the notebook label is a signed-residual threshold rather than a formal significance test.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| SFIG-2:01 - Figure S2 panel documentary trace | True | True | true |
| SFIG-2:02 - Figure S2 numerical acceptance rerun | False | False | true |

Validated inputs:
- `paper/paper.md`
- `2_downstream_analysis/manuscript_notebooks/2_1_predict_continuous_assays.ipynb`
- `2_downstream_analysis/other_notebooks/01_checkwelleffects.ipynb`
- `paper/evidence/regression-and-figure-s2.md`

Limitations and deviations:
- All panel directions and major patterns hold; current base selects 292 versus camera-ready text n = 138, and the notebook label is a signed-residual threshold rather than a formal significance test
- The required numerical substrate is not tracked; numerical acceptance was not rerun, and this recipe validates source, notebook, or code trace only.

### SFIG-3 - ToxCast binarization and cytotoxicity patterns

Source: supp:p4:figure-s3.
Kind: figure.
Expected: Published binarization procedure and broad cell-line and tissue cytotoxicity clusters.
Full acceptance: qualitative: same procedure, category coverage, and major clustered patterns.
Producer: 2_downstream_analysis/manuscript_notebooks/3_1_toxcast_endpoints.ipynb.
Ledger evidence: evidence/toxcast-curation-and-figure-s3.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `source-recomputation`.
Declared deviation: The 12-cell and 6-tissue heatmaps preserve broad concordance and selective patterns; the image is labeled B and C while the supplemental legend incorrectly says C and D.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| SFIG-3:01 - cytotoxicity heatmap summary | {"cell_categories": 12, "complete_compounds": 839, "tissue_categories": 6} | {"cell_categories": 12, "complete_compounds": 839, "tissue_categories": 6} | true |

Validated inputs:
- `1_snakemake/inputs/annotations/toxcast_cytotox_binary.parquet`
- `paper/evidence/toxcast-curation-and-figure-s3.md`

Limitations and deviations:
- The 12-cell and 6-tissue heatmaps preserve broad concordance and selective patterns; the image is labeled B and C while the supplemental legend incorrectly says C and D

### SFIG-4 - Classifier PRAUC across concentration and image representations

Source: supp:p5:figure-s4.
Kind: figure.
Expected: Filtering and representation comparisons do not materially improve PRAUC.
Full acceptance: qualitative: same no-material-improvement conclusion and similar distributions.
Producer: 2_downstream_analysis/manuscript_notebooks/3_2_2_compare_concs_reps.ipynb; 2_downstream_analysis/manuscript_notebooks/3_2_3_compare_endpoints_detail.ipynb.
Ledger evidence: evidence/classifier-results.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `derived-artifact-reanalysis`.
Declared deviation: PRAUC shows no practical improvement, while POD-filtered values drift and small unadjusted representation tests differ from Tukey results.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| SFIG-4:01 - PRAUC filtering and representation practical conclusion | True | True | true |

Validated inputs:
- `2_downstream_analysis/compiled_results/compiled_axiom_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellbased_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellfree_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cytotox_metrics.parquet`

Limitations and deviations:
- PRAUC shows no practical improvement, while POD-filtered values drift and small unadjusted representation tests differ from Tukey results
- Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated.

### TABLE-S1 - OASIS compound list

Source: supp:table-s1.
Kind: table.
Expected: Published compound identities and annotations used to define the study library.
Full acceptance: exact: stable compound identifiers and tested-library membership agree; annotation-only differences are documented.
Producer: paper/sources/table-s1.xlsx; 1_snakemake/inputs/metadata/metadata.parquet.
Ledger evidence: evidence/remaining-paper-reproduction-targets.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `source-recomputation`.
Declared deviation: All 966 workbook OASIS IDs and 119 blinded labels map to metadata, but tested metadata additionally has Ribociclib; Vasopressin has two IDs, one workbook name is encoding-corrupted, and 176 preferred-name labels differ.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| TABLE-S1:01 - Table S1 rows | 1085 | 1085 | true |
| TABLE-S1:02 - Table S1 stable IDs | 966 | 966 | true |
| TABLE-S1:03 - Table S1 blank IDs | 119 | 119 | true |

Validated inputs:
- `paper/sources/table-s1.xlsx`
- `1_snakemake/inputs/annotations/v5_oasis_03Sept2024_simple.csv`

Limitations and deviations:
- All 966 workbook OASIS IDs and 119 blinded labels map to metadata, but tested metadata additionally has Ribociclib; Vasopressin has two IDs, one workbook name is encoding-corrupted, and 176 preferred-name labels differ

### TABLE-S2 - Cytotoxicity points of departure

Source: supp:table-s2.
Kind: table.
Expected: Published MT, cell-count, and LDH POD results.
Full acceptance: close: schemas and semantic keys agree; coverage, median differences, validity, and material tail satisfy the existing POD gates.
Producer: 2_downstream_analysis/compiled_results/SI_tables.
Ledger evidence: evidence/published-table-bridge.md; ../REPRODUCING.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `source-recomputation`.
Declared deviation: Published workbook keys match all 796 committed semantic rows and POD values agree to spreadsheet precision; regenerated gates pass with documented drift.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| TABLE-S2:01 - Table S2 semantic keys | 796 | 796 | true |
| TABLE-S2:02 - Table S2 maximum POD difference | 4.40536496171262e-13 | 1e-12 | true |

Validated inputs:
- `paper/sources/table-s2.xlsx`
- `2_downstream_analysis/compiled_results/SI_tables/mt_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellcount_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/ldh_pods.csv`

Limitations and deviations:
- Published workbook keys match all 796 committed semantic rows and POD values agree to spreadsheet precision; regenerated gates pass with documented drift

### TABLE-S3 - Cell Painting points of departure

Source: supp:table-s3.
Kind: table.
Expected: Published CellProfiler, CP-CNN, and DINO POD results.
Full acceptance: close: schemas and semantic keys agree; coverage, median differences, validity, and material tail satisfy the existing POD gates.
Producer: 2_downstream_analysis/compiled_results/SI_tables.
Ledger evidence: evidence/published-table-bridge.md; ../REPRODUCING.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `source-recomputation`.
Declared deviation: Published workbook keys match all 10935 nonblank committed semantic rows and POD values agree to spreadsheet precision; regenerated gates pass with documented drift.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| TABLE-S3:01 - Table S3 semantic keys | 10935 | 10935 | true |
| TABLE-S3:02 - Table S3 exact bioactivity flags | 10935 | 10935 | true |

Validated inputs:
- `paper/sources/table-s3.xlsx`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_cellprofiler_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_cpcnn_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_dino_pods.csv`

Limitations and deviations:
- Published workbook keys match all 10935 nonblank committed semantic rows and POD values agree to spreadsheet precision; regenerated gates pass with documented drift

### TABLE-S4 - Activity summary across all assays

Source: supp:table-s4.
Kind: table.
Expected: Published cross-assay compound activity summary including the 121-compound all-POD subset.
Full acceptance: close: compound identities and main assay-activity relationships agree; small POD pass-call drift is documented.
Producer: 2_downstream_analysis/manuscript_notebooks/4_1_results_tables_SI.ipynb.
Ledger evidence: evidence/published-table-bridge.md; ../REPRODUCING.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `source-recomputation`.
Declared deviation: Published workbook matches all 1086 committed hit-summary rows; regenerated keys are exact and 1070 of 1086 complete hit calls agree.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| TABLE-S4:01 - Table S4 semantic keys | 1086 | 1086 | true |
| TABLE-S4:02 - Table S4 exact tracked hit rows | 1086 | 1086 | true |

Validated inputs:
- `paper/sources/table-s4.xlsx`
- `2_downstream_analysis/compiled_results/SI_tables/hit_summary.csv`

Limitations and deviations:
- Published workbook matches all 1086 committed hit-summary rows; regenerated keys are exact and 1070 of 1086 complete hit calls agree

### TABLE-S5 - ToxCast activity for 2-ethylanthraquinone

Source: supp:table-s5.
Kind: table.
Expected: Activity in 12 nuclear-receptor assays at about 1-45 uM without cytotoxicity, plus mitochondrial depolarization signal.
Full acceptance: close: same broad assay set, concentration range, and metabolic-disruption interpretation.
Producer: paper/sources/table-s5.xlsx; 2_downstream_analysis/manuscript_notebooks/3_1_toxcast_endpoints.ipynb.
Ledger evidence: evidence/remaining-paper-reproduction-targets.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `source-recomputation`.
Declared deviation: Workbook has 12 receptor hits at 1.648-45 uM; pinned inputs retain 8 of 12, confirm zero cytotoxicity hits across 102 tests, and support MMP activity without proving directional uncoupling.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| TABLE-S5:01 - Table S5 nuclear-receptor assays | 12 | 12 | true |
| TABLE-S5:02 - Table S5 nuclear-receptor AC50 minimum | [1.64808942, 0.001] | 1.648 | true |
| TABLE-S5:03 - Table S5 nuclear-receptor AC50 maximum | 45.0 | 45.0 | true |
| TABLE-S5:04 - Table S5 retained pinned receptor assays | 8 | 8 | true |
| TABLE-S5:05 - Table S5 source cytotoxicity hits | 0 | 0 | true |
| TABLE-S5:06 - Table S5 MMP activity evidence | {"ac50_um": 14.8795940571651, "hitcall_above_0_9": true} | active finite MMP signal | true |

Validated inputs:
- `paper/sources/table-s5.xlsx`
- `1_snakemake/inputs/annotations/toxcast_cellbased_info.parquet`
- `1_snakemake/inputs/annotations/toxcast_cytotox_info.parquet`
- `1_snakemake/inputs/annotations/toxcast_cytotox_binary.parquet`

Limitations and deviations:
- Workbook has 12 receptor hits at 1.648-45 uM; pinned inputs retain 8 of 12, confirm zero cytotoxicity hits across 102 tests, and support MMP activity without proving directional uncoupling

### TABLE-KEY-RESOURCES - Published biological samples, reagents, deposited data, software, and equipment

Source: main:e1-e2:key-resources-table.
Kind: table.
Expected: All Key Resources Table rows and identifiers from the camera-ready paper.
Full acceptance: exact: resource names, versions, deposited-data paths, and identifiers agree with the published table.
Producer: paper/paper.md; paper/sources/main.pdf.
Ledger evidence: paper.md.
Historical ledger status: `reproduced`.
Execution outcome: `documentary-only`; availability: `documentary-only`; evidence strength: `documentary-trace`.
Declared deviation: Transcribed from the camera-ready PDF.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| TABLE-KEY-RESOURCES:01 - Key Resources transcription trace | True | True | true |
| TABLE-KEY-RESOURCES:02 - Key Resources Markdown data rows | 34 | 34 | true |

Validated inputs:
- `paper/paper.md`
- `paper/sources/main.pdf`

Limitations and deviations:
- Transcribed from the camera-ready PDF
- The required numerical substrate is not tracked; numerical acceptance was not rerun, and this recipe validates source, notebook, or code trace only.

### METHOD-POD - Concentration-response model and POD selection

Source: main:e4-e5:concentration-response.
Kind: method.
Expected: Paper describes eight named models, residual-SD selection, DMSO 95th-percentile benchmark, and confidence-ratio and concentration filters.
Full acceptance: exact: model families and thresholds match; the known selection-rule discrepancy is explicit.
Producer: 1_snakemake/concresponse.
Ledger evidence: evidence/method-deviations.md; ../REPRODUCING.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `documentary-only`; availability: `documentary-only`; evidence strength: `documentary-trace`.
Declared deviation: Morphology selects minimum residual SD; cell count, MT, and LDH use scoresPOD default rounded-AIC selection despite the paper's general residual-SD wording.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| METHOD-POD:01 - POD implementation and deviation trace | {"compound_minimum_pod": true, "dmso_control": true, "documented_ci_ratio_threshold_40": true, "documented_dmso_95th_percentile_benchmark": true, "documented_eight_model_names": true, "documented_highest_tested_concentration_filter": true, "known_selection_deviation_traced": true, "morphology_residual_sd_selection": true, "paired_assay_scorespod_default": true} | True | true |

Validated inputs:
- `1_snakemake/concresponse/fit_curves.R`
- `1_snakemake/concresponse/fit_curves_meta.R`
- `1_snakemake/concresponse/select_pod.R`
- `paper/paper.md`
- `paper/evidence/method-deviations.md`

Limitations and deviations:
- Morphology selects minimum residual SD; cell count, MT, and LDH use scoresPOD default rounded-AIC selection despite the paper's general residual-SD wording
- The required numerical substrate is not tracked; numerical acceptance was not rerun, and this recipe validates source, notebook, or code trace only.

### METHOD-TOXCAST - ToxCast hit and cytotoxicity-confounding curation

Source: main:e3-e4:toxcast-curation.
Kind: method.
Expected: Hit call > 0.9; 20 percent consensus cytotoxicity rule; AC50 comparison; minimum five positive and negative calls.
Full acceptance: exact: thresholds and decision rules match code; input-version effects are separate deviations.
Producer: 2_downstream_analysis/manuscript_notebooks/3_1_toxcast_endpoints.ipynb.
Ledger evidence: evidence/toxcast-curation-and-figure-s3.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `documentary-only`; availability: `documentary-only`; evidence strength: `documentary-trace`.
Declared deviation: Core thresholds and matching rules trace exactly, but the stated specific-endpoint 100 uM reset is omitted and raw invitrodb regeneration is not repository-only executable.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| METHOD-TOXCAST:01 - ToxCast threshold and decision-rule trace | {"cytotoxicity_consensus_20_percent": true, "hitcall_strictly_above_0_9": true, "median_positive_ac50": true, "minimum_five_positive_and_negative": true, "notebook_reads_pinned_parquets": true, "specific_endpoint_100_um_deviation_traced": true} | True | true |

Validated inputs:
- `paper/paper.md`
- `2_downstream_analysis/manuscript_notebooks/3_1_toxcast_endpoints.ipynb`
- `paper/evidence/toxcast-curation-and-figure-s3.md`

Limitations and deviations:
- Core thresholds and matching rules trace exactly, but the stated specific-endpoint 100 uM reset is omitted and raw invitrodb regeneration is not repository-only executable
- The required numerical substrate is not tracked; numerical acceptance was not rerun, and this recipe validates source, notebook, or code trace only.

### METHOD-CLASSIFIER - Classifier validation design

Source: main:e4:supervised-analysis.
Kind: method.
Expected: XGBoost classifiers use five-fold compound-level stratified splits, published baselines, and three consensus-profile strategies.
Full acceptance: exact: splits, model family, baselines, and consensus definitions match code.
Producer: 1_snakemake/classifier/classify.py; 2_downstream_analysis/manuscript_notebooks.
Ledger evidence: evidence/method-deviations.md.
Historical ledger status: `reproduced`.
Execution outcome: `documentary-only`; availability: `documentary-only`; evidence strength: `documentary-trace`.
Declared deviation: Classifier implementation uses StratifiedKFold with five splits.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| METHOD-CLASSIFIER:01 - classifier implementation trace | {"compound_level_label_join": true, "consensus_strategies": true, "folds": 5, "model": "XGBClassifier", "paired_assay_hitcalls": true, "published_baselines": true, "stratified": true, "workflow_wiring": true} | True | true |

Validated inputs:
- `1_snakemake/classifier/classify.py`
- `1_snakemake/classifier/aggregate_profiles.py`
- `1_snakemake/classifier/hitcalls.py`
- `1_snakemake/rules/classifier.smk`

Limitations and deviations:
- Classifier implementation uses StratifiedKFold with five splits
- The required numerical substrate is not tracked; numerical acceptance was not rerun, and this recipe validates source, notebook, or code trace only.

### METHOD-REGRESSION - Regression validation design

Source: main:p5:table-1; e4:supervised-analysis.
Kind: method.
Expected: Table 1 reports ten train-test splits; regression code uses ten repeated 80/20 compound-group splits.
Full acceptance: exact: regression split count, group isolation, test fraction, and model family match Table 1; STAR Methods inconsistency is recorded.
Producer: 1_snakemake/classifier/regression.py.
Ledger evidence: evidence/method-deviations.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `documentary-only`; availability: `documentary-only`; evidence strength: `documentary-trace`.
Declared deviation: Code and Table 1 use ten GroupShuffleSplit splits, while STAR Methods incorrectly states five-fold validation for all scenarios.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| METHOD-REGRESSION:01 - ten 80/20 compound-group splits | True | True | true |

Validated inputs:
- `1_snakemake/classifier/regression.py`
- `paper/evidence/method-deviations.md`

Limitations and deviations:
- Code and Table 1 use ten GroupShuffleSplit splits, while STAR Methods incorrectly states five-fold validation for all scenarios
- The required numerical substrate is not tracked; numerical acceptance was not rerun, and this recipe validates source, notebook, or code trace only.

### METHOD-STATS - Statistical thresholds and sample design

Source: main:e5:quantification-and-statistics.
Kind: method.
Expected: p < 0.05; FDR < 0.05; 5500 seeded cells per well; sixteen wells per compound.
Full acceptance: exact: thresholds and design constants agree.
Producer: paper methods; analysis notebooks.
Ledger evidence: evidence/remaining-paper-reproduction-targets.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `documentary-only`; availability: `documentary-only`; evidence strength: `documentary-trace`.
Declared deviation: All constants are declared and BH FDR is executable, but initial seeding is not recomputable, 0.05 gates are not centralized, and only 446 of 1,085 processed compounds retain exactly 16 rows.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| METHOD-STATS:01 - statistical thresholds and sample design trace | True | True | true |

Validated inputs:
- `paper/paper.md`

Limitations and deviations:
- All constants are declared and BH FDR is executable, but initial seeding is not recomputable, 0.05 gates are not centralized, and only 446 of 1,085 processed compounds retain exactly 16 rows
- The required numerical substrate is not tracked; numerical acceptance was not rerun, and this recipe validates source, notebook, or code trace only.

### CONCLUSION-001 - Morphology is more sensitive than paired cytotoxicity readouts

Source: main:p1:summary; p7-p10:discussion.
Kind: claim.
Expected: Morphology detects more activity and at lower concentrations.
Full acceptance: qualitative: assay ordering and overall conclusion hold across reproduced counts and PODs.
Producer: multiple targets above.
Ledger evidence: evidence/bioactivity-and-figure-2b-d.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `derived-artifact-reanalysis`.
Declared deviation: General-morphology detected-frequency counts exceed all cytotoxicity counts, and complete-case PODs preserve morphology > MT > cell count > LDH sensitivity despite key and pass-call drift..

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| CONCLUSION-001:01 - morphology sensitivity inequalities | {"complete_case_median_order": true, "general_morphology_count_exceeds_mt": true} | True | true |

Validated inputs:
- `paper/sources/table-s2.xlsx`
- `paper/sources/table-s3.xlsx`
- `paper/sources/table-s4.xlsx`
- `2_downstream_analysis/compiled_results/SI_tables/mt_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellcount_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/ldh_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_cellprofiler_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_cpcnn_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/cellpainting_dino_pods.csv`
- `2_downstream_analysis/compiled_results/SI_tables/hit_summary.csv`

Limitations and deviations:
- General-morphology detected-frequency counts exceed all cytotoxicity counts, and complete-case PODs preserve morphology > MT > cell count > LDH sensitivity despite key and pass-call drift.
- Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated.

### CONCLUSION-002 - Morphology predicts cell-based but not cell-free assay activity

Source: main:p1:summary; p7-p9:results.
Kind: claim.
Expected: Cytotoxicity and targeted cell-based assays are predictable above random while cell-free assays are not.
Full acceptance: qualitative: classifier ordering and baseline comparisons support the same conclusion.
Producer: multiple targets above.
Ledger evidence: evidence/classifier-results.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `derived-artifact-reanalysis`.
Declared deviation: Conclusion holds for 2/34/267/53 modeled endpoints with caption-count, test-provenance, and cell-free non-convergence caveats.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| CONCLUSION-002:01 - cell-based but not cell-free inequality gate | True | True | true |

Validated inputs:
- `2_downstream_analysis/compiled_results/compiled_axiom_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellbased_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellfree_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cytotox_metrics.parquet`

Limitations and deviations:
- Conclusion holds for 2/34/267/53 modeled endpoints with caption-count, test-provenance, and cell-free non-convergence caveats
- Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated.

### CONCLUSION-003 - Representations and concentration filtering do not materially change performance

Source: main:p1:summary; p9:results.
Kind: claim.
Expected: CellProfiler, CP-CNN, and DINO are similar; filtering concentrations gives no practical improvement.
Full acceptance: qualitative: small numerical differences are allowed if the practical conclusion holds.
Producer: multiple targets above.
Ledger evidence: evidence/classifier-results.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `derived-artifact-reanalysis`.
Declared deviation: Practical conclusion holds despite localized significance differences, CellProfiler scenario provenance, and POD-filtered numerical drift.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| CONCLUSION-003:01 - representation and filtering practical-equivalence gates | True | True | true |

Validated inputs:
- `2_downstream_analysis/compiled_results/compiled_axiom_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellbased_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cellfree_metrics.parquet`
- `2_downstream_analysis/compiled_results/compiled_toxcast_cytotox_metrics.parquet`

Limitations and deviations:
- Practical conclusion holds despite localized significance differences, CellProfiler scenario provenance, and POD-filtered numerical drift
- Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated.

### RESOURCE-001 - Published data and code availability statements

Source: main:p10:resource-availability.
Kind: resource.
Expected: Cell Painting Gallery data, this analysis repository, and repository DOI are traceable.
Full acceptance: trace-only: confirm references and access locations; this is not a numerical reproduction target.
Producer: paper key resources; README.md.
Ledger evidence: evidence/remaining-paper-reproduction-targets.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `documentary-only`; availability: `documentary-only`; evidence strength: `documentary-trace`.
Declared deviation: Access classes and paths are traceable, but raw images, ignored compiled inputs and outputs, raw invitrodb, DOI resolution, and equivalence of the published owner URL to the current Broad origin remain external.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| RESOURCE-001:01 - published data and code locations | True | True | true |
| RESOURCE-001:02 - tracked-only resource boundary | True | True | true |

Validated inputs:
- `README.md`
- `paper/paper.md`
- `paper/evidence/remaining-paper-reproduction-targets.md`

Limitations and deviations:
- Access classes and paths are traceable, but raw images, ignored compiled inputs and outputs, raw invitrodb, DOI resolution, and equivalence of the published owner URL to the current Broad origin remain external
- The required numerical substrate is not tracked; numerical acceptance was not rerun, and this recipe validates source, notebook, or code trace only.

### INTERPRETATION-001 - Mechanistic interpretation of MT prediction discrepancies

Source: main:p7-p10:discussion.
Kind: claim.
Expected: CYP, neurotransmitter-receptor, metabolic, stress, and apoptosis signals motivate testable hypotheses.
Full acceptance: trace-only: preserve the distinction between enrichment evidence and mechanistic hypothesis.
Producer: paper discussion and cited literature.
Ledger evidence: evidence/remaining-paper-reproduction-targets.md.
Historical ledger status: `reproduced-with-deviation`.
Execution outcome: `checked`; availability: `available`; evidence strength: `derived-artifact-reanalysis`.
Declared deviation: Direct enrichment supports CYP, serotonergic, transporter, proteasome, and xenobiotic-metabolism associations; other process and receptor labels remain interpretations and all mechanism claims remain hypotheses.

| Target-specific check | Observed | Expected | Passed |
| --- | --- | --- | --- |
| INTERPRETATION-001:01 - direct enrichment associations separated from mechanism | True | True | true |

Validated inputs:
- `2_downstream_analysis/compiled_results/mtt_higher_targets.csv`
- `2_downstream_analysis/compiled_results/mtt_lower_targets.csv`
- `paper/paper.md`

Limitations and deviations:
- Direct enrichment supports CYP, serotonergic, transporter, proteasome, and xenobiotic-metabolism associations; other process and receptor labels remain interpretations and all mechanism claims remain hypotheses
- Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated.
