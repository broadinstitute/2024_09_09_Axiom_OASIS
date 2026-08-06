# ruff: noqa: CPY001, PT009
"""Integration tests for atomic, restartable OASIS image conversion."""

from __future__ import annotations

import io
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import cast
from unittest.mock import patch

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import tifffile

from image_archive.archive import (
    run_archive,
    state_report,
    validate_archive,
)
from image_archive.codec import decode_jxl
from image_archive.contract import (
    CodecContract,
    Contract,
    DestinationContract,
    IndexContract,
    InventoryContract,
    SourceContract,
)
from image_archive.io import atomic_write_bytes, sha256_file
from image_archive.state import ArchiveState, StateRecord

TEST_SHAPE = (31, 37)
SOURCE_KEY = "cpg0037-oasis/axiom/images/prod_25/images/plate_00000001/r01c01f01p01-ch1sk1fk1fl1.tiff"
DESTINATION_RELATIVE = "jpegxl-d1-e5/prod_25/images/plate_00000001/r01c01f01p01-ch1sk1fk1fl1.jxl"
SECOND_SOURCE_KEY = SOURCE_KEY.replace("f01p01", "f02p01")
SECOND_DESTINATION_RELATIVE = DESTINATION_RELATIVE.replace("f01p01", "f02p01")


class _Body:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return self.payload

    def close(self) -> None:
        return None


class _S3Client:
    def __init__(
        self,
        payload: bytes,
        etag: str = "fixture-etag",
        version_id: str | None = None,
        *,
        bucket: str = "cellpainting-gallery",
        key: str = SOURCE_KEY,
    ) -> None:
        self.payload = payload
        self.etag = etag
        self.version_id = version_id
        self.bucket = bucket
        self.key = key
        self.calls = 0

    def get_object(self, **arguments: object) -> dict[str, object]:
        self.calls += 1
        expected_arguments = {"Bucket": self.bucket, "Key": self.key}
        if self.version_id is not None:
            expected_arguments["VersionId"] = self.version_id
        if arguments != expected_arguments:
            message = f"unexpected S3 request: {arguments}"
            raise AssertionError(message)
        response: dict[str, object] = {
            "Body": _Body(self.payload),
            "ContentLength": len(self.payload),
            "ETag": f'"{self.etag}"',
        }
        if self.version_id is not None:
            response["VersionId"] = self.version_id
        return response


