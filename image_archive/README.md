# Adapt the JPEG XL archive to another Cell Painting dataset

This is the agent-facing runbook for adapting the existing archive engine to one unfamiliar Cell Painting dataset.
Run every command from a clean isolated checkout and stop at the first failed assertion.
The only reusable handoff is a deterministic post-preflight `inventory.parquet`, pinned contract, rejected-row artifact, and `summary.json` remote-preflight result.
Source discovery and normalization remain direct dataset-specific code.
The archive, resume, status, validation, locking, atomic-write, circuit-breaker, and schema-v4 ledger paths remain unchanged.

The source TIFFs remain the source of truth.
The current `jpegxl-d1-e5` derivative is lossy JPEG XL at distance 1.0 and effort 5.
It is for browsing, visualization, and retrieval, and this workflow makes no claim of biological equivalence.

The exact completed Axiom reconstruction procedure is in [axiom/README.md](axiom/README.md).
Four surfaces are Axiom-only: the CLI `DEFAULT_CONTRACT`, the six-column `inventory` reference compiler, the optional systemd service, and `verify-receipt`.
Do not weaken or generalize `verify-receipt`; it is pinned to one historical Axiom receipt.

## Supported boundary and stop conditions

Proceed only when all of these statements are true:

- The source is public anonymous S3 under one exact bucket and prefix.
- Every selected source object ends in `.tif` or `.tiff`.
- Every selected TIFF decodes as exactly one two-dimensional uint16 plane.
- Each selected TIFF maps to exactly one `.jxl` object.
- The unchanged JPEG XL codec and settings are acceptable.
- No channel stacking, cropping, resizing, normalization, intensity transformation, biological recalibration, or other pixel transform is required.
- The existing contract can state the selected image count, rejected count, fixed channel cardinality, source scope, codec, and destination honestly.
- A reviewable authoritative index or explicit source-selection artifact exists.

Stop and request a separate design before any conversion if one statement is false.
Do not make a dataset fit by weakening validation or hiding ambiguity.
Do not add dependencies, frameworks, parser registries, adapter layers or protocols, base classes, Makefiles, workflow engines, generic services, receipt hierarchies, dataset templates, or speculative multi-dataset machinery.

## 1. Start from a clean isolated checkout

Begin in a clean repository root and create a dedicated worktree and branch for this one adaptation.
Choose a short stable dataset slug before running these commands:

```bash
set -euo pipefail
test -f image_archive/axiom/source.toml
test -z "$(git status --porcelain)"
dataset_slug=replace_with_dataset_slug
test "$dataset_slug" != replace_with_dataset_slug
worktree_parent=/work/users/"$(id -un)"/worktrees
install -d -m 0770 "$worktree_parent"
worktree="$worktree_parent/2024_09_09_Axiom_OASIS-image-archive-$dataset_slug"
test ! -e "$worktree"
git worktree add "$worktree" -b "codex/image-archive-$dataset_slug" HEAD
cd "$worktree"
test -z "$(git status --porcelain)"
```

Approve the repository environment once in the isolated checkout and use `direnv` for every Python command:

```bash
direnv allow
direnv exec . pixi install --locked -e images
direnv exec . pixi run -e images python --version
git diff --exit-code -- pixi.lock flake.lock
```

Do not update dependencies or regenerate either lockfile.
Create an external qualification directory under the normal `/work/users` policy and start a terminal transcript before source discovery:

```bash
export dataset_slug
export qualification_root=/work/users/"$(id -un)"/image-archive-qualification/"$dataset_slug"
install -d -m 0770 "$qualification_root"
command -v script
script -q -e -f "$qualification_root/terminal.typescript"
```

Continue the remaining steps inside that recorded shell and run `set -euo pipefail` there.
The raw transcript is execution evidence.
Do not reconstruct commands from shell history after the run.

## 2. Discover and define the source without changing it

Keep discovery read-only.
Inspect upstream documentation, the authoritative index, anonymous S3 listings, and representative TIFF headers without writing to the source or destination.
Do not start by editing the Axiom parser.

