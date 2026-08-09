# Copyright (c) 2026 Broad Institute.
# ruff: noqa: D101, D102, PT009, PT027
"""Focused checks for the boring image-archive path."""

from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import polars as pl
import tifffile
import tomllib

from image_archive.__main__ import _require_destination_storage
from image_archive.archive import iter_manifest_identities, run_archive, state_report, validate_archive
from image_archive.contract import (
    CodecContract,
    Contract,
    DestinationContract,
    IndexContract,
    InventoryContract,
    SourceContract,
    load_contract,
)
from image_archive.inventory import InventoryValidationError, build_inventory, require_remote_inventory
from image_archive.io import exclusive_workflow_lock, sha256_file
from image_archive.state import ArchiveState, ManifestIdentity

REPO_ROOT = Path(__file__).resolve().parents[2]
OASIS_CONTRACT = REPO_ROOT / "image_archive" / "axiom" / "source.toml"
OASIS_RECEIPT = REPO_ROOT / "image_archive" / "records" / "run-receipt-2026-08-05.toml"
CONTRACT_SHA256 = "a85639eb25908bdf900a67daeba8fc8a755db4c03841d21aff3fed9609d197dd"
RECEIPT_SHA256 = "d4af5e083b90a50a2a891ad1a068cd54510f6da274801388fd81bb1cffba4e99"
BUCKET = "fixture-bucket"
PREFIX = "demo-images"
BATCH = "batch_demo"
PLATE = "plate_00000042"
CHANNEL = "Nuclei"
DIRECT_SOURCE_KEY = f"{PREFIX}/vendor-flat/raw/acquisition-x/image-7.tif"
DIRECT_DESTINATION_RELATIVE = "jpegxl-d1-e5/freeform/image-7.jxl"


class _Body:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return self.payload

    def close(self) -> None:
        return None


class _Paginator:
    def __init__(self, client: _S3) -> None:
        self.client = client

    def paginate(self, **arguments: str) -> list[dict[str, object]]:
        prefix = arguments["Prefix"]
        contents = [
            {
                "ETag": f'"{self.client.etags[key]}"',
                "Key": key,
                "LastModified": datetime(2026, 1, 1, tzinfo=UTC),
                "Size": len(payload),
                "StorageClass": "STANDARD",
            }
            for key, payload in self.client.objects.items()
            if key.startswith(prefix)
        ]
        return [{"Contents": contents}]


class _S3:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects
        self.etags = {key: hashlib.md5(payload).hexdigest() for key, payload in objects.items()}  # noqa: S324
        self.downloads = 0

    def get_paginator(self, operation_name: str) -> _Paginator:
        if operation_name != "list_objects_v2":
            raise AssertionError(operation_name)
        return _Paginator(self)

    def get_object(self, **arguments: object) -> dict[str, object]:
        if arguments["Bucket"] != BUCKET:
            raise AssertionError(arguments)
        key = str(arguments["Key"])
        payload = self.objects[key]
        self.downloads += 1
        return {
            "Body": _Body(payload),
            "ContentLength": len(payload),
            "ETag": f'"{self.etags[key]}"',
        }


def _tiff(seed: int) -> bytes:
    pixels = np.arange(11 * 13, dtype=np.uint16).reshape(11, 13) + np.uint16(seed)
    stream = io.BytesIO()
    tifffile.imwrite(stream, pixels)
    return stream.getvalue()


def _stem(well: str, site: int) -> str:
    return f"r02c{well[1:]}f{site:02d}p01-ch1sk1fk1fl1"


