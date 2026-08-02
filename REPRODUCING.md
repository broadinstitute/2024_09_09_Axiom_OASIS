# Reproducing the paper 1A results

Status: in progress. This file records what had to change to make the published
pipeline runnable, so that any difference between regenerated and committed
results can be attributed.

## Scope

Target: regenerate the committed artifacts in `2_downstream_analysis/compiled_results/`
and `compiled_results/SI_tables/` and compare them numerically to what is in git.

Fidelity: numerical equivalence within a documented tolerance, with every
deviation explained. Bit-identical output is not achievable here -- the original
environment was macOS arm64 (the deleted `environment.yml` recorded
`prefix: /Users/jewald/miniforge3/envs/axiom`), this runs on Linux x86_64, and
the R dependency set was never pinned by anything.

First pass covers three configs: `cellprofiler.json`, `cpcnn.json`, `dino.json`.
The full processing-variation matrix (12 configs) needed by
`SI_compare_processing.ipynb` is a second pass.

## Setup

```bash
nix develop          # R + snakemake + awscli
pixi install -e pipeline
python 0_prepare_data/4A_download_compiled_inputs.py    # run from inside 0_prepare_data/
```

Inputs come from Zenodo record 17067683 (open access, CC-BY-4.0,
DOI 10.5281/zenodo.17067683), 0.86 GB total. That record is a complete
substitute for scripts `1A`-`2E`. Verify against the MD5s Zenodo publishes;
`4A` does no checksum or resume, so a truncated download yields a corrupt
parquet silently.

Do not run `3A_download_invitrodb.sh`. It is non-functional as written (a
`curl -O` given an argument, interactive mysql REPL lines pasted into a shell
script, macOS/Homebrew only, and a Clowder file ID for invitrodb v4.1 that has
likely been superseded), it wants a ~100 GB MySQL import, and its six outputs
are already committed under `1_snakemake/inputs/annotations/`. The pipeline
reads only the three `_binary` files.

Run the pipeline once per config, from `1_snakemake/`:

```bash
cd 1_snakemake
snakemake --configfile inputs/conf/cpcnn.json --cores 32
```

R scripts `source()` `./concresponse/*.R` by relative path, so the working
directory must be `1_snakemake/`.

## Changes required to make it run

Each is a separate commit on this branch.

1. **Environment** (`flake.nix`, `pixi.toml`, `.envrc`). The repo shipped no R
   dependency declaration of any kind, and `requirements.txt` omits `cupy` and
   `copairs`, both imported by the pipeline.

2. **`rule int`** (`1_snakemake/rules/processing.smk`). Called
   `pp.select_features(*input, *output)` -- two args against a three-arg
   signature, and the wrong function. Now `pp.transform.rank_int(*input, *output)`.
   As published the three `*_int.json` configs could not run at all, so the
   `_int` results in `SI_compare_processing.ipynb` did not come from this code.

3. **`rule all`** (`1_snakemake/Snakefile`). All targets but one were commented
   out, and the surviving one hardcoded `mad_featselect` instead of `{scenario}`.
   `visualize.smk` was included but never requested by anything.

4. **`refchemdb_oasis.parquet`**. Deleted in `defa7fd` but still read by
   `2_2_outlier_enrichment_analysis.ipynb`; no script regenerates it. Recovered
   from `defa7fd^`.

5. **Notebook paths**. The five non-`Plot_images` notebooks in `other_notebooks/`
   plus four cells in `2_1` and `2_2` used paths one directory level too shallow.

6. **polars API split**. See the table in `pixi.toml`. Handled by environment
   separation rather than by editing notebooks.

## Known caveats

- **`cellprofiler_filt` vs `cellprofiler`.** `inputs/conf/README.md` says the
  manuscript CellProfiler result uses `cellprofiler_filt.json`, whose `name` is
  `mad_featselect_filt`. But every notebook reads
  `outputs/cellprofiler/mad_featselect/`, produced by `cellprofiler.json`. No
  notebook references a `mad_featselect_filt` path. The two configs differ only
  in `outlier_feat_thresh` (10,000 vs an effectively-unlimited 10,000,000), so
  they select different feature sets and will not agree. Unresolved; until it
  is, `SI_tables/cellpainting_cellprofiler_pods.csv` cannot be claimed as
  exactly reproduced.

- **`cc.parquet` is unreproducible.** Committed with no generating script
  anywhere in the repo, and load-bearing: it supplies `Metadata_Count_Cells` to
  the cell-count POD fits and to `classifier/aggregate_profiles.py`. Taken as
  given.

- **`4_1_results_tables_SI.ipynb` has no stored cell outputs** and
  non-monotonic execution counts (1, 9, 40, 41, 42, 18, 47, 49), so the
  committed SI CSVs may not correspond to a single clean top-to-bottom run.

- **`copairs` is unpinned** and absent from `requirements.txt`. Only the
  `*_ap.json` configs reach it, so it does not affect the three-config first
  pass.

- **Hardware assumption.** `classifier/classify.py` hardcodes `num_gpus = 4`
  and indexes `cp.cuda.Device(i % 4)`. It requires a 4-GPU node.
  `concresponse/compute_distances.R` hardcodes 30 R workers; `concresponse/ap.py`
  hardcodes 10. No rule declares `threads:` or `resources:`, so `--cores N`
  will oversubscribe.

- **Orphan artifacts.** `compiled_results/motive_highexp_PHH.parquet` and
  `inputs/annotations/motive_binary.parquet` are referenced by no code in the
  repo.

- **R version drift.** The flake resolves to R 4.6.1, considerably newer than
  the 2024-era R the original work would have used. Nothing in the repo or its
  history pins an R version, so there is no target to match; this is recorded
  as a known deviation rather than a fixable one.

## Verified so far

- Nix R environment builds and all eleven packages load: dplyr, arrow,
  ggplot2, ggforce, reshape2, foreach, doParallel, data.table, stringr, drc,
  fastbmdR. `arrow::arrow_info()` reports Parquet support TRUE, and fastbmdR
  exports the four functions the pipeline calls (`scoresPOD`,
  `PerformCurveFitting`, `PerformBMDCalc`, `FilterDRFit`).
- `cellprofiler_raw.parquet` downloaded and MD5-verified against Zenodo
  (413,433,180 bytes, md5 prefix 0cf2b9d11268).