Record these facts in a small dataset-specific README and in an ambiguity log:

- The authoritative index URL, upstream record or version, filename, byte size, upstream MD5 when supplied, and locally computed SHA-256.
- Why that index or selection artifact is authoritative for the intended source scope.
- The exact S3 bucket, prefix, and any narrower selected subpaths.
- What one physical row in the raw index represents.
- What one normalized image row represents.
- Every expansion, selection, exclusion, channel mapping, filename rule, and destination mapping.
- Raw index rows, normalized image rows, rejected rows, fields, plates, channels, selected bytes, and prefix extras as separate counts.
- Every unresolved or judgment-dependent source ambiguity and its resolution.

The raw index grain and normalized image-row grain are often different.
For example, one raw row may describe a field while several columns or URLs expand to one normalized row per channel image.
The contract's `row_count`, `complete_unique_tiff_uris`, and `incomplete_rows` describe the normalized image-row input to this engine, not an unrelated physical-row count from upstream.
Preserve the raw count separately rather than forcing the two grains to agree.

Verify the local authoritative index bytes before parsing:

```bash
index_path=replace_with_local_authoritative_index_path
test -f "$index_path"
stat -c '%s %n' "$index_path"
md5sum "$index_path"
sha256sum "$index_path"
```

MD5 is only an upstream identity check when the source publishes it.
SHA-256 is the local frozen identity.

## 3. Resolve current storage policy and the destination contract

The absolute destination root is contract-bound, so resolve it before writing `source.toml`, bootstrapping artifacts, or freezing the implementation SHA.
Storage ownership is site- and dataset-specific.
Do not copy Axiom's group or invent one universal archive group.

Before server administration, resolve a reviewed host-appropriate checkout of `imaging-server-maintenance`.
On a `/work` server, use its verified server path rather than assuming a Mac home-directory layout.
Read its current `MAINTENANCE_LOG.md`, reconcile older runbook text against it, inspect `/work/datasets/REGISTRY.yaml`, and inspect the intended mount:

```bash
maintenance_root=replace_with_reviewed_host_maintenance_checkout
test "$maintenance_root" != replace_with_reviewed_host_maintenance_checkout
test -f "$maintenance_root/MAINTENANCE_LOG.md"
sed -n '1,240p' "$maintenance_root/MAINTENANCE_LOG.md"
test -f /work/datasets/REGISTRY.yaml
sed -n '1,240p' /work/datasets/REGISTRY.yaml
direnv exec . findmnt -T /work/datasets
test "$(direnv exec . findmnt -nro TARGET -T /work/datasets)" != "/"
```

Resolve and record the exact destination, owner, group, and mode from current policy:

```bash
archive_root=replace_with_policy_approved_absolute_path
archive_owner=replace_with_policy_owner
archive_group=replace_with_policy_group
archive_mode=replace_with_policy_mode
test "$archive_root" != replace_with_policy_approved_absolute_path
test "$archive_owner" != replace_with_policy_owner
test "$archive_group" != replace_with_policy_group
test "$archive_mode" != replace_with_policy_mode
```

Put that exact `archive_root` into the dataset contract created in step 5.
Record the required registry entry, but defer the registry edit and destination creation until the contract and implementation are reviewed and frozen.
Stop if the mount, registry placement, owner, group, mode, or exact path is unresolved.

## 4. Map normalized rows to the canonical manifest

The unchanged executor reads these identities from `inventory.parquet`:

| Column | Required meaning |
| --- | --- |
| `source_key` | Non-null unique S3 key under the contracted prefix, ending in `.tif` or `.tiff` |
| `source_uri` | Non-null unique exact `s3://<bucket>/<source_key>` identity |
| `destination_relative` | Non-null unique safe relative path ending in lowercase `.jxl` |
| `source_size` | Non-null positive integer from the frozen remote snapshot |
| `etag` | Non-null nonempty S3 ETag with surrounding quotes removed |
| `version_id` | Optional nonempty S3 version ID, or null when the listing does not provide one |

