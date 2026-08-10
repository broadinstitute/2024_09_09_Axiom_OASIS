# TIFF to JPEG XL

This directory does one job: convert large TIFF images into smaller JPEG XL images.

The JPEG XL settings are fixed at distance 1.0, effort 5, 16 bits per sample, and one codec thread per worker.
The output is lossy and intended for browsing, visualization, and retrieval.
The original TIFF remains the scientific source of truth.

## Agent-run contract

An agent needs only `SOURCE_ROOT` and `OUTPUT_ROOT` to run a complete conversion.

1. Inspect `SOURCE_ROOT` read-only.
   It must be an absolute local directory or public anonymous `s3://` prefix with an unambiguous recursive TIFF scope.
   Enumerate every `.tif` and `.tiff` with complete pagination, record their count and total bytes, and decode a representative sample to confirm one 2D uint16 plane.
2. Require `OUTPUT_ROOT` to be absent or empty before a fresh run.
   Resume only when its `manifest.tsv` is identical and every existing file belongs to that run; never mix or reuse another conversion.
3. Write `OUTPUT_ROOT/manifest.tsv` using the exact schema below.
   Include every source TIFF once, mirror its path relative to `SOURCE_ROOT`, replace only its suffix with `.jxl`, sort by `destination_relative`, and reject collisions or unsafe paths.
4. Use the existing locked converter without adding dependencies, tracked dataset adapters, frameworks, or workflow code.
   Proceed autonomously through conversion and full verification, resuming an interruption with the identical manifest.
5. Accept the run only when conversion reports `complete=true` and `failed=0`, verification reports `complete=true` and `invalid=0`, and `checked` equals the manifest row count.
6. Report the two roots; manifest path, count, and SHA-256; source and output bytes and compression ratio; conversion and verification counts; and paths to `manifest.tsv`, `jxl-run.json`, and `jxl-validation.json`.
   State that verification proves decodable 2D uint16 JPEG XL outputs, not losslessness or biological equivalence.

Stop before conversion only when the source scope, image compatibility, destination ownership, or safe resume state is unresolved.

A complete agent prompt is therefore:

```text
Read README.md and complete the Agent-run contract.
SOURCE_ROOT=<absolute directory or public s3:// prefix>
OUTPUT_ROOT=<absolute destination directory>
```

## Input

Provide a UTF-8 tab-separated manifest with exactly two columns:

```text
source_uri	destination_relative
s3://bucket/path/image1.tif	batch/plate/image1.jxl
s3://bucket/path/image2.tif	batch/plate/image2.jxl
```

`source_uri` may be an anonymous `s3://` URI or an absolute local path.
`destination_relative` must be a safe relative path ending in `.jxl`.
Rows must be strictly sorted by `destination_relative`, which also makes destination collisions invalid.
Preparing this list is a data-selection task and is deliberately outside the converter.

## Convert

Enter the locked environment and run:

```bash
direnv exec . pixi run -e images python -m image_archive convert \
  --manifest /absolute/path/images.tsv \
  --output-root /absolute/path/images-jxl \
  --workers 32
```

Each worker downloads and decodes one TIFF, encodes JPEG XL, decodes the result, and atomically moves it into place.
Failures are retried up to five times.
The run stops scheduling new work after 32 consecutive failed files.

An existing destination is skipped.
After interruption, run the identical command again; completed atomic outputs are the resume state.
The command writes `jxl-run.json` under the output root.

Only one conversion or verification process may use an output root at a time.

## Verify

Decode every expected output after conversion:

```bash
direnv exec . pixi run -e images python -m image_archive verify \
  --manifest /absolute/path/images.tsv \
  --output-root /absolute/path/images-jxl \
  --workers 32
```

Success requires one decodable 2D uint16 JPEG XL for every manifest row.
The command writes `jxl-validation.json` under the output root.

## Test

```bash
direnv exec . pixi run -e images pytest -q image_archive/tests
```

## Completed `cpg0037-oasis/axiom` dataset run

[`axiom-run.json`](axiom-run.json) records the completed TIFF-to-JPEG-XL conversion for the `cpg0037-oasis/axiom` dataset.
The complete previous framework and immutable receipt remain available in Git at commit `2423d28`.
The external JPEG XL archive for this dataset is not modified by this simplification.
