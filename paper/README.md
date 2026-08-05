# Paper reproduction guide

This directory turns the published paper into a searchable source and a small work queue for systematic reproduction.
The goal is scientific agreement at the level appropriate for each result.
Deviations are expected and are successful outcomes when they are measured, explained, and do not overturn the paper's conclusion.

## Sources of truth

`sources/main.pdf` is the canonical camera-ready paper.
`sources/supplemental-figures.pdf` and `sources/table-s1.xlsx` through `sources/table-s5.xlsx` are the published supplemental files.
`sources/manuscript-source.docx` is retained only because it provides cleaner semantic structure for the searchable transcription.
`paper.md` is the greppable working copy, and the PDF wins whenever the two differ.
Comments such as `<!-- source-page: 6 -->` connect major sections, figures, tables, and methods to the printed camera-ready pages used by `targets.tsv`.
Inline reference numbers in the author-manuscript scaffold can differ from final publisher numbering.
`figures/` contains compact JPEG navigation copies of all four main and four supplemental figures.
They make the paper usable in Markdown but are not pixel-level acceptance baselines.

Verify the immutable sources from the repository root:

```bash
cd paper/sources
sha256sum -c SHA256SUMS
```

The original 135 MB submission bundle contains draft manuscripts, administrative documents, and redundant figure sources.
It is deliberately excluded from Git because the compact published source set is sufficient for this workflow.

## Fresh-clone setup

Clone the repository and install the locked notebook environment:

```bash
git clone https://github.com/broadinstitute/2024_09_09_Axiom_OASIS.git
cd 2024_09_09_Axiom_OASIS
nix develop path:. --command pixi install -e notebooks --frozen
```

Enter `nix develop` before running the Pixi commands below.
Marimo 0.23.16 is pinned in the `notebooks` environment by `pixi.toml` and `pixi.lock`.

The optional project-local marimo skills used by Claude Code and Codex can be restored exactly from a fresh clone:

```bash
npx skills@1.5.20 add marimo-team/skills -s add-molab-badge -a claude-code -a codex -y
npx skills@1.5.20 add marimo-team/skills -s marimo-notebook -a claude-code -a codex -y
npx skills@1.5.20 add marimo-team/marimo-pair -s marimo-pair -a claude-code -a codex -y
```

`skills-lock.json` records their sources and content hashes.
The installer-owned copies under `.agents/skills/` and `.claude/skills/` are local generated state and are ignored by Git.

## Living results notebook

