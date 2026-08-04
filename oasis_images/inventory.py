# Copyright (c) 2026 Broad Institute.
"""Build and validate the frozen OASIS source-image inventory."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from string import Formatter
from typing import TYPE_CHECKING, Any, Final, NoReturn, Protocol, cast
from urllib.request import Request, urlopen

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from .io import atomic_write_json
from .s3 import public_s3_client

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .contract import Contract

_COPY_CHUNK_BYTES = 1024 * 1024
_FILE_SHA256_SCOPE = "file_bytes"
_MAX_SITE_NUMBER = 99
_SUMMARY_SHA256_SCOPE = "canonical_json_without_summary_evidence_v1"
_INDEX_COLUMNS: Final = (
    "Metadata_Batch",
    "Metadata_Plate",
    "Metadata_Well",
    "Metadata_Site",
    "Channel",
    "Filename",
)
_FIELD_COLUMNS: Final = (
    "Metadata_Batch",
    "Metadata_Plate",
    "Metadata_Well",
    "Metadata_Site",
)
_INVENTORY_COLUMNS: Final = (
    "source_uri",
    "bucket",
    "source_key",
    "batch",
    "plate",
    "well",
    "site",
    "channel",
    "channel_number",
    "destination_relative",
)
_EXPECTED_INDEX_SCHEMA: Final = pl.Schema(
    {
        "Metadata_Batch": pl.String,
        "Metadata_Plate": pl.String,
        "Metadata_Well": pl.String,
        "Metadata_Site": pl.Float64,
        "Channel": pl.String,
        "Filename": pl.String,
    },
)
_REMOTE_ARROW_SCHEMA: Final = pa.schema(
    [
        pa.field("bucket", pa.string(), nullable=False),
        pa.field("key", pa.string(), nullable=False),
        pa.field("size", pa.int64(), nullable=False),
        pa.field("etag", pa.string(), nullable=False),
        pa.field("last_modified", pa.timestamp("us", tz="UTC")),
        pa.field("storage_class", pa.string()),
        pa.field("version_id", pa.string()),
    ],
)
_WELL_ROW_NUMBER: Final = {chr(ord("A") + offset): f"{offset + 1:02d}" for offset in range(16)}


class _Paginator(Protocol):
    """Structural type for the only paginator operation used here."""

    def paginate(self, **kwargs: str) -> Iterable[Mapping[str, object]]:
        """Yield list_objects_v2 response pages."""
        ...


class _S3Client(Protocol):
    """Structural type for the only S3 client operation used here."""

    def get_paginator(self, operation_name: str) -> _Paginator:
        """Return a paginator for ``operation_name``."""
        ...


class InventoryValidationError(RuntimeError):
    """Report a source, contract, inventory, or remote-snapshot mismatch."""


def _raise_validation(message: str) -> NoReturn:
    """Raise an inventory validation error with a contextual message."""
    raise InventoryValidationError(message)


@dataclass(frozen=True, slots=True)
class InventoryArtifacts:
    """Paths produced by one inventory build."""

    index_path: Path
    inventory_path: Path
    rejected_path: Path
    summary_path: Path
    remote_objects_path: Path | None = None
    indexed_missing_path: Path | None = None
    prefix_extra_path: Path | None = None


def _file_identity(path: Path) -> tuple[int, str, str]:
    """Return exact byte size, MD5, and SHA256 for a local file."""
    md5 = hashlib.md5()  # noqa: S324 - MD5 is a pinned artifact identity, not a security primitive.
    sha256 = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(_COPY_CHUNK_BYTES):
            size += len(chunk)
            md5.update(chunk)
            sha256.update(chunk)
    return size, md5.hexdigest(), sha256.hexdigest()


def _parquet_row_count(path: Path) -> int:
    """Return one Parquet artifact's metadata row count without loading its rows."""
    try:
        return pq.ParquetFile(path).metadata.num_rows
    except (OSError, pa.ArrowException) as error:
        message = f"cannot read Parquet metadata for {path}: {error}"
        raise InventoryValidationError(message) from error


def _artifact_evidence(path: Path) -> dict[str, object]:
    """Return deterministic byte and row evidence for one Parquet artifact."""
    size, _, sha256 = _file_identity(path)
    return {
        "row_count": _parquet_row_count(path),
        "sha256": sha256,
        "sha256_scope": _FILE_SHA256_SCOPE,
        "size_bytes": size,
    }


def _validate_index_file(contract: Contract, path: Path) -> None:
    """Require a local index to match every identity pinned by the contract."""
    actual_size, actual_md5, actual_sha256 = _file_identity(path)
    expected = contract.index
    mismatches: list[str] = []
    if actual_size != expected.size_bytes:
        mismatches.append(f"size={actual_size} expected={expected.size_bytes}")
    if actual_md5 != expected.md5:
        mismatches.append(f"md5={actual_md5} expected={expected.md5}")
    if actual_sha256 != expected.sha256:
        mismatches.append(f"sha256={actual_sha256} expected={expected.sha256}")
    if mismatches:
        details = "; ".join(mismatches)
        _raise_validation(f"index identity mismatch for {path}: {details}")


