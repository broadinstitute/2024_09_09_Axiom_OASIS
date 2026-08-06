# Copyright (c) 2026 Broad Institute.
"""Durable SQLite state for the OASIS image archive.

The database is an execution ledger, not an output-existence cache. A record is
``verified`` only after the archive worker has validated and atomically promoted
its output. A full audit is intentionally separate from an ordinary fast resume;
invalid audited outputs return to the queue through ``requeue``.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from types import TracebackType

_SCHEMA_VERSION = 4
_MANIFEST_STAGE_BATCH_SIZE = 10_000
_MANIFEST_DIGEST_BATCH_SIZE = 10_000
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_MISSING = object()


class ArchiveStateError(RuntimeError):
    """Base class for archive-state failures."""


class StateConflictError(ArchiveStateError):
    """Raised when a manifest record conflicts with persisted identity."""


class InvalidTransitionError(ArchiveStateError):
    """Raised when a record cannot make the requested state transition."""


@dataclass(frozen=True, slots=True)
class ManifestIdentity:
    """Immutable identity fields accepted by :meth:`ArchiveState.initialize`."""

    source_key: str
    source_uri: str
    destination_relative: str
    expected_size: int | None = None
    expected_etag: str | None = None
    expected_version_id: str | None = None


@dataclass(frozen=True, slots=True)
class ManifestBinding:
    """Exact persisted identity of the source manifest bound to this ledger."""

    sha256: str
    artifact_sha256: str | None
    record_count: int
    bound_at: str
    last_validated_at: str

    @property
    def identity_sha256(self) -> str:
        """Return the sorted canonical identity digest."""
        return self.sha256


@dataclass(frozen=True, slots=True)
class InitializeResult:
    """Counts from an insert-or-validate manifest initialization."""

    inserted: int
    existing: int

    @property
    def total(self) -> int:
        """Return the total number of records inspected."""
        return self.inserted + self.existing


@dataclass(frozen=True, slots=True)
class StateRecord:
    """One persisted archive record."""

    source_key: str
    source_uri: str
    destination_relative: str
    expected_size: int | None
    expected_etag: str | None
    status: str
    attempts: int
    source_sha256: str | None
    output_sha256: str | None
    source_bytes: int | None
    output_bytes: int | None
    shape: tuple[int, ...] | None
    dtype: str | None
    error: str | None
    created_at: str
    updated_at: str
    started_at: str | None
    verified_at: str | None
    expected_version_id: str | None = None


class ArchiveState:
    """Main-thread SQLite ledger for restartable archive creation.

    SQLite access intentionally retains its default same-thread check. Archive
    workers should return results to the main thread, which performs every state
    transition. WAL mode allows read-only inspection by a separate process while
    the archive is running, and ``synchronous=FULL`` makes successful commits
    durable before this class reports them to the caller.
    """

    def __init__(self, path: str | Path) -> None:
        """Open or create an archive-state database at *path*."""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: sqlite3.Connection | None = sqlite3.connect(
            self.path,
            timeout=60.0,
            check_same_thread=True,
        )
        try:
            self._connection.row_factory = sqlite3.Row
            self._configure()
            self._create_schema()
            self.path.chmod(0o660)
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> Self:
        """Return this open state database."""
        self._require_connection()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the database when leaving a context manager."""
        del exc_type, exc_value, traceback
        self.close()

    def initialize(
        self,
        records: Iterable[object],
        *,
        artifact_sha256: str | None = None,
        artifact_record_count: int | None = None,
    ) -> InitializeResult:
        """Bind the exact manifest or validate it against the existing ledger.

        The iterable is staged in SQLite rather than accumulated in Python.
        Duplicate source keys, missing keys in either direction, and immutable
        identity differences fail before any archive record is changed. The
        sorted identity digest is independent of input row order.
        """
        binding = self._stage_manifest(
            records,
            artifact_sha256=artifact_sha256,
            artifact_record_count=artifact_record_count,
        )
        return self._apply_manifest_binding(binding, allow_initialize=True)

    def validate_manifest(
        self,
        records: Iterable[object],
        *,
        artifact_sha256: str | None = None,
        artifact_record_count: int | None = None,
    ) -> ManifestBinding:
        """Require *records* to exactly match the bound manifest and ledger."""
        binding = self._stage_manifest(
            records,
            artifact_sha256=artifact_sha256,
            artifact_record_count=artifact_record_count,
        )
        self._apply_manifest_binding(binding, allow_initialize=False)
        persisted = self.manifest_binding()
        if persisted is None:
            msg = "manifest validation completed without a persisted binding"
            raise ArchiveStateError(msg)
        return persisted

    def require_manifest_binding(self, artifact_sha256: str, record_count: int) -> ManifestBinding:
        """Validate a raw manifest artifact against state without replaying rows."""
        artifact_digest = _sha256(artifact_sha256, "artifact_sha256")
        expected_count = _nonnegative_int(record_count, "record_count")
        binding = self.manifest_binding()
        if binding is None:
            msg = "archive state is not bound to a manifest artifact"
            raise StateConflictError(msg)
        if binding.artifact_sha256 != artifact_digest or binding.record_count != expected_count:
            msg = (
                "manifest artifact differs from its persisted binding: "
                f"persisted={(binding.artifact_sha256, binding.record_count)!r}, "
                f"supplied={(artifact_digest, expected_count)!r}"
            )
            raise StateConflictError(msg)
        return binding

    def manifest_binding(self) -> ManifestBinding | None:
        """Return the persisted manifest digest and count, if initialized."""
        row = (
            self._require_connection()
            .execute(
                """
            SELECT sha256, artifact_sha256, record_count, bound_at, last_validated_at
            FROM archive_manifest_binding
            WHERE singleton = 1
            """,
            )
            .fetchone()
        )
        if row is None:
            return None
        return ManifestBinding(
            sha256=str(row["sha256"]),
            artifact_sha256=row["artifact_sha256"],
            record_count=int(row["record_count"]),
            bound_at=str(row["bound_at"]),
            last_validated_at=str(row["last_validated_at"]),
        )

    def recover_running(self) -> int:
        """Return interrupted ``running`` records to ``pending``.

        The attempt count remains unchanged because the interrupted attempt did
        start. No output is inferred to be usable from its presence on disk.
        """
        connection = self._require_connection()
        now = _utc_now()
        with connection:
            cursor = connection.execute(
                """
                UPDATE archive_records
                SET status = 'pending',
                    error = NULL,
                    started_at = NULL,
                    updated_at = ?
                WHERE status = 'running'
                """,
                (now,),
            )
        return cursor.rowcount

    def pending(self, limit: int | None = None, max_attempts: int = 5) -> Iterator[StateRecord]:
        """Yield pending and retryable error records in source-key order.

        Fresh or explicitly requeued ``pending`` rows are returned regardless of
        their historical attempt count. Error rows become terminal when their
        count reaches *max_attempts*.
        """
        if limit is not None and limit < 0:
            msg = "limit must be non-negative or None"
            raise ValueError(msg)
        if max_attempts < 1:
            msg = "max_attempts must be at least one"
            raise ValueError(msg)
        sql = """
            SELECT *
            FROM archive_records INDEXED BY sqlite_autoindex_archive_records_1
            WHERE (
                status = 'pending'
                OR (status = 'error' AND attempts < ?)
            )
        """
        parameters: list[int] = [max_attempts]
        return self._iter_records(sql, parameters, limit=limit)

    def mark_running(self, source_key: str) -> StateRecord:
        """Atomically start one pending or retryable-error record."""
        key = _required_text(source_key, "source_key")
        connection = self._require_connection()
        now = _utc_now()
        with connection:
            cursor = connection.execute(
                """
                UPDATE archive_records
                SET status = 'running',
                    attempts = attempts + 1,
                    error = NULL,
                    started_at = ?,
                    verified_at = NULL,
                    updated_at = ?
                WHERE source_key = ?
                  AND status IN ('pending', 'error')
                """,
                (now, now, key),
            )
            if cursor.rowcount != 1:
                self._raise_transition(key, "running", connection)
        return self._record(key)

    def mark_verified(  # noqa: PLR0913
        self,
        source_key: str,
        *,
        source_sha256: str,
        output_sha256: str,
        source_bytes: int,
        output_bytes: int,
        shape: Sequence[int],
        dtype: str,
    ) -> StateRecord:
        """Persist complete validation evidence and mark a running record verified."""
        key = _required_text(source_key, "source_key")
        source_digest = _sha256(source_sha256, "source_sha256")
        output_digest = _sha256(output_sha256, "output_sha256")
        source_count = _nonnegative_int(source_bytes, "source_bytes")
        output_count = _nonnegative_int(output_bytes, "output_bytes")
        encoded_shape = _encode_shape(shape)
        dtype_text = _required_text(dtype, "dtype")
        connection = self._require_connection()
        current = connection.execute(
            "SELECT * FROM archive_records WHERE source_key = ?",
            (key,),
        ).fetchone()
        if current is None:
            raise KeyError(key)
        expected_size = current["expected_size"]
        if expected_size is not None and source_count != expected_size:
            msg = f"source byte count for {key!r} is {source_count}, expected {expected_size}"
            raise StateConflictError(msg)
        persisted_source_digest = current["source_sha256"]
        if persisted_source_digest is not None and persisted_source_digest != source_digest:
            msg = (
                f"source SHA-256 for {key!r} changed after requeue: "
                f"persisted={persisted_source_digest!r}, supplied={source_digest!r}"
            )
            raise StateConflictError(msg)
        persisted_source_count = current["source_bytes"]
        if persisted_source_count is not None and persisted_source_count != source_count:
            msg = (
                f"source byte count for {key!r} changed after requeue: "
                f"persisted={persisted_source_count}, supplied={source_count}"
            )
            raise StateConflictError(msg)

        verification = (
            source_digest,
            output_digest,
            source_count,
            output_count,
            encoded_shape,
            dtype_text,
        )
        if current["status"] == "verified":
            persisted = (
                current["source_sha256"],
                current["output_sha256"],
                current["source_bytes"],
                current["output_bytes"],
                current["shape"],
                current["dtype"],
            )
            if persisted != verification:
                msg = f"conflicting verification evidence for {key!r}"
                raise StateConflictError(msg)
            return _row_to_record(current)
        if current["status"] != "running":
            self._raise_transition(key, "verified", connection)

        now = _utc_now()
        with connection:
            connection.execute(
                """
                UPDATE archive_records
                SET status = 'verified',
                    source_sha256 = ?,
                    output_sha256 = ?,
                    source_bytes = ?,
                    output_bytes = ?,
                    shape = ?,
                    dtype = ?,
                    error = NULL,
                    verified_at = ?,
                    updated_at = ?
                WHERE source_key = ? AND status = 'running'
                """,
                (*verification, now, now, key),
            )
        return self._record(key)

    def mark_error(self, source_key: str, error: str | BaseException) -> StateRecord:
        """Persist the complete error text for a running record."""
        key = _required_text(source_key, "source_key")
        error_text = _required_text(str(error), "error")
        connection = self._require_connection()
        now = _utc_now()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT status, attempts FROM archive_records WHERE source_key = ?",
                (key,),
            ).fetchone()
            _require_row(current, key)
            if current["status"] != "running":
                self._raise_transition(key, "error", connection)
            connection.execute(
                """
                UPDATE archive_records
                SET status = 'error',
                    error = ?,
                    updated_at = ?
                WHERE source_key = ? AND status = 'running'
                """,
                (error_text, now, key),
            )
            connection.execute(
                """
                INSERT INTO archive_errors (source_key, attempt, kind, error, created_at)
                VALUES (?, ?, 'error', ?, ?)
                """,
                (key, current["attempts"], error_text, now),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        return self._record(key)

    def requeue(
        self,
        source_key: str,
        reason: str,
        *,
        preserve_source_evidence: bool = True,
    ) -> StateRecord:
        """Invalidate output evidence and explicitly return a record to pending.

        Output-audit failures retain the already verified source digest and byte
        count by default. The next successful conversion must match that source
        evidence before it can return to ``verified``.
        """
        key = _required_text(source_key, "source_key")
        reason_text = _required_text(reason, "reason")
        if not isinstance(preserve_source_evidence, bool):
            msg = "preserve_source_evidence must be a boolean"
            raise TypeError(msg)
        connection = self._require_connection()
        now = _utc_now()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT status, attempts FROM archive_records WHERE source_key = ?",
                (key,),
            ).fetchone()
            _require_row(current, key)
            connection.execute(
                """
                UPDATE archive_records
                SET status = 'pending',
                    source_sha256 = CASE WHEN ? THEN source_sha256 ELSE NULL END,
                    source_bytes = CASE WHEN ? THEN source_bytes ELSE NULL END,
                    output_sha256 = NULL,
                    output_bytes = NULL,
                    shape = NULL,
                    dtype = NULL,
                    error = ?,
                    started_at = NULL,
                    verified_at = NULL,
                    updated_at = ?
                WHERE source_key = ?
                """,
                (
                    preserve_source_evidence,
                    preserve_source_evidence,
                    reason_text,
                    now,
                    key,
                ),
            )
            connection.execute(
                """
                INSERT INTO archive_errors (source_key, attempt, kind, error, created_at)
                VALUES (?, ?, 'requeue', ?, ?)
                """,
                (key, current["attempts"], reason_text, now),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        return self._record(key)

    def counts(self, max_attempts: int = 5) -> dict[str, int]:
        """Return status counts, including retryable and terminal errors."""
        if max_attempts < 1:
            msg = "max_attempts must be at least one"
            raise ValueError(msg)
        counts: dict[str, int] = dict.fromkeys(("pending", "running", "verified", "error"), 0)
        rows = (
            self._require_connection()
            .execute(
                "SELECT status, COUNT(*) AS count FROM archive_records GROUP BY status",
            )
            .fetchall()
        )
        for row in rows:
            counts[str(row["status"])] = int(row["count"])
        retryable = (
            self._require_connection()
            .execute(
                """
            SELECT COUNT(*) AS count
            FROM archive_records
            WHERE status = 'error' AND attempts < ?
            """,
                (max_attempts,),
            )
            .fetchone()
        )
        terminal = (
            self._require_connection()
            .execute(
                """
            SELECT COUNT(*) AS count
            FROM archive_records
            WHERE status = 'error' AND attempts >= ?
            """,
                (max_attempts,),
            )
            .fetchone()
        )
        counts["retryable_errors"] = int(retryable["count"])
        counts["terminal_errors"] = int(terminal["count"])
        counts["total"] = sum(counts[status] for status in ("pending", "running", "verified", "error"))
        counts["unresolved"] = counts["total"] - counts["verified"]
        return counts

    def byte_totals(self) -> dict[str, int]:
        """Return source and output byte totals for verified records."""
        row = (
            self._require_connection()
            .execute(
                """
            SELECT
                COALESCE(SUM(source_bytes), 0) AS source_bytes,
                COALESCE(SUM(output_bytes), 0) AS output_bytes
            FROM archive_records
            WHERE status = 'verified'
            """,
            )
            .fetchone()
        )
        if row is None:
            msg = "SQLite did not return verified byte totals"
            raise ArchiveStateError(msg)
        return {
            "source_bytes": int(row["source_bytes"]),
            "output_bytes": int(row["output_bytes"]),
        }

    def verified_record(self, source_key: str) -> StateRecord | None:
        """Return one verified record, or ``None`` when it is not verified."""
        key = _required_text(source_key, "source_key")
        row = (
            self._require_connection()
            .execute(
                """
            SELECT * FROM archive_records
            WHERE source_key = ? AND status = 'verified'
            """,
                (key,),
            )
            .fetchone()
        )
        return None if row is None else _row_to_record(row)

    def verified_records(self) -> Iterator[StateRecord]:
        """Yield every verified record in deterministic source-key order."""
        sql = """
            SELECT * FROM archive_records INDEXED BY sqlite_autoindex_archive_records_1
            WHERE status = 'verified'
        """
        return self._iter_records(sql, ())

    def unresolved_errors(
        self,
        *,
        terminal_only: bool = False,
        max_attempts: int = 5,
    ) -> Iterator[StateRecord]:
        """Yield persisted error records in deterministic source-key order."""
        if max_attempts < 1:
            msg = "max_attempts must be at least one"
            raise ValueError(msg)
        sql = """
            SELECT * FROM archive_records INDEXED BY sqlite_autoindex_archive_records_1
            WHERE status = 'error'
        """
        parameters: tuple[int, ...] = ()
        if terminal_only:
            sql += " AND attempts >= ?"
            parameters = (max_attempts,)
        return self._iter_records(sql, parameters)

    def close(self) -> None:
        """Commit pending work and close the database; safe to call repeatedly."""
        connection = self._connection
        if connection is None:
            return
        try:
            connection.commit()
        finally:
            connection.close()
            self._connection = None

    def _configure(self) -> None:
        connection = self._require_connection()
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 60000")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA temp_store = FILE")

    def _create_schema(self) -> None:
        connection = self._require_connection()
        current_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if current_version not in (0, 1, 2, 3, _SCHEMA_VERSION):
            msg = f"unsupported archive-state schema version {current_version}"
            raise ArchiveStateError(msg)
        with connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS archive_records (
                    source_key TEXT PRIMARY KEY,
                    source_uri TEXT NOT NULL,
                    destination_relative TEXT NOT NULL,
                    expected_size INTEGER,
                    expected_etag TEXT,
                    expected_version_id TEXT,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'verified', 'error')),
                    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
                    source_sha256 TEXT,
                    output_sha256 TEXT,
                    source_bytes INTEGER CHECK (source_bytes IS NULL OR source_bytes >= 0),
                    output_bytes INTEGER CHECK (output_bytes IS NULL OR output_bytes >= 0),
                    shape TEXT,
                    dtype TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    verified_at TEXT,
                    CHECK (expected_size IS NULL OR expected_size >= 0),
                    CHECK (source_sha256 IS NULL OR length(source_sha256) = 64),
                    CHECK (output_sha256 IS NULL OR length(output_sha256) = 64)
                );

                CREATE INDEX IF NOT EXISTS archive_records_status_attempts_key
                ON archive_records (status, attempts, source_key);

                CREATE UNIQUE INDEX IF NOT EXISTS archive_records_source_uri
                ON archive_records (source_uri);

                CREATE UNIQUE INDEX IF NOT EXISTS archive_records_destination_relative
                ON archive_records (destination_relative);

                CREATE TABLE IF NOT EXISTS archive_errors (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_key TEXT NOT NULL,
                    attempt INTEGER NOT NULL CHECK (attempt >= 0),
                    kind TEXT NOT NULL CHECK (kind IN ('error', 'requeue')),
                    error TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (source_key) REFERENCES archive_records (source_key)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE INDEX IF NOT EXISTS archive_errors_source_key_event
                ON archive_errors (source_key, event_id);

                CREATE TABLE IF NOT EXISTS archive_manifest_binding (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
                    artifact_sha256 TEXT
                        CHECK (artifact_sha256 IS NULL OR length(artifact_sha256) = 64),
                    record_count INTEGER NOT NULL CHECK (record_count >= 0),
                    bound_at TEXT NOT NULL,
                    last_validated_at TEXT NOT NULL
                );

                """,
            )
            record_columns = {
                str(row["name"]) for row in connection.execute("PRAGMA table_info(archive_records)").fetchall()
            }
            if "expected_version_id" not in record_columns:
                connection.execute(
                    "ALTER TABLE archive_records ADD COLUMN expected_version_id TEXT",
                )
            binding_columns = {
                str(row["name"]) for row in connection.execute("PRAGMA table_info(archive_manifest_binding)").fetchall()
            }
            if "artifact_sha256" not in binding_columns:
                connection.execute(
                    "ALTER TABLE archive_manifest_binding ADD COLUMN artifact_sha256 TEXT",
                )
            connection.executescript(
                """
                CREATE TRIGGER IF NOT EXISTS archive_records_identity_immutable
                BEFORE UPDATE OF
                    source_key,
                    source_uri,
                    destination_relative,
                    expected_size,
                    expected_etag,
                    expected_version_id
                ON archive_records
                WHEN EXISTS (
                    SELECT 1 FROM archive_manifest_binding WHERE singleton = 1
                )
                BEGIN
                    SELECT RAISE(ABORT, 'bound archive manifest identities are immutable');
                END;

                CREATE TRIGGER IF NOT EXISTS archive_records_bound_insert_forbidden
                BEFORE INSERT ON archive_records
                WHEN EXISTS (
                    SELECT 1 FROM archive_manifest_binding WHERE singleton = 1
                )
                BEGIN
                    SELECT RAISE(ABORT, 'cannot insert into a bound archive manifest');
                END;

                CREATE TRIGGER IF NOT EXISTS archive_records_bound_delete_forbidden
                BEFORE DELETE ON archive_records
                WHEN EXISTS (
                    SELECT 1 FROM archive_manifest_binding WHERE singleton = 1
                )
                BEGIN
                    SELECT RAISE(ABORT, 'cannot delete from a bound archive manifest');
                END;
                """,
            )
            connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")

    def _stage_manifest(
        self,
        records: Iterable[object],
        *,
        artifact_sha256: str | None,
        artifact_record_count: int | None,
    ) -> ManifestBinding:
        """Stage, deduplicate, sort, and hash manifest identities on disk."""
        if (artifact_sha256 is None) != (artifact_record_count is None):
            msg = "artifact_sha256 and artifact_record_count must be supplied together"
            raise ValueError(msg)
        artifact_digest = None if artifact_sha256 is None else _sha256(artifact_sha256, "artifact_sha256")
        artifact_count = (
            None if artifact_record_count is None else _nonnegative_int(artifact_record_count, "artifact_record_count")
        )
        connection = self._require_connection()
        self._drop_manifest_stage()
        connection.execute(
            """
            CREATE TEMP TABLE archive_manifest_stage (
                source_key TEXT PRIMARY KEY,
                source_uri TEXT NOT NULL UNIQUE,
                destination_relative TEXT NOT NULL UNIQUE,
                expected_size INTEGER,
                expected_etag TEXT,
                expected_version_id TEXT
            ) WITHOUT ROWID
            """,
        )
        insert_sql = """
            INSERT INTO archive_manifest_stage (
                source_key,
                source_uri,
                destination_relative,
                expected_size,
                expected_etag,
                expected_version_id
            ) VALUES (?, ?, ?, ?, ?, ?)
        """
        staged_rows: list[tuple[str, str, str, int | None, str | None, str | None]] = []
        try:
            for raw_record in records:
                record = _coerce_identity(raw_record)
                staged_rows.append(
                    (
                        record.source_key,
                        record.source_uri,
                        record.destination_relative,
                        record.expected_size,
                        record.expected_etag,
                        record.expected_version_id,
                    ),
                )
                if len(staged_rows) >= _MANIFEST_STAGE_BATCH_SIZE:
                    connection.executemany(insert_sql, staged_rows)
                    staged_rows.clear()
            if staged_rows:
                connection.executemany(insert_sql, staged_rows)
            connection.commit()
        except sqlite3.IntegrityError as error:
            connection.rollback()
            self._drop_manifest_stage()
            msg = f"manifest contains a duplicate identity: {error}"
            raise StateConflictError(msg) from error
        except BaseException:
            connection.rollback()
            self._drop_manifest_stage()
            raise
        row_count = int(
            connection.execute(
                "SELECT COUNT(*) AS count FROM archive_manifest_stage",
            ).fetchone()["count"],
        )
        if artifact_count is not None and artifact_count != row_count:
            self._drop_manifest_stage()
            msg = f"manifest artifact row count is {artifact_count}, but staged identity count is {row_count}"
            raise StateConflictError(msg)
        digest = hashlib.sha256()
        cursor = connection.execute(
            """
            SELECT
                source_key,
                source_uri,
                destination_relative,
                expected_size,
                expected_etag,
                expected_version_id
            FROM archive_manifest_stage
            ORDER BY source_key
            """,
        )
        while rows := cursor.fetchmany(_MANIFEST_DIGEST_BATCH_SIZE):
            for row in rows:
                digest.update(_canonical_manifest_row(row))
        now = _utc_now()
        return ManifestBinding(
            sha256=digest.hexdigest(),
            artifact_sha256=artifact_digest,
            record_count=row_count,
            bound_at=now,
            last_validated_at=now,
        )

    def _apply_manifest_binding(
        self,
        binding: ManifestBinding,
        *,
        allow_initialize: bool,
    ) -> InitializeResult:
        """Initialize or compare the ledger while holding the writer lock."""
        connection = self._require_connection()
        now = _utc_now()
        try:
            connection.execute("BEGIN IMMEDIATE")
            state_count = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM archive_records",
                ).fetchone()["count"],
            )
            persisted = connection.execute(
                """
                SELECT sha256, artifact_sha256, record_count, bound_at
                FROM archive_manifest_binding
                WHERE singleton = 1
                """,
            ).fetchone()
            if state_count == 0 and persisted is None:
                if not allow_initialize:
                    msg = "archive state has not been initialized with a manifest"
                    _raise_conflict(msg)
                connection.execute(
                    """
                    INSERT INTO archive_records (
                        source_key,
                        source_uri,
                        destination_relative,
                        expected_size,
                        expected_etag,
                        expected_version_id,
                        status,
                        attempts,
                        created_at,
                        updated_at
                    )
                    SELECT
                        source_key,
                        source_uri,
                        destination_relative,
                        expected_size,
                        expected_etag,
                        expected_version_id,
                        'pending',
                        0,
                        ?,
                        ?
                    FROM archive_manifest_stage
                    ORDER BY source_key
                    """,
                    (now, now),
                )
                self._insert_manifest_binding(binding, bound_at=now, validated_at=now)
                connection.commit()
                return InitializeResult(inserted=binding.record_count, existing=0)

            difference = self._manifest_difference(state_count, binding.record_count)
            if difference is not None:
                _raise_conflict(difference)
            if persisted is not None:
                persisted_identity = (str(persisted["sha256"]), int(persisted["record_count"]))
                supplied_identity = (binding.sha256, binding.record_count)
                if persisted_identity != supplied_identity:
                    msg = (
                        "manifest digest/count differs from its persisted binding: "
                        f"persisted={persisted_identity!r}, supplied={supplied_identity!r}"
                    )
                    _raise_conflict(msg)
                persisted_artifact = persisted["artifact_sha256"]
                if (
                    binding.artifact_sha256 is not None
                    and persisted_artifact is not None
                    and persisted_artifact != binding.artifact_sha256
                ):
                    msg = (
                        "manifest artifact SHA-256 differs from its persisted binding: "
                        f"persisted={persisted_artifact!r}, "
                        f"supplied={binding.artifact_sha256!r}"
                    )
                    _raise_conflict(msg)
                connection.execute(
                    """
                    UPDATE archive_manifest_binding
                    SET artifact_sha256 = COALESCE(artifact_sha256, ?),
                        last_validated_at = ?
                    WHERE singleton = 1
                    """,
                    (binding.artifact_sha256, now),
                )
            else:
                self._insert_manifest_binding(binding, bound_at=now, validated_at=now)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            self._drop_manifest_stage()
        return InitializeResult(inserted=0, existing=binding.record_count)

    def _insert_manifest_binding(
        self,
        binding: ManifestBinding,
        *,
        bound_at: str,
        validated_at: str,
    ) -> None:
        self._require_connection().execute(
            """
            INSERT INTO archive_manifest_binding (
                singleton,
                sha256,
                artifact_sha256,
                record_count,
                bound_at,
                last_validated_at
            ) VALUES (1, ?, ?, ?, ?, ?)
            """,
            (
                binding.sha256,
                binding.artifact_sha256,
                binding.record_count,
                bound_at,
                validated_at,
            ),
        )

    def _manifest_difference(self, state_count: int, manifest_count: int) -> str | None:
        connection = self._require_connection()
        missing_from_state = [
            str(row["source_key"])
            for row in connection.execute(
                """
                SELECT manifest.source_key
                FROM archive_manifest_stage AS manifest
                LEFT JOIN archive_records AS state USING (source_key)
                WHERE state.source_key IS NULL
                ORDER BY manifest.source_key
                LIMIT 10
                """,
            ).fetchall()
        ]
        missing_from_manifest = [
            str(row["source_key"])
            for row in connection.execute(
                """
                SELECT state.source_key
                FROM archive_records AS state
                LEFT JOIN archive_manifest_stage AS manifest USING (source_key)
                WHERE manifest.source_key IS NULL
                ORDER BY state.source_key
                LIMIT 10
                """,
            ).fetchall()
        ]
        conflicts = [
            str(row["source_key"])
            for row in connection.execute(
                """
                SELECT manifest.source_key
                FROM archive_manifest_stage AS manifest
                JOIN archive_records AS state USING (source_key)
                WHERE state.source_uri IS NOT manifest.source_uri
                   OR state.destination_relative IS NOT manifest.destination_relative
                   OR state.expected_size IS NOT manifest.expected_size
                   OR state.expected_etag IS NOT manifest.expected_etag
                   OR state.expected_version_id IS NOT manifest.expected_version_id
                ORDER BY manifest.source_key
                LIMIT 10
                """,
            ).fetchall()
        ]
        if missing_from_state or missing_from_manifest or conflicts or state_count != manifest_count:
            return (
                "manifest does not exactly match archive state: "
                f"state_count={state_count}, manifest_count={manifest_count}, "
                f"missing_from_state={missing_from_state!r}, "
                f"missing_from_manifest={missing_from_manifest!r}, "
                f"identity_conflicts={conflicts!r}"
            )
        return None

    def _drop_manifest_stage(self) -> None:
        connection = self._require_connection()
        connection.execute("DROP TABLE IF EXISTS archive_manifest_stage")
        connection.commit()

    def _record(self, source_key: str) -> StateRecord:
        row = (
            self._require_connection()
            .execute(
                "SELECT * FROM archive_records WHERE source_key = ?",
                (source_key,),
            )
            .fetchone()
        )
        if row is None:
            raise KeyError(source_key)
        return _row_to_record(row)

    def _iter_records(
        self,
        base_sql: str,
        parameters: Sequence[object],
        *,
        limit: int | None = None,
    ) -> Iterator[StateRecord]:
        """Iterate by keyset pagination without materializing the full ledger."""

        def records() -> Iterator[StateRecord]:
            last_key: str | None = None
            remaining = limit
            while remaining is None or remaining > 0:
                page_size = 1_000 if remaining is None else min(1_000, remaining)
                key_clause = "" if last_key is None else " AND source_key > ?"
                query_parameters = [*parameters]
                if last_key is not None:
                    query_parameters.append(last_key)
                query_parameters.append(page_size)
                rows = (
                    self._require_connection()
                    .execute(
                        f"{base_sql}{key_clause} ORDER BY source_key LIMIT ?",
                        query_parameters,
                    )
                    .fetchall()
                )
                if not rows:
                    return
                for row in rows:
                    yield _row_to_record(row)
                last_key = str(rows[-1]["source_key"])
                if remaining is not None:
                    remaining -= len(rows)

        return records()

    @staticmethod
    def _raise_transition(
        source_key: str,
        target: str,
        connection: sqlite3.Connection,
    ) -> None:
        row = connection.execute(
            "SELECT status FROM archive_records WHERE source_key = ?",
            (source_key,),
        ).fetchone()
        if row is None:
            raise KeyError(source_key)
        msg = f"cannot transition {source_key!r} from {row['status']!r} to {target!r}"
        raise InvalidTransitionError(msg)

    def _require_connection(self) -> sqlite3.Connection:
        connection = self._connection
        if connection is None:
            msg = "archive-state database is closed"
            raise ArchiveStateError(msg)
        return connection


def _coerce_identity(record: object) -> ManifestIdentity:
    if isinstance(record, ManifestIdentity):
        return record
    return ManifestIdentity(
        source_key=_required_text(_field(record, "source_key"), "source_key"),
        source_uri=_required_text(_field(record, "source_uri"), "source_uri"),
        destination_relative=_required_text(
            _field(record, "destination_relative"),
            "destination_relative",
        ),
        expected_size=_optional_nonnegative_int(
            _field(record, "expected_size", default=None),
            "expected_size",
        ),
        expected_etag=_optional_text(
            _field(record, "expected_etag", default=None),
            "expected_etag",
        ),
        expected_version_id=_optional_text(
            _field(record, "expected_version_id", default=None),
            "expected_version_id",
        ),
    )


def _field(record: object, name: str, *, default: object = _MISSING) -> object:
    if isinstance(record, Mapping):
        if name in record:
            return record[name]
    elif hasattr(record, name):
        return getattr(record, name)
    if default is not _MISSING:
        return default
    msg = f"manifest record is missing {name!r}"
    raise ValueError(msg)


def _required_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        msg = f"{name} must be a non-empty string"
        raise ValueError(msg)
    return value


def _optional_text(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, name)


def _nonnegative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        msg = f"{name} must be a non-negative integer"
        raise ValueError(msg)
    return value


def _optional_nonnegative_int(value: object, name: str) -> int | None:
    if value is None:
        return None
    return _nonnegative_int(value, name)


def _sha256(value: object, name: str) -> str:
    text = _required_text(value, name).lower()
    if _SHA256_RE.fullmatch(text) is None:
        msg = f"{name} must be a 64-character hexadecimal digest"
        raise ValueError(msg)
    return text


def _encode_shape(shape: Sequence[int]) -> str:
    if isinstance(shape, (str, bytes)) or not shape:
        msg = "shape must be a non-empty sequence of positive integers"
        raise ValueError(msg)
    values = tuple(_nonnegative_int(value, "shape element") for value in shape)
    if any(value == 0 for value in values):
        msg = "shape elements must be positive"
        raise ValueError(msg)
    return json.dumps(values, separators=(",", ":"))


def _decode_shape(value: str | None) -> tuple[int, ...] | None:
    if value is None:
        return None
    decoded = json.loads(value)
    if not isinstance(decoded, list):
        msg = f"invalid persisted shape {value!r}"
        raise ArchiveStateError(msg)
    return tuple(_nonnegative_int(item, "persisted shape element") for item in decoded)


def _row_to_record(row: sqlite3.Row) -> StateRecord:
    return StateRecord(
        source_key=str(row["source_key"]),
        source_uri=str(row["source_uri"]),
        destination_relative=str(row["destination_relative"]),
        expected_size=row["expected_size"],
        expected_etag=row["expected_etag"],
        expected_version_id=row["expected_version_id"],
        status=str(row["status"]),
        attempts=int(row["attempts"]),
        source_sha256=row["source_sha256"],
        output_sha256=row["output_sha256"],
        source_bytes=row["source_bytes"],
        output_bytes=row["output_bytes"],
        shape=_decode_shape(row["shape"]),
        dtype=row["dtype"],
        error=row["error"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        started_at=row["started_at"],
        verified_at=row["verified_at"],
    )


def _canonical_manifest_row(row: sqlite3.Row) -> bytes:
    values = [
        row["source_key"],
        row["source_uri"],
        row["destination_relative"],
        row["expected_size"],
        row["expected_etag"],
        row["expected_version_id"],
    ]
    payload = json.dumps(values, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    return f"{payload}\n".encode("ascii")


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _raise_conflict(message: str) -> None:
    raise StateConflictError(message)


def _require_row(row: sqlite3.Row | None, source_key: str) -> None:
    if row is None:
        raise KeyError(source_key)
