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

- **R environment.** All eleven packages load under R 4.6.1: dplyr, arrow,
  ggplot2, ggforce, reshape2, foreach, doParallel, data.table, stringr, drc,
  fastbmdR. `arrow::arrow_info()` reports Parquet support TRUE, and fastbmdR
  exports the four functions the pipeline calls (`scoresPOD`,
  `PerformCurveFitting`, `PerformBMDCalc`, `FilterDRFit`).

- **Python environment.** numpy 1.24.4, pandas 2.2.2, polars 0.20.0,
  pyarrow 14.0.1, scikit-learn 1.5.2, xgboost 2.1.1, pycytominer 1.2.0,
  snakemake 7.32.4, copairs 0.5.4. numpy resolves to 1.24.4 rather than
  requirements.txt's 1.24.3 because it is solved by conda (cupy pulls it in);
  recorded as a deviation.

- **GPU.** cupy 13.6.0 sees all four H100s and computes on each;
  `XGBClassifier(device="cuda:0")` fits successfully. This is the code path
  `classifier/classify.py` uses.

- **Data.** All five Zenodo inputs downloaded and MD5-verified:
  cellprofiler_raw 413,433,180 / dino_raw 399,927,644 / cpcnn_raw 48,201,019 /
  metadata 734,477 / index 2,524,798 bytes.

- **DAG.** `snakemake --configfile inputs/conf/cellprofiler.json -n` resolves
  cleanly to 24 jobs with no missing inputs, covering every rule from
  compute_negcon_stats through the four classifiers, the four curve PDFs and
  umaps.pdf. The restored `rule all` reaches all 17 targets.

## Pipeline runs

All three manuscript configs completed with zero errors.

| Config | Wall time | Outputs |
| --- | ---: | ---: |
| `cellprofiler.json` | ~85 min | 25 |
| `cpcnn.json` | 45 min | 24 (no `cmd.parquet`; gmd-only config) |
| `dino.json` | 70 min | 25 |

Per-rule wall time (cpcnn, the fully instrumented run):

| Rule | Wall |
| --- | ---: |
| `toxcast_cellbased_binary` | 1542s |
| `plot_ldh_curve_fits` | 1391s |
| `plot_cc_curve_fits` | 1369s |
| `plot_mtt_curve_fits` | 1285s |
| `predict_axiom_continuous` | 968s |
| `toxcast_cytotox_binary` | 672s |
| `toxcast_cellfree_binary` | 666s |
| `compute_distances_R` | 340s |
| `plot_cp_curve_fits` | 253s |
| `fit_curves` | 101s |
| all others | < 3s |

Two observations for anyone planning a run:

- **`fit_curves` scales with endpoint count and is single-threaded.** 101s for cpcnn
  (1 distance endpoint), 770s for dino (7), 1650s for cellprofiler (19), all at a
  CPU:wall ratio of 1.0 while 383 cores idle. The per-compound loop is
  embarrassingly parallel; `compute_distances_R` beside it forks 30 workers.
- **The four curve-fit PDFs cost more than anything except the classifiers**
  (~68 CPU-minutes combined for cpcnn) and nothing reads them: no notebook, no
  SI table, no verification artifact. Dropping them from `rule all` for routine
  runs roughly halves a cpcnn run.

`toxcast_cellbased_binary` costs the same in every config (1542s / 1532s / 1705s)
because the classifiers consume aggregated profiles and do not care about endpoint
count. That is an irreducible ~50 min of classifier work per config.

## Reproduction results

### Classifier metrics (`compiled_*_metrics.parquet`, via `3_2_0`)

Structure reproduces exactly: identical row counts and identical key sets in all
four files (81 / 918 / 1431 / 7209 rows), no keys added or lost.

Values split cleanly by aggregation type:

