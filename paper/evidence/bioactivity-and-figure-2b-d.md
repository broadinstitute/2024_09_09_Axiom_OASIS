# Bioactivity and Figure 2B-D

Targets: `BIOACTIVITY-001`, `FIG-2B`, `BIOACTIVITY-002`, `FIG-2C`, `BIOACTIVITY-003`, `FIG-2D`, and `CONCLUSION-001`.

The input commit was `ec2e836223ddf5f591e60b19c20608a32d9c737b`.
This check used the camera-ready PDF and Figure 2, published Tables S2-S4, their exact committed SI CSV bridge, current base-scenario Parquets, stored code and outputs in `4_1_results_tables_SI.ipynb` and `1_3_compare_pods.ipynb`, and `REPRODUCING.md`.
No notebook or scientific workflow was executed.
Small read-only calculations applied the committed filters and paired tests to the existing files.
The blocked `1_3_compare_pods.ipynb` notebook was not executed, and none of the nine excluded `_log10`, `_int`, or `_ap` pipeline configurations was run.

## Figure 2B activity counts and POD distributions

The denominator is 1,085 unique tested compounds excluding DMSO.
Each table entry is active compounds followed by the median POD in uM.
The published-workbook layer is exactly equal to the committed SI CSV layer by the bridge in `published-table-bridge.md`.
The current notebook-read layer is `mad_featselect`, which is the path used by every committed notebook.

| Representation and distance | Camera-ready Figure 2B | Published Table S3 and committed SI | Current `mad_featselect` |
| --- | ---: | ---: | ---: |
| CellProfiler global | 372 (34.3%); 25.0 | 169 (15.6%); 52.8 | 371 (34.2%); 25.6 |
| CellProfiler categorical | 598 (55.1%); 12.9 | 598 (55.1%); 11.5 | 598 (55.1%); 13.0 |
| CellProfiler general | 600 (55.3%); 12.4 | 607 (55.9%); 11.6 | 606 (55.9%); 12.7 |
| CP-CNN global and general | 538 (49.6%); 26.3 | 539 (49.7%); 25.5 | 535 (49.3%); 26.2 |
| DINO global | 546 (50.3%); 15.1 | 545 (50.2%); 14.9 | 547 (50.4%); 14.9 |
| DINO categorical | 624 (57.5%); 21.8 | 626 (57.7%); 20.0 | 625 (57.6%); 21.3 |
| DINO general | 642 (59.2%); 17.2 | 644 (59.4%); 16.0 | 643 (59.3%); 16.9 |

The current notebook-read layer preserves the 34%-59% range, the complete activity-count ordering, and CellProfiler-global as the 34% outlier.
Its count differences from the panel are zero to six compounds, and its median differences are at most 0.6 uM.
The README-labelled `mad_featselect_filt` CellProfiler alternative gives 363 global, 601 categorical, and 611 general active compounds with medians 26.8, 13.1, and 12.9 uM.
It also preserves the ordering and CellProfiler-global outlier, but it is not the path read by the notebooks.

Published Table S3 preserves the ordering and the upper 59% endpoint but not the reported range or global distribution because it has only 169 CellProfiler-global calls and a 52.8 uM median.
The published and current CellProfiler-global key sets overlap for 150 compounds, with 19 published-only and 221 current-only calls.
The other published-to-current active sets are much more stable: their overlaps are 596 of 598 CellProfiler-categorical, 596 of 607 published CellProfiler-general, 533 of 539 CP-CNN, 545 of 545 DINO-global, 623 of 626 DINO-categorical, and 641 of 644 DINO-general compounds.
The existing verifier shows that the continuous POD values usually agree closely while discrete model and pass calls drift under the unpinned R stack and residual-SD model selection, which is the likely cause of these key-set differences.

## Figure 2C paired representations

Figure 2C displays five series and reports 342 compounds with complete PODs.
The available five-series complete-case universes differ sharply by evidence layer.

| Evidence layer | Complete compounds | CP-CNN / CellProfiler general | CP-CNN / DINO general | CellProfiler vs DINO paired t-test |
| --- | ---: | ---: | ---: | --- |
| Camera-ready text and panel | 342 | about 2.0 | about 1.5 | not significant; exact p-value not reported |
| Published Table S3 and committed SI | 156 | 2.6408 | 1.5444 | p = 5.23e-8; CellProfiler lower |
| Current notebook-read `mad_featselect` | 341 | 2.2980 | 1.5978 | p = 4.87e-7; CellProfiler lower |
| Current README-labelled filtered CellProfiler | 330 | 2.2555 | 1.5664 | p = 1.11e-6; CellProfiler lower |

Ratios are geometric mean paired POD ratios on the complete set in each row, and the tests use paired log10 PODs as in the notebook.
The published and current five-series sets overlap for 148 compounds, with eight published-only and 193 current-only compounds.
The current notebook-read layer is one compound below the reported panel count and reproduces the approximate panel distributions with complete-set medians of 25.6, 7.57, 17.8, 16.5, and 21.8 uM for CellProfiler-global, CellProfiler-categorical, DINO-global, DINO-categorical, and CP-CNN.
The published complete set has corresponding medians of 46.2, 5.86, 17.8, 11.4, and 18.1 uM because the CellProfiler-global pass-call loss changes both sample inclusion and distribution.

