# Activity counts and Figure 2A

Targets: `ACTIVITY-001`, `ACTIVITY-002`, `ACTIVITY-003`, and `FIG-2A`.

The input commit was `243c966f90bf6254858b2f3cb7e3183d89de4a30`.
This check used the camera-ready PDF, published Table S2, committed SI CSVs, committed pipeline Parquets, stored notebook code and outputs, and the existing reproduction record.
No scientific workflow or notebook was rerun.

## Count comparison

The fixed denominator is 1,085 unique tested compound names, excluding DMSO.
The read-only Parquet calculation reproduced notebook cells 6-10 by requiring `all.pass == true` and `SDres < 3 * SDctrl`.
Direction-aware cytotoxicity was the union of decreased MT, decreased cell count, and increased LDH calls.

| Evidence layer | MT active | Cell count active | LDH active | Any active | Direction-aware cytotoxic | MT increasing |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Camera-ready text | 430 | 221 | 144 | 438 | 429 | 10 |
| Published Table S2 and committed SI CSVs | 429 | 220 | 147 | 437 | not encoded | not encoded |
| Current CellProfiler assay Parquets | 430 | 221 | 144 | 438 | 429 | 10 |
| Stored DINO count-notebook output | 431 | 220 | 144 | 439 | 429 | 11 |

Published Table S2 contains 796 POD rows and agrees exactly by semantic key and spreadsheet precision with the committed `mt_pods.csv`, `cellcount_pods.csv`, and `ldh_pods.csv`, as recorded in `published-table-bridge.md`.
Its 429 MT, 220 cell-count, and 147 LDH rows have 437 unique compound names, so Table S2 does not support the four camera-ready activity totals even though the paper cites it for them.
Relative to Table S2, the current CellProfiler MT set adds Binimetinib, Omadacycline, and Progesterone and loses Alfacalcidol and Clodinafop-propargyl.
The current CellProfiler cell-count set adds Tolterodine, while the current LDH set loses Infigratinib, Tenofovir alafenamide, and Triclosan.
Across assays, the current CellProfiler union adds Binimetinib, Omadacycline, and Progesterone and loses Alfacalcidol and Clodinafop-propargyl relative to Table S2, for a net change from 437 to 438.
The existing `paper/REPRODUCING.md` comparison independently documents environment-sensitive curve-model and pass-call drift for these assay POD tables, which is the likely cause of the historical Table S2 differences.
The deviations are at most three assay calls and one unique compound in each total, preserve the rounded percentages, and preserve the MT greater than cell count greater than LDH activity ranking.

The DINO notebook discrepancy is more specific.
`4_1_results_tables_SI.ipynb` reads CellProfiler assay curves to produce the SI tables, while `1_2_number_active_readouts.ipynb` reads DINO assay curves to count activity, so the two committed producers select different scenario layers for nominally representation-independent readouts.
Compared with the current CellProfiler layer, DINO adds only Clodinafop-propargyl to the accepted MT set and loses only Ezetimibe from the accepted cell-count set.
Clodinafop-propargyl is an increasing, non-cytotoxic MT call, while Ezetimibe remains a decreasing MT hit, so the two layers have the identical 429-compound direction-aware cytotoxic set.
For Clodinafop-propargyl, the compound wells and values and the 1,035 applicable DMSO wells and values are canonically identical between the CellProfiler and DINO profile Parquets, but the DMSO physical row order differs.
`fit_curves_meta.R` sorts only by concentration, leaving the equal-concentration DMSO order unresolved.
The CellProfiler order selects a failing Exp2 fit, while the DINO order selects a passing Exp3 fit with a 79.4353 uM POD, which accounts exactly for the displayed change from 430 and 10 to 431 and 11.
Ezetimibe similarly changes from a passing Power cell-count fit in CellProfiler to a failing Poly2 fit in DINO.
This is consistent with the order-sensitive nonlinear model selection already demonstrated in `paper/REPRODUCING.md`.

## Figure 2A

The camera-ready Figure 2A and the stored output in `1_2_1_cmpds_increase_mt.ipynb` contain Benzarone, Tiratricol, Tolcapone, and 2-Ethylanthracene-9,10-dione.
The discussion calls the last compound 2-ethylanthraquinone, which is a synonym for the plotted name.
The notebook explicitly includes only these four compounds, reads MT values and curves from the CellProfiler `mad_featselect` Parquets, adds a seeded sample of 100 DMSO controls, plots the observed normalized MT values and fitted curve, and marks the POD with a blue dashed line.
All four current curve rows pass the activity filters, have increasing direction, and select the Exp3 model.

| Compound | Current POD (uM) | Published Table S2 POD (uM) | Median normalized MT at 100 uM |
| --- | ---: | ---: | ---: |
| Benzarone | 69.337657 | 69.337144 | 1.369 |
| Tiratricol | 25.860689 | 25.860426 | 1.364 |
| Tolcapone | 23.606293 | 23.606292 | 1.337 |
| 2-Ethylanthracene-9,10-dione | 8.660721 | 8.660848 | 1.532 |

The current and published PODs differ by at most 0.000514 uM and 1.5e-5 relative.
The labels, upward response directions, late-rising Exp3 curve shapes, approximate dashed POD locations, and plotted inclusion logic agree with the camera-ready panel.
The lowest POD and largest high-dose response belong to 2-Ethylanthracene-9,10-dione, agreeing with the paper's interpretation.

## Decisions

`ACTIVITY-001` is reproduced with deviation because the current CellProfiler substrate gives every camera-ready count exactly, while the stored DINO notebook and published Table S2 contain quantified, conclusion-preserving count and call differences.
`ACTIVITY-002` is reproduced because both current assay layers produce the same 429-compound direction-aware cytotoxic set under the paper's definition.
`ACTIVITY-003` is reproduced with deviation because CellProfiler gives the reported ten MT-increasing compounds and the same four dominant responses, while the DINO notebook adds the order-sensitive Clodinafop-propargyl call.
`FIG-2A` is reproduced because the compounds, directions, curves, POD positions, labels, and inclusion logic agree scientifically with the camera-ready panel.