def ensure_index(contract: Contract, cache_dir: Path) -> Path:
    """Return a locally verified copy of the pinned index, downloading atomically."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / contract.index.filename
    if destination.is_file():
        try:
            _validate_index_file(contract, destination)
        except InventoryValidationError:
            pass
        else:
            return destination

    descriptor, temporary_name = tempfile.mkstemp(
        dir=cache_dir,
        prefix=f".{contract.index.filename}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        request = Request(contract.index.url, headers={"User-Agent": "oasis-images/1"})  # noqa: S310
        with os.fdopen(descriptor, "wb") as output, urlopen(request, timeout=120) as response:  # noqa: S310
            while chunk := response.read(_COPY_CHUNK_BYTES):
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        _validate_index_file(contract, temporary_path)
        temporary_path.chmod(0o660)
        temporary_path.replace(destination)
        _sync_directory(cache_dir)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return destination


def _sync_directory(path: Path) -> None:
    """Sync a directory after atomically replacing one of its children."""
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write_parquet(frame: pl.DataFrame, path: Path) -> None:
    """Write a deterministic Parquet artifact through a sibling temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        frame.write_parquet(
            temporary_path,
            compression="zstd",
            statistics=True,
        )
        with temporary_path.open("rb") as stream:
            os.fsync(stream.fileno())
        temporary_path.chmod(0o660)
        temporary_path.replace(path)
        _sync_directory(path.parent)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _canonical_summary_payload(summary: Mapping[str, object]) -> bytes:
    """Serialize summary content while excluding its self-evidence record."""
    raw_evidence = summary.get("artifact_evidence")
    if not isinstance(raw_evidence, dict):
        _raise_validation("summary lacks its artifact_evidence map")
    payload = dict(summary)
    payload["artifact_evidence"] = {name: value for name, value in raw_evidence.items() if name != "summary"}
    try:
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        message = f"summary cannot be canonicalized: {error}"
        raise InventoryValidationError(message) from error
    return canonical.encode()


