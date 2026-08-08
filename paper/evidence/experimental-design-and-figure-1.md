# Experimental design and Figure 1 evidence

This note resolves DESIGN-001, DESIGN-002, DESIGN-003, and FIG-1 against the camera-ready paper and the repository state at `b13bb743c01aa086f3217648212f54d7d487f36d`.
The audit reused the published sources, downloaded input Parquets, committed workflow code, and existing outputs.
No scientific workflow was rerun.

## Source contract

Camera-ready page 2 states that 1,085 compounds were tested at eight concentrations from 0.01 to 100 uM with two biological replicates, and that 384-well plates were exposed for 44 h.
STAR Methods further defines each biological replicate as one well and says that the two wells for each compound-concentration group were placed on different plates.
Published Table S1 contains one header and 1,085 compound rows.
Camera-ready page 3 and Figure 1 connect the exposures to Cell Painting morphology, membrane-rupture LDH, and mitochondrial-activity MT readouts, followed by morphology and cytotoxicity processing, dose-response analysis, and cytotoxicity and mode-of-action prediction using ToxCast annotations.

## DESIGN-001

The downloaded analysis metadata contains exactly 1,085 distinct non-DMSO compound labels.
Its observed concentrations span 0.0091286311 to 100 uM; the lower endpoint rounds to the published 0.01 uM at camera-ready precision.
Of the 1,085 compound labels, 1,084 retain eight distinct concentrations and Hycanthone retains seven.

The metadata is a post-QC analysis input rather than a complete execution ledger.
`0_prepare_data/2A_format_metadata.py` explicitly removes plates 41002695, 41002696, and 41002698 because they used a different microscope.
After that exclusion, the file contains 16,607 non-DMSO exposure rows in 8,679 compound-concentration groups: 7,672 groups have two retained rows, 941 have one, and 66 have more than two because some compound labels occur in additional exposures.
The missing Hycanthone concentration and single-row groups therefore quantify downstream plate-level attrition from the published two-well design.

Decision: `reproduced-with-deviation`.
The published library count, concentration range, and replicate design are confirmed, while the post-QC input does not retain both designed wells for every group.
This deviation does not alter the experimental-design conclusion.

## DESIGN-002

The raw profile schemas contain the following non-`Metadata_` columns:

| Representation | Feature columns | Schema examples |
| --- | ---: | --- |
| CellProfiler | 5,640 | `Image_Granularity_10_AGP` through `Nuclei_Texture_Variance_RNA_5_03_256` |
| CP-CNN | 672 | `f_001` through `f_672` |
| DINO | 4,608 | channel-labelled embeddings such as `DNA_001` through `Brightfield_768` |

These counts and representation semantics exactly match camera-ready page 2 and STAR Methods.

Decision: `reproduced` with no deviation.

## DESIGN-003

The camera-ready paper specifies 384-well plates, 44 h exposure, and Cell Painting, LDH, and MT as the three measured assays.
The metadata spans zero-based rows 0-15 and columns 0-23 and contains all 384 well labels, exactly confirming the plate format.
It contains the MT, LDH, and derived cell-count fields used by the concentration-response rules, while the three raw profile inputs provide the Cell Painting readouts.

Decision: `reproduced` with no deviation.

## FIG-1

The repository implements every scientific stage shown in Figure 1:

- `1_snakemake/inputs/metadata/metadata.parquet` and the three raw profile inputs represent the hepatocyte exposures and measured readouts.
- `1_snakemake/rules/concresponse.smk` processes morphology, cell count, MT, and LDH readouts into curve fits and points of departure.
- `1_snakemake/rules/classifier.smk` combines processed profiles with paired-assay and ToxCast annotations for cytotoxicity and mode-of-action prediction.
- Existing outputs under `1_snakemake/outputs/{cellprofiler,cpcnn,dino}/` cover morphology profiles, dose-response results, and classifier predictions.

`paper/REPRODUCING.md` independently records successful runs of all three manuscript configurations and the resulting output classes.
The stages, sample scale, assay identities, and intended outcomes agree with the published overview.
Publisher layout was not treated as an acceptance baseline.

Decision: `reproduced` with no deviation.

## Read-only checks

The source and artifact audit used:

```bash
(cd paper/sources && sha256sum -c SHA256SUMS)

pdftotext -f 2 -l 3 -layout paper/sources/main.pdf -

pixi run -e pipeline python - <<'PY'
import pyarrow.parquet as pq

for name in ("cellprofiler", "cpcnn", "dino"):
    schema = pq.read_schema(f"1_snakemake/inputs/profiles/{name}/raw.parquet")
    features = [field.name for field in schema if not field.name.startswith("Metadata_")]
    print(name, len(features))
PY
```

The metadata counts above were computed by grouping the seven required columns from `metadata.parquet`; no feature matrix was loaded into memory.
