# 2024_09_09_Axiom_OASIS

This repository contains the Axiom OASIS analysis, its paper reproduction record, and image-archive tools.

## Repository map

- `0_prepare_data/` prepares the original analysis inputs.
- `1_snakemake/` contains the primary analysis pipeline.
- `2_downstream_analysis/` contains manuscript and exploratory notebooks plus compiled results.
- `paper/` contains the published sources, target ledger, evidence, executable paper, and end-to-end reproduction workflow.
- `image_archive/` contains the reusable image-archive package and the completed Axiom JPEG XL archive record.

## Reproduction and archive entry points

Run `uv run paper/reproduce.py` for the repository-only executable paper.
Run `uv run paper/reproduce_all.py` for the isolated, resumable end-to-end reproduction, or add `--dry-run` to inspect its exact plan first.
See [paper/README.md](paper/README.md) for the paper evidence workflow and [paper/REPRODUCING.md](paper/REPRODUCING.md) for the manual from-scratch recipe, acceptance boundaries, and known deviations.
See [image_archive/axiom/README.md](image_archive/axiom/README.md) for the restartable JPEG XL archive workflow and completed-run evidence.

The data-preparation notes below describe the original analysis workflow.
Some original scripts do not run as published; `paper/REPRODUCING.md` identifies the repairs and remaining boundaries.

Tests live with the pipeline, paper, or archive subsystem they exercise.
The locked pipeline and paper test commands are in [paper/README.md](paper/README.md), and the archive test command is in [image_archive/axiom/README.md](image_archive/axiom/README.md).

Scripts for downloading and preparing the data are included in the `0_prepare_data` folder.
The main analysis is in the 1_snakemake folder, and exploratory notebooks for visualizing results and comparing across pipeline variations are in the 2_downstream_analysis folder.

## Skipping input data formatting

The scripts in `0_prepare_data` compile profiles, metadata, and image locations across plates and batches, and ensure that formatting is consistent across different cell representations.
These compiled files are the inputs to the snakemake pipeline.
To make things easier, we've deposited a [copy of the compiled inputs on Zenodo](https://zenodo.org/records/17067683). The script `4A_download_compiled_inputs.py` can be run instead of scripts 1A - 2E.

## Plotting images

Run `uv run paper/render_sfig1.py --output-dir OUTPUT_DIR` to resolve, download, and render the exact five-channel field published as supplemental Figure S1.
The historical `2_downstream_analysis/other_notebooks/Plot_images.ipynb` remains available for broader exploratory image selection.
