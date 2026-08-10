# TIFF to JPEG XL

This directory does one job: convert large TIFF images into smaller JPEG XL images.

The JPEG XL settings are fixed at distance 1.0, effort 5, 16 bits per sample, and one codec thread per worker.
The output is lossy and intended for browsing, visualization, and retrieval.
The original TIFF remains the scientific source of truth.

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

## Historical Axiom run

[`axiom-run.json`](axiom-run.json) is the concise historical record for the completed Axiom OASIS conversion.
The complete previous framework and immutable receipt remain available in Git at commit `2423d28`.
The existing external archive is not modified by this simplification.
