# Reconstruct the Axiom OASIS JPEG XL image archive

This runbook reconstructs the Axiom OASIS JPEG XL v1 archive from a fresh checkout.
Run every command from the repository root.
The original Cell Painting Gallery TIFFs remain the source of truth.

Deterministic reconstruction succeeds when the pinned index produces the exact inventory and rejected-row artifacts, every inventory row has the exact ledger-bound source and output evidence recorded by the historical receipt, the final counts and byte totals match, and the deterministic validation report matches.
Host, timestamps, attempts, retry history, service history, absolute paths, historical command spellings, mtimes, and other execution details are context only.
They do not need to match the 2026-08-05 run.

The `jpegxl-d1-e5` tier is lossy JPEG XL at distance 1.0 and effort 5.
No channel stacking, normalization, intensity transformation, cropping, resizing, or biological recalibration is performed.
Biological equivalence to the source TIFFs has not been established for this dataset.
Use the TIFFs for measurements and scientific results, and use this derivative only for browsing, visualization, and retrieval.
Issue [#44](https://github.com/broadinstitute/2024_09_09_Axiom_OASIS/issues/44) records the available measurements and the particular Brightfield concern.

## 1. Start from a clean checkout and enter the pinned environment

Confirm that this is the repository root and that the reconstruction inputs are tracked and unmodified:

```bash
test -f image_archive/axiom/source.toml
test -f image_archive/records/run-receipt-2026-08-05.toml
git diff --exit-code -- \
  image_archive/axiom/source.toml \
  image_archive/records/run-receipt-2026-08-05.toml \
  pixi.lock \
  flake.lock
```

Approve the repository environment once, install the locked `images` environment without updating the lockfile, and enter it through `direnv` for every command:

```bash
direnv allow
direnv exec . pixi install --locked -e images
direnv exec . pixi run -e images python --version
git diff --exit-code -- pixi.lock flake.lock
```

The environment remains named `images` because renaming it would rewrite `pixi.lock`.
Do not update dependencies or regenerate either lockfile during reconstruction.

## 2. Verify the tracked contract, lockfiles, and immutable receipt

Verify the exact bytes in the current checkout:

```bash
sha256sum --check <<'EOF'
a85639eb25908bdf900a67daeba8fc8a755db4c03841d21aff3fed9609d197dd  image_archive/axiom/source.toml
d4af5e083b90a50a2a891ad1a068cd54510f6da274801388fd81bb1cffba4e99  image_archive/records/run-receipt-2026-08-05.toml
55665368f14dc6e2b82b5b06bc5b6495abad863ff40fff10f93bea34235fe900  pixi.lock
8628426df569bbe3fb2b8367fbb411fb4cd4c04f023b1afeeb2cba094b7f8c30  flake.lock
EOF
```

The immutable historical receipt records `pixi_lock_sha256 = f1412dfb...`, which was the whole-repository lockfile at the original archive run.
Later tracked paper-environment work changed the whole lockfile to the current hash above without changing the pinned `images` package versions recorded in the receipt.
The receipt comparison therefore treats lockfile hashes and runtime versions as historical context; it does not require a current whole-repository lockfile to reproduce an earlier unrelated environment graph.
The contract and receipt hashes themselves must remain exact.

The contract pins Zenodo record 17067683, `index.parquet` SHA-256 `f83a16fa...`, the public S3 namespace, all inventory counts and mappings, the one-TIFF-to-one-JXL destination rule, and the JUMP_lite codec provenance.
The inventory command rehashes the downloaded index before accepting it.

## 3. Run the focused tests and inspect the CLI

Run the complete focused archive test suite and both help surfaces before touching external storage:

```bash
direnv exec . pixi run -e images python -m unittest discover -s image_archive/tests
direnv exec . pixi run -e images python -m image_archive --help
direnv exec . pixi run -e images python -m image_archive verify-receipt --help
```

The workflow engine consists of `inventory`, `archive`, `status`, and `validate`.
`verify-receipt` is a final read-only comparison and never substitutes for any of those four commands.

## 4. Provision and register the external destination

The contracted destination is:

```text
/work/datasets/cpg0037-oasis/axiom/images-jxl/v1
```

First verify that `/work/datasets` is available from a non-root mounted filesystem:

```bash
archive_root=/work/datasets/cpg0037-oasis/axiom/images-jxl/v1
test -d /work/datasets
test "$(direnv exec . findmnt -nro TARGET -T /work/datasets)" != "/"
direnv exec . findmnt -T /work/datasets
```

Create the exact destination with the operator's registered storage group, then verify writability and path resolution:

```bash
archive_root=/work/datasets/cpg0037-oasis/axiom/images-jxl/v1
archive_group=$(id -gn)
sudo install -d -o "$(id -un)" -g "$archive_group" -m 2770 "$archive_root"
test -d "$archive_root"
test -w "$archive_root"
direnv exec . namei -l "$archive_root"
```

Register this exact root in `/work/datasets/REGISTRY.yaml` using the schema and ownership fields of the adjacent `cpg0037-oasis` entry:

```bash
sudoedit /work/datasets/REGISTRY.yaml
rg -n 'cpg0037-oasis|axiom/images-jxl/v1' /work/datasets/REGISTRY.yaml
```

Stop if the mount, group, registry entry, or exact path is wrong.
The CLI also rejects a missing destination, a root-filesystem destination, a non-writable destination, or any symlinked path component.
Generated state belongs under `$archive_root/_archive`, generated objects under `$archive_root/jpegxl-d1-e5`, and the destination-scoped coordination file is `$archive_root/.oasis-images.lock`.

## 5. Build and review the remote inventory

Run the metadata-only preflight before transferring any TIFF pixels:

```bash
direnv exec . pixi run -e images python -m image_archive inventory \
  --contract image_archive/axiom/source.toml \
  --remote-snapshot
```

This verifies the pinned index bytes and exact six-column Axiom schema, requires 2,019,342 index rows, plans 2,017,182 complete unique TIFFs, preserves 2,160 incomplete rows as explicit rejections, and reconciles every indexed object against the four public S3 batch prefixes.
It records prefix extras separately and never adds them to the pinned scope.
It does not download TIFF pixels or write JPEG XL objects.

Review the generated summary and exact artifacts:

```bash
archive_work=/work/datasets/cpg0037-oasis/axiom/images-jxl/v1/_archive
direnv exec . pixi run -e images python -m json.tool "$archive_work/summary.json"
sha256sum --check <<'EOF'
b8c20a37213831b55161a8ed9fe0a1c60522c8951f2b5e19713c7105c8200381  /work/datasets/cpg0037-oasis/axiom/images-jxl/v1/_archive/inventory.parquet
0bd61c7b852530c8d3ec491f2a99bab2f4cf15bbf1b015389c571ca7c768a66a  /work/datasets/cpg0037-oasis/axiom/images-jxl/v1/_archive/rejected.parquet
EOF
```

Do not start conversion unless `indexed_missing_count` is zero, `indexed_present_count` is 2,017,182, `indexed_present_bytes` is 17,825,492,086,890, the inventory and rejected counts are exact, and both hashes pass.

## 6. Start or resume conversion with the direct CLI

The direct CLI is the primary launch path:

```bash
direnv exec . pixi run -e images python -m image_archive archive \
  --contract image_archive/axiom/source.toml \
  --workers 64 \
  --max-in-flight 128 \
  --max-attempts 5 \
  --max-consecutive-failures 32
```

Each selected TIFF is checked against its remote size, ETag, and version ID when available, decoded as one 2D uint16 plane, encoded by a single-threaded codec worker, decoded at the same shape and dtype, and promoted through an atomic sibling write.
The schema-v4 SQLite ledger binds the exact manifest and stores source and output hashes and byte counts.
The circuit breaker stops new scheduling after 32 consecutive failed conversion attempts so that a systemic failure does not sweep the inventory.

An interruption is safe.
Rerun the exact same command to recover `running` rows to `pending` and resume from the durable ledger.
Normal resume trusts only exact manifest binding and prior `verified` ledger evidence; it does not treat file existence as completion.
Use `archive --audit-verified` only when an expensive full hash/decode scan before resume is specifically warranted.
After correcting a terminal error, raise the cumulative ceiling, for example to `--max-attempts 10`, instead of editing or deleting ledger rows.

## 7. Optionally use the tracked systemd service

This is an optional Spirit-specific wrapper around the same `archive` command and the same 64-worker, 128-in-flight profile.
Choose either the direct CLI in step 6 or the service for a given run; the destination lock prevents both from mutating the archive together.
The unit assumes the canonical checkout at `/work/users/shsingh/GitHub/oasis/2024_09_09_Axiom_OASIS` and `/work/datasets` as a mount point.

```bash
mkdir -p ~/.config/systemd/user
ln -sfn \
  /work/users/shsingh/GitHub/oasis/2024_09_09_Axiom_OASIS/image_archive/deploy/oasis-axiom-jpegxl.service \
  ~/.config/systemd/user/oasis-axiom-jpegxl.service
systemctl --user daemon-reload
systemctl --user enable --now oasis-axiom-jpegxl.service
```

User lingering must already be enabled for the service to survive SSH logout.
The service lowers CPU and I/O priority and stops for inspection after an ordinary terminal failure.
It performs conversion only; it never runs final validation or receipt verification.

## 8. Monitor and resume without changing evidence

`status` reads durable ledger progress and does not hash or decode outputs:

```bash
direnv exec . pixi run -e images python -m image_archive status \
  --contract image_archive/axiom/source.toml
```

For the optional service, monitor its wrapper separately:

```bash
systemctl --user status oasis-axiom-jpegxl.service
journalctl --user -fu oasis-axiom-jpegxl.service
```

If the service is active, stop it and wait for lock release before using the direct CLI:

```bash
systemctl --user stop oasis-axiom-jpegxl.service
systemctl --user is-active oasis-axiom-jpegxl.service
```

Conversion is ledger-complete only when `verified` is 2,017,182, `pending`, `running`, `error`, and `unresolved` are zero, the manifest binding matches, and `ledger_complete` is true.
This is not yet full archive validation.

## 9. Run the separate full validation gate

After conversion has stopped and released the destination lock, hash and decode every verified output:

```bash
direnv exec . pixi run -e images python -m image_archive validate \
  --contract image_archive/axiom/source.toml \
  --workers 64 \
  --max-attempts 5
```

This is the expensive whole-archive validator.
It checks output byte identity against the ledger, JPEG XL decoding, shape and dtype, inventory and rejected-row counts, manifest binding, and final completeness.
Any invalid or unresolved object produces a nonzero exit status.
The required result is `complete: true`, `audit_passed: true`, `checked: 2017182`, `invalid: 0`, and no failures or unresolved rows.
The deterministic report is written to `_archive/validation.json`.

## 10. Compare reconstructed evidence with the historical receipt

Run the focused comparison only after full validation:

```bash
direnv exec . pixi run -e images python -m image_archive verify-receipt \
  --contract image_archive/axiom/source.toml \
  --receipt image_archive/records/run-receipt-2026-08-05.toml
```

`verify-receipt` first checks the receipt schema, receipt ID, contract byte hash, and pinned index identity.
It then acquires the existing destination lock in shared nonblocking mode and refuses to run while `inventory`, `archive`, or `validate` holds the exclusive lock.
It hashes the inventory, rejected rows, and validation report; checks Parquet row counts; recomputes the manifest identity; opens SQLite with `mode=ro`, `immutable=1`, and `PRAGMA query_only`; checks schema, record count, exact manifest binding, final counts, and byte totals; and streams the receipt-defined canonical ledger evidence digest.
It does not create a directory or lock, recover or migrate a ledger, invoke another workflow, inspect or rewrite JPEG XL objects, or write a report.
All deterministic mismatches are printed together and the command exits nonzero.

The required output has `matches: true` and an empty `mismatches` list.
The expected deterministic evidence includes:

```text
manifest identity SHA-256: 24a0621ce8b5e88914e50fb4710515811b9f382450cad38d675dba001507b207
ledger evidence SHA-256:   bae3ad62b1940e9f97b964a9fc658ad0d8e13ba0d5e5d9fcb6ecedb7c0b2112a
source bytes:              17825492086890
output bytes:              323337920405
validation report SHA-256: 83ad5f170295039102fe619c6108c7f76c70eede2678baf1b391513b3e4cb457
```

The output also reports historical host, paths, attempt distribution, and timestamps as context.
Those fields may differ and never cause reconstruction failure.

## 11. Declare reconstruction complete

Reconstruction is complete only when all of the following are true:

1. The tracked contract and historical receipt retain their exact SHA-256 hashes.
2. The pinned index and remote inventory preflight pass with zero indexed objects missing.
3. `inventory.parquet` and `rejected.parquet` have the exact hashes and counts in the contract and receipt.
4. `status` reports 2,017,182 verified rows, zero unresolved rows, and an exact manifest binding.
5. The separate full validator reports `complete: true` and `audit_passed: true` for all 2,017,182 outputs and 2,160 rejected rows.
6. `verify-receipt` reports `matches: true` with no deterministic mismatch.
7. No claim is made that the lossy derivative is biologically equivalent to the source TIFFs.

Do not recompress an already verified archive merely to reproduce historical timestamps, attempts, host details, command paths, or service history.
