# 2024_09_09_Axiom_OASIS

> **Reproducing the results?** See [REPRODUCING.md](REPRODUCING.md) for a
> from-scratch recipe (Nix + pixi environments, data, pipeline, notebooks) and
> for what the regenerated results look like next to the committed ones. The
> instructions below describe the original layout; several of the scripts they
> reference do not run as published, and `REPRODUCING.md` says which.

> **Working from the paper?**
> See [paper/README.md](paper/README.md) for the searchable paper, published source files, target inventory, flexible acceptance rules, and evidence workflow for systematic reproduction.

This repository is for analyzing the Axiom OASIS imaging data. Scripts for downloading the data from the Cell Painting Gallery are included in the 0_data_download folder. The main analysis is in the 1_snakemake folder, and exploratory notebooks for visualizing results and comparing across pipeline variations are in the 2_downstream_analysis folder.

## Skipping input data formatting

The scripts in `0_prepare_data` compile profiles, metadata, and image locations across plates and batches, and ensure that formatting is consistent across different cell representations. These compiled files are the inputs to the snakemake pipeline. To make things easier, we've deposited a [copy of the compiled inputs on Zenodo](https://zenodo.org/records/17067683). The script `4A_download_compiled_inputs.py` can be run instead of scripts 1A - 2E.

## Plotting images

If you are only interested in viewing example images from OASIS, check out the `2_downstream_analysis/other_notebooks/Plot_images.ipynb` notebook. It contains instructions for downloading the necessary metadata for downloading images from AWS and functions for combining them into nice plots.
