# OASIS JPEG XL image archive

This workflow builds a storage derivative of the Axiom OASIS TIFF collection.
The original Cell Painting Gallery TIFFs remain the source of truth.

The tracked contract in `image_archive/axiom/source.toml` is the authoritative dataset description.
It pins the image index, expected inventory, source S3 namespace, codec settings, destination layout, batches, and channels without duplicating those values in Python.
Its channel-number mapping is DNA 1, ER 2, AGP 3, RNA 4, Mito 5, and Brightfield 6.
The only v1 codec is JPEG XL HQ with distance 1.0 and effort 5, identified as `jpegxl-d1-e5`.
Those settings reproduce the `jpegxl_lossy_hq` tier in JUMP_lite's [`compress_tif.py`](https://github.com/afermg/JUMP_lite/blob/5f0fc9be6135e74cfee0b3504fd20a35a9531a22/src/compress_tif.py), pinned at commit `5f0fc9be6135e74cfee0b3504fd20a35a9531a22` and source-file SHA-256 `9bb6bec0a23a8fb091c1e1990f62690c55b74e34d1a49165b21bbb1aabaa54bf`.
The reference leaves JPEG XL effort at its imagecodecs default, which is byte-identical to explicit effort 5 in the pinned images environment.
Each complete source TIFF becomes one standard `.jxl` object at:

```text
/work/datasets/cpg0037-oasis/axiom/images-jxl/v1/
  jpegxl-d1-e5/<batch>/images/<plate>/<stem>.jxl
```

The completed Spirit v1 run is frozen in `image_archive/axiom/run-receipt-2026-08-05.toml`.
That machine-readable receipt binds the exact source and manifest identities, codec runtime, two conversion phases, a deterministically specified ledger evidence digest and totals, and the external validation report without copying generated image data into Git.

No channel stacking, normalization, intensity transformation, cropping, resizing, or biological recalibration is performed.

## Known limitation: do not measure from this archive

`jpegxl-d1-e5` is a lossy tier, and no one has checked whether profiles computed from these `.jxl` objects match profiles computed from the source TIFFs for this dataset.
Use the Cell Painting Gallery TIFFs for anything that ends up in a result, and treat this archive as a storage derivative for browsing, visualization, and retrieval.

The tier is not unexamined: JUMP-lite, where these settings come from, evaluates it against a lossless reference on a large JUMP subset.
That was measured on JUMP, not on Axiom OASIS.
Brightfield is the weakest channel here by a wide margin, because transmitted light occupies a narrow intensity band that a perceptual codec has no way to know is load-bearing.

Measurements, the codec authors' own guidance on this failure mode, and what remains to be checked are in [issue #44](https://github.com/broadinstitute/2024_09_09_Axiom_OASIS/issues/44).

## Requirements

Run through the dedicated Pixi environment from the repository root.
Before any image transfer, provision and register the destination according to the host's storage policy.
The command-line interface requires the configured destination to exist, be writable, contain no symlinked path components, and reside on a non-root mounted filesystem.
User, group, registry, and exact-path policy remain in the runbook and service configuration rather than the reusable Python code.

## Reuse

The Python package in `image_archive/` is the dataset-agnostic tool; `image_archive/axiom/` is one worked instance of it.
For another dataset with the same six-column Axiom index schema, create a sibling directory such as `image_archive/<dataset>/`, copy `source.toml` into it, and change the index identity, S3 namespace, expected counts, batches, channels, codec settings, destination root, and object template.
Run `inventory` to build the canonical manifest, record its inventory and rejected-row SHA-256 values in the contract, and then run `archive`.
The conversion engine consumes only the canonical manifest columns and the contract, so image dimensions and dataset names are not compiled into the runtime.

## Workflow

Run the metadata-only preflight first:

```bash
direnv exec . pixi run -e images python -m image_archive inventory \
  --contract image_archive/axiom/source.toml \
  --remote-snapshot
```

