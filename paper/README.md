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

## Agent workflow

1. Read this file, the relevant section of `paper.md`, and the existing top-level `REPRODUCING.md`.
2. Select one `pending` row from `targets.tsv`.
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