| Outcome | AggType | n | exact | mean abs dAUROC | max |
| --- | --- | ---: | ---: | ---: | ---: |
| toxcast_cellbased | `all` | 2403 | **2403** | **0.0000** | **0.0000** |
| toxcast_cellbased | `allpod` | 2403 | 111 | 0.0479 | 0.5317 |
| toxcast_cellbased | `allpodcc` | 2403 | 102 | 0.0531 | 0.6278 |
| toxcast_cytotox | `all` | 306 | **306** | **0.0000** | **0.0000** |
| toxcast_cytotox | `allpod` | 306 | 48 | 0.0288 | 0.2312 |
| toxcast_cytotox | `allpodcc` | 306 | 46 | 0.0333 | 0.5268 |
| axiom | `all` | 27 | 18 | 0.0017 | 0.0175 |
| axiom | `allpod` | 27 | 0 | 0.0195 | 0.2062 |
| axiom | `allpodcc` | 27 | 0 | 0.0196 | 0.1097 |

`AggType == "all"` reproduces **bit-exactly** across all 2709 ToxCast rows. That
rules out the classifier as a source of divergence: GPU XGBoost training, the
StratifiedKFold splits, MAD normalisation, feature selection and the ToxCast label
joins are all exactly reproducible in the rebuilt environment.

Only `allpod` and `allpodcc` differ, and those are the two aggregation types that
filter wells by whether concentration exceeds the compound's POD. The exception
confirms the rule: axiom's `all` shows small differences because axiom *labels*
come from hit calls, which are also POD-derived, whereas ToxCast labels come from
committed annotation files and are POD-independent.

**Every observed difference traces to one stage: the R curve fitting produces
slightly different PODs.**

### PODs (`SI_tables/*.csv`, via `4_1`)

Join key `(OASIS_ID, Compound_name, Assay_Endpoint)` -- note `OASIS_ID` alone is
not unique (199 distinct IDs across 220 rows in `cellcount_pods.csv`).

| SI table | ref | new | matched | only ref | only new | exact | <=1% | median rel | max rel |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cellcount_pods` | 220 | 221 | 198 | 22 | 23 | 7 | 175 | 2.5e-6 | 1.39 |
| `mt_pods` | 429 | 430 | 375 | 54 | 55 | 36 | 346 | 1.2e-6 | 4.39 |
| `ldh_pods` | 147 | 144 | 127 | 20 | 17 | 12 | 123 | 7.1e-8 | 0.78 |
| `cellpainting_cellprofiler` | 6965 | 7161 | 6094 | 871 | 1067 | 157 | 5403 | 9.7e-7 | 69.6 |
| `cellpainting_cpcnn` | 539 | 535 | 473 | 66 | 62 | 1 | 433 | 9.9e-7 | 10.7 |
| `cellpainting_dino` | 3431 | 3437 | 3031 | 400 | 406 | 34 | 2791 | 1.8e-6 | 28.7 |

Median relative difference is 1e-6 to 1e-7: for the typical compound the
reproduced POD matches the published one to six or seven significant figures.
88-97% of matched PODs agree within 1%.

The tail is the finding. Roughly one matched POD in ten diverges materially
(maxima 10x to 70x), and 10-15% of rows appear in only one of the two runs.
Both follow from the same mechanism: `fastbmdR` selects among eight model
families (Exp2, Exp3, Exp4, Exp5, Hill, Pow, Poly2, Lin) by AIC and then applies
pass/fail gates. Model selection is discrete, so when two families fit nearly
equally well a difference in the seventh decimal flips the choice and the POD can
move by an order of magnitude. The same knife-edge behaviour at the `all.pass`
gates moves compounds in and out of the tables.

Summary: continuous quantities reproduce to numerical precision; the discrete
decisions layered on top of them are unstable to an environment change that
involved no code change. The most likely driver is the unpinned R stack -- R 4.6.1
with whatever `drc` and `fastbmdR` builds nixpkgs resolved, versus the authors'
2024-era R. Nothing in the repo ever pinned those.

This bears directly on the OASIS Phase I discovery question about which POD
methods are stable and interpretable.

### Corrected earlier suspicion

An apparent dtype landmine in `4_1` -- metadata POD tables filtered with
`pl.col("all.pass") == "true"` (string) against a Boolean column, while the Cell
Painting tables use `== True` -- turns out to be harmless. Both polars 0.20.0 and
1.43.2 coerce the string and return the same 221 rows. No fix needed.
