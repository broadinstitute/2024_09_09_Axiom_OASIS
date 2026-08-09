# Copyright (c) 2026 Broad Institute.
# ruff: noqa: ANN401, EM101, EM102, TRY003
"""Build an archive manifest from the six-column Axiom image index."""

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
from typing import TYPE_CHECKING, Any, Final, cast
from urllib.request import Request, urlopen

import boto3
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
from botocore import UNSIGNED
from botocore.config import Config

from .io import atomic_write_json, sha256_file

if TYPE_CHECKING:
    from .contract import Contract

_INDEX_COLUMNS: Final = (
    "Metadata_Batch",
    "Metadata_Plate",
    "Metadata_Well",
    "Metadata_Site",
    "Channel",
    "Filename",
)
_INDEX_SCHEMA: Final = pl.Schema(
    {
        "Metadata_Batch": pl.String,
        "Metadata_Plate": pl.String,
        "Metadata_Well": pl.String,
        "Metadata_Site": pl.Float64,
        "Channel": pl.String,
        "Filename": pl.String,
    },
)
_FIELD_COLUMNS: Final = ("Metadata_Batch", "Metadata_Plate", "Metadata_Well", "Metadata_Site")
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
_REMOTE_SCHEMA: Final = pa.schema(
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
_WELL_ROWS: Final = {chr(ord("A") + offset): f"{offset + 1:02d}" for offset in range(16)}
_COPY_CHUNK_BYTES = 1024 * 1024
_MAX_SITE = 99


class InventoryValidationError(RuntimeError):
    """Raised when the index, remote listing, or generated manifest is invalid."""


@dataclass(frozen=True, slots=True)
class InventoryArtifacts:
    """Canonical outputs of one inventory run."""

    index_path: Path
    inventory_path: Path
    rejected_path: Path
    summary_path: Path


def ensure_index(contract: Contract, cache_dir: Path) -> Path:
    """Download the pinned index once and always verify its exact bytes."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / contract.index.filename
    if destination.is_file():
        try:
            _check_index(contract, destination)
        except InventoryValidationError:
            pass
        else:
            return destination

    descriptor, name = tempfile.mkstemp(dir=cache_dir, prefix=f".{destination.name}.", suffix=".tmp")
    temporary = Path(name)
    try:
        request = Request(contract.index.url, headers={"User-Agent": "image-archive/1"})  # noqa: S310
        with os.fdopen(descriptor, "wb") as output, urlopen(request, timeout=120) as response:  # noqa: S310
            while chunk := response.read(_COPY_CHUNK_BYTES):
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        _check_index(contract, temporary)
        temporary.chmod(0o660)
        temporary.replace(destination)
        _sync_directory(cache_dir)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def build_inventory(
    contract: Contract,
    work_dir: Path,
    index_path: Path | None = None,
    remote_snapshot: bool = False,  # noqa: FBT001, FBT002
    s3_client: Any | None = None,
) -> InventoryArtifacts:
    """Validate the index and atomically write the canonical manifest artifacts."""
    work_dir.mkdir(parents=True, exist_ok=True)
    verified_index = ensure_index(contract, work_dir / "cache") if index_path is None else Path(index_path)
    _check_index(contract, verified_index)
    frame = _read_index(verified_index)
    missing = pl.any_horizontal(pl.col(column).is_null() for column in _INDEX_COLUMNS)
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
    _equal("source row count", frame.height, contract.inventory.row_count)
    _equal("incomplete row count", rejected.height, contract.inventory.incomplete_rows)
    _equal("complete row count", complete.height, contract.inventory.complete_unique_tiff_uris)
    _validate_complete_rows(contract, complete)
    inventory = _plan_rows(contract, complete)

    inventory_path = work_dir / "inventory.parquet"
    rejected_path = work_dir / "rejected.parquet"
    summary_path = work_dir / "summary.json"
    _write_parquet(rejected, rejected_path)
    _check_pin(rejected_path, contract.inventory.rejected_sha256, "rejected rows", required=False)

    summary: dict[str, object] = {
        "artifacts": {
            "index": verified_index.name,
            "inventory": inventory_path.name,
            "rejected": rejected_path.name,
            "summary": summary_path.name,
        },
        "inventory": {
            "row_count": frame.height,
            "complete_unique_tiff_uris": inventory.height,
            "incomplete_rows": rejected.height,
            "field_count": contract.inventory.field_count,
            "plate_count": contract.inventory.plate_count,
            "channel_count": contract.inventory.channel_count,
        },
        "source": {"bucket": contract.source.bucket, "prefix": contract.source.prefix},
    }
    if remote_snapshot:
        if not contract.source.anonymous:
            raise InventoryValidationError("only anonymous public S3 sources are supported")
        client = s3_client or _s3_client()
        remote = _list_remote(contract, work_dir, client)
        missing_remote = inventory.join(
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
        _write_parquet(missing_remote, work_dir / "indexed_missing.parquet")
        _write_parquet(extra, work_dir / "prefix_extra.parquet")
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
        ).sort("batch", "plate", "well", "site", "channel_number", "source_uri")
        summary["artifacts"] = {
            **cast("dict[str, str]", summary["artifacts"]),
            "indexed_missing": "indexed_missing.parquet",
            "prefix_extra": "prefix_extra.parquet",
            "remote_objects": "remote_objects.parquet",
        }
        summary["remote_snapshot"] = _remote_summary(remote, extra, missing_remote, inventory)
        if not missing_remote.is_empty():
            _write_parquet(inventory, inventory_path)
            atomic_write_json(summary_path, summary)
            raise InventoryValidationError(
                "remote snapshot is missing "
                f"{missing_remote.height} indexed objects; see {work_dir / 'indexed_missing.parquet'}",
            )

    _write_parquet(inventory, inventory_path)
    if remote_snapshot:
        _check_pin(inventory_path, contract.inventory.manifest_sha256, "inventory manifest", required=False)
    atomic_write_json(summary_path, summary)
    return InventoryArtifacts(verified_index, inventory_path, rejected_path, summary_path)


def require_remote_inventory(contract: Contract, work_dir: Path) -> dict[str, object]:
    """Require the completed remote preflight and its two contract-pinned artifacts."""
    summary_path = work_dir / "summary.json"
    try:
        summary = json.loads(summary_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise InventoryValidationError(f"cannot read remote preflight {summary_path}: {error}") from error
    if not isinstance(summary, dict) or not isinstance(summary.get("remote_snapshot"), dict):
        raise InventoryValidationError("inventory summary lacks a remote snapshot")
    remote = cast("dict[str, object]", summary["remote_snapshot"])
    if remote.get("indexed_missing_count") != 0:
        raise InventoryValidationError("remote snapshot has missing indexed objects")
    extra = remote.get("prefix_extra_count")
    if isinstance(extra, bool) or not isinstance(extra, int) or extra < 0:
        raise InventoryValidationError("remote snapshot has an invalid prefix-extra count")
    inventory_path = work_dir / "inventory.parquet"
    rejected_path = work_dir / "rejected.parquet"
    _check_pin(inventory_path, contract.inventory.manifest_sha256, "inventory manifest", required=True)
    _check_pin(rejected_path, contract.inventory.rejected_sha256, "rejected rows", required=True)
    _equal("inventory rows", _parquet_rows(inventory_path), contract.inventory.complete_unique_tiff_uris)
    _equal("rejected rows", _parquet_rows(rejected_path), contract.inventory.incomplete_rows)
    return cast("dict[str, object]", summary)


def _check_index(contract: Contract, path: Path) -> None:
    md5 = hashlib.md5()  # noqa: S324 - identity from the upstream record, not a security check.
    sha256 = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(_COPY_CHUNK_BYTES):
                size += len(chunk)
                md5.update(chunk)
                sha256.update(chunk)
    except OSError as error:
        raise InventoryValidationError(f"cannot read index {path}: {error}") from error
    actual = (size, md5.hexdigest(), sha256.hexdigest())
    expected = (contract.index.size_bytes, contract.index.md5, contract.index.sha256)
    if actual != expected:
        raise InventoryValidationError(f"index identity mismatch: actual={actual!r}, expected={expected!r}")


def _read_index(path: Path) -> pl.DataFrame:
    try:
        frame = pl.read_parquet(path)
    except (OSError, pl.exceptions.PolarsError) as error:
        raise InventoryValidationError(f"cannot read index {path}: {error}") from error
    if frame.columns != list(_INDEX_COLUMNS) or frame.schema != _INDEX_SCHEMA:
        raise InventoryValidationError(
            f"index must have the exact six-column Axiom schema; columns={frame.columns!r}, schema={frame.schema!r}",
        )
    return frame.with_row_index("source_row_number")


def _validate_complete_rows(contract: Contract, frame: pl.DataFrame) -> None:
    _equal("batches", tuple(sorted(frame["Metadata_Batch"].unique())), tuple(sorted(contract.batches)))
    _equal("plate count", frame["Metadata_Plate"].n_unique(), contract.inventory.plate_count)
    if not frame.filter(~pl.col("Metadata_Plate").str.contains(r"^plate_[0-9]{8}$")).is_empty():
        raise InventoryValidationError("invalid plate identifier")
    if not frame.filter(~pl.col("Metadata_Well").str.contains(r"^[A-P](0[1-9]|1[0-9]|2[0-4])$")).is_empty():
        raise InventoryValidationError("invalid well identifier")
    invalid_site = ~(
        pl.col("Metadata_Site").is_finite()
        & (pl.col("Metadata_Site") >= 1)
        & (pl.col("Metadata_Site") <= _MAX_SITE)
        & ((pl.col("Metadata_Site") % 1) == 0)
    )
    if not frame.filter(invalid_site).is_empty():
        raise InventoryValidationError("invalid site identifier")
    _equal("channels", set(frame["Channel"].unique()), set(contract.channels))
    fields = frame.group_by(_FIELD_COLUMNS).agg(
        pl.len().alias("rows"),
        pl.col("Channel").n_unique().alias("channels"),
    )
    _equal("field count", fields.height, contract.inventory.field_count)
    if not fields.filter(
        (pl.col("rows") != contract.inventory.channel_count) | (pl.col("channels") != contract.inventory.channel_count),
    ).is_empty():
        raise InventoryValidationError("each field must contain the exact channel set")


def _plan_rows(contract: Contract, frame: pl.DataFrame) -> pl.DataFrame:
    pattern = (
        rf"^s3://{re.escape(contract.source.bucket)}/{re.escape(contract.source.prefix)}/"
        r"([^/]+)/images/([^/]+)/([^/]+)\.tiff$"
    )
    parsed = frame.with_columns(
        pl.col("Filename").str.extract(pattern, 1).alias("_batch"),
        pl.col("Filename").str.extract(pattern, 2).alias("_plate"),
        pl.col("Filename").str.extract(pattern, 3).alias("_stem"),
    )
    if not parsed.filter(
        pl.col("_stem").is_null()
        | (pl.col("_batch") != pl.col("Metadata_Batch"))
        | (pl.col("_plate") != pl.col("Metadata_Plate")),
    ).is_empty():
        raise InventoryValidationError("source URI disagrees with the Axiom row metadata")
    if parsed["Filename"].n_unique() != parsed.height:
        raise InventoryValidationError("source TIFF URIs must be unique")
    channel_number = pl.col("Channel").replace_strict(dict(contract.channels), return_dtype=pl.UInt8)
    expected_stem = pl.concat_str(
        pl.lit("r"),
        pl.col("Metadata_Well").str.slice(0, 1).replace_strict(_WELL_ROWS),
        pl.lit("c"),
        pl.col("Metadata_Well").str.slice(1, 2),
        pl.lit("f"),
        pl.col("Metadata_Site").cast(pl.UInt8).cast(pl.String).str.pad_start(2, "0"),
        pl.lit("p01-ch"),
        channel_number.cast(pl.String),
        pl.lit("sk1fk1fl1"),
    )
    parsed = parsed.with_columns(channel_number.alias("_channel_number"), expected_stem.alias("_expected_stem"))
    if not parsed.filter(pl.col("_stem") != pl.col("_expected_stem")).is_empty():
        raise InventoryValidationError("TIFF stem disagrees with well, site, or channel metadata")
    uri_root = f"s3://{contract.source.bucket}/"
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
        _destination_expression(contract).alias("destination_relative"),
    ).sort("batch", "plate", "well", "site", "channel_number", "source_uri")
    if (
        inventory.columns != list(_INVENTORY_COLUMNS)
        or inventory["destination_relative"].n_unique() != inventory.height
    ):
        raise InventoryValidationError("planned destination paths are not unique")
    return inventory


def _destination_expression(contract: Contract) -> pl.Expr:
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
                raise InventoryValidationError("unsupported destination template")
            parts.append(values[field])
    return pl.concat_str(parts)


def _list_remote(contract: Contract, work_dir: Path, client: Any) -> pl.DataFrame:
    destination = work_dir / "remote_objects.parquet"
    descriptor, name = tempfile.mkstemp(dir=work_dir, prefix=".remote.", suffix=".parquet")
    os.close(descriptor)
    temporary = Path(name)
    try:
        paginator = client.get_paginator("list_objects_v2")
        with pq.ParquetWriter(temporary, _REMOTE_SCHEMA, compression="zstd") as writer:
            for batch in sorted(contract.batches):
                prefix = f"{contract.source.prefix}/{batch}/images/"
                for page in paginator.paginate(Bucket=contract.source.bucket, Prefix=prefix):
                    contents = page.get("Contents", [])
                    if not isinstance(contents, list):
                        raise InventoryValidationError("invalid S3 listing page")
                    rows = [_remote_row(contract.source.bucket, prefix, raw) for raw in contents]
                    if rows:
                        writer.write_table(pa.Table.from_pylist(rows, schema=_REMOTE_SCHEMA))
        remote = pl.read_parquet(temporary).sort("key")
        if remote["key"].n_unique() != remote.height:
            raise InventoryValidationError("remote listing contains duplicate keys")
        _write_parquet(remote, destination)
        return remote
    finally:
        temporary.unlink(missing_ok=True)


def _remote_row(bucket: str, prefix: str, raw: object) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        raise InventoryValidationError("invalid S3 object metadata")
    key = raw.get("Key")
    size = raw.get("Size")
    etag = str(raw.get("ETag", "")).strip().strip('"')
    if not isinstance(key, str) or not key.startswith(prefix) or isinstance(size, bool) or not isinstance(size, int):
        raise InventoryValidationError("invalid S3 object identity")
    if size < 0 or not etag:
        raise InventoryValidationError(f"invalid S3 metadata for {key!r}")
    modified = raw.get("LastModified")
    if isinstance(modified, str):
        modified = datetime.fromisoformat(modified.replace("Z", "+00:00"))
    if isinstance(modified, datetime):
        modified = modified.replace(tzinfo=modified.tzinfo or UTC).astimezone(UTC)
    elif modified is not None:
        raise InventoryValidationError(f"invalid LastModified for {key!r}")
    return {
        "bucket": bucket,
        "key": key,
        "size": size,
        "etag": etag,
        "last_modified": modified,
        "storage_class": _optional_text(raw.get("StorageClass")),
        "version_id": _optional_text(raw.get("VersionId")),
    }


def _remote_summary(
    remote: pl.DataFrame,
    extra: pl.DataFrame,
    missing: pl.DataFrame,
    inventory: pl.DataFrame,
) -> dict[str, int]:
    plate_indexes = extra.filter(pl.col("key").str.ends_with("/Index.xml"))
    tiffs = extra.filter(pl.col("key").str.ends_with(".tiff"))
    other = extra.filter(~pl.col("key").str.ends_with("/Index.xml") & ~pl.col("key").str.ends_with(".tiff"))
    return {
        "indexed_missing_count": missing.height,
        "indexed_present_bytes": int(inventory["source_size"].sum() or 0),
        "indexed_present_count": inventory["source_size"].count(),
        "object_count": remote.height,
        "other_extra_bytes": int(other["size"].sum() or 0),
        "other_extra_count": other.height,
        "plate_index_xml_bytes": int(plate_indexes["size"].sum() or 0),
        "plate_index_xml_count": plate_indexes.height,
        "prefix_extra_bytes": int(extra["size"].sum() or 0),
        "prefix_extra_count": extra.height,
        "total_bytes": int(remote["size"].sum() or 0),
        "unindexed_tiff_bytes": int(tiffs["size"].sum() or 0),
        "unindexed_tiff_count": tiffs.height,
    }


def _write_parquet(frame: pl.DataFrame, path: Path) -> None:
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    os.close(descriptor)
    temporary = Path(name)
    try:
        frame.write_parquet(temporary, compression="zstd", statistics=True)
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        temporary.chmod(0o660)
        temporary.replace(path)
        _sync_directory(path.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _check_pin(path: Path, expected: str | None, label: str, *, required: bool) -> None:
    if expected is None:
        if required:
            raise InventoryValidationError(f"contract lacks the {label} SHA-256 pin")
        return
    actual = sha256_file(path)
    if actual != expected:
        raise InventoryValidationError(f"{label} SHA-256 differs: expected={expected}, actual={actual}")


def _parquet_rows(path: Path) -> int:
    try:
        return pq.ParquetFile(path).metadata.num_rows
    except (OSError, pa.ArrowException) as error:
        raise InventoryValidationError(f"cannot read Parquet metadata for {path}: {error}") from error


def _s3_client() -> Any:
    return boto3.client(
        "s3",
        region_name="us-east-1",
        config=Config(
            signature_version=UNSIGNED,
            max_pool_connections=1,
            connect_timeout=15,
            read_timeout=120,
            retries={"max_attempts": 10, "mode": "adaptive"},
        ),
    )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _equal(label: str, actual: object, expected: object) -> None:
    if actual != expected:
        raise InventoryValidationError(f"{label} mismatch: actual={actual!r}, expected={expected!r}")


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
