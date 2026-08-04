# Published supplemental table bridge

This note connects the publisher XLSX files to the committed CSV artifacts evaluated by the existing semantic verifier.
The comparison used the published workbooks in `paper/sources/` and the committed files under `2_downstream_analysis/compiled_results/SI_tables/` at the `6ca56dc` reproduction baseline.
The read-only check parsed the workbook XML and CSV values directly, compared semantic keys, and compared POD fields after numeric parsing.
No scientific workflow was rerun.

## TABLE-S2

Published Table S2 contains 796 semantic POD rows.
The rows map to `mt_pods.csv` (429), `cellcount_pods.csv` (220), and `ldh_pods.csv` (147).
The workbook and committed CSVs have identical `(OASIS_ID, Compound_name)` keys within each assay file.
POD point and bound values agree to spreadsheet precision, with maximum absolute difference `4.55e-13` and maximum relative difference `4.78e-15` after numeric parsing.

The regenerated-versus-committed comparison in `REPRODUCING.md` passes the configured coverage, within-1%, median-difference, and validity gates while reporting expected row and model-selection drift.

Decision: `reproduced-with-deviation`.

## TABLE-S3

Published Table S3 contains 10,935 nonblank semantic POD rows.
The rows map to `cellpainting_cellprofiler_pods.csv` (6,965), `cellpainting_cpcnn_pods.csv` (539), and `cellpainting_dino_pods.csv` (3,431).
The workbook and committed CSVs have identical `(OASIS_ID, Compound_name, Assay_Endpoint)` keys and identical bioactivity flags.
POD point and bound values agree to spreadsheet precision, with maximum absolute difference `5.12e-13` and maximum relative difference `4.95e-15` after numeric parsing.

The regenerated-versus-committed comparison in `REPRODUCING.md` passes the configured gates with the documented environment-sensitive tail.

Decision: `reproduced-with-deviation`.

## TABLE-S4

Published Table S4 has 1,086 rows and is exactly equal by value to the committed `hit_summary.csv`.
The regenerated result retains the exact semantic key set, and 1,070 of 1,086 complete hit-call rows agree.
The 16 call differences are diagnostic under the existing acceptance policy and do not change the overall paper conclusion.

Decision: `reproduced-with-deviation`.