[![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/broadinstitute/2024_09_09_Axiom_OASIS/blob/main/paper/living_results.py)

`living_results.py` is the short, reactive Results paper.
It reads the tracked audit in `reproduction/report.json` and publication metadata in `sources/manifest.toml`; it does not discover candidate outputs under `runs/` or launch the GPU workflow.
Molab renders the committed snapshot at `__marimo__/session/living_results.py.json`.
The contract test binds that snapshot to the current notebook, report, source manifest, and three rendered SVG inputs so stale preview output fails validation.

Edit the source notebook with a loopback-only marimo session:

```bash
pixi run -e notebooks marimo edit paper/living_results.py --no-token
```

Run the read-only app, check the notebook, or export a code-free standalone HTML file:

```bash
pixi run -e notebooks marimo run paper/living_results.py --host 127.0.0.1
pixi run -e notebooks marimo check paper/living_results.py
pixi run -e notebooks marimo export html --no-include-code --force paper/living_results.py -o /tmp/oasis-living-results.html
```

The `/tmp` export is deliberately disposable so it cannot make the committed reproduction report appear stale.
After changing the target ledger or tracked evidence, refresh the machine-readable audit first, then reopen or rerun the living notebook:

```bash
uv run paper/reproduce.py
pixi run -e notebooks marimo check paper/living_results.py
pixi run -e notebooks marimo export session paper/living_results.py --force-overwrite
```

`uv run paper/reproduce.py` is the canonical tracked-report refresh because its PEP 723 environment and lock belong to the report producer.
Existing values, statuses, limitations, and target tables update automatically when that report changes.
To promote a newly checked result into the short narrative, add its target ID to `RESULT_SECTION_TARGETS` in `living_results.py`; the contract tests reject blocked, documentary-only, and out-of-scope mappings.
Use `uv run paper/reproduce_all.py` only for the separate, multi-hour upstream GPU reproduction described below.

## Run the executable paper

Run the tracked-data reproduction from the repository root:

```bash
uv run paper/reproduce.py
```

The command evaluates or accounts for every row in `targets.tsv` using only committed inputs.
It writes a deterministic Markdown report, a machine-readable JSON report, summary tables, and simplified SVG figures under `paper/reproduction/`.
The standalone Python environment is pinned by `reproduce.py.lock`.
The canonical outputs are committed, and the test suite fails if they no longer match a fresh render.
Use `uv run paper/reproduce.py --list` to list target IDs.
For a focused scratch report, repeat `--target ID` as needed and set `--output`, for example `uv run paper/reproduce.py --target FILTER-002 --output /tmp/oasis-filter-002`.

Each target keeps four ideas separate: the historical ledger status, this run's execution outcome, the available evidence strength, and the target-specific acceptance class.
An execution outcome of `checked` means that the declared tracked-input checks passed; it does not claim that upstream workflows or the full acceptance target were regenerated.
A reported blocker or out-of-scope target is a complete accounting result, not a reproduced result.
The command fails if the explicit recipe registry no longer covers the ledger exactly or if a declared check contradicts the tracked evidence.

This is the small, repository-only entry point for reviewing the whole paper.
The longer GPU workflow in `REPRODUCING.md` remains the manual path for regenerating upstream compiled artifacts from downloaded raw inputs.

## Run the supported upstream reproduction

The end-to-end runner turns that manual workflow into one resumable command:

```bash
uv run paper/reproduce_all.py
```

It creates a new ignored directory under `paper/runs/`, archives the current commit into an isolated workspace, verifies or downloads the five Zenodo inputs, installs both locked environments, and is wired to run three core configurations plus the full filtered CellProfiler configuration and nine targeted current sensitivity configurations.
A completed run renders Figure S1 from its five public TIFFs, executes all 17 currently runnable analysis notebooks, applies the semantic compiled-results gates, runs the tracked 53-target audit on a separate pristine snapshot, and exports the executed notebooks to greppable Markdown.
The canonical checkout and its published artifacts are never compute targets.
The first complete 13-configuration, 17-notebook GPU invocation remains pending; the core notebooks, repaired MTT layer, semantic verifier, and Figure S1 path have been exercised independently.

Review the exact commands before spending several GPU-hours:

```bash
uv run paper/reproduce_all.py --dry-run
```

Every stage writes a durable status and log to `manifest.json` in the run directory.
Resume an interrupted run by passing its directory explicitly:

```bash
uv run paper/reproduce_all.py --resume --run-dir paper/runs/RUN_NAME
```

Resume is deliberately bound to the exact commit and unchanged `paper/reproduce_all.py` recorded by the run manifest.
If the checkout has advanced, use a separate checkout at the recorded `repository.head` and pass the existing run directory explicitly.

The generated-candidate verdict is `artifacts/semantic-verification.json`.
`artifacts/tracked-audit/` is a separate source-integrity and target-accounting report; it is not used to reject acceptable regenerated POD drift.
`artifacts/notebooks/index.md` links the executed code, tables, and extracted plot assets.

A completed invocation regenerates the supported core analysis, all current transformation comparisons, and Figure S1, including the formerly broken MT/LDH enrichment, well-effect, and extended comparison notebooks.
The core candidate is judged by the numerical verifier.
The filtered, `_log10`, `_int`, and `_ap` outputs are current sensitivity layers and are inventoried without being mistaken for recovered historical substrates.
It still does not rebuild pixel-identical publisher-layout composites, resolve the historical Figure 2C significance substrate, or recover the manuscript-era enrichment substrate.
Those remaining boundaries stay explicit in the run manifest rather than being filled with tracked outputs.
The tracked notebook files retain historical embedded outputs; the current outputs are the Markdown and assets exported from an isolated completed run.

## Agent workflow

1. Read this file, the relevant section of `paper.md`, and the existing top-level `REPRODUCING.md`.
2. Select one `pending` row from `targets.tsv`, or audit a completed row and its evidence when no pending rows remain.
3. Reuse existing outputs and prior verification evidence before launching expensive workflows.
4. Identify the smallest notebook, script, table, or verifier that can test the target.
5. Compare the result using the acceptance rule written in that row.
6. Put concise evidence in `evidence/` or link an existing repository artifact.
7. Change the status to `reproduced`, `reproduced-with-deviation`, `blocked`, or `out-of-scope`.
8. Record deviations plainly, including magnitude, likely cause, and whether the paper's conclusion still holds.

Work on one logical target or tightly related target group at a time.
Do not rerun the full pipeline when committed artifacts or the existing semantic verifier already answer the question.
Do not widen an acceptance criterion only to make a result pass.

## Acceptance classes

- `exact`: Use for stable schemas, semantic keys, fixed counts, categories, and deterministic values.
- `close`: Use when numerical drift is expected and a target-specific tolerance or comparison summary is more meaningful than byte identity.
- `qualitative`: Use when the relevant result is a direction, ranking, conclusion, or visible pattern.
- `trace-only`: Use for background facts, interpretations, hypotheses, and external claims that are not computational reproduction targets.

`reproduced-with-deviation` is a normal successful status.
It means the result differs from the published value or artifact but satisfies the stated acceptance rule and preserves the scientific conclusion.

## Target inventory

`targets.tsv` has one line per meaningful result, figure panel or panel group, table, or methods contract.
It intentionally does not duplicate every spreadsheet cell or every sentence in the paper.

The columns are:

- `id`: Stable identifier used in evidence and discussions.
- `source`: Published location in the main paper or supplement.
- `kind`: Claim, figure, table, method, or resource.
- `description`: What is being reproduced.
- `expected`: The published result at useful resolution.
- `acceptance`: `exact`, `close`, `qualitative`, or `trace-only`, followed by the target-specific rule.
- `producer`: Likely code or artifact to start from; `unknown` is allowed.
- `evidence`: Existing or future evidence path.
- `status`: Current workflow state.
- `deviation`: Short description of any difference from publication.

Tab characters delimit fields.
Keep each target on one physical line so standard tools such as `rg`, `cut`, and spreadsheet software can inspect the queue.

Examples:

```bash
rg $'\tpending\t' paper/targets.tsv
rg '^FIG-3' paper/targets.tsv
```

## Existing reproduction baseline

The top-level `REPRODUCING.md` and `verification/compiled_results.py` already provide substantial evidence.
They establish exact classifier key and row contracts, bit-exact core ToxCast metrics, close POD agreement with expected model-selection drift, and stable enrichment definitions with diagnostic hit-list and FDR deviations.
Use that evidence to resolve paper targets before repeating the multi-hour computation.