Use explicit column types and sort deterministically by `source_key` before writing Parquet.
Reject duplicate keys, duplicate URIs, destination collisions, unsafe paths, objects outside the contracted bucket or prefix, missing remote metadata, and URI-key disagreement.
The ledger independently enforces unique source keys, source URIs, and destination paths when it binds the manifest.

The manifest may carry narrowly useful audit columns, but the six identities above are the reusable seam.
For a new dataset, prefer those six columns unless an additional column is required to review the source-specific mapping.
Write `rejected.parquet` deterministically with a stable upstream identifier and an explicit reason for every rejected normalized row.

Anonymous S3 listings commonly omit version IDs.
Use null rather than an empty or invented value when no version ID is available.
In that case the evidence binds the observed key, size, ETag, pinned index, and the source SHA-256 captured during conversion, but it does not prove upstream version-pinned immutability.
State that limitation in the ambiguity log and run record.

## 5. Implement one direct dataset normalizer

In the isolated branch, add only the concrete files needed for the real dataset, normally a `source.toml`, one ordinary normalization script, and a short source README under `image_archive/<dataset_slug>/`.
Hard-code the reviewed source columns, URL expansion, channel mapping, path grammar, and selection rules in that script.
Do not add dataset-name branches to `image_archive/inventory.py` and do not call its Axiom-only `build_inventory` compiler.

The normalizer must use the existing locked environment and must:

1. Verify the exact index URL, size, MD5 when available, and SHA-256 before parsing.
2. Assert the raw schema and raw row grain before normalization.
3. Expand or select rows into one row per TIFF using the documented dataset rules.
4. Reconcile every selected key against one frozen anonymous S3 metadata snapshot.
5. Fail when any selected key is missing and report prefix extras separately without adding them to scope.
6. Assert all counts, field and channel cardinality, source identities, and destination uniqueness.
7. Atomically write `inventory.parquet`, `rejected.parquet`, `summary.json`, the remote snapshot, the zero-missing artifact, and the separate prefix-extra artifact.
8. Atomically replace any earlier successful `summary.json` with a non-authorizing result before a remote-snapshot rerun can fail or raise.
9. Refuse a nonempty contract pin mismatch.

The CLI preflight gate reads `summary.json` before both `archive` and `validate`.
It must contain a `remote_snapshot` object with integer `indexed_missing_count` equal to zero and integer `prefix_extra_count` greater than or equal to zero.
Keep the separate prefix-extra artifact even when that count is zero.
No failed rerun may leave an earlier zero-missing summary in place, because that stale summary could authorize `archive` or `validate` against mismatched artifacts.
Every retained dataset normalizer must have a focused regression equivalent to `test_missing_source_rerun_replaces_successful_preflight`: create a successful preflight, rerun after one selected remote object is missing, require the rerun to fail, require `require_remote_inventory` to refuse the work directory, and assert that the replacement summary records the failure.

Use no TIFF pixel downloads in this step.
Keep the implementation small enough that another agent can compare every rule with the upstream index and object layout.
If the existing TOML contract cannot describe the normalized rows truthfully, stop instead of expanding the shared contract model speculatively.

## 6. Bootstrap artifacts with empty pins

Set only these two artifact pins to empty strings for the first metadata-only run:

```toml
[inventory]
manifest_sha256 = ""
rejected_sha256 = ""
```

All source identities, counts, codec settings, and destination rules must already be concrete.
The empty pins are a bootstrap state, not permission to convert.
The unchanged archive CLI refuses to proceed without both nonempty artifact pins.

Run the dataset normalizer in a new qualification directory with the remote snapshot enabled:

```bash
bootstrap_work="$qualification_root/bootstrap"
test ! -e "$bootstrap_work"
install -d -m 0770 "$bootstrap_work"
direnv exec . pixi run -e images python \
  "image_archive/$dataset_slug/prepare_manifest.py" \
  --contract "image_archive/$dataset_slug/source.toml" \
  --work-dir "$bootstrap_work" \
  --remote-snapshot
```

Review the summary, both Parquet schemas, sample mappings, rejection reasons, and exact hashes:

```bash
direnv exec . pixi run -e images python -m json.tool "$bootstrap_work/summary.json"
sha256sum "$bootstrap_work/inventory.parquet" "$bootstrap_work/rejected.parquet"
```

Require `indexed_missing_count` to be zero.
Review every category and count of prefix extras separately.
Do not continue if an extra object was silently included, a selected object lacks metadata, or the raw and normalized grains are not both explicit.

## 7. Pin the artifacts and rerun from fresh state

Put the reviewed inventory and rejected-row SHA-256 values into the dataset contract.
Update its normalized counts from reviewed evidence, not from assumptions.
Then run the same normalizer in a second empty directory:

```bash
pinned_work="$qualification_root/pinned"
test ! -e "$pinned_work"
install -d -m 0770 "$pinned_work"
direnv exec . pixi run -e images python \
  "image_archive/$dataset_slug/prepare_manifest.py" \
  --contract "image_archive/$dataset_slug/source.toml" \
  --work-dir "$pinned_work" \
  --remote-snapshot
cmp --silent "$bootstrap_work/inventory.parquet" "$pinned_work/inventory.parquet"
cmp --silent "$bootstrap_work/rejected.parquet" "$pinned_work/rejected.parquet"
sha256sum "$pinned_work/inventory.parquet" "$pinned_work/rejected.parquet"
```

This second run must enforce the nonempty pins and produce the exact reviewed artifact bytes in fresh state.
If the source changed between runs, stop, investigate, and repeat qualification from the beginning with a new explicit source identity.

## 8. Test and freeze the exact implementation SHA

Run the focused checks before any conversion:

```bash
direnv exec . pixi run -e images python -m unittest discover -s image_archive/tests
direnv exec . pixi run -e images ruff check image_archive
direnv exec . pixi run -e images ruff format --check image_archive
direnv exec . pixi run -e images pyright \
  --pythonpath "$PWD/.pixi/envs/images/bin/python" image_archive
git diff --check
git diff --exit-code -- pixi.lock flake.lock
```

Commit the reviewed dataset contract, normalizer, source README, and tests on the isolated run branch.
Never launch conversion from uncommitted code.
Freeze the exact implementation SHA outside Git and prove the checkout is clean:

```bash
test -z "$(git status --porcelain)"
implementation_sha=$(git rev-parse HEAD)
git show --format=fuller --stat "$implementation_sha"
printf '%s\n' "$implementation_sha" > "$qualification_root/implementation-sha.txt"
```

Keep recording the exact commands and their output in the terminal transcript started in step 1.
Do not replace the raw transcript with a reconstructed command appendix.

## 9. Install the frozen preflight at the destination

Reconfirm that the checkout still has the frozen SHA and no changes.
Register the exact root according to current policy, then provision the already contracted root and assert its actual filesystem state:

```bash
test "$(git rev-parse HEAD)" = "$implementation_sha"
test -z "$(git status --porcelain)"
id -nG | tr ' ' '\n' | grep -Fx "$archive_group"
test ! -e "$archive_root"
sudo install -d -o "$archive_owner" -g "$archive_group" -m "$archive_mode" "$archive_root"
test -d "$archive_root"
test -w "$archive_root"
test "$(direnv exec . stat -c '%U:%G:%a' "$archive_root")" = \
  "$archive_owner:$archive_group:$archive_mode"
direnv exec . stat -c '%U:%G %a %n' "$archive_root"
direnv exec . namei -l "$archive_root"
first_destination_entry=$(direnv exec . find "$archive_root" -mindepth 1 -maxdepth 1 -print -quit)
test -z "$first_destination_entry"
archive_work="$archive_root/_archive"
test ! -e "$archive_work"
sudo install -d -o "$archive_owner" -g "$archive_group" -m "$archive_mode" "$archive_work"
```

Stop if the registry entry, path resolution, writability, owner, group, or mode assertion is wrong.
The root-absence assertion must run before `sudo install` or any archive CLI, and a pre-existing root is a stop even when it is empty.
The post-provision empty-root assertion detects unexpected entries before `_archive`, `.oasis-images.lock`, or an output object can be created.
Full validation is manifest-bound and does not enumerate or certify unrelated destination extras, so clean-room qualification requires the entire contracted root to start empty.