def _serialized_summary_size(summary: Mapping[str, object]) -> int:
    """Return the exact byte size emitted by atomic_write_json."""
    try:
        payload = json.dumps(summary, indent=2, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as error:
        message = f"summary cannot be serialized: {error}"
        raise InventoryValidationError(message) from error
    return len(f"{payload}\n".encode())


def _strict_nonnegative_int(value: object, label: str) -> int:
    """Return a JSON integer while rejecting booleans and invalid counts."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _raise_validation(f"invalid {label}: {value!r}")
    return value


def _validate_evidence_record(
    raw: object,
    *,
    label: str,
    expected_scope: str,
    expected_rows: int | None,
) -> tuple[int, str]:
    """Validate one exact artifact-evidence record and return size and digest."""
    if not isinstance(raw, dict):
        _raise_validation(f"artifact evidence for {label!r} is not a dictionary")
    expected_fields = {"row_count", "sha256", "sha256_scope", "size_bytes"}
    if set(raw) != expected_fields:
        _raise_validation(
            f"artifact evidence fields for {label!r} mismatch: "
            f"observed={sorted(raw)!r}, expected={sorted(expected_fields)!r}",
        )
    if raw["sha256_scope"] != expected_scope:
        _raise_validation(
            f"artifact SHA-256 scope for {label!r} mismatch: "
            f"observed={raw['sha256_scope']!r}, expected={expected_scope!r}",
        )
    sha256 = raw["sha256"]
    if not isinstance(sha256, str) or re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
        _raise_validation(f"invalid artifact SHA-256 for {label!r}: {sha256!r}")
    size = _strict_nonnegative_int(raw["size_bytes"], f"artifact size for {label!r}")
    observed_rows = raw["row_count"]
    if expected_rows is None:
        rows_match = observed_rows is None
    else:
        rows_match = _strict_nonnegative_int(observed_rows, f"artifact row count for {label!r}") == expected_rows
    if not rows_match:
        _raise_validation(
            f"artifact row count for {label!r} mismatch: observed={observed_rows!r}, expected={expected_rows!r}",
        )
    return size, sha256


def _require_contract_artifact_pins(
    contract: Contract,
    evidence: Mapping[str, object],
    *,
    complete_remote_snapshot: bool,
) -> None:
    """Require generated manifest identities to match optional contract pins."""
    rejected_pin = contract.inventory.rejected_sha256
    rejected = evidence.get("rejected")
    if rejected_pin is not None and (not isinstance(rejected, dict) or rejected.get("sha256") != rejected_pin):
        _raise_validation(
            "rejected artifact SHA-256 differs from the contract pin: "
            f"observed={rejected.get('sha256') if isinstance(rejected, dict) else None!r}, "
            f"expected={rejected_pin!r}",
        )
    inventory_pin = contract.inventory.manifest_sha256
    inventory = evidence.get("inventory")
    if (
        complete_remote_snapshot
        and inventory_pin is not None
        and (not isinstance(inventory, dict) or inventory.get("sha256") != inventory_pin)
    ):
        _raise_validation(
            "inventory artifact SHA-256 differs from the contract pin: "
            f"observed={inventory.get('sha256') if isinstance(inventory, dict) else None!r}, "
            f"expected={inventory_pin!r}",
        )


def _write_summary_with_evidence(
    summary_path: Path,
    summary: dict[str, object],
    artifact_paths: Mapping[str, Path],
    contract: Contract,
) -> None:
    """Attest final artifacts and atomically write a self-verifying summary."""
    evidence = {name: _artifact_evidence(path) for name, path in sorted(artifact_paths.items())}
    remote = summary.get("remote_snapshot")
    complete_remote_snapshot = isinstance(remote, dict) and remote.get("indexed_missing_count") == 0
    _require_contract_artifact_pins(
        contract,
        evidence,
        complete_remote_snapshot=complete_remote_snapshot,
    )
    summary["artifact_evidence"] = evidence
    evidence["summary"] = {
        "row_count": None,
        "sha256": hashlib.sha256(_canonical_summary_payload(summary)).hexdigest(),
        "sha256_scope": _SUMMARY_SHA256_SCOPE,
        "size_bytes": 0,
    }
    summary_evidence = evidence["summary"]
    if not isinstance(summary_evidence, dict):
        _raise_validation("internal summary evidence is not a dictionary")
    for _ in range(4):
        size = _serialized_summary_size(summary)
        if summary_evidence["size_bytes"] == size:
            break
        summary_evidence["size_bytes"] = size
    else:
        _raise_validation("summary byte-size evidence did not converge")
    atomic_write_json(summary_path, summary)


def _verify_remote_reconciliation(summary: Mapping[str, object], inventory_rows: int) -> None:
    """Require remote totals and extra classifications to reconcile exactly."""
    raw_remote = summary.get("remote_snapshot")
    if not isinstance(raw_remote, dict):
        _raise_validation("summary lacks the required remote_snapshot dictionary")
    values = {
        name: _strict_nonnegative_int(raw_remote.get(name), f"remote_snapshot.{name}")
        for name in (
            "indexed_missing_count",
            "indexed_present_bytes",
            "indexed_present_count",
            "object_count",
            "other_extra_bytes",
            "other_extra_count",
            "plate_index_xml_bytes",
            "plate_index_xml_count",
            "prefix_extra_bytes",
            "prefix_extra_count",
            "total_bytes",
            "unindexed_tiff_bytes",
            "unindexed_tiff_count",
        )
    }
    if values["indexed_present_count"] + values["indexed_missing_count"] != inventory_rows:
        _raise_validation("remote indexed-present and indexed-missing counts do not reconcile")
    if values["indexed_present_count"] + values["prefix_extra_count"] != values["object_count"]:
        _raise_validation("remote indexed-present and prefix-extra counts do not reconcile")
    classified_count = values["other_extra_count"] + values["plate_index_xml_count"] + values["unindexed_tiff_count"]
    if classified_count != values["prefix_extra_count"]:
        _raise_validation("prefix-extra classification counts do not reconcile")
    classified_bytes = values["other_extra_bytes"] + values["plate_index_xml_bytes"] + values["unindexed_tiff_bytes"]
    if classified_bytes != values["prefix_extra_bytes"]:
        _raise_validation("prefix-extra classification bytes do not reconcile")
    if values["indexed_present_bytes"] + values["prefix_extra_bytes"] != values["total_bytes"]:
        _raise_validation("remote indexed-present and prefix-extra bytes do not reconcile")


def _require_unattested_summary_contract(
    summary_path: Path,
    summary: Mapping[str, object],
    contract: Contract,
) -> dict[str, Path]:
    """Validate frozen semantics and resolve an older summary's generated artifacts."""
    expected_index = {
        "filename": contract.index.filename,
        "md5": contract.index.md5,
        "sha256": contract.index.sha256,
        "size_bytes": contract.index.size_bytes,
    }
    if summary.get("index") != expected_index:
        _raise_validation("unattested summary index identity differs from the contract")
    expected_inventory = {
        "channel_count": contract.inventory.channel_count,
        "complete_unique_tiff_uris": contract.inventory.complete_unique_tiff_uris,
        "field_count": contract.inventory.field_count,
        "incomplete_rows": contract.inventory.incomplete_rows,
        "plate_count": contract.inventory.plate_count,
        "row_count": contract.inventory.row_count,
    }
    if summary.get("inventory") != expected_inventory:
        _raise_validation("unattested summary inventory counts differ from the contract")
    expected_source = {"bucket": contract.source.bucket, "prefix": contract.source.prefix}
    if summary.get("source") != expected_source:
        _raise_validation("unattested summary source identity differs from the contract")
    _verify_remote_reconciliation(summary, contract.inventory.complete_unique_tiff_uris)
    remote = summary["remote_snapshot"]
    if not isinstance(remote, dict) or remote.get("indexed_missing_count") != 0:
        _raise_validation("only a zero-missing remote snapshot can be attested for archive use")

    expected_names = {
        "index": contract.index.filename,
        "indexed_missing": "indexed_missing.parquet",
        "inventory": "inventory.parquet",
        "prefix_extra": "prefix_extra.parquet",
        "rejected": "rejected.parquet",
        "remote_objects": "remote_objects.parquet",
        "summary": summary_path.name,
    }
    if summary.get("artifacts") != expected_names:
        _raise_validation("unattested summary artifact names differ from the required layout")
    paths = {
        name: summary_path.parent / filename
        for name, filename in expected_names.items()
        if name not in {"index", "summary"}
    }
    absent = [str(path) for path in paths.values() if not path.is_file()]
    if absent:
        _raise_validation(f"unattested summary artifacts are absent: {absent!r}")
    expected_rows = {
        "indexed_missing": 0,
        "inventory": contract.inventory.complete_unique_tiff_uris,
        "prefix_extra": _strict_nonnegative_int(
            remote.get("prefix_extra_count"),
            "remote_snapshot.prefix_extra_count",
        ),
        "rejected": contract.inventory.incomplete_rows,
        "remote_objects": _strict_nonnegative_int(
            remote.get("object_count"),
            "remote_snapshot.object_count",
        ),
    }
    for name, expected in expected_rows.items():
        observed = _parquet_row_count(paths[name])
        if observed != expected:
            _raise_validation(
                f"unattested artifact row count for {name!r} mismatch: observed={observed}, expected={expected}",
            )
    return paths


def _require_exact_remote_partitions(
    paths: Mapping[str, Path],
    summary: Mapping[str, object],
) -> None:
    """Recompute stored missing, extra, classification, and byte evidence locally."""
    try:
        inventory_keys = pl.read_parquet(paths["inventory"], columns=["source_key"])
        remote_keys = pl.read_parquet(paths["remote_objects"], columns=["key"])
        if inventory_keys.get_column("source_key").n_unique() != inventory_keys.height:
            _raise_validation("unattested inventory contains duplicate source keys")
        if remote_keys.get_column("key").n_unique() != remote_keys.height:
            _raise_validation("unattested remote snapshot contains duplicate object keys")
        missing = inventory_keys.join(
            remote_keys,
            left_on="source_key",
            right_on="key",
            how="anti",
        ).sort("source_key")
        extra = remote_keys.join(
            inventory_keys,
            left_on="key",
            right_on="source_key",
            how="anti",
        ).sort("key")
        reported_missing = pl.read_parquet(paths["indexed_missing"], columns=["source_key"]).sort("source_key")
        reported_extra = pl.read_parquet(paths["prefix_extra"], columns=["key", "size"]).sort("key")
        if not missing.get_column("source_key").equals(reported_missing.get_column("source_key")):
            _raise_validation("indexed-missing artifact differs from the recomputed key partition")
        if not extra.get_column("key").equals(reported_extra.get_column("key")):
            _raise_validation("prefix-extra artifact differs from the recomputed key partition")
        del inventory_keys, remote_keys, missing, extra

        remote_totals = (
            pl.scan_parquet(paths["remote_objects"])
            .select(pl.len().alias("count"), pl.col("size").sum().alias("bytes"))
            .collect(engine="streaming")
            .row(0, named=True)
        )
        inventory_totals = (
            pl.scan_parquet(paths["inventory"])
            .select(
                pl.len().alias("count"),
                pl.col("source_size").sum().alias("bytes"),
                pl.col("source_size").null_count().alias("null_sizes"),
                pl.col("etag").null_count().alias("null_etags"),
            )
            .collect(engine="streaming")
            .row(0, named=True)
        )
    except (OSError, pl.exceptions.PolarsError) as error:
        message = f"cannot recompute remote inventory partitions: {error}"
        raise InventoryValidationError(message) from error
    if inventory_totals["null_sizes"] or inventory_totals["null_etags"]:
        _raise_validation("unattested enriched inventory contains null size or ETag metadata")

    plate_indexes = reported_extra.filter(pl.col("key").str.ends_with("/Index.xml"))
    unindexed_tiffs = reported_extra.filter(pl.col("key").str.ends_with(".tiff"))
    other_extras = reported_extra.filter(
        ~pl.col("key").str.ends_with("/Index.xml") & ~pl.col("key").str.ends_with(".tiff"),
    )
    observed = {
        "indexed_missing_count": reported_missing.height,
        "indexed_present_bytes": int(inventory_totals["bytes"] or 0),
        "indexed_present_count": int(inventory_totals["count"]),
        "object_count": int(remote_totals["count"]),
        "other_extra_bytes": int(other_extras.get_column("size").sum() or 0),
        "other_extra_count": other_extras.height,
        "plate_index_xml_bytes": int(plate_indexes.get_column("size").sum() or 0),
        "plate_index_xml_count": plate_indexes.height,
        "prefix_extra_bytes": int(reported_extra.get_column("size").sum() or 0),
        "prefix_extra_count": reported_extra.height,
        "total_bytes": int(remote_totals["bytes"] or 0),
        "unindexed_tiff_bytes": int(unindexed_tiffs.get_column("size").sum() or 0),
        "unindexed_tiff_count": unindexed_tiffs.height,
    }
    if summary.get("remote_snapshot") != observed:
        _raise_validation("unattested remote snapshot totals differ from the stored artifacts")


def attest_existing_inventory_summary(
    summary_path: Path,
    contract: Contract,
) -> dict[str, object]:
    """Safely add evidence to an exact older remote snapshot without relisting S3."""
    summary_path = Path(summary_path)
    summary = _read_summary(summary_path)
    if "artifact_evidence" in summary:
        return verify_inventory_artifacts(summary_path, contract)
    if contract.inventory.manifest_sha256 is None or contract.inventory.rejected_sha256 is None:
        _raise_validation("existing snapshot attestation requires pinned inventory and rejected SHA-256 values")
    paths = _require_unattested_summary_contract(summary_path, summary, contract)
    _require_exact_remote_partitions(paths, summary)
    _write_summary_with_evidence(summary_path, summary, paths, contract)
    return verify_inventory_artifacts(summary_path, contract)


def _read_summary(summary_path: Path) -> dict[str, object]:
    """Read one JSON summary as a dictionary with contextual errors."""
    try:
        raw_summary = json.loads(summary_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        message = f"cannot read inventory summary {summary_path}: {error}"
        raise InventoryValidationError(message) from error
    if not isinstance(raw_summary, dict):
        _raise_validation("inventory summary is not a dictionary")
    return cast("dict[str, object]", raw_summary)


def _expected_artifact_rows(summary: Mapping[str, object]) -> tuple[dict[str, int], bool]:
    """Return expected Parquet row counts and whether remote evidence is present."""
    raw_inventory = summary.get("inventory")
    if not isinstance(raw_inventory, dict):
        _raise_validation("summary lacks its inventory counts")
    inventory_rows = _strict_nonnegative_int(
        raw_inventory.get("complete_unique_tiff_uris"),
        "inventory complete row count",
    )
    expected_rows = {
        "inventory": inventory_rows,
        "rejected": _strict_nonnegative_int(raw_inventory.get("incomplete_rows"), "rejected row count"),
    }
    remote_snapshot = "remote_snapshot" in summary
    if not remote_snapshot:
        return expected_rows, False
    _verify_remote_reconciliation(summary, inventory_rows)
    remote = summary["remote_snapshot"]
    if not isinstance(remote, dict):
        _raise_validation("summary lacks the required remote_snapshot dictionary")
    expected_rows.update(
        {
            "indexed_missing": _strict_nonnegative_int(
                remote.get("indexed_missing_count"),
                "remote_snapshot.indexed_missing_count",
            ),
            "prefix_extra": _strict_nonnegative_int(
                remote.get("prefix_extra_count"),
                "remote_snapshot.prefix_extra_count",
            ),
            "remote_objects": _strict_nonnegative_int(
                remote.get("object_count"),
                "remote_snapshot.object_count",
            ),
        },
    )
    return expected_rows, True


def _verify_summary_evidence(
    summary_path: Path,
    summary: Mapping[str, object],
    evidence: Mapping[str, object],
) -> None:
    """Verify the summary's size and canonical content digest."""
    expected_size, expected_sha256 = _validate_evidence_record(
        evidence.get("summary"),
        label="summary",
        expected_scope=_SUMMARY_SHA256_SCOPE,
        expected_rows=None,
    )
    actual_size = summary_path.stat().st_size
    if actual_size != expected_size:
        _raise_validation(
            f"summary artifact size mismatch: observed={actual_size}, expected={expected_size}",
        )
    actual_sha256 = hashlib.sha256(_canonical_summary_payload(summary)).hexdigest()
    if actual_sha256 != expected_sha256:
        _raise_validation(
            f"summary canonical SHA-256 mismatch: observed={actual_sha256}, expected={expected_sha256}",
        )


def _verify_parquet_artifacts(
    summary_path: Path,
    artifact_names: Mapping[str, object],
    evidence: Mapping[str, object],
    expected_rows: Mapping[str, int],
) -> None:
    """Verify every generated Parquet against its summary evidence."""
    resolved_paths: set[Path] = set()
    for name, row_count in sorted(expected_rows.items()):
        filename = artifact_names.get(name)
        if not isinstance(filename, str) or Path(filename).name != filename:
            _raise_validation(f"unsafe or absent artifact filename for {name!r}: {filename!r}")
        path = summary_path.parent / filename
        if path in resolved_paths:
            _raise_validation(f"multiple evidence records resolve to the same artifact: {path}")
        resolved_paths.add(path)
        if not path.is_file():
            _raise_validation(f"generated artifact is absent: {path}")
        expected_size, expected_sha256 = _validate_evidence_record(
            evidence.get(name),
            label=name,
            expected_scope=_FILE_SHA256_SCOPE,
            expected_rows=row_count,
        )
        actual_size, _, actual_sha256 = _file_identity(path)
        if actual_size != expected_size:
            _raise_validation(
                f"artifact size mismatch for {name!r}: observed={actual_size}, expected={expected_size}",
            )
        if actual_sha256 != expected_sha256:
            _raise_validation(
                f"artifact SHA-256 mismatch for {name!r}: observed={actual_sha256}, expected={expected_sha256}",
            )
        actual_rows = _parquet_row_count(path)
        if actual_rows != row_count:
            _raise_validation(
                f"artifact row count mismatch for {name!r}: observed={actual_rows}, expected={row_count}",
            )


def verify_inventory_artifacts(
    summary_path: Path,
    contract: Contract | None = None,
) -> dict[str, object]:
    """Fail closed unless a summary and every generated artifact match their evidence."""
    summary_path = Path(summary_path)
    summary = _read_summary(summary_path)
    raw_evidence = summary.get("artifact_evidence")
    if not isinstance(raw_evidence, dict):
        _raise_validation("summary lacks its artifact_evidence map")
    expected_rows, remote_snapshot = _expected_artifact_rows(summary)
    expected_artifacts = {*expected_rows, "summary"}
    if remote_snapshot:
        expected_artifacts.update({"indexed_missing", "prefix_extra", "remote_objects"})
    if set(raw_evidence) != expected_artifacts:
        _raise_validation(
            "artifact evidence set mismatch: "
            f"observed={sorted(raw_evidence)!r}, expected={sorted(expected_artifacts)!r}",
        )
    _verify_summary_evidence(summary_path, summary, raw_evidence)
    artifact_names = summary.get("artifacts")
    if not isinstance(artifact_names, dict):
        _raise_validation("summary lacks its artifact-name map")
    _verify_parquet_artifacts(summary_path, artifact_names, raw_evidence, expected_rows)
    summary_filename = artifact_names.get("summary")
    if summary_filename != summary_path.name:
        _raise_validation(
            f"summary artifact filename mismatch: observed={summary_filename!r}, expected={summary_path.name!r}",
        )
    if contract is not None:
        raw_remote = summary.get("remote_snapshot")
        complete_remote_snapshot = isinstance(raw_remote, dict) and raw_remote.get("indexed_missing_count") == 0
        _require_contract_artifact_pins(
            contract,
            raw_evidence,
            complete_remote_snapshot=complete_remote_snapshot,
        )
    return summary


def _require_equal(label: str, actual: object, expected: object) -> None:
    """Raise one precise error when an observed frozen value differs."""
    if actual != expected:
        _raise_validation(f"{label} mismatch: observed={actual!r}, expected={expected!r}")


def _sample(frame: pl.DataFrame, columns: list[str] | tuple[str, ...]) -> list[dict[str, Any]]:
    """Return a small stable sample for a validation error."""
    return frame.select(columns).head(5).to_dicts()


def _read_index(path: Path) -> pl.DataFrame:
    """Read the exact six-column pinned index schema."""
    try:
        frame = pl.read_parquet(path)
    except (OSError, pl.exceptions.PolarsError) as error:
        message = f"cannot read index Parquet {path}: {error}"
        raise InventoryValidationError(message) from error
    if frame.columns != list(_INDEX_COLUMNS):
        _raise_validation(
            f"index columns mismatch: observed={frame.columns!r}, expected={list(_INDEX_COLUMNS)!r}",
        )
    if frame.schema != _EXPECTED_INDEX_SCHEMA:
        _raise_validation(
            f"index schema mismatch: observed={frame.schema!r}, expected={_EXPECTED_INDEX_SCHEMA!r}",
        )
    return frame.with_row_index("source_row_number")


def _split_complete_and_rejected(
    contract: Contract,
    frame: pl.DataFrame,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Separate complete rows while preserving every incomplete source row."""
    missing = pl.any_horizontal([pl.col(column).is_null() for column in _INDEX_COLUMNS])
    rejected = frame.filter(missing)
    reasons = [
        "missing required fields: " + ",".join(column for column in _INDEX_COLUMNS if row[column] is None)
        for row in rejected.select(_INDEX_COLUMNS).iter_rows(named=True)
    ]
    rejected = rejected.with_columns(pl.Series("reason", reasons, dtype=pl.String)).select(
        "source_row_number",
        *_INDEX_COLUMNS,
        "reason",
    )
    complete = frame.filter(~missing).select(_INDEX_COLUMNS)

    _require_equal("source row count", frame.height, contract.inventory.row_count)
    _require_equal("incomplete row count", rejected.height, contract.inventory.incomplete_rows)
    _require_equal(
        "complete row count",
        complete.height,
        contract.inventory.complete_unique_tiff_uris,
    )
    return complete, rejected


def _validate_complete_metadata(contract: Contract, complete: pl.DataFrame) -> None:
    """Validate frozen batch, plate, field, site, well, and channel identities."""
    observed_batches = tuple(sorted(complete.get_column("Metadata_Batch").unique().to_list()))
    _require_equal("batch set", observed_batches, tuple(sorted(contract.batches)))

    invalid_plates = complete.filter(~pl.col("Metadata_Plate").str.contains(r"^plate_[0-9]{8}$"))
    if not invalid_plates.is_empty():
        _raise_validation(
            f"malformed plate identifiers: {_sample(invalid_plates, ['Metadata_Plate'])!r}",
        )
    plate_count = complete.get_column("Metadata_Plate").n_unique()
    _require_equal("plate count", plate_count, contract.inventory.plate_count)

    invalid_wells = complete.filter(~pl.col("Metadata_Well").str.contains(r"^[A-P](0[1-9]|1[0-9]|2[0-4])$"))
    if not invalid_wells.is_empty():
        _raise_validation(
            f"malformed well identifiers: {_sample(invalid_wells, ['Metadata_Well'])!r}",
        )
    invalid_sites = complete.filter(
        ~(
            pl.col("Metadata_Site").is_finite()
            & (pl.col("Metadata_Site") >= 1)
            & (pl.col("Metadata_Site") <= _MAX_SITE_NUMBER)
            & ((pl.col("Metadata_Site") % 1) == 0)
        ),
    )
    if not invalid_sites.is_empty():
        _raise_validation(
            f"malformed site identifiers: {_sample(invalid_sites, ['Metadata_Site'])!r}",
        )

    observed_channels = set(complete.get_column("Channel").unique().to_list())
    _require_equal("channel set", observed_channels, set(contract.channels))
    _require_equal("channel count", len(observed_channels), contract.inventory.channel_count)

    field_stats = complete.group_by(_FIELD_COLUMNS).agg(
        pl.len().alias("row_count"),
        pl.col("Channel").n_unique().alias("distinct_channels"),
    )
    _require_equal("field count", field_stats.height, contract.inventory.field_count)
    invalid_fields = field_stats.filter(
        (pl.col("row_count") != contract.inventory.channel_count)
        | (pl.col("distinct_channels") != contract.inventory.channel_count),
    )
    if not invalid_fields.is_empty():
        _raise_validation(
            "fields do not each contain the exact channel set: "
            f"{_sample(invalid_fields, [*_FIELD_COLUMNS, 'row_count', 'distinct_channels'])!r}",
        )


def _plan_complete_rows(contract: Contract, complete: pl.DataFrame) -> pl.DataFrame:
    """Validate source URIs and produce the deterministic archive inventory."""
    uri_pattern = (
        rf"^s3://{re.escape(contract.source.bucket)}/{re.escape(contract.source.prefix)}/"
        r"([^/]+)/images/([^/]+)/([^/]+)\.tiff$"
    )
    parsed = complete.with_columns(
        pl.col("Filename").str.extract(uri_pattern, 1).alias("_uri_batch"),
        pl.col("Filename").str.extract(uri_pattern, 2).alias("_uri_plate"),
        pl.col("Filename").str.extract(uri_pattern, 3).alias("_stem"),
    )
    malformed = parsed.filter(pl.col("_stem").is_null())
    if not malformed.is_empty():
        _raise_validation(
            f"malformed or noncontract source URIs: {_sample(malformed, ['Filename'])!r}",
        )

    inconsistent_paths = parsed.filter(
        (pl.col("_uri_batch") != pl.col("Metadata_Batch")) | (pl.col("_uri_plate") != pl.col("Metadata_Plate")),
    )
    if not inconsistent_paths.is_empty():
        _raise_validation(
            "source URI path disagrees with batch or plate metadata: "
            f"{_sample(inconsistent_paths, ['Filename', 'Metadata_Batch', 'Metadata_Plate'])!r}",
        )

    duplicate_uris = parsed.filter(pl.col("Filename").is_duplicated())
    if not duplicate_uris.is_empty():
        _raise_validation(
            f"duplicate source URIs: {_sample(duplicate_uris, ['Filename'])!r}",
        )
    _require_equal(
        "unique complete TIFF URI count",
        parsed.get_column("Filename").n_unique(),
        contract.inventory.complete_unique_tiff_uris,
    )

    channel_number = pl.col("Channel").replace_strict(
        contract.channels,
        return_dtype=pl.UInt8,
    )
    expected_stem = pl.concat_str(
        pl.lit("r"),
        pl.col("Metadata_Well").str.slice(0, 1).replace_strict(_WELL_ROW_NUMBER),
        pl.lit("c"),
        pl.col("Metadata_Well").str.slice(1, 2),
        pl.lit("f"),
        pl.col("Metadata_Site").cast(pl.UInt8).cast(pl.String).str.pad_start(2, "0"),
        pl.lit("p01-ch"),
        channel_number.cast(pl.String),
        pl.lit("sk1fk1fl1"),
    )
    parsed = parsed.with_columns(
        channel_number.alias("_channel_number"),
        expected_stem.alias("_expected_stem"),
    )
    inconsistent_stems = parsed.filter(pl.col("_stem") != pl.col("_expected_stem"))
    if not inconsistent_stems.is_empty():
        _raise_validation(
            "source TIFF stem disagrees with well, site, or channel metadata: "
            f"{_sample(inconsistent_stems, ['Filename', 'Metadata_Well', 'Metadata_Site', 'Channel'])!r}",
        )

    uri_root = f"s3://{contract.source.bucket}/"
    destination_relative = _destination_expression(contract)
    inventory = parsed.select(
        pl.col("Filename").alias("source_uri"),
        pl.lit(contract.source.bucket).alias("bucket"),
        pl.col("Filename").str.slice(len(uri_root)).alias("source_key"),
        pl.col("Metadata_Batch").alias("batch"),
        pl.col("Metadata_Plate").alias("plate"),
        pl.col("Metadata_Well").alias("well"),
        pl.col("Metadata_Site").cast(pl.UInt8).alias("site"),
        pl.col("Channel").alias("channel"),
        pl.col("_channel_number").alias("channel_number"),
        destination_relative.alias("destination_relative"),
    ).sort(
        "batch",
        "plate",
        "well",
        "site",
        "channel_number",
        "source_uri",
    )
    if inventory.columns != list(_INVENTORY_COLUMNS):
        _raise_validation("internal inventory column order changed")
    duplicate_destinations = inventory.filter(pl.col("destination_relative").is_duplicated())
    if not duplicate_destinations.is_empty():
        _raise_validation(
            f"duplicate destination paths: {_sample(duplicate_destinations, ['source_uri', 'destination_relative'])!r}",
        )
    return inventory


def _destination_expression(contract: Contract) -> pl.Expr:
    """Render the contract template using validated scalar column expressions."""
    values = {
        "codec_id": pl.lit(contract.codec.id),
        "batch": pl.col("Metadata_Batch"),
        "plate": pl.col("Metadata_Plate"),
        "stem": pl.col("_stem"),
    }
    parts: list[pl.Expr] = []
    for literal, field, format_spec, conversion in Formatter().parse(contract.destination.object_template):
        if literal:
            parts.append(pl.lit(literal))
        if field is not None:
            if field not in values or format_spec or conversion:
                _raise_validation("unsupported destination template formatting")
            parts.append(values[field])
    return pl.concat_str(parts)


def _normalize_last_modified(value: object) -> datetime | None:
    """Normalize an S3 LastModified value to an aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            message = f"invalid S3 LastModified value: {value!r}"
            raise InventoryValidationError(message) from error
    if not isinstance(value, datetime):
        _raise_validation(f"invalid S3 LastModified value: {value!r}")
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _nullable_string(value: object) -> str | None:
    """Normalize an optional S3 metadata scalar to a non-empty string."""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _etag(value: object) -> str | None:
    """Normalize S3's quoted ETag representation."""
    normalized = _nullable_string(value)
    if normalized is None:
        return None
    return normalized.strip('"') or None


def _remote_row(
    contract: Contract,
    prefix: str,
    raw: Mapping[str, object],
) -> dict[str, object]:
    """Validate and normalize one list_objects_v2 result."""
    key = raw.get("Key")
    if not isinstance(key, str) or not key.startswith(prefix):
        _raise_validation(f"S3 listing returned an out-of-prefix key: {key!r}")
    size = raw.get("Size")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        _raise_validation(f"S3 listing returned an invalid size for {key!r}: {size!r}")
    etag = _etag(raw.get("ETag"))
    if etag is None:
        _raise_validation(f"S3 listing returned no ETag for {key!r}")
    return {
        "bucket": contract.source.bucket,
        "key": key,
        "size": size,
        "etag": etag,
        "last_modified": _normalize_last_modified(raw.get("LastModified")),
        "storage_class": _nullable_string(raw.get("StorageClass")),
        "version_id": _nullable_string(raw.get("VersionId")),
    }


def _list_remote_objects(
    contract: Contract,
    work_dir: Path,
    s3_client: _S3Client,
) -> tuple[pl.DataFrame, Path]:
    """List every contracted source prefix with a paginator and write one snapshot."""
    output_path = work_dir / "remote_objects.parquet"
    descriptor, temporary_name = tempfile.mkstemp(
        dir=work_dir,
        prefix=".remote-listing.",
        suffix=".parquet",
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        with pq.ParquetWriter(temporary_path, _REMOTE_ARROW_SCHEMA, compression="zstd") as writer:
            for batch in sorted(contract.batches):
                prefix = f"{contract.source.prefix}/{batch}/images/"
                pages = paginator.paginate(Bucket=contract.source.bucket, Prefix=prefix)
                for page in pages:
                    contents = page.get("Contents", ())
                    if not isinstance(contents, list | tuple):
                        _raise_validation(f"S3 listing returned invalid Contents for prefix {prefix!r}")
                    if any(not isinstance(raw, Mapping) for raw in contents):
                        _raise_validation(f"S3 listing returned invalid object metadata for prefix {prefix!r}")
                    rows = [_remote_row(contract, prefix, raw) for raw in contents]
                    if rows:
                        writer.write_table(pa.Table.from_pylist(rows, schema=_REMOTE_ARROW_SCHEMA))

        remote = pl.read_parquet(temporary_path).sort("key")
        duplicates = remote.filter(pl.col("key").is_duplicated())
        if not duplicates.is_empty():
            _raise_validation(
                f"duplicate keys in remote S3 listing: {_sample(duplicates, ['key'])!r}",
            )
        _atomic_write_parquet(remote, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return remote, output_path


def _batch_summary(inventory: pl.DataFrame, contract: Contract) -> list[dict[str, object]]:
    """Return stable per-batch complete-row, plate, and field counts."""
    summary = (
        inventory.group_by("batch")
        .agg(
            pl.len().alias("complete_rows"),
            pl.col("plate").n_unique().alias("plate_count"),
            pl.struct("batch", "plate", "well", "site").n_unique().alias("field_count"),
        )
        .sort("batch")
    )
    observed = tuple(summary.get_column("batch").to_list())
    _require_equal("summary batch set", observed, tuple(sorted(contract.batches)))
    return summary.to_dicts()


def _channel_summary(inventory: pl.DataFrame, contract: Contract) -> list[dict[str, object]]:
    """Return stable per-channel numbers and complete-row counts."""
    counts = {
        row["channel"]: row["complete_rows"]
        for row in inventory.group_by("channel").agg(pl.len().alias("complete_rows")).to_dicts()
    }
    return [
        {
            "channel": channel,
            "channel_number": number,
            "complete_rows": counts[channel],
        }
        for channel, number in sorted(contract.channels.items(), key=lambda item: item[1])
    ]


def _base_summary(
    contract: Contract,
    inventory: pl.DataFrame,
    rejected: pl.DataFrame,
    artifacts: InventoryArtifacts,
) -> dict[str, object]:
    """Build the deterministic local inventory summary."""
    return {
        "artifacts": {
            "index": artifacts.index_path.name,
            "inventory": artifacts.inventory_path.name,
            "rejected": artifacts.rejected_path.name,
            "summary": artifacts.summary_path.name,
        },
        "batches": _batch_summary(inventory, contract),
        "channels": _channel_summary(inventory, contract),
        "index": {
            "filename": contract.index.filename,
            "md5": contract.index.md5,
            "sha256": contract.index.sha256,
            "size_bytes": contract.index.size_bytes,
        },
        "inventory": {
            "channel_count": inventory.get_column("channel").n_unique(),
            "complete_unique_tiff_uris": inventory.height,
            "field_count": inventory.select(pl.struct("batch", "plate", "well", "site").n_unique()).item(),
            "incomplete_rows": rejected.height,
            "plate_count": inventory.get_column("plate").n_unique(),
            "row_count": inventory.height + rejected.height,
        },
        "plates": sorted(inventory.get_column("plate").unique().to_list()),
        "source": {
            "bucket": contract.source.bucket,
            "prefix": contract.source.prefix,
        },
    }


def _add_remote_summary(
    summary: dict[str, object],
    remote: pl.DataFrame,
    missing: pl.DataFrame,
    extra: pl.DataFrame,
    inventory: pl.DataFrame,
) -> None:
    """Add deterministic remote counts, byte totals, and artifact names."""
    present_sizes = inventory.get_column("source_size").drop_nulls()
    artifact_names = summary["artifacts"]
    if not isinstance(artifact_names, dict):
        _raise_validation("summary artifacts must be a dictionary")
    artifact_names.update(
        {
            "indexed_missing": "indexed_missing.parquet",
            "prefix_extra": "prefix_extra.parquet",
            "remote_objects": "remote_objects.parquet",
        },
    )
    plate_indexes = extra.filter(pl.col("key").str.ends_with("/Index.xml"))
    unindexed_tiffs = extra.filter(pl.col("key").str.ends_with(".tiff"))
    other_extras = extra.filter(
        ~pl.col("key").str.ends_with("/Index.xml") & ~pl.col("key").str.ends_with(".tiff"),
    )
    summary["remote_snapshot"] = {
        "indexed_missing_count": missing.height,
        "indexed_present_bytes": int(present_sizes.sum() or 0),
        "indexed_present_count": len(present_sizes),
        "object_count": remote.height,
        "other_extra_bytes": int(other_extras.get_column("size").sum() or 0),
        "other_extra_count": other_extras.height,
        "plate_index_xml_bytes": int(plate_indexes.get_column("size").sum() or 0),
        "plate_index_xml_count": plate_indexes.height,
        "prefix_extra_bytes": int(extra.get_column("size").sum() or 0),
        "prefix_extra_count": extra.height,
        "total_bytes": int(remote.get_column("size").sum() or 0),
        "unindexed_tiff_bytes": int(unindexed_tiffs.get_column("size").sum() or 0),
        "unindexed_tiff_count": unindexed_tiffs.height,
    }


def build_inventory(
    contract: Contract,
    work_dir: Path,
    index_path: Path | None = None,
    remote_snapshot: bool = False,  # noqa: FBT001, FBT002
    s3_client: _S3Client | None = None,
) -> InventoryArtifacts:
    """Validate the pinned index and atomically write deterministic inventory artifacts."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    if index_path is None:
        verified_index = ensure_index(contract, work_dir / "cache")
    else:
        verified_index = Path(index_path)
        _validate_index_file(contract, verified_index)

    source = _read_index(verified_index)
    complete, rejected = _split_complete_and_rejected(contract, source)
    del source
    rejected_path = work_dir / "rejected.parquet"
    _atomic_write_parquet(rejected, rejected_path)

    _validate_complete_metadata(contract, complete)
    inventory = _plan_complete_rows(contract, complete)
    inventory_path = work_dir / "inventory.parquet"
    summary_path = work_dir / "summary.json"
    _atomic_write_parquet(inventory, inventory_path)

    artifacts = InventoryArtifacts(
        index_path=verified_index,
        inventory_path=inventory_path,
        rejected_path=rejected_path,
        summary_path=summary_path,
    )
    summary = _base_summary(contract, inventory, rejected, artifacts)
    del complete, rejected
    artifact_paths = {
        "inventory": inventory_path,
        "rejected": rejected_path,
    }
    if not remote_snapshot:
        _write_summary_with_evidence(summary_path, summary, artifact_paths, contract)
        return artifacts

    client = s3_client if s3_client is not None else cast("_S3Client", public_s3_client(max_pool_connections=1))
    remote, remote_path = _list_remote_objects(contract, work_dir, client)
    missing = inventory.join(
        remote.select("key"),
        left_on="source_key",
        right_on="key",
        how="anti",
    ).sort("source_key")
    extra = remote.join(
        inventory.select("source_key"),
        left_on="key",
        right_on="source_key",
        how="anti",
    ).sort("key")
    missing_path = work_dir / "indexed_missing.parquet"
    extra_path = work_dir / "prefix_extra.parquet"
    _atomic_write_parquet(missing, missing_path)
    _atomic_write_parquet(extra, extra_path)
    artifacts = InventoryArtifacts(
        index_path=verified_index,
        inventory_path=inventory_path,
        rejected_path=rejected_path,
        summary_path=summary_path,
        remote_objects_path=remote_path,
        indexed_missing_path=missing_path,
        prefix_extra_path=extra_path,
    )
    inventory = inventory.join(
        remote.select(
            pl.col("key").alias("source_key"),
            pl.col("size").alias("source_size"),
            "etag",
            "last_modified",
            "storage_class",
            "version_id",
        ),
        on="source_key",
        how="left",
        validate="1:1",
    ).sort(
        "batch",
        "plate",
        "well",
        "site",
        "channel_number",
        "source_uri",
    )
    _atomic_write_parquet(inventory, inventory_path)
    _add_remote_summary(summary, remote, missing, extra, inventory)
    del remote
    artifact_paths.update(
        {
            "indexed_missing": missing_path,
            "prefix_extra": extra_path,
            "remote_objects": remote_path,
        },
    )
    _write_summary_with_evidence(summary_path, summary, artifact_paths, contract)
    if not missing.is_empty():
        _raise_validation(
            "remote snapshot is missing objects from the pinned index: "
            f"indexed_missing={missing.height}; see {missing_path}. "
            f"The {extra.height} prefix-extra objects remain reported in {extra_path}",
        )
    return artifacts
