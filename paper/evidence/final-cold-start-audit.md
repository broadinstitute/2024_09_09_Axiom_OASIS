# Final repository-only cold-start audit

This final audit covers draft PR #39 at signed starting commit `dc1f22ddec050c454775bacf18c2049780601a0c` on `codex/paper-reproduction-contract`.
The branch was clean, synchronized with `origin/codex/paper-reproduction-contract`, and zero commits ahead or behind before editing.
The audit used only repository content and local read-only tools.
It did not browse for evidence, download data, execute notebooks, rerun classifiers or concentration-response fitting, modify scientific artifacts, or access external services other than reading the existing PR and branch state.

## Tracked-only snapshot

The cold-start tree was created at `/tmp/oasis-pr39-cold.0rD39R` with:

```bash
snapshot_root=$(mktemp -d /tmp/oasis-pr39-cold.XXXXXX)
git archive --format=tar dc1f22ddec050c454775bacf18c2049780601a0c | tar -xf - -C "$snapshot_root"
```

The initial archive contained exactly the 165 files listed by `git ls-files` and no `.git`, ignored input data, ignored pipeline outputs, caches, or local environments.
The locked pipeline environment installed successfully from this archive with `nix develop path:. --command pixi install -e pipeline --frozen`.
Bare `nix develop` treated `/tmp` as the enclosing Git input and failed because the archive intentionally has no Git metadata, so the guide now uses the explicit `path:.` form.

## Snapshot validation

The following checks passed from the tracked-only snapshot:

- `paper/sources/SHA256SUMS` verified all eight published source files.
- Every manifest SHA-256 and byte count matched the corresponding source, and the manifest and checksum file named the same eight files.
- Standard-library ZIP CRC checks and `unzip -t` passed all five XLSX files and `manuscript-source.docx`.
- `main.pdf` is a readable 20-page camera-ready article, and `supplemental-figures.pdf` is a readable five-page supplement.
- `paper/paper.md` is ASCII, greppable, semantically line-broken, and connected to the camera-ready source by 27 page markers covering the main article, figures, and STAR Methods.
- The searchable paper contains all 34 resource entries from the camera-ready Key Resources Table after six category rows and ASCII transcription of publisher symbols.
- All eight figure links resolve to nonempty tracked JPEGs.
- All local Markdown and image links resolve, applicable Markdown anchors exist, and every ledger evidence path resolves.
- All tracked Markdown and `paper/targets.tsv` are ASCII-only, use LF endings, and contain no trailing whitespace.
- The target ledger has exactly ten columns, 53 unique nonempty IDs, valid kind, acceptance, and status vocabularies, one physical row per target, and concrete notes for every deviation, blocker, and out-of-scope decision.
- The ledger contains no pending row and has the expected inventory of 7 reproduced, 42 reproduced with deviation, 3 blocked, and 1 out of scope.
- The full 12-test `unittest` suite passed under the locked Nix and pixi environments.
- The compiled-results verifier returned exit status 0 and no gate failures when run against two temporary copies of the tracked compiled results.
- SHA-256 inventories before and after the verifier were identical, confirming that the verifier did not modify either input tree.

The verifier integrity exercise read 81 Axiom metric rows, 7,209 ToxCast cell-based rows, 1,431 cell-free rows, 918 cytotoxicity rows, all six POD CSVs, 1,086 hit-summary rows, and both 8,858-row enrichment tables.
It confirmed all 2,709 configured ToxCast `AggType == "all"` core rows exactly between the two copies.
Because the two inputs were copies of the same committed tree, this exercise validates tracked artifact readability, schema rules, and read-only behavior rather than claiming a new scientific regeneration.

The tracked figure JPEG SHA-256 values are:

- Figure 1: `0d6d5e63242fff53e2c85ea52e06eb7d70f0a7a8dfbdf0c2dafc1d1211435243`.
- Figure 2: `ad7040a8a95f8a4f1e4c907a38a1578efd7d8470d30a61ed0ac5780597cbe16f`.
- Figure 3: `9fd6c94bbfb3de513008e014ca3d9a45856d8038d1d274627eae599995b670d7`.
- Figure 4: `bf32c81c0b8bb4e75530a423114555f7d2829944a4dcde26cefec30008c2f995`.
- Figure S1: `8d06b306f781201580ddac11beefa3c91f957791267908d92dfa072b8ee63839`.
- Figure S2: `ce7b1efaeb4ed8f9fec3b0a2b338c967d48026b30ca120f7a157999c4a894d78`.
- Figure S3: `6073503207e9322f8926ba6e14731dc5e9865323720a27ba4fbcf86624f4da1d`.
- Figure S4: `2a6953179938e26d6dfea8e026adab72d0dc694047e527b17c36bd26629d4c4f`.

## Status audit

