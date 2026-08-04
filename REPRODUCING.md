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

Requires Nix with flakes, and at least one CUDA GPU (see caveats). Roughly
3.5 hours of wall clock for the three configs on a 4-GPU node; expect longer
on fewer GPUs.

**1. Environments.** R comes from Nix; Python and snakemake come from pixi.
Everything below assumes you are inside the Nix shell.

```bash
nix develop path:.
pixi install -e pipeline
pixi install -e notebooks
```

`nix develop path:.` sets `R_LIBS_USER=/dev/null` so the `.R` scripts cannot attempt runtime `install.packages`, and it puts the host driver's `libcuda.so` on `LD_LIBRARY_PATH` to prevent `cudaErrorInsufficientDriver` from cupy.

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
rules each run 4 workers across every GPU they can see.

**4. Notebooks.** Which environment matters -- the repo mixes two incompatible
polars API generations (see the table in `pixi.toml`). Run in this order; the
first three write the artifacts the rest compare against.

Pass `--ExecutePreprocessor.kernel_name=python3`. Several notebooks embed a
kernelspec named `oasis-prot-proc`, which does not exist anywhere; without the
override, execution fails on a missing kernel rather than on anything real.

The loops below are fail-fast (`set -e`). Do not drop that: a plain `for` loop
lets an early failure scroll past while later notebooks succeed, which is how
`3_2_1` was wrongly recorded as passing in an earlier revision of this file.

`--inplace` rewrites the notebooks. They are committed with their outputs, so a
clean run produces a large diff (~10k lines) that is entirely execution
metadata: iopub timestamps, execution counts and embedded images. That is
expected, and it is not evidence of a behaviour change. `.gitattributes`
registers nbdime as the notebook diff and merge driver; run
`nbdime config-git --enable --global` once to make it take effect.

