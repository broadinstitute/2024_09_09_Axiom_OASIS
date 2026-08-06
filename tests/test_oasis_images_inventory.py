# ruff: noqa: CPY001, PT009, PT027
"""Remote-inventory scope and artifact-evidence tests."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import polars as pl

from oasis_images.contract import (
    CodecContract,
    Contract,
    DestinationContract,
    IndexContract,
    InventoryContract,
    SourceContract,
)
from oasis_images.inventory import (
    InventoryValidationError,
    attest_existing_inventory_summary,
    build_inventory,
    verify_inventory_artifacts,
)

SOURCE_PREFIX = "cpg0037-oasis/axiom/images"
PLATE = "plate_00000001"
INDEXED_KEY = f"{SOURCE_PREFIX}/prod_25/images/{PLATE}/r01c01f01p01-ch1sk1fk1fl1.tiff"
PLATE_INDEX_KEY = f"{SOURCE_PREFIX}/prod_25/images/{PLATE}/Index.xml"
UNINDEXED_TIFF_KEY = f"{SOURCE_PREFIX}/prod_25/images/{PLATE}/unindexed.tiff"
OTHER_EXTRA_KEY = f"{SOURCE_PREFIX}/prod_25/images/{PLATE}/notes.txt"


class _Paginator:
    def __init__(self, objects: list[dict[str, object]]) -> None:
        self.objects = objects

    def paginate(self, **arguments: str) -> list[dict[str, object]]:
        prefix = arguments["Prefix"]
        return [{"Contents": [row for row in self.objects if str(row["Key"]).startswith(prefix)]}]


class _S3Client:
    def __init__(self, objects: list[dict[str, object]]) -> None:
        self.paginator = _Paginator(objects)

    def get_paginator(self, operation_name: str) -> _Paginator:
        if operation_name != "list_objects_v2":
            message = f"unexpected paginator: {operation_name}"
            raise AssertionError(message)
        return self.paginator


def _remote_object(key: str, size: int) -> dict[str, object]:
    return {
        "ETag": f'"etag-{size}"',
        "Key": key,
        "LastModified": datetime(2026, 8, 4, tzinfo=UTC),
        "Size": size,
        "StorageClass": "STANDARD",
    }


def _write_index(path: Path) -> None:
    frame = pl.DataFrame(
        {
            "Metadata_Batch": ["prod_25", "prod_25"],
            "Metadata_Plate": [PLATE, PLATE],
            "Metadata_Well": ["A01", None],
            "Metadata_Site": [1.0, 1.0],
            "Channel": ["DNA", "DNA"],
            "Filename": [f"s3://cellpainting-gallery/{INDEXED_KEY}", None],
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
    frame.write_parquet(path, compression="zstd", statistics=True)


def _contract(root: Path, index_path: Path) -> Contract:
    payload = index_path.read_bytes()
    return Contract(
        index=IndexContract(
            record_id=1,
            filename=index_path.name,
            url="https://example.invalid/index.parquet",
            size_bytes=len(payload),
            md5=hashlib.md5(payload).hexdigest(),  # noqa: S324 - fixture identity only
            sha256=hashlib.sha256(payload).hexdigest(),
        ),
        source=SourceContract(
            bucket="cellpainting-gallery",
            prefix=SOURCE_PREFIX,
            anonymous=True,
        ),
        inventory=InventoryContract(
            row_count=2,
            complete_unique_tiff_uris=1,
            incomplete_rows=1,
            field_count=1,
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
        destination=DestinationContract(root / "archive", "{codec_id}/{batch}/images/{plate}/{stem}.jxl"),
        batches=("prod_25",),
        channels={"DNA": 1},
    )


def _complete_remote() -> list[dict[str, object]]:
    return [
        _remote_object(INDEXED_KEY, 101),
        _remote_object(PLATE_INDEX_KEY, 7),
        _remote_object(UNINDEXED_TIFF_KEY, 11),
        _remote_object(OTHER_EXTRA_KEY, 13),
    ]


class OasisImageInventoryTest(unittest.TestCase):
    """Keep remote extras separate and make every generated artifact tamper-evident."""

    def test_extra_only_snapshot_succeeds_without_expanding_pinned_scope(self) -> None:
        """Report prefix extras while enriching only the pinned-index row."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            index_path = root / "index.parquet"
            work_dir = root / "metadata"
            _write_index(index_path)
            contract = _contract(root, index_path)

            artifacts = build_inventory(
                contract,
                work_dir,
                index_path=index_path,
                remote_snapshot=True,
                s3_client=_S3Client(_complete_remote()),
            )
            summary = verify_inventory_artifacts(artifacts.summary_path, contract)
            inventory = pl.read_parquet(artifacts.inventory_path)
            extras = pl.read_parquet(cast("Path", artifacts.prefix_extra_path))

            self.assertEqual(inventory.get_column("source_key").to_list(), [INDEXED_KEY])
            self.assertEqual(inventory.get_column("source_size").to_list(), [101])
            self.assertEqual(set(extras.get_column("key")), {PLATE_INDEX_KEY, UNINDEXED_TIFF_KEY, OTHER_EXTRA_KEY})
            self.assertTrue(set(inventory.get_column("source_key")).isdisjoint(extras.get_column("key")))

            remote = cast("dict[str, int]", summary["remote_snapshot"])
            self.assertEqual(remote["indexed_missing_count"], 0)
            self.assertEqual(remote["prefix_extra_count"], 3)
            self.assertEqual(remote["prefix_extra_bytes"], 31)
            self.assertEqual(remote["plate_index_xml_count"], 1)
            self.assertEqual(remote["plate_index_xml_bytes"], 7)
            self.assertEqual(remote["unindexed_tiff_count"], 1)
            self.assertEqual(remote["unindexed_tiff_bytes"], 11)
            self.assertEqual(remote["other_extra_count"], 1)
            self.assertEqual(remote["other_extra_bytes"], 13)
            self.assertEqual(
                remote["plate_index_xml_count"] + remote["unindexed_tiff_count"] + remote["other_extra_count"],
                remote["prefix_extra_count"],
            )
            self.assertEqual(
                remote["plate_index_xml_bytes"] + remote["unindexed_tiff_bytes"] + remote["other_extra_bytes"],
                remote["prefix_extra_bytes"],
            )

            evidence = cast("dict[str, dict[str, object]]", summary["artifact_evidence"])
            self.assertEqual(
                set(evidence),
                {"indexed_missing", "inventory", "prefix_extra", "rejected", "remote_objects", "summary"},
            )
            self.assertEqual(evidence["inventory"]["row_count"], 1)
            self.assertEqual(evidence["prefix_extra"]["row_count"], 3)
            self.assertIsNone(evidence["summary"]["row_count"])

    def test_indexed_missing_object_fails_after_preserving_verifiable_evidence(self) -> None:
        """Fail a missing indexed object after writing complete diagnostic evidence."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            index_path = root / "index.parquet"
            work_dir = root / "metadata"
            _write_index(index_path)
            contract = _contract(root, index_path)

            with self.assertRaisesRegex(InventoryValidationError, "indexed_missing=1"):
                build_inventory(
                    contract,
                    work_dir,
                    index_path=index_path,
                    remote_snapshot=True,
                    s3_client=_S3Client([_remote_object(UNINDEXED_TIFF_KEY, 11)]),
                )

            summary = verify_inventory_artifacts(work_dir / "summary.json", contract)
            remote = cast("dict[str, int]", summary["remote_snapshot"])
            self.assertEqual(remote["indexed_missing_count"], 1)
            self.assertEqual(pl.read_parquet(work_dir / "indexed_missing.parquet").height, 1)

    def test_verifier_rejects_artifact_and_summary_tampering(self) -> None:
        """Detect changed Parquet bytes and changed canonical summary content."""
        for target in ("inventory", "summary"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory)
                index_path = root / "index.parquet"
                work_dir = root / "metadata"
                _write_index(index_path)
                contract = _contract(root, index_path)
                artifacts = build_inventory(
                    contract,
                    work_dir,
                    index_path=index_path,
                    remote_snapshot=True,
                    s3_client=_S3Client(_complete_remote()),
                )
                verify_inventory_artifacts(artifacts.summary_path, contract)

                if target == "inventory":
                    with artifacts.inventory_path.open("ab") as stream:
                        stream.write(b"tampered")
                    expected_error = "artifact size mismatch for 'inventory'"
                else:
                    original = artifacts.summary_path.read_text()
                    tampered = original.replace('"bucket": "cellpainting-gallery"', '"bucket": "cellpainting-gallfry"')
                    self.assertNotEqual(tampered, original)
                    self.assertEqual(len(tampered), len(original))
                    artifacts.summary_path.write_text(tampered)
                    expected_error = "summary canonical SHA-256 mismatch"

                with self.assertRaisesRegex(InventoryValidationError, expected_error):
                    verify_inventory_artifacts(artifacts.summary_path, contract)

    def test_verifier_accepts_legacy_summary_size_evidence(self) -> None:
        """Read the four-key summary record produced by the completed archive run."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            index_path = root / "index.parquet"
            work_dir = root / "metadata"
            _write_index(index_path)
            contract = _contract(root, index_path)
            artifacts = build_inventory(
                contract,
                work_dir,
                index_path=index_path,
                remote_snapshot=True,
                s3_client=_S3Client(_complete_remote()),
            )
            summary = cast("dict[str, object]", json.loads(artifacts.summary_path.read_text()))
            evidence = cast("dict[str, dict[str, object]]", summary["artifact_evidence"])
            evidence["summary"]["size_bytes"] = 5_155
            artifacts.summary_path.write_text(f"{json.dumps(summary, indent=2, sort_keys=True)}\n")

            verified = verify_inventory_artifacts(artifacts.summary_path, contract)
            verified_evidence = cast("dict[str, dict[str, object]]", verified["artifact_evidence"])

            self.assertEqual(verified_evidence["summary"]["size_bytes"], 5_155)

    def test_existing_exact_snapshot_can_be_attested_without_remote_relisting(self) -> None:
        """Upgrade older exact evidence only after local scope and pin validation."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            index_path = root / "index.parquet"
            work_dir = root / "metadata"
            _write_index(index_path)
            contract = _contract(root, index_path)
            artifacts = build_inventory(
                contract,
                work_dir,
                index_path=index_path,
                remote_snapshot=True,
                s3_client=_S3Client(_complete_remote()),
            )
            generated = verify_inventory_artifacts(artifacts.summary_path)
            evidence = cast("dict[str, dict[str, object]]", generated["artifact_evidence"])
            pinned_inventory = replace(
                contract.inventory,
                manifest_sha256=cast("str", evidence["inventory"]["sha256"]),
                rejected_sha256=cast("str", evidence["rejected"]["sha256"]),
            )
            pinned_contract = replace(contract, inventory=pinned_inventory)

            generated.pop("artifact_evidence")
            artifacts.summary_path.write_text(f"{json.dumps(generated, indent=2, sort_keys=True)}\n")
            attested = attest_existing_inventory_summary(artifacts.summary_path, pinned_contract)
            attested_evidence = cast("dict[str, dict[str, object]]", attested["artifact_evidence"])

            self.assertIn("artifact_evidence", attested)
            self.assertEqual(
                attested_evidence["inventory"]["sha256"],
                pinned_inventory.manifest_sha256,
            )


if __name__ == "__main__":
    unittest.main()
