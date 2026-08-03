# Reproducing the paper 1A results

This file records what had to change to make the published pipeline runnable,
and what the regenerated results look like next to the committed ones.

**Outcome.** The pipeline reproduces. The classifier path is bit-exact:
`AggType == "all"` matches the committed metrics on all 2709 ToxCast rows.
PODs agree to 6-7 significant figures at the median, but ~10% diverge
materially because model selection is discrete. Outlier enrichment reproduces
its machinery exactly but starts from a hit list of 292 rather than 304. Both
divergences are characterised below.

**The committed code cannot have produced the committed outputs.** Four
independent demonstrations: `rule int` raises `TypeError`, so the three `_int`
configs never ran; `requirements.txt` omits `cupy` and `copairs` and
under-constrains `pulp` such that snakemake will not start; `regression.py`
writes raw object pointers into four metadata columns, so notebooks `2_1` and
`2_2` cannot have produced their four committed CSVs; and `2_1`'s cells 4 and 5
require two different polars versions simultaneously.

## Scope

Target: regenerate the committed artifacts in `2_downstream_analysis/compiled_results/`
and `compiled_results/SI_tables/` and compare them numerically to what is in git.

Fidelity: numerical equivalence within a documented tolerance, with every
deviation explained. Bit-identical output is not achievable here -- the original
environment was macOS arm64 (the deleted `environment.yml` recorded
`prefix: /Users/jewald/miniforge3/envs/axiom`), this runs on Linux x86_64, and
the R dependency set was never pinned by anything.

Covers four configs: `cellprofiler.json`, `cpcnn.json`, `dino.json`, and
`cellprofiler_filt.json` (run to settle which one the manuscript used -- see
below; the answer is that it does not matter).

Not covered: the nine further runs for the `_log10`, `_int` and `_ap` variants
that `SI_compare_processing.ipynb`, `1_3` and `05_compare_pods_transforms`
need. Note before spending that compute that the `_int` branch could not have
run as published, so whatever is in the committed `_int` results came from
different code.

## Running it from scratch

Requires Nix with flakes, and a machine with 4 GPUs (see caveats). Roughly
3.5 hours of wall clock for the three configs.

**1. Environments.** R comes from Nix; Python and snakemake come from pixi.
Everything below assumes you are inside the Nix shell.

```bash
nix develop
pixi install -e pipeline
pixi install -e notebooks
```

`nix develop` sets `R_LIBS_USER=/dev/null` (so the `.R` scripts cannot attempt
runtime `install.packages`) and puts the host driver's `libcuda.so` on
`LD_LIBRARY_PATH` (without which cupy fails with
`cudaErrorInsufficientDriver`).

**2. Data.** 0.86 GB from Zenodo record 17067683 (open access, CC-BY-4.0,
DOI 10.5281/zenodo.17067683). This is a complete substitute for scripts
`1A`-`2E`.

```bash
cd 0_prepare_data
pixi run --manifest-path ../pixi.toml -e pipeline python 4A_download_compiled_inputs.py
cd ..
```

Use the pixi Python, not a bare `python`: `4A` imports `requests`, which the
system interpreter will not have.

`4A` has no resume and no checksum, so a truncated download yields a corrupt
parquet with no error. Verify against the sizes and MD5 prefixes Zenodo
publishes:

```bash
cd 1_snakemake/inputs
for f in profiles/cellprofiler/raw.parquet profiles/dino/raw.parquet \
         profiles/cpcnn/raw.parquet metadata/metadata.parquet images/index.parquet; do
  printf '%-40s %12s %s\n' "$f" "$(stat -c%s "$f")" "$(md5sum "$f" | cut -c1-12)"
done
```

Expected:

| file | bytes | md5 prefix |
| --- | ---: | --- |
| `profiles/cellprofiler/raw.parquet` | 413433180 | `0cf2b9d11268` |
| `profiles/dino/raw.parquet` | 399927644 | `421529eb8088` |
| `profiles/cpcnn/raw.parquet` | 48201019 | `d79b1cebc8aa` |
| `metadata/metadata.parquet` | 734477 | `6731b56f8f4f` |
| `images/index.parquet` | 2524798 | `b56e249504f7` |

Do **not** run `3A_download_invitrodb.sh`. It is non-functional as written (a
`curl -O` given an argument, interactive mysql REPL lines pasted into a shell
script, macOS/Homebrew only, and a Clowder file ID for invitrodb v4.1 that has
likely been superseded), it wants a ~100 GB MySQL import, and its six outputs
are already committed under `1_snakemake/inputs/annotations/`. The pipeline
reads only the three `_binary` files.

**3. Pipeline**, once per config. The working directory must be `1_snakemake/`
because the R scripts `source()` `./concresponse/*.R` by relative path.

```bash
cd 1_snakemake
for cfg in cellprofiler cpcnn dino; do
  pixi run --manifest-path ../pixi.toml -e pipeline \
    snakemake --configfile inputs/conf/$cfg.json --cores 4
done
cd ..
```