```bash
set -e
cd 2_downstream_analysis/manuscript_notebooks
for nb in 3_2_0_assay_metrics 4_1_results_tables_SI 2_1_predict_continuous_assays \
          3_2_1_compare_endpoint_types 1_2_number_active_readouts \
          1_2_1_cmpds_increase_mt 3_1_toxcast_endpoints 3_2_2_compare_concs_reps; do
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

Not runnable, by design or defect: `2_2` and `01_checkwelleffects` (see below);
`1_3`, `SI_compare_processing` and `05_compare_pods_transforms`
need the extended config matrix; `Plot_images` needs S3 TIFF downloads into PNG
subdirectories it does not create.

**5. Comparing.** The notebooks overwrite `2_downstream_analysis/compiled_results/`.
Copy the committed directory aside before executing them so it can serve as the reference.

```bash
reference_root=$(mktemp -d /tmp/axiom-reference.XXXXXX)
cp -a 2_downstream_analysis/compiled_results "$reference_root/compiled_results"
```

After running the notebooks, invoke the read-only verifier from the repository root:

```bash
(
  trap 'git checkout -- 2_downstream_analysis/compiled_results' EXIT
  pixi run -e pipeline python -m verification.compiled_results \
    --reference "$reference_root/compiled_results" \
    --candidate 2_downstream_analysis/compiled_results \
    --json-report /tmp/axiom-verification.json
)
```

The JSON report is optional, deterministic for a given invocation, and must be outside both input directories.
The terminal summary reports every comparison even when a gate fails.
Exit status 0 means all gates passed, 1 means a reproducibility gate failed, and 2 means the command or an input artifact was invalid.
An exit-0 PASS covers only the configured gates listed below.
Differences in non-core metric payloads, hit calls, and enrichment hit-list size, overlap, p-value, and FDR values remain diagnostic and are printed even when the gates pass.
The verifier rejects identical resolved input directories, missing or unreadable files, empty tables, unexpected schemas, duplicate semantic keys, invalid values, and a report path inside either input.

The gates are:

- **Classifier metrics.** The four Parquets must have their expected row counts: 81 Axiom, 7,209 ToxCast cell-based, 1,431 ToxCast cell-free, and 918 ToxCast cytotoxicity.
  Their `(Metadata_AggType, Metadata_Label, Model_type, Feat_type)` key sets must match exactly.
  AUROC, PRAUC, and both class counts must be IEEE bit-exact for the 2,709 `AggType == "all"` rows from the cell-based and cytotoxicity files.
  Other metric payload differences are reported but do not fail the comparison.

- **PODs.** The six SI POD CSVs use `(OASIS_ID, Compound_name, Assay_Endpoint)` as the key.
  `OASIS_ID` alone is not unique, and the endpoint column has a capital E.
  Blank `OASIS_ID` values remain subject to within-file duplicate validation but do not match across inputs, following SQL and Polars join semantics.
  At least 80% of each side's keys must match.
  Of the comparable `POD_um` point estimates (matched rows where both reference and candidate values are positive), at least 85% must be within 1% relative to the reference and the median reference-relative difference must be at most `1e-5`.
  Every POD and bound must be positive and finite, with `POD_um_l <= POD_um <= POD_um_u`.
  This validity gate is independent: a non-positive point estimate is excluded from the relative-difference statistics but still makes the comparison fail.
  Row-count drift and the fraction with relative difference above 10% are reported rather than gated.
  The approximately 0.2% row drift observed between pre-fix runs is informational run-to-run noise, not the acceptance threshold for published-versus-regenerated key drift.
  These are paper-1A acceptance gates calibrated against the locked recipe and the documented clean comparison, not portability bounds for arbitrary R or BLAS builds.
  If an environment change crosses a gate, investigate and recalibrate only from documented clean-run evidence; do not widen a threshold merely to clear a failing run.

- **Hit summary.** `SI_tables/hit_summary.csv` must have unique, identical `(OASIS_ID, Compound_name)` key sets and only `Yes` or `No` hit values.
  Hit-call agreement is reported but is not a numerical gate.

- **Outlier enrichment.** Each `err_*_targets.csv` must contain exactly 8,858 unique and identical `target_set` keys, identical `target_set_size` values, and `universe_size == 13176` on every row.
  Each input must have one positive constant `hit_list_size`, but the reference and candidate constants may differ.
  Set sizes, overlap sizes, p-values, and FDR values must remain in valid ranges.
  `overlap_hits` is parsed using the produced sample-ID grammar and compared as an unordered set, including compound names that contain commas.
  Hit-list, overlap, p-value, and FDR differences are diagnostic; the report records their exact agreement counts.

The default comparison deliberately excludes `mtt_higher_targets.csv`, `mtt_lower_targets.csv`, the orphaned `motive_highexp_PHH.parquet`, and static `SI_tables/readme.txt`.

The validated committed-versus-regenerated comparison returned exit status 0.
All four metric row and key sets matched, and all 2,709 core ToxCast rows were bit-exact.
The six POD tables matched 198, 375, 127, 6,087, 472, and 3,029 keys respectively; bidirectional coverage was 85.1-90.0%, 88.4-96.9% of matched values were within 1%, and median relative differences ranged from `7.13e-8` to `2.50e-6`.
The fraction of matched PODs differing by more than 10% was 2.4-8.8%.
The hit-summary key sets matched, with 1,070 of 1,086 complete hit-call rows exact.
Both enrichment files retained all 8,858 target definitions and universe size 13,176 while the higher hit list changed from 304 to 292 and the lower list from 138 to 134.
FDR was exact for 6,962 of 8,858 higher-target rows and all 8,858 lower-target rows.

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

4. **Notebook paths**. The five non-`Plot_images` notebooks in `other_notebooks/`
   plus four cells in `2_1` and `2_2` used paths one directory level too shallow.

5. **polars API split**. See the table in `pixi.toml`. Handled by environment
   separation rather than by editing notebooks.

6. **Deterministic distance-table order** (`concresponse/compile_dist.py`).
   Polars `unique()` and `pivot()` emitted the same values in a different row order on each process.
   The R curve fitter sorts only by concentration, so replicates at the same concentration reached `nls` in that arbitrary order and changed convergence, selected models and POD pass calls.
   The compiler now preserves input order while deduplicating, orders distance columns, and sorts rows by the complete pivot key before writing Parquet.

7. **Endpoint-category comparison** (`3_2_1_compare_endpoint_types.ipynb`).
   Its "Redo after filtering by compound number" section also filtered `Metadata_Label` with `.str.contains("_AR")`, despite the notebook question and facet labels covering four endpoint categories.
   That reduced the Axiom-cytotoxicity, ToxCast-cytotoxicity, ToxCast-cell-based, and ToxCast-cell-free groups from 9/69/696/6 rows to 0/0/36/0; `groupby(observed=False)` then passed empty categorical groups to `mixedlm`.
   The unrelated label filter is removed, the notebook requires all four categories to be nonempty, and the models iterate observed groups only.

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

- **Hardware assumption.** `classifier/classify.py` used to hardcode
  `num_gpus = 4` and index `cp.cuda.Device(i % 4)`, which required a 4-GPU node.
  Worse, `process_label_and_agg` catches every exception and returns `None`, and
  the caller filters `None` out, so on a smaller node three quarters of the
  classifier tasks were dropped silently while snakemake still exited 0.
  It now takes the device count from `cp.cuda.runtime.getDeviceCount()` and keeps
  the worker count at 4, which is a no-op on a 4-GPU node and correct below that.
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

The tail is the finding.
Roughly one matched POD in ten diverges materially (maxima 10x to 70x), and
10-15% of rows appear in only one of the two runs.
`fastbmdR` fits eight model families (Exp2, Exp3, Exp4, Exp5, Hill, Power, Poly2, Lin) and then applies discrete model and pass/fail decisions.
For Cell Painting distances, `fit_curves.R` explicitly selects the model with the smallest residual SD (`filt.var = "SDres"`); the cell-count, MTT and LDH fits use `scoresPOD`'s default rounded AIC selection.
Small numerical differences can therefore change the selected model or a pass/fail gate and move the POD by an order of magnitude.

Summary: continuous quantities reproduce to numerical precision; the discrete
decisions layered on top of them are unstable to an environment change that
involved no code change. The most likely driver is the unpinned R stack -- R 4.6.1
with whatever `drc` and `fastbmdR` builds nixpkgs resolved, versus the authors'
2024-era R. Nothing in the repo ever pinned those.

This bears directly on the OASIS Phase I discovery question about which POD
methods are stable and interpretable.

### Root cause and fix for run-to-run nondeterminism

An independent clean run on the same host, same commit, same environment
(recorded separately) produced POD tables that differ from the ones above:

| table | run A new rows / matched | run B new rows / matched |
| --- | ---: | ---: |
| `cellpainting_cellprofiler` | 7161 / 6094 | 7150 / 6087 |
| `cellpainting_dino` | 3437 / 3031 | 3434 / 3029 |
| `cellpainting_cpcnn` | 535 / 473 | 535 / 472 |

The enrichment output drifts the same way: 6966 vs 6962 of 8858 `fdr` values
bit-identical to the committed file.

The divergence begins at `concresponse/compile_dist.py`, immediately before curve fitting.
The two runs' well profiles, `gmd.parquet`, and `cmd.parquet` were byte-identical.
Their compiled `distances.parquet` files were not byte-identical, but all 21,319 rows and all distance values aligned bit-exactly on the complete metadata key.
Only physical row order differed.

The cause was `dat.unique()` with Polars 0.20's default `maintain_order=False`, followed by a pivot with no final sort.
Two direct compilations in separate Python processes reproduced the problem: the output checksums differed even though a canonical comparison found no value difference.
`fit_curves.R` then sorts observations only by concentration, preserving that arbitrary order among tied replicates.
Nonlinear fits and likelihood-profile confidence intervals are numerically sensitive to observation order, so the ordering difference changes convergence and downstream model selection without changing the underlying data.

The parallel and RNG hypotheses are ruled out for this path.
The installed `fastbmdR::scoresPOD` calls both `PerformCurveFitting` and `PerformBMDCalc` with `ncpus = 1`, so its FORK branches are unreachable.
The nonlinear fits and `confint.nls` profile path contain no RNG; the Lin and Poly2 lack-of-fit helper does call `rnorm`, but resets the same hard-coded seed before every call.

The fix preserves order during deduplication, puts distance columns in a canonical order, and sorts rows by the complete metadata pivot key before writing `distances.parquet`.
Two post-fix compilations of the full CellProfiler inputs produced the same checksum (`31555961fbb75cdd114284513e6d2c10b78de1a084fa48cd54ca807626d614c5`).
The same two-process check produced byte-identical outputs for CPCNN and DINO.
A regression test also shuffles rows, distance-column discovery order, and exact duplicates, then requires byte-identical wide Parquets.

As a full serial check, three fresh R processes reached the same result.
The first two used a byte-identical canonical-row input with the pre-fix distance-column order (checksum `f8c5ff025e3276363cb4dd568add2b5ad141a8b23175669d02b1998cba6e6c87`) and took 1662 and 1663 seconds.
The third used the exact post-fix compiler output (checksum `31555961fbb75cdd114284513e6d2c10b78de1a084fa48cd54ca807626d614c5`) and took 1646 seconds.
All three wrote byte-identical 20,508-row `bmds.parquet` files with checksum `2cf2af783c4b0a0e3f3a02878b1f0d8fc381c0908705e39e3969b1f981473fb5`.
This validates consecutive serial determinism on canonical rows and a full fit from the exact current compiler output; the feature-column ordering difference between the two inputs did not affect the fitted result.
The canonical result has 7156 rows after `4_1`'s `all.pass & SDres < 3*SDctrl` filter, a stable new baseline between the two arbitrary pre-fix outcomes of 7161 and 7150.

A one-compound serial test demonstrates causality rather than correlation.
Two value-identical but differently ordered Oxyphenbutazone inputs changed 17 of 19 endpoint BMDs.
For Cytoplasm_Mito, Exp5 converged in one order (BMD 3.692345) but not the other, which selected Poly2 (BMD 2.362112).
Sorting both inputs by the complete metadata key made the inputs and resulting BMD objects byte-identical.

The historical ~0.2% POD row drift remains the compatibility tolerance for comparing pre-fix runs, but it is no longer expected between new runs made from the canonical distance table.
The classifier path remains unaffected: `AggType == "all"` was bit-exact in both historical runs.

This fix covers the observed morphology `bmds.parquet` path.
`fit_curves_meta.R` reads the profile Parquet directly and also uses only concentration as its explicit sort key.
Those profile inputs and the resulting cell-count, MTT and LDH curve Parquets were byte-identical across the two historical runs, so no meta-path drift was observed; a future change to profile row order would need the same tie-break guarantee at that boundary.

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

This is the same fragility as the version-drift result, measured independently and without changing any software: residual-SD model selection over eight families amplifies small input perturbations into large output changes.
It is not specific to R versions.

### Notebook execution

Run from clean, each in its assigned environment.

Pass (12): `1_2`, `1_2_1`, `2_1`, `3_1`, `3_2_0`, `3_2_1`, `3_2_2`,
`3_2_3`, `4_1`, `02_analyze_AR`, `03_analyze_ER`, `04_analyze_GR`.

Fixed to get there:

- `regression.py` corrupt metadata columns (see defect list) -- blocked `2_1`
  and `2_2`.
- `3_2_1` had two independent clean-kernel defects: two cells used `pn.options`
  without importing `plotnine as pn`, and its compound-count section
  accidentally retained only labels containing `_AR`.
  The latter contradicted the four-category question and facets; removing it
  restores all four endpoint types.
- `2_1` cell 4 pivots to columns named
  `Metadata_mtt_ridge_norm_Replicate_number_1`, and successfully selects them,
  but cell 5 refers to `Metadata_mtt_ridge_norm_1`. Those are two different
  polars pivot-naming conventions, so cells 4 and 5 cannot both succeed under
  any single polars version. Fixed by aliasing in cell 4.

After the fix, a clean pipeline-environment execution completed with code-cell execution counts 1-10 and no error outputs.
The mixed-effects section received 9/69/696/6 rows for Axiom cytotoxicity, ToxCast cytotoxicity, ToxCast cell-based, and ToxCast cell-free.
All four AUROC fits converged; the first three PRAUC fits converged, while the six-row ToxCast cell-free PRAUC fit reported `converged=False`.
The figures use the observed metrics and still render all four facets, but the cell-free PRAUC post-hoc result should not be interpreted as coming from a converged model.
Before and after hash manifests confirmed that `compiled_results/` and `SI_tables/` were unchanged.

Still failing, documented rather than patched:

- `2_2_outlier_enrichment_analysis`: cell 1 ends with
  `group_by(["Metadata_Perturbation", "Variable", "Metadata_Well",
  "Metadata_Plate"]).agg(...)`, which drops `Metadata_Compound`; later cells
  select `Metadata_Compound` from that same derived frame and raise
  `ColumnNotFoundError`. Recovering it means either re-joining or parsing it out
  of `Metadata_Perturbation`, and guessing wrong would put incorrect numbers
  into `mtt_higher_targets.csv` / `mtt_lower_targets.csv`, which are
  verification artifacts. Left unrepaired deliberately.
  A later dead cell also reads the deleted `refchemdb_oasis.parquet` and builds
  a `refchemdb` table that no subsequent cell consumes; every
  `overrepresentation_analysis` call uses `targets` from `cg_motive.parquet`.
  The input remains deleted because neither the in-scope reproduction nor any
  produced artifact uses it.
- `01_checkwelleffects`: `KeyError: 'Metadata_ldh_ridge_norm'` at the pivot in
  cell 13, although the column is float64 with 21426 non-null values in the
  source profile -- an earlier transform in the notebook drops it. Exploratory
  only; produces no verification artifact.

Neither remaining in-scope notebook runs top-to-bottom from a clean kernel.

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
