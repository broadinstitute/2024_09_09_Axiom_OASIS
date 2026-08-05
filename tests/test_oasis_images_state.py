# ruff: noqa: CPY001, S101
"""Focused tests for exact archive-state manifest binding."""

from __future__ import annotations

import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from oasis_images.state import ArchiveState, ManifestIdentity, StateConflictError

if TYPE_CHECKING:
    from collections.abc import Iterator

_ARTIFACT_SHA256 = "f" * 64
_SOURCE_SHA256 = "a" * 64
_OUTPUT_SHA256 = "b" * 64
_SHARED_FILE_MODE = 0o660


def _records() -> list[ManifestIdentity]:
    return [
        ManifestIdentity(
            source_key="prefix/b.tiff",
            source_uri="s3://bucket/prefix/b.tiff",
            destination_relative="jpegxl-d1-e5/b/b.jxl",
            expected_size=20,
            expected_etag='"etag-b"',
            expected_version_id="version-b",
        ),
        ManifestIdentity(
            source_key="prefix/a.tiff",
            source_uri="s3://bucket/prefix/a.tiff",
            destination_relative="jpegxl-d1-e5/a/a.jxl",
            expected_size=10,
            expected_etag='"etag-a"',
        ),
    ]


@contextmanager
def _expect_conflict() -> Iterator[None]:
    """Require the wrapped operation to reject an identity conflict."""
    try:
        yield
    except StateConflictError:
        return
    msg = "expected StateConflictError"
    raise AssertionError(msg)


@contextmanager
def _expect_sqlite_integrity_error() -> Iterator[None]:
    """Require a bound-identity trigger to reject a direct SQLite edit."""
    try:
        yield
    except sqlite3.IntegrityError:
        return
    msg = "expected sqlite3.IntegrityError"
    raise AssertionError(msg)


class TestArchiveStateManifest:
    """Exercise manifest membership and preserved source evidence."""

    def test_exact_manifest_binding_is_order_independent_and_fast_checkable(self) -> None:
        """Bind raw and semantic identities and accept a reordered replay."""
        records = _records()
        with (
            tempfile.TemporaryDirectory() as directory,
            ArchiveState(Path(directory) / "state.sqlite3") as state,
        ):
            initialized = state.initialize(
                records,
                artifact_sha256=_ARTIFACT_SHA256,
                artifact_record_count=len(records),
            )
            binding = state.require_manifest_binding(_ARTIFACT_SHA256, len(records))
            validated = state.validate_manifest(reversed(records))

            assert initialized.inserted == len(records)
            assert binding.artifact_sha256 == _ARTIFACT_SHA256
            assert validated.identity_sha256 == binding.identity_sha256
            assert state.verified_record(records[0].source_key) is None
            assert state.path.stat().st_mode & 0o777 == _SHARED_FILE_MODE

    def test_duplicate_missing_and_changed_identities_are_rejected(self) -> None:
        """Reject duplicate keys, omitted rows, and version-ID changes."""
        records = _records()
        changed_version = ManifestIdentity(
            source_key=records[1].source_key,
            source_uri=records[1].source_uri,
            destination_relative=records[1].destination_relative,
            expected_size=records[1].expected_size,
            expected_etag=records[1].expected_etag,
            expected_version_id="changed-version",
        )
        invalid_manifests = (
            records[:1],
            [records[0], records[0]],
            [records[0], changed_version],
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            ArchiveState(Path(directory) / "state.sqlite3") as state,
        ):
            state.initialize(records)
            for invalid in invalid_manifests:
                with _expect_conflict():
                    state.validate_manifest(invalid)
            assert state.counts()["total"] == len(records)

    def test_output_requeue_preserves_and_enforces_source_evidence(self) -> None:
        """Keep source evidence across output repair and reject source drift."""
        record = _records()[0]
        with (
            tempfile.TemporaryDirectory() as directory,
            ArchiveState(Path(directory) / "state.sqlite3") as state,
        ):
            state.initialize([record])
            state.mark_running(record.source_key)
            state.mark_verified(
                record.source_key,
                source_sha256=_SOURCE_SHA256,
                output_sha256=_OUTPUT_SHA256,
                source_bytes=record.expected_size or 0,
                output_bytes=8,
                shape=(2160, 2160),
                dtype="uint16",
            )
            requeued = state.requeue(record.source_key, "output digest changed")

            assert requeued.source_sha256 == _SOURCE_SHA256
            assert requeued.source_bytes == record.expected_size
            assert requeued.output_sha256 is None
            state.mark_running(record.source_key)
            with _expect_conflict():
                state.mark_verified(
                    record.source_key,
                    source_sha256="c" * 64,
                    output_sha256=_OUTPUT_SHA256,
                    source_bytes=record.expected_size or 0,
                    output_bytes=8,
                    shape=(2160, 2160),
                    dtype="uint16",
                )

    def test_bound_manifest_identities_are_immutable_in_sqlite(self) -> None:
        """Prevent accidental ledger edits from bypassing the fast resume binding."""
        records = _records()
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.sqlite3"
            with ArchiveState(state_path) as state:
                state.initialize(
                    records,
                    artifact_sha256=_ARTIFACT_SHA256,
                    artifact_record_count=len(records),
                )

            with sqlite3.connect(state_path) as connection, _expect_sqlite_integrity_error():
                connection.execute(
                    "UPDATE archive_records SET source_uri = ? WHERE source_key = ?",
                    ("s3://bucket/prefix/repointed.tiff", records[0].source_key),
                )

    def test_archive_queue_pages_use_the_source_key_index(self) -> None:
        """Avoid repeatedly sorting the remaining multi-million-row queue."""
        records = _records()
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.sqlite3"
            with ArchiveState(state_path) as state:
                state.initialize(records)

            queries = (
                (
                    """SELECT * FROM archive_records
                    INDEXED BY sqlite_autoindex_archive_records_1
                    WHERE (status = 'pending' OR (status = 'error' AND attempts < ?))
                    AND source_key > ? ORDER BY source_key LIMIT ?""",
                    (5, "", 1_000),
                ),
                (
                    """SELECT * FROM archive_records
                    INDEXED BY sqlite_autoindex_archive_records_1
                    WHERE status = 'verified' AND source_key > ?
                    ORDER BY source_key LIMIT ?""",
                    ("", 1_000),
                ),
            )
            with sqlite3.connect(state_path) as connection:
                for query, parameters in queries:
                    plan = " ".join(
                        str(row[3])
                        for row in connection.execute(
                            f"EXPLAIN QUERY PLAN {query}",
                            parameters,
                        )
                    )
                    assert "sqlite_autoindex_archive_records_1" in plan
                    assert "TEMP B-TREE" not in plan