def _contract(
    root: Path,
    *,
    manifest_sha256: str | None = None,
    rejected_sha256: str | None = None,
    complete_images: int = 1,
) -> Contract:
    return Contract(
        index=IndexContract(1, "index.parquet", "https://example.invalid/index", 1, "0" * 32, "0" * 64),
        source=SourceContract(
            bucket="cellpainting-gallery",
            prefix="cpg0037-oasis/axiom/images",
            anonymous=True,
        ),
        inventory=InventoryContract(
            complete_images + 1,
            complete_images,
            1,
            complete_images,
            1,
            1,
            manifest_sha256=manifest_sha256,
            rejected_sha256=rejected_sha256,
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
        destination=DestinationContract(root, "{codec_id}/{batch}/images/{plate}/{stem}.jxl"),
        batches=("prod_25",),
        channels={"DNA": 1},
    )


def _runtime_contract(
    root: Path,
    inventory: Path,
    *,
    rejected: Path | None = None,
    complete_images: int = 1,
) -> Contract:
    return _contract(
        root,
        manifest_sha256=sha256_file(inventory),
        rejected_sha256=sha256_file(rejected) if rejected is not None else "0" * 64,
        complete_images=complete_images,
    )


def _tiff_bytes(shape: tuple[int, int] = TEST_SHAPE) -> bytes:
    array = np.arange(shape[0] * shape[1], dtype=np.uint16).reshape(shape)
    stream = io.BytesIO()
    tifffile.imwrite(stream, array)
    return stream.getvalue()


def _write_inventory(
    path: Path,
    source: bytes,
    etag: str = "fixture-etag",
    version_id: str | None = None,
) -> None:
    write_inventory_fixture(
        path,
        [
            {
                "source_key": SOURCE_KEY,
                "source_uri": f"s3://cellpainting-gallery/{SOURCE_KEY}",
                "destination_relative": DESTINATION_RELATIVE,
                "source_size": len(source),
                "etag": etag,
                "version_id": version_id,
            },
        ],
    )


def write_inventory_fixture(path: Path, records: list[dict[str, object]]) -> None:
    """Write a tiny Parquet fixture without exposing test helpers in production."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(records), path)


class OasisImageArchiveTest(unittest.TestCase):
    """Exercise conversion, durable evidence, corruption recovery, and failure state."""

    def test_conversion_is_verified_and_corrupt_resume_is_rebuilt(self) -> None:
        """Require exact-byte audit to rebuild a corrupt verified output."""
        source = _tiff_bytes()
        client = _S3Client(source)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inventory = root / "metadata" / "inventory.parquet"
            rejected = root / "metadata" / "rejected.parquet"
            state_path = root / "metadata" / "state.sqlite3"
            _write_inventory(inventory, source)
            write_inventory_fixture(rejected, [{"reason": "fixture incomplete row"}])
            contract = _runtime_contract(root, inventory, rejected=rejected)
            with patch("image_archive.archive.public_s3_client", return_value=client):
                first = run_archive(
                    contract,
                    inventory_path=inventory,
                    state_path=state_path,
                    workers=1,
                    max_in_flight=1,
                )
                output = root / DESTINATION_RELATIVE
                output.write_bytes(b"corrupt")
                second = run_archive(
                    contract,
                    inventory_path=inventory,
                    state_path=state_path,
                    workers=1,
                    max_in_flight=1,
                    audit_verified=True,
                )
                validation = validate_archive(
                    contract,
                    inventory_path=inventory,
                    rejected_path=rejected,
                    state_path=state_path,
                    workers=1,
                )
                progress = state_report(state_path)

            self.assertEqual(first.verified, 1)
            self.assertEqual(first.failed, 0)
            self.assertEqual(second.requeued_verified, 1)
            self.assertEqual(second.verified, 1)
            self.assertEqual(client.calls, 2)
            self.assertTrue(validation.complete)
            self.assertGreater(progress["size_reduction_fraction"], 0)
            self.assertEqual(output.parent.stat().st_mode & 0o7777, 0o2770)
            with ArchiveState(state_path) as state:
                record = state.verified_record(SOURCE_KEY)
                self.assertIsNotNone(record)
                record = cast("StateRecord", record)
                self.assertEqual(record.source_bytes, len(source))
                self.assertEqual(record.shape, TEST_SHAPE)
                self.assertEqual(record.dtype, "uint16")
                self.assertEqual(len(record.source_sha256 or ""), 64)
                self.assertEqual(len(record.output_sha256 or ""), 64)

    def test_atomic_write_failure_is_an_unresolved_error(self) -> None:
        """Never promote a failed atomic write to verified state."""
        source = _tiff_bytes()
        client = _S3Client(source)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inventory = root / "metadata" / "inventory.parquet"
            state_path = root / "metadata" / "state.sqlite3"
            _write_inventory(inventory, source)
            contract = _runtime_contract(root, inventory)
            with (
                patch("image_archive.archive.public_s3_client", return_value=client),
                patch("image_archive.archive.atomic_write_bytes", side_effect=OSError("injected write failure")),
            ):
                result = run_archive(
                    contract,
                    inventory_path=inventory,
                    state_path=state_path,
                    workers=1,
                    max_in_flight=1,
                )

            self.assertEqual(result.failed, 1)
            self.assertEqual(result.retried, 4)
            self.assertEqual(result.state_counts["error"], 1)
            self.assertEqual(result.state_counts["unresolved"], 1)
            self.assertFalse((root / DESTINATION_RELATIVE).exists())
            with ArchiveState(state_path) as state:
                record = next(state.unresolved_errors())
                self.assertIn("Traceback (most recent call last)", record.error or "")

    def test_transient_failure_is_retried_in_the_same_invocation(self) -> None:
        """Retry a selected image without requiring an expensive whole-run restart."""
        source = _tiff_bytes()
        client = _S3Client(source)
        write_calls = 0

        def flaky_write(path: Path, payload: bytes) -> None:
            nonlocal write_calls
            write_calls += 1
            if write_calls == 1:
                message = "injected transient write failure"
                raise OSError(message)
            atomic_write_bytes(path, payload)

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inventory = root / "metadata" / "inventory.parquet"
            state_path = root / "metadata" / "state.sqlite3"
            _write_inventory(inventory, source)
            contract = _runtime_contract(root, inventory)
            with (
                patch("image_archive.archive.public_s3_client", return_value=client),
                patch("image_archive.archive.atomic_write_bytes", side_effect=flaky_write),
            ):
                result = run_archive(
                    contract,
                    inventory_path=inventory,
                    state_path=state_path,
                    workers=1,
                    max_in_flight=1,
                    max_attempts=2,
                )

            self.assertEqual(result.selected, 1)
            self.assertEqual(result.retried, 1)
            self.assertEqual(result.verified, 1)
            self.assertEqual(result.failed, 0)
            self.assertEqual(client.calls, 2)

    def test_systemic_failure_stops_before_selecting_the_full_inventory(self) -> None:
        """Bound repeated local failures and leave untouched rows pending."""
        source = _tiff_bytes()
        client = _S3Client(source)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inventory = root / "metadata" / "inventory.parquet"
            state_path = root / "metadata" / "state.sqlite3"
            write_inventory_fixture(
                inventory,
                [
                    {
                        "source_key": SOURCE_KEY,
                        "source_uri": f"s3://cellpainting-gallery/{SOURCE_KEY}",
                        "destination_relative": DESTINATION_RELATIVE,
                        "source_size": len(source),
                        "etag": "fixture-etag",
                        "version_id": None,
                    },
                    {
                        "source_key": SECOND_SOURCE_KEY,
                        "source_uri": f"s3://cellpainting-gallery/{SECOND_SOURCE_KEY}",
                        "destination_relative": SECOND_DESTINATION_RELATIVE,
                        "source_size": len(source),
                        "etag": "fixture-etag",
                        "version_id": None,
                    },
                ],
            )
            contract = _runtime_contract(root, inventory, complete_images=2)
            with (
                patch("image_archive.archive.public_s3_client", return_value=client),
                patch("image_archive.archive.atomic_write_bytes", side_effect=OSError("systemic failure")),
            ):
                result = run_archive(
                    contract,
                    inventory_path=inventory,
                    state_path=state_path,
                    workers=1,
                    max_in_flight=1,
                    max_attempts=5,
                    max_consecutive_failures=2,
                )

            self.assertTrue(result.failure_limit_reached)
            self.assertEqual(result.failure_attempts, 2)
            self.assertEqual(result.selected, 1)
            self.assertEqual(result.retried, 1)
            self.assertEqual(result.failed, 1)
            self.assertEqual(result.state_counts["error"], 1)
            self.assertEqual(result.state_counts["pending"], 1)

    def test_versioned_inventory_uses_a_version_pinned_get(self) -> None:
        """Honor a source version ID whenever the remote snapshot provides one."""
        source = _tiff_bytes()
        client = _S3Client(source, version_id="fixture-version")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inventory = root / "metadata" / "inventory.parquet"
            state_path = root / "metadata" / "state.sqlite3"
            _write_inventory(inventory, source, version_id="fixture-version")
            contract = _runtime_contract(root, inventory)
            with patch("image_archive.archive.public_s3_client", return_value=client):
                result = run_archive(
                    contract,
                    inventory_path=inventory,
                    state_path=state_path,
                    workers=1,
                    max_in_flight=1,
                )

            self.assertEqual(result.verified, 1)
            self.assertEqual(client.calls, 1)

    def test_manifest_pin_fails_before_creating_an_s3_client(self) -> None:
        """Reject replaced inventory bytes before any source object request."""
        source = _tiff_bytes()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inventory = root / "metadata" / "inventory.parquet"
            state_path = root / "metadata" / "state.sqlite3"
            _write_inventory(inventory, source)
            contract = _runtime_contract(root, inventory)
            wrong_inventory = replace(contract.inventory, manifest_sha256="f" * 64)
            with (
                patch("image_archive.archive.public_s3_client") as client_factory,
                self.assertRaisesRegex(ValueError, "inventory manifest SHA-256 differs"),  # noqa: PT027
            ):
                run_archive(
                    replace(contract, inventory=wrong_inventory),
                    inventory_path=inventory,
                    state_path=state_path,
                    workers=1,
                    max_in_flight=1,
                )
            client_factory.assert_not_called()

    def test_verified_only_audit_passes_without_claiming_partial_archive_complete(self) -> None:
        """Separate an engineering smoke audit from the final completeness gate."""
        source = _tiff_bytes()
        client = _S3Client(source)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inventory = root / "metadata" / "inventory.parquet"
            rejected = root / "metadata" / "rejected.parquet"
            state_path = root / "metadata" / "state.sqlite3"
            write_inventory_fixture(
                inventory,
                [
                    {
                        "source_key": SOURCE_KEY,
                        "source_uri": f"s3://cellpainting-gallery/{SOURCE_KEY}",
                        "destination_relative": DESTINATION_RELATIVE,
                        "source_size": len(source),
                        "etag": "fixture-etag",
                        "version_id": None,
                    },
                    {
                        "source_key": SECOND_SOURCE_KEY,
                        "source_uri": f"s3://cellpainting-gallery/{SECOND_SOURCE_KEY}",
                        "destination_relative": SECOND_DESTINATION_RELATIVE,
                        "source_size": len(source),
                        "etag": "fixture-etag",
                        "version_id": None,
                    },
                ],
            )
            write_inventory_fixture(rejected, [{"reason": "fixture incomplete row"}])
            contract = _runtime_contract(root, inventory, rejected=rejected, complete_images=2)
            with patch("image_archive.archive.public_s3_client", return_value=client):
                run_archive(
                    contract,
                    inventory_path=inventory,
                    state_path=state_path,
                    workers=1,
                    max_in_flight=1,
                    limit=1,
                )
                validation = validate_archive(
                    contract,
                    inventory_path=inventory,
                    rejected_path=rejected,
                    state_path=state_path,
                    workers=1,
                    verified_only=True,
                )

            self.assertTrue(validation.audit_passed)
            self.assertFalse(validation.complete)
            self.assertEqual(validation.checked, 1)
            self.assertEqual(validation.state_counts["pending"], 1)

    def test_contract_drives_a_different_source_prefix_layout_and_image_shape(self) -> None:
        """Run the same manifest-driven engine with a different dataset description."""
        shape = (9, 13)
        source_key = "portable/raw/acq-7/frame.alpha.tiff"
        destination_relative = "group-x/asset.alpha.jxl"
        source = _tiff_bytes(shape)
        client = _S3Client(source, bucket="fixture-bucket", key=source_key)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inventory = root / "metadata" / "inventory.parquet"
            rejected = root / "metadata" / "rejected.parquet"
            state_path = root / "metadata" / "state.sqlite3"
            write_inventory_fixture(
                inventory,
                [
                    {
                        "source_key": source_key,
                        "source_uri": f"s3://fixture-bucket/{source_key}",
                        "destination_relative": destination_relative,
                        "source_size": len(source),
                        "etag": "fixture-etag",
                    },
                ],
            )
            write_inventory_fixture(rejected, [{"reason": "fixture rejected row"}])
            base = _runtime_contract(root, inventory, rejected=rejected)
            contract = replace(
                base,
                source=SourceContract(bucket="fixture-bucket", prefix="portable/raw", anonymous=True),
                destination=DestinationContract(root, "{batch}/{plate}/{codec_id}/{stem}.jxl"),
            )

            with patch("image_archive.archive.public_s3_client", return_value=client):
                run = run_archive(
                    contract,
                    inventory_path=inventory,
                    state_path=state_path,
                    workers=1,
                    max_in_flight=1,
                )
                validation = validate_archive(
                    contract,
                    inventory_path=inventory,
                    rejected_path=rejected,
                    state_path=state_path,
                    workers=1,
                )

            output = root / destination_relative
            self.assertEqual(run.verified, 1)
            self.assertTrue(validation.complete)
            self.assertEqual(tuple(decode_jxl(output.read_bytes()).shape), shape)
            self.assertEqual(client.calls, 1)


if __name__ == "__main__":
    unittest.main()