Use `--cores 4`, not more: no rule declares `threads:` or `resources:`, several
rules spawn their own pools sized to the whole machine, and the four classifier
rules each expect all 4 GPUs.

**4. Notebooks.** Which environment matters -- the repo mixes two incompatible
polars API generations (see the table in `pixi.toml`). Run in this order; the
first three write the artifacts the rest compare against.

Pass `--ExecutePreprocessor.kernel_name=python3`. Several notebooks embed a
kernelspec named `oasis-prot-proc`, which does not exist anywhere; without the
override, execution fails on a missing kernel rather than on anything real.

The loops below are fail-fast (`set -e`). Do not drop that: a plain `for` loop
lets an early failure scroll past while later notebooks succeed, which is how
`3_2_1` was wrongly recorded as passing in an earlier revision of this file.

```bash
set -e
cd 2_downstream_analysis/manuscript_notebooks
for nb in 3_2_0_assay_metrics 4_1_results_tables_SI 2_1_predict_continuous_assays \
          1_2_number_active_readouts 1_2_1_cmpds_increase_mt 3_1_toxcast_endpoints \
          3_2_2_compare_concs_reps; do
  pixi run --manifest-path ../../pixi.toml -e pipeline \
    jupyter nbconvert --to notebook --execute --inplace \
    --ExecutePreprocessor.kernel_name=python3 $nb.ipynb
done
pixi run --manifest-path ../../pixi.toml -e notebooks \
  jupyter nbconvert --to notebook --execute --inplace \
  --ExecutePreprocessor.kernel_name=python3 3_2_3_compare_endpoints_detail.ipynb
cd ../other_notebooks
for nb in 02_analyze_AR 03_analyze_ER 04_analyze_GR; do
  pixi run --manifest-path ../../pixi.toml -e notebooks \
    jupyter nbconvert --to notebook --execute --inplace \
    --ExecutePreprocessor.kernel_name=python3 $nb.ipynb
done
```

Not runnable, by design or defect: `3_2_1`, `2_2` and `01_checkwelleffects`
(see below); `1_3`, `SI_compare_processing` and `05_compare_pods_transforms`
need the extended config matrix; `Plot_images` needs S3 TIFF downloads into PNG
subdirectories it does not create.

**5. Comparing.** The notebooks overwrite
`2_downstream_analysis/compiled_results/`. Copy that directory aside first, or
`git stash` after, so the committed artifacts can be diffed against the
regenerated ones. Use `(OASIS_ID, Compound_name, Assay_Endpoint)` as the join
key for the SI tables -- `OASIS_ID` alone is not unique (199 distinct IDs across
220 rows in `cellcount_pods.csv`), and the CSV column is `Assay_Endpoint` with a
capital E.

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

### The pipeline is not deterministic run to run

An independent clean run on the same host, same commit, same environment
(recorded separately) produced POD tables that differ from the ones above:

| table | run A new rows / matched | run B new rows / matched |
| --- | ---: | ---: |
| `cellpainting_cellprofiler` | 7161 / 6094 | 7150 / 6087 |
| `cellpainting_dino` | 3437 / 3031 | 3434 / 3029 |
| `cellpainting_cpcnn` | 535 / 473 | 535 / 472 |

The enrichment output drifts the same way: 6966 vs 6962 of 8858 `fdr` values
bit-identical to the committed file.

This is more consequential than the drift against the published run. Two
executions of *identical* code, on the same machine, with byte-identical inputs
do not agree on which compounds pass. So the POD instability is not only
sensitivity to environment or feature-set changes -- there is genuine
run-to-run nondeterminism inside the curve-fitting stage itself. The classifier
path is unaffected: `AggType == "all"` is bit-exact in both runs.

Consequence for anyone comparing results: a POD table differing by ~0.2% of
rows is within observed run-to-run noise and is not evidence of a real change.
Only the bit-exact `all` classifier rows are a reliable regression signal.

Separately, `overlap_hits` in the enrichment CSVs is built from unordered
Python sets and the final sort keys only on FDR, so tied rows serialise in
arbitrary order. The numbers are repeatable; the file bytes are not. Compare
those files by value, never by checksum.

### `cellprofiler_filt` vs `cellprofiler`: resolved, and immaterial

`inputs/conf/README.md` names `cellprofiler_filt.json` as the manuscript
CellProfiler config, while every notebook reads
`outputs/cellprofiler/mad_featselect/`, which only `cellprofiler.json` produces.
Both were run to settle it.

Applying `4_1`'s filter (`all.pass & SDres < 3*SDctrl`) to each:

| config | bmds rows | passing filter |
| --- | ---: | ---: |
| committed `cellpainting_cellprofiler_pods.csv` | -- | 6965 |
| `cellprofiler` (`mad_featselect`) | 20510 | 7161 |
| `cellprofiler_filt` (`mad_featselect_filt`) | 20510 | 7158 |

Neither matches the committed 6965, and the two differ from each other by 3 rows.
The config choice therefore does not explain the gap; the ~200-row difference is
the POD instability described above. The README/notebook discrepancy is real but
has no bearing on reproduction.