def _fixture(root: Path, complete_rows: int = 1) -> tuple[Contract, Path, _S3]:
    destination = root / "archive"
    destination.mkdir()
    wells = ["B03", "B04"][:complete_rows]
    sites = list(range(2, 2 + complete_rows))
    keys = [
        f"{PREFIX}/{BATCH}/images/{PLATE}/{_stem(well, site)}.tiff" for well, site in zip(wells, sites, strict=True)
    ]
    objects = {key: _tiff(position) for position, key in enumerate(keys, start=1)}
    objects[f"{PREFIX}/{BATCH}/images/{PLATE}/notes.txt"] = b"unindexed"
    client = _S3(objects)
    index_path = root / "index.parquet"
    frame = pl.DataFrame(
        {
            "Metadata_Batch": [*([BATCH] * complete_rows), None],
            "Metadata_Plate": [*([PLATE] * complete_rows), None],
            "Metadata_Well": [*wells, None],
            "Metadata_Site": [*[float(site) for site in sites], None],
            "Channel": [*([CHANNEL] * complete_rows), None],
            "Filename": [*[f"s3://{BUCKET}/{key}" for key in keys], None],
        },
        schema={
            "Metadata_Batch": pl.String,
            "Metadata_Plate": pl.String,
            "Metadata_Well": pl.String,
            "Metadata_Site": pl.Float64,
            "Channel": pl.String,
            "Filename": pl.String,
        },
    )
    frame.write_parquet(index_path, compression="zstd", statistics=True)
    payload = index_path.read_bytes()
    contract = Contract(
        index=IndexContract(
            record_id=1,
            filename=index_path.name,
            url="https://example.invalid/index.parquet",
            size_bytes=len(payload),
            md5=hashlib.md5(payload).hexdigest(),  # noqa: S324
            sha256=hashlib.sha256(payload).hexdigest(),
        ),
        source=SourceContract(bucket=BUCKET, prefix=PREFIX, anonymous=True),
        inventory=InventoryContract(
            row_count=complete_rows + 1,
            complete_unique_tiff_uris=complete_rows,
            incomplete_rows=1,
            field_count=complete_rows,
            plate_count=1,
            channel_count=1,
            manifest_sha256=None,
            rejected_sha256=None,
        ),
        codec=CodecContract(
            id="jpegxl-d1-e5",
            name="jpegxl",
            profile="hq",
            lossless=False,
            distance=1.0,
            effort=5,
            reference_repository="https://example.invalid/reference",
            reference_commit="0" * 40,
            reference_path="codec.py",
            reference_sha256="0" * 64,
            reference_tier="fixture",
        ),
        destination=DestinationContract(destination, "{codec_id}/{batch}/images/{plate}/{stem}.jxl"),
        batches=(BATCH,),
        channels={CHANNEL: 1},
    )
    return contract, index_path, client


def _inventory(root: Path, rows: int = 1) -> tuple[Contract, Path, _S3]:
    contract, index_path, client = _fixture(root, rows)
    work_dir = root / "archive" / "_archive"
    artifacts = build_inventory(
        contract,
        work_dir,
        index_path=index_path,
        remote_snapshot=True,
        s3_client=client,
    )
    pinned = replace(
        contract.inventory,
        manifest_sha256=sha256_file(artifacts.inventory_path),
        rejected_sha256=sha256_file(artifacts.rejected_path),
    )
    return replace(contract, inventory=pinned), work_dir, client