The inventory command is the preflight: it verifies `image_archive/axiom/source.toml` and the pinned `index.parquet` artifact, checks the expected row, batch, plate, field, channel, complete-URI, and incomplete-row counts, and plans destination keys.
It paginates the four public S3 batch prefixes without downloading TIFF pixels and records size, ETag, last-modified time, storage class, and version ID where available.
Missing indexed objects fail the preflight.
Prefix-extra objects are preserved in a separate report and never added silently to the pinned-index scope.
The final enriched inventory and rejected-row artifact are SHA-256 pinned in `image_archive/axiom/source.toml`, and every generated preflight artifact is attested in the self-verifying summary.
It must not download any source TIFF or write any JPEG XL object.

After reviewing the preflight report and confirming storage registration, start or resume the archive explicitly:

```bash
direnv exec . pixi run -e images python -m image_archive archive \
  --contract image_archive/axiom/source.toml \
  --workers 64 \
  --max-in-flight 128 \
  --max-attempts 5 \
  --max-consecutive-failures 32
```

For an engineering smoke run, add `--limit 6`, then audit only the current verified subset with `validate --verified-only`.
The subset audit exits successfully when every currently verified object passes, while its `complete` field remains false until the full contracted archive is present.

Each selected TIFF is downloaded, checked against its pinned size, ETag, and version ID when available, decoded as one 2D uint16 plane, encoded, decoded again at the same shape and dtype, and promoted through an atomic sibling write.
The ledger stores full source and output SHA-256 evidence and retries failures up to five times in the same invocation.
The run stops scheduling new images after 32 consecutive failed conversion attempts, leaving untouched rows pending instead of repeating a systemic storage, codec, or network failure across the full inventory.
Normal resume verifies the exact manifest binding without rereading terabytes of prior outputs.
Use `archive --audit-verified` only when a full pre-resume hash/decode scan is warranted; it is intentionally expensive.
The inventory, archive, and validation workflows share one destination-scoped exclusive lock, so only one process can mutate the archive at a time.

After correcting the cause of a terminal error, resume with a cumulative attempt ceiling above the recorded count, for example `archive --max-attempts 10` after the default five attempts are exhausted.
Do not edit or delete ledger rows to force a retry.

After the smoke audit passes, install the tracked user service from the canonical repository checkout:

```bash
mkdir -p ~/.config/systemd/user
ln -sfn \
  /work/users/shsingh/GitHub/oasis/2024_09_09_Axiom_OASIS/image_archive/axiom/oasis-axiom-jpegxl.service \
  ~/.config/systemd/user/oasis-axiom-jpegxl.service
systemctl --user daemon-reload
systemctl --user enable --now oasis-axiom-jpegxl.service
```

The service needs user lingering enabled to survive SSH logout.
Monitor it with `systemctl --user status oasis-axiom-jpegxl.service` and `journalctl --user -fu oasis-axiom-jpegxl.service`.
It uses the completed Spirit run's setting of 64 single-threaded codec workers and at most 128 conversions in flight, lowers CPU and I/O scheduling priority, and stops for inspection after an ordinary terminal failure.

The conversion service stops after ledger completion and does not run the whole-archive validator.
After conversion has stopped and released the destination lock, inspect durable progress and run the final completeness gate separately:

```bash
direnv exec . pixi run -e images python -m image_archive status \
  --contract image_archive/axiom/source.toml
direnv exec . pixi run -e images python -m image_archive validate \
  --contract image_archive/axiom/source.toml \
  --workers 64 \
  --max-attempts 5
```

Conversion is complete only when all 2,017,182 complete unique TIFF URIs have verified JPEG XL objects and all 2,160 incomplete index rows remain explicitly accounted for.
The archive is fully validated only when the separate full `validate` command reports `complete: true` after hashing and decoding all 2,017,182 outputs.
An existing output is reusable only after successful decode plus source/destination identity checks.
Corrupt or partial outputs are replaced atomically and must never be accepted by an existence-only resume check.
Any unresolved transfer, encode, decode, contract, count, or completeness error produces a nonzero exit status and prevents a complete status.
`status` reports durable ledger progress and is not an on-disk completeness gate; only the full `validate` command hashes and decodes every verified JPEG XL object.