All seven `reproduced` rows have evidence appropriate to their acceptance rules.
`DESIGN-002`, `DESIGN-003`, and `FIG-1` record exact feature counts, assay and plate constants, and complete workflow-stage coverage.
`ACTIVITY-002` records the exact 429-compound direction-aware cytotoxic set across both current assay layers.
`FIG-2A` records the same four compounds, response directions, curve shapes, and POD locations at a maximum POD difference of 0.000514 uM.
`TABLE-KEY-RESOURCES` is directly traceable to the camera-ready PDF and the complete searchable table.
`METHOD-CLASSIFIER` traces the five compound-level stratified folds directly to `classify.py`.

The three blocked rows have concrete blockers that are stricter than ordinary drift.
`BIOACTIVITY-002` preserves the approximate ratios, but its required CellProfiler-DINO null conclusion changes between current CellProfiler configurations and the historical extended matrix is absent.
`ENRICH-001` has neither the reported 480-target count nor a repository pathway mapping for the named cell-cycle, PI3K-Akt, MAPK, and p53 signals.
`ENRICH-002` has the no-enrichment conclusion only in the 138 or 134 well groups, while the approximately 304-well scale belongs to the enriched code-labeled group.
No repository layer satisfies either enrichment target's full acceptance rule.

Representative reproduced-with-deviation rows were checked across every major contract class.
`DESIGN-001` confirms the designed library and exposure constants while explicitly separating them from post-QC plate attrition.
`ACTIVITY-001` and `ACTIVITY-003` preserve the camera-ready counts and dominant responses on the fixed CellProfiler substrate while identifying Table S2 drift and one order-sensitive DINO call.
`BIOACTIVITY-001`, `FIG-2B`, `FIG-2C`, `BIOACTIVITY-003`, and `FIG-2D` preserve ordering and qualitative distributions while recording layer-specific key, count, ratio, and p-value differences.
`TABLE-1`, `TABLE-2`, and `CLASSIFIER-001` record exact schemas and small numerical drift without hiding split-count or keyed-universe inconsistencies.
`TOXCAST-001`, `TOXCAST-002`, and `METHOD-TOXCAST` distinguish the 963-ID stored union from the 670-ID tested intersection, the 48 source categories from 38 supported binary endpoints, and the missing 100 uM implementation rule.
`FIG-3AB`, `FIG-3C`, `FIG-4A`, `FIG-4B`, and `SFIG-4` retain the assay ordering and practical conclusions while documenting modeled endpoint counts, statistical provenance, non-convergence, and POD-derived drift.
`TABLE-S1`, `TABLE-S2`, `TABLE-S3`, `TABLE-S4`, and `TABLE-S5` are connected to the publisher Office files by semantic keys and precisely bounded identifier, pass-call, or curation deviations.
`METHOD-POD`, `METHOD-REGRESSION`, and `METHOD-STATS` separate declared methods from executable behavior and unavailable initial conditions.
`RESOURCE-001` and `INTERPRETATION-001` preserve traceability while keeping external resources and biological hypotheses outside reproduced numerical claims.

No unsupported classification or broken evidence reference was found, so all 53 target rows and the PR inventory remain unchanged.

## Tracked and external boundaries

The cold-start tree includes the paper sources, searchable transcription, 12 substantive evidence notes, eight figure JPEGs, ten pinned annotation inputs, 17 compiled-result artifacts, notebooks, workflow code, verifier, and tests.
The producer paths in `targets.tsv` resolve from tracked state except `1_snakemake/inputs/metadata/metadata.parquet`, which is explicitly documented as a downloaded, ignored input for `DESIGN-001` and `TABLE-S1`.

The canonical checkout also contains five ignored compiled inputs and 99 ignored pipeline-output files that were absent from the snapshot and were not used to make cold-start validation pass.
The five ignored inputs are the three raw profile Parquets, processed metadata, and image index obtained from Zenodo record 17067683.
Raw TIFF images and the Figure S1 source image remain external to the Cell Painting Gallery, which is why `SFIG-1` remains out of scope.
Raw invitrodb v4.1 regeneration requires an external database and a documented non-functional download script, while the six derived ToxCast annotation Parquets are tracked.
The full pipeline also requires Nix dependencies, pixi packages, CUDA hardware, and several hours of computation.
DOI resolution and equivalence between the published GitHub owner URL and the current Broad origin require external state.

The source hashes, Office archives, ledger, evidence graph, figure navigation copies, compiled artifacts, verifier, and tests are usable from tracked state alone.
Scientific regeneration that crosses the documented input, hardware, or intentionally excluded notebook boundaries remains a declared external or blocked operation rather than a hidden prerequisite.

## Conclusion

The repository is usable as a cold-start paper contract and guides a new agent to every target, acceptance rule, evidence record, deviation, blocker, and external dependency without relying on ignored local state.
The final inventory is internally supported at 0 pending, 7 reproduced, 42 reproduced with deviation, 3 blocked, and 1 out of scope.
All PR phases have repository evidence and can be marked complete under the contract's explicit allowance for documented deviations, blocked targets, and out-of-scope resources.