def _direct_manifest(root: Path) -> tuple[Contract, Path, _S3]:
    contract, _, _ = _fixture(root)
    work_dir = root / "archive" / "_archive"
    work_dir.mkdir()
    payload = _tiff(7)
    client = _S3({DIRECT_SOURCE_KEY: payload})
    inventory_path = work_dir / "inventory.parquet"
    pl.DataFrame(
        {
            "source_key": [DIRECT_SOURCE_KEY],
            "source_uri": [f"s3://{BUCKET}/{DIRECT_SOURCE_KEY}"],
            "destination_relative": [DIRECT_DESTINATION_RELATIVE],
            "source_size": [len(payload)],
            "etag": [client.etags[DIRECT_SOURCE_KEY]],
            "version_id": [None],
        },
        schema={
            "source_key": pl.String,
            "source_uri": pl.String,
            "destination_relative": pl.String,
            "source_size": pl.Int64,
            "etag": pl.String,
            "version_id": pl.String,
        },
    ).write_parquet(inventory_path, compression="zstd", statistics=True)
    rejected_path = work_dir / "rejected.parquet"
    pl.DataFrame(
        {
            "source_identifier": ["raw-row-without-uri"],
            "reason": ["missing image URI"],
        },
        schema={"source_identifier": pl.String, "reason": pl.String},
    ).write_parquet(rejected_path, compression="zstd", statistics=True)
    (work_dir / "summary.json").write_text(
        json.dumps(
            {
                "remote_snapshot": {
                    "indexed_missing_count": 0,
                    "prefix_extra_count": 0,
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return (
        replace(
            contract,
            inventory=replace(
                contract.inventory,
                manifest_sha256=sha256_file(inventory_path),
                rejected_sha256=sha256_file(rejected_path),
            ),
        ),
        work_dir,
        client,
    )


class ImageArchiveTest(unittest.TestCase):
    def test_missing_source_rerun_replaces_successful_preflight(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            contract, work_dir, client = _inventory(root)
            require_remote_inventory(contract, work_dir)
            indexed_key = next(key for key in client.objects if key.endswith(".tiff"))
            client.objects.pop(indexed_key)

            with self.assertRaisesRegex(InventoryValidationError, "missing 1 indexed objects"):
                build_inventory(
                    contract,
                    work_dir,
                    index_path=root / "index.parquet",
                    remote_snapshot=True,
                    s3_client=client,
                )
            with self.assertRaisesRegex(InventoryValidationError, "missing indexed objects"):
                require_remote_inventory(contract, work_dir)
            summary = json.loads((work_dir / "summary.json").read_text())
            self.assertEqual(summary["remote_snapshot"]["indexed_missing_count"], 1)

    def test_direct_manifest_resume_status_validate_and_repair(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            contract, work_dir, client = _direct_manifest(root)
            inventory_path = work_dir / "inventory.parquet"
            rejected_path = work_dir / "rejected.parquet"
            state_path = work_dir / "state.sqlite3"
            manifest = list(iter_manifest_identities(inventory_path, contract))
            self.assertEqual(manifest[0].source_key, DIRECT_SOURCE_KEY)
            self.assertEqual(manifest[0].destination_relative, DIRECT_DESTINATION_RELATIVE)
            require_remote_inventory(contract, work_dir)
            with ArchiveState(state_path) as state:
                state.initialize(
                    manifest,
                    artifact_sha256=contract.inventory.manifest_sha256 or "",
                    record_count=1,
                )
                state.mark_running(manifest[0].source_key)

            with patch("image_archive.archive._s3_client", return_value=client):
                first = run_archive(
                    contract,
                    inventory_path=inventory_path,
                    state_path=state_path,
                    workers=1,
                    max_in_flight=1,
                )
                resumed = run_archive(
                    contract,
                    inventory_path=inventory_path,
                    state_path=state_path,
                    workers=1,
                    max_in_flight=1,
                )

            self.assertEqual(first.recovered_running, 1)
            self.assertEqual(first.selected, 1)
            self.assertEqual(first.verified, 1)
            self.assertEqual(resumed.selected, 0)
            self.assertEqual(resumed.verified, 0)
            self.assertEqual(resumed.recovered_running, 0)
            self.assertEqual(client.downloads, 1)
            progress = state_report(state_path)
            self.assertEqual(progress["counts"]["verified"], 1)
            self.assertEqual(progress["counts"]["unresolved"], 0)
            self.assertEqual(
                progress["manifest_binding"]["artifact_sha256"],
                contract.inventory.manifest_sha256,
            )

            report_path = work_dir / "validation.json"
            valid = validate_archive(
                contract,
                inventory_path=inventory_path,
                rejected_path=rejected_path,
                state_path=state_path,
                workers=1,
                report_path=report_path,
            )
            self.assertTrue(valid.complete)
            self.assertTrue(valid.audit_passed)
            self.assertTrue(json.loads(report_path.read_text())["complete"])

            output = contract.destination.root / manifest[0].destination_relative
            output.write_bytes(b"corrupt")
            self.assertFalse(
                validate_archive(
                    contract,
                    inventory_path=inventory_path,
                    rejected_path=rejected_path,
                    state_path=state_path,
                    workers=1,
                ).complete,
            )
            with (
                patch("image_archive.archive._s3_client", return_value=client),
                patch("image_archive.archive.LOGGER.warning"),
            ):
                repaired = run_archive(
                    contract,
                    inventory_path=inventory_path,
                    state_path=state_path,
                    workers=1,
                    max_in_flight=1,
                    audit_verified=True,
                )
            self.assertEqual(repaired.requeued_verified, 1)
            self.assertEqual(repaired.verified, 1)
            self.assertEqual(client.downloads, 2)

            wrong = replace(contract.inventory, manifest_sha256="f" * 64)
            with self.assertRaisesRegex(ValueError, "manifest SHA-256 differs"):
                run_archive(
                    replace(contract, inventory=wrong),
                    inventory_path=inventory_path,
                    state_path=state_path,
                    workers=1,
                    max_in_flight=1,
                )

    def test_atomic_failure_trips_the_circuit_breaker(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            contract, work_dir, client = _inventory(root, rows=2)
            with (
                patch("image_archive.archive._s3_client", return_value=client),
                patch("image_archive.archive.atomic_write_bytes", side_effect=OSError("disk failure")),
                patch("image_archive.archive.LOGGER.error"),
                patch("image_archive.archive.LOGGER.warning"),
            ):
                result = run_archive(
                    contract,
                    inventory_path=work_dir / "inventory.parquet",
                    state_path=work_dir / "state.sqlite3",
                    workers=1,
                    max_in_flight=1,
                    max_attempts=5,
                    max_consecutive_failures=2,
                )
            self.assertTrue(result.failure_limit_reached)
            self.assertEqual(result.failure_attempts, 2)
            self.assertEqual(result.state_counts["error"], 1)
            self.assertEqual(result.state_counts["pending"], 1)
            self.assertFalse(list((root / "archive").rglob("*.jxl")))

    def test_lock_and_destination_safety(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            lock = root / ".archive.lock"
            with (
                exclusive_workflow_lock(lock, "archive"),
                self.assertRaisesRegex(RuntimeError, "already held"),
                exclusive_workflow_lock(lock, "validate"),
            ):
                self.fail("nested lock acquired")
            real = root / "real"
            real.mkdir()
            link = root / "link"
            link.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, "contains a symlink"):
                _require_destination_storage(link)

    def test_oasis_contract_receipt_and_ledger_schema_contract(self) -> None:
        self.assertEqual(sha256_file(OASIS_CONTRACT), CONTRACT_SHA256)
        self.assertEqual(sha256_file(OASIS_RECEIPT), RECEIPT_SHA256)
        contract = load_contract(OASIS_CONTRACT)
        receipt = tomllib.loads(OASIS_RECEIPT.read_text())
        self.assertEqual(receipt["contract_sha256"], CONTRACT_SHA256)
        self.assertEqual(receipt["ledger"]["schema_version"], 4)
        self.assertEqual(receipt["manifest"]["inventory_sha256"], contract.inventory.manifest_sha256)
        self.assertTrue(receipt["validation"]["result"]["complete"])

        with TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.sqlite3"
            identity = ManifestIdentity(
                "demo/a.tiff",
                "s3://fixture-bucket/demo/a.tiff",
                "jpegxl/demo/a.jxl",
                1,
                "etag",
            )
            with ArchiveState(state_path) as state:
                state.initialize(
                    [identity],
                    artifact_sha256="a" * 64,
                    record_count=1,
                )
            with sqlite3.connect(state_path) as connection:
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 4)
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("UPDATE archive_records SET source_uri = 's3://changed' ")


if __name__ == "__main__":
    unittest.main()