Run the exact pinned normalizer into the canonical work directory:

```bash
direnv exec . pixi run -e images python \
  "image_archive/$dataset_slug/prepare_manifest.py" \
  --contract "image_archive/$dataset_slug/source.toml" \
  --work-dir "$archive_work" \
  --remote-snapshot
cmp --silent "$pinned_work/inventory.parquet" "$archive_work/inventory.parquet"
cmp --silent "$pinned_work/rejected.parquet" "$archive_work/rejected.parquet"
direnv exec . pixi run -e images python -m json.tool "$archive_work/summary.json"
```

Require the frozen remote snapshot to report zero indexed objects missing.
Require prefix extras to remain a separate artifact and count, never part of the selected manifest.
Recheck both contract pins and normalized row counts before any TIFF transfer.

## 10. Qualify interruption, resume, status, and the completed no-op

Choose conservative worker limits for the first real run and record the reason for them.
Use the direct CLI because the tracked systemd service is Axiom-only:

```bash
workers=replace_with_reviewed_worker_count
max_in_flight=replace_with_reviewed_in_flight_count
set +e
direnv exec . pixi run -e images python -m image_archive archive \
  --contract "image_archive/$dataset_slug/source.toml" \
  --workers "$workers" \
  --max-in-flight "$max_in_flight" \
  --max-attempts 5 \
  --max-consecutive-failures 32
interrupted_status=$?
set -e
printf 'intentional interruption status: %s\n' "$interrupted_status"
test "$interrupted_status" -ne 0
```

For a new dataset, deliberately interrupt once after the ledger has verified a nonzero sample.
Record the interruption point in the live transcript.
The `set +e` exception applies only to this deliberate Ctrl-C because Pixi may return 1 or 130 for it.
Fail-fast mode is restored immediately, and the transcript plus ledger status must distinguish the expected interruption from a systemic failure.
Read status without writing a report:

```bash
direnv exec . pixi run -e images python -m image_archive status \
  --contract "image_archive/$dataset_slug/source.toml"
```

Rerun the exact archive command to recover `running` rows and resume from the schema-v4 ledger.
Do not edit or delete ledger rows.
The circuit breaker must remain enabled.
After completion, status must report the exact manifest binding, every selected row `verified`, and zero `pending`, `running`, `error`, and `unresolved` rows.

Run the exact archive command one more time against the completed destination and capture its JSON:

```bash
direnv exec . pixi run -e images python -m image_archive archive \
  --contract "image_archive/$dataset_slug/source.toml" \
  --workers "$workers" \
  --max-in-flight "$max_in_flight" \
  --max-attempts 5 \
  --max-consecutive-failures 32 \
  > "$qualification_root/completed-noop.json"
direnv exec . pixi run -e images python -m json.tool \
  "$qualification_root/completed-noop.json"
```

The completed invocation must select zero rows, recover zero running rows, and download or rewrite no output.
Run `status --write` once after completion to freeze `_archive/progress.json` as evidence.

```bash
direnv exec . pixi run -e images python -m image_archive status \
  --contract "image_archive/$dataset_slug/source.toml" \
  --write
```

## 11. Run full validation

After conversion has stopped and released the destination lock, hash and decode every verified output:

```bash
direnv exec . pixi run -e images python -m image_archive validate \
  --contract "image_archive/$dataset_slug/source.toml" \
  --workers "$workers" \
  --max-attempts 5
```

The required result is `complete: true`, `audit_passed: true`, the exact expected inventory count, `invalid: 0`, and zero unresolved rows.
The deterministic report is `_archive/validation.json`.
This is archive integrity evidence only.
It does not establish biological equivalence or scientific replacement of the source TIFFs.

## 12. Freeze one external evidence set

Stop all archive commands and confirm that no service or agent can mutate the destination.
Close the recorded shell before copying or hashing evidence:

```bash
exit
```