The camera-ready text does not state whether its 2.0-fold, 1.5-fold, and significance calculations were restricted to the five-series panel-complete set.
On the three general-bioactivity series, published Table S3 has 488 shared compounds, CP-CNN ratios of 1.8181 to CellProfiler and 1.6865 to DINO, and a non-significant CellProfiler-DINO comparison at p = 0.261.
The current notebook-read layer has 485 shared compounds, ratios of 1.8685 and 1.6255, and p = 0.034 for CellProfiler versus DINO.
The current filtered CellProfiler alternative has 486 shared compounds, ratios of 1.8451 and 1.6245, and p = 0.0545.
The effect ratios are stable at the reported magnitude, but the CellProfiler-DINO threshold conclusion depends on which current CellProfiler configuration is selected.

The stored blocked-notebook output reports 408 five-series complete compounds, while its ratio cells use different pairwise universes of 407, 489, and 410 compounds rather than the complete set.
Those stored pairwise outputs give CP-CNN ratios of 1.9330 to CellProfiler and 1.5341 to DINO, but they report a significant CellProfiler-DINO difference at p = 8.89e-61.
The historical `_log10` Parquets needed to reconstruct those stored universes are absent, and executing the excluded extended matrix is outside this target batch.

## Figure 2D assay sensitivity

Figure 2D reports 121 compounds, morphology / MT / cell count / LDH ordering, morphology PODs lower by 1.8-fold, 3.9-fold, and 7.0-fold, and all p-values below 1e-14.
The morphology POD is the DINO general-bioactivity POD.
The table gives complete-case counts and geometric mean paired ratios of the other assay POD to morphology POD.

| Evidence layer and inclusion rule | Shared compounds | MT / morphology | Cell count / morphology | LDH / morphology |
| --- | ---: | ---: | ---: | ---: |
| Camera-ready | 121 | 1.8 | 3.9 | 7.0 |
| Published Table S4 all-hit set with S2-S3 PODs | 121 | 1.7855 | 4.2813 | 8.1537 |
| Published S2-S3 raw compound-name intersection | 136 | 1.7570 | 4.1571 | 7.9322 |
| Current DINO scenario, cytotoxic directions | 131 | 1.6839 | 3.8703 | 7.4134 |
| Current CellProfiler scenario, cytotoxic directions | 131 | 1.7366 | 3.9099 | 7.3413 |
| Current DINO scenario, all pass calls | 134 | 1.6383 | 3.8898 | 7.4491 |
| Current CellProfiler scenario, all pass calls | 134 | 1.6884 | 3.9287 | 7.3783 |

The 121 published Table S4 compounds have median PODs of 5.06, 8.96, 23.82, and 40.54 uM for morphology, MT, cell count, and LDH.
The 131 current DINO direction-aware compounds have corresponding medians of 6.34, 8.96, 22.54, and 42.85 uM.
The ordering, broad spreads, and paired concentration relationships therefore agree scientifically.

The published Table S4 set gives paired-log10 t-test p-values of 3.17e-6, 2.03e-28, and 2.13e-33 for morphology versus MT, cell count, and LDH.
The current DINO direction-aware set gives p-values of 1.01e-6, 1.94e-28, and 4.70e-34.
All three direction and significance conclusions hold, but the exact camera-ready statement that every p-value is below 1e-14 is not reproduced for MT by the documented notebook test.

The difference between the published 121 and raw 136-compound intersections is a key and inclusion artifact rather than a biological filter.
Fifteen anonymized `Compound_*` rows have blank `OASIS_ID` values and PODs in all four published SI files, but the `4_1` join on `(OASIS_ID, Compound_name)` cannot match null IDs and marks all four hit fields `No` in Table S4.
The current direction-aware calculation instead joins by compound name and excludes increasing MT, increasing cell-count, and decreasing LDH calls, producing 131 complete compounds.
Published Table S2 and Table S4 do not encode direction, so they cannot reconstruct that direction-aware universe exactly.

The blocked notebook's stored all-assay complete-case count is also 131, not 121.
Its stored statistical cell does not test that complete set and instead uses pairwise sample sizes of 338, 217, and 142 for morphology versus MT, cell count, and LDH.
The stored output therefore cannot serve as clean evidence for the camera-ready complete-case ratios or p-values.

## Conclusion and decisions

Detected-frequency evidence and concentration-sensitivity evidence answer different questions.
For detected frequency, every current and published general-morphology representation has 535-644 active compounds, more than MT, cell count, or LDH at 429-431, 220-221, and 144-147 active compounds.
For concentration sensitivity, every published and current complete-case layer preserves morphology lower than MT lower than cell count lower than LDH, with broadly comparable fold differences and paired distributions.
`CONCLUSION-001` therefore follows despite the sample-set and pass-call drift.

`BIOACTIVITY-001` and `FIG-2B` are reproduced with deviation because the current notebook-read layer preserves the reported range, ordering, outlier, and distributions, while published Table S3 has a quantified CellProfiler-global call loss.
`BIOACTIVITY-002` is blocked because the ratios are close but the required CellProfiler-DINO null conclusion changes across the two current CellProfiler configurations, and the absent historical extended matrix is excluded from execution.
`FIG-2C` is reproduced with deviation because the current notebook-read layer gives 341 rather than 342 complete compounds and closely matching panel distributions, while the published and stored layers have documented key-set drift.
`BIOACTIVITY-003` and `FIG-2D` are reproduced with deviation because the sensitivity ordering and broad fold differences hold, while the complete-case count, exact folds, and MT p-value differ by layer.
`CONCLUSION-001` is reproduced with deviation because both detected-frequency and concentration-sensitivity evidence support the conclusion under their distinct denominators.
