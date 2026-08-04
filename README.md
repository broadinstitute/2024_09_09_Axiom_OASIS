# 2024_09_09_Axiom_OASIS

> **Reproducing the results?**
>
> Run `uv run paper/reproduce_all.py` for the isolated, resumable end-to-end reproduction, or add `--dry-run` to inspect its exact plan first.
> See [REPRODUCING.md](REPRODUCING.md) for the manual from-scratch recipe (Nix + Pixi environments, data, pipeline, notebooks), the acceptance boundaries, and what the regenerated results look like next to the committed ones.
> The instructions below describe the original layout; several of the scripts they reference do not run as published, and `REPRODUCING.md` says which.

> **Working from the paper?**
>
> Run `uv run paper/reproduce.py` for the repository-only executable paper.
> See [paper/README.md](paper/README.md) for the searchable paper, published source files, complete target inventory, acceptance rules, and evidence workflow.

This repository is for analyzing the Axiom OASIS imaging data.
Scripts for downloading the data from the Cell Painting Gallery are included in the 0_data_download folder.
The main analysis is in the 1_snakemake folder, and exploratory notebooks for visualizing results and comparing across pipeline variations are in the 2_downstream_analysis folder.

## Skipping input data formatting

The scripts in `0_prepare_data` compile profiles, metadata, and image locations across plates and batches, and ensure that formatting is consistent across different cell representations.
These compiled files are the inputs to the snakemake pipeline.
To make things easier, we've deposited a [copy of the compiled inputs on Zenodo](https://zenodo.org/records/17067683). The script `4A_download_compiled_inputs.py` can be run instead of scripts 1A - 2E.

## Plotting images

Run `uv run paper/render_sfig1.py --output-dir OUTPUT_DIR` to resolve, download, and render the exact five-channel field published as supplemental Figure S1.
The historical `2_downstream_analysis/other_notebooks/Plot_images.ipynb` remains available for broader exploratory image selection.