Wait until `script` returns to its parent shell so `terminal.typescript` is closed and flushed.
Do not run any evidence-copy or SHA-256 command from the still-recorded shell.
Restore fail-fast mode and the exact recorded paths in the parent shell:

```bash
set -euo pipefail
archive_root=replace_with_policy_approved_absolute_path
archive_work="$archive_root/_archive"
implementation_sha=$(cat "$qualification_root/implementation-sha.txt")
test -s "$qualification_root/terminal.typescript"
test "$(git rev-parse HEAD)" = "$implementation_sha"
test -z "$(git status --porcelain)"
```

Choose one policy-approved external run directory outside the checkout and object tree, and keep the evidence flat rather than creating a generic receipt system.
Include all of the following:

- The exact implementation SHA and clean-tree assertion.
- A tracked source archive generated from that exact clean implementation SHA, plus its commit metadata.
- The exact contract and authoritative index bytes.
- `inventory.parquet`, `rejected.parquet`, `summary.json`, and the frozen remote, zero-missing, and prefix-extra artifacts.
- The raw command transcript captured during execution.
- The ambiguity log, including source grain and version-ID limitations.
- A schema-v4 ledger snapshot with a missing or zero-byte WAL.
- `progress.json`, `validation.json`, and the completed no-op result.
- One plain run record containing counts, bytes, interruption and resume facts, codec settings, storage owner/group/mode, and final conclusions.
- One SHA-256 manifest over every evidence file.

Acquire the same destination lock while copying the ledger and refuse a live WAL:

```bash
evidence_dir=replace_with_policy_approved_external_run_directory
test "$evidence_dir" != replace_with_policy_approved_external_run_directory
test ! -e "$evidence_dir"
install -d -m 0770 "$evidence_dir"
cp "$qualification_root/terminal.typescript" "$evidence_dir/terminal.typescript"
cp "$qualification_root/implementation-sha.txt" "$evidence_dir/implementation-sha.txt"
git show --no-patch --format=fuller "$implementation_sha" \
  > "$evidence_dir/implementation-commit.txt"
git archive --format=tar.gz \
  --output="$evidence_dir/implementation-$implementation_sha.tar.gz" \
  "$implementation_sha" -- \
  .envrc README.md image_archive pixi.toml pyproject.toml pixi.lock flake.nix flake.lock
test -s "$evidence_dir/implementation-$implementation_sha.tar.gz"
test -f "$archive_root/.oasis-images.lock"
flock -n "$archive_root/.oasis-images.lock" \
  sh -eu -c '
    test ! -s "$1/state.sqlite3-wal"
    cp --reflink=auto "$1/state.sqlite3" "$2/state.sqlite3"
    test ! -s "$2/state.sqlite3-wal"
  ' sh "$archive_work" "$evidence_dir"
```

A nonempty WAL is a stop condition.
Do not certify or copy only the main SQLite file while committed frames remain in a WAL.
The source archive above is generated only after the recorded HEAD and clean-tree assertions pass.
It is an exact tracked snapshot from the frozen SHA and requires no push.
Do not substitute a working-tree patch, which can omit untracked files.

After copying the remaining listed artifacts, create and verify a standard manifest:

```bash
cd "$evidence_dir"
find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
sha256sum --check SHA256SUMS
```

Place the evidence directory under the site's current immutable or versioned retention policy and verify that retained copy.
A new dataset uses its plain run record and SHA-256 manifest.
Do not add it to `image_archive/records/` or change the Axiom-only `verify-receipt` command.

## 13. Completion criteria

The adaptation is complete only when the exact tracked implementation SHA produced a pinned deterministic manifest in fresh state, the final remote snapshot has zero selected objects missing, prefix extras remain separate, the interrupted run resumed safely, the completed rerun selected zero rows, full validation passed every object, the external ledger snapshot has no nonempty WAL, and the external SHA-256 manifest verifies.

Report any unavailable upstream version IDs as a limitation.
Preserve the original TIFFs as the scientific source of truth and make no biological-equivalence claim for the lossy derivative.