The comparison did expose something sharper. The two configs differ only in
`outlier_feat_thresh` (10,000 vs an effectively unlimited 10,000,000), which
changes the retained feature set by 4 dropped and 8 added out of ~820 -- about
1.5%. (The count rises under the tighter threshold because `select_features`
runs variance threshold, then the outlier drop, then correlation pruning:
removing outlier features changes which correlated pairs survive.)

That 1.5% input perturbation changes **83% of the fitted BMDs**: only 3067 of
18453 matched (compound, endpoint) pairs have identical `bmd`, with differences
up to 1e4.

This is the same fragility as the version-drift result, measured independently
and without changing any software: AIC-based model selection over eight families
amplifies small input perturbations into large output changes. It is not
specific to R versions.

### Notebook execution

Run from clean, each in its assigned environment.

Pass (11): `1_2`, `1_2_1`, `2_1`, `3_1`, `3_2_0`, `3_2_2`, `3_2_3`, `4_1`,
`02_analyze_AR`, `03_analyze_ER`, `04_analyze_GR`.

Fixed to get there:

- `regression.py` corrupt metadata columns (see defect list) -- blocked `2_1`
  and `2_2`.
- `3_2_1` used `pn.options` in two cells that never `import plotnine as pn`,
  while three other cells in the same notebook do have the import. Only ever
  worked with leftover kernel state.
- `2_1` cell 4 pivots to columns named
  `Metadata_mtt_ridge_norm_Replicate_number_1`, and successfully selects them,
  but cell 5 refers to `Metadata_mtt_ridge_norm_1`. Those are two different
  polars pivot-naming conventions, so cells 4 and 5 cannot both succeed under
  any single polars version. Fixed by aliasing in cell 4.

Still failing, documented rather than patched:

- `3_2_1_compare_endpoint_types`: fails at `smf.mixedlm` with
  `ValueError: negative dimensions are not allowed`. Its `_AR` filter reduces
  the endpoint group counts from 9/69/696/6 to 0/0/36/0, and pandas
  `groupby(observed=False)` then iterates the empty `axiom_cytotox` category
  into `mixedlm`, where Patsy fails on an empty design matrix. Deterministic:
  the committed and the regenerated metrics produce the same empty groups.
  Fixing the `pn` import (below) was necessary but not sufficient. An earlier
  revision of this file listed this notebook as passing; that was wrong -- the
  import fix was made and the notebook was never re-run to confirm.

- `2_2_outlier_enrichment_analysis`: cell 1 ends with
  `group_by(["Metadata_Perturbation", "Variable", "Metadata_Well",
  "Metadata_Plate"]).agg(...)`, which drops `Metadata_Compound`; later cells
  select `Metadata_Compound` from that same derived frame and raise
  `ColumnNotFoundError`. Recovering it means either re-joining or parsing it out
  of `Metadata_Perturbation`, and guessing wrong would put incorrect numbers
  into `mtt_higher_targets.csv` / `mtt_lower_targets.csv`, which are
  verification artifacts. Left unrepaired deliberately.
- `01_checkwelleffects`: `KeyError: 'Metadata_ldh_ridge_norm'` at the pivot in
  cell 13, although the column is float64 with 21426 non-null values in the
  source profile -- an earlier transform in the notebook drops it. Exploratory
  only; produces no verification artifact.

None of these four notebooks has ever run top-to-bottom from a clean kernel.

### Outlier enrichment (`err_*_targets.csv`, via `2_1`)

Shape and schema reproduce exactly: 8858 rows and the same 8 columns in both
files. The enrichment machinery is exact --- `universe_size` is 13176 in all
8858 rows of both, target-set definitions agree, and 6966 of 8858 `fdr` values
are identical.

The input hit list is not: for `err_higher_targets.csv`, `hit_list_size` is 304
in the committed file and 292 in the reproduction, differing in every row, which
reshuffles p-values and the top-ranked targets. `err_lower_targets.csv` shows
the same pattern at 138 committed vs 134 reproduced, though all 8858 of its
`fdr` values are bit-identical.

This is a **second, independent divergence**, not more of the POD story:
`predict_axiom_continuous` reads well-level profiles directly and never touches
PODs or POD-filtered aggregates. The mechanism has not been established; it
warrants its own investigation. `regression.py` seeds `GroupShuffleSplit`
(`random_state=42`) but sets no seed on the XGBoost regressor.

Blocked on the extended config matrix (not run): `1_3` and
`05_compare_pods_transforms` need `mad_featselect_log10` and
`mad_int_featselect`; `SI_compare_processing` additionally needs
`mad_featselect_ap`. That is 9 further pipeline runs, and note that the `_int`
branch could not have run as published (see defect 2). `Plot_images` needs S3
TIFF downloads into PNG subdirectories it does not create.

### Corrected earlier suspicion

An apparent dtype landmine in `4_1` -- metadata POD tables filtered with
`pl.col("all.pass") == "true"` (string) against a Boolean column, while the Cell
Painting tables use `== True` -- turns out to be harmless. Both polars 0.20.0 and
1.43.2 coerce the string and return the same 221 rows. No fix needed.
