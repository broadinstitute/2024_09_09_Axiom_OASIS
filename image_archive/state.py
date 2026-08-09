# Copyright (c) 2026 Broad Institute.
# ruff: noqa: D102, D105, D107, EM101, EM102, PLR0913, TC003, TRY003, TRY301
"""SQLite ledger for restartable JPEG XL archive builds."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from types import TracebackType

SCHEMA_VERSION = 4
_BATCH_SIZE = 10_000
_SHA256 = re.compile(r"[0-9a-f]{64}")


class ArchiveStateError(RuntimeError):
    """Raised when a ledger is invalid or used inconsistently."""


class StateConflictError(ArchiveStateError):
    """Raised when immutable archive evidence changes."""


@dataclass(frozen=True, slots=True)
class ManifestIdentity:
    """Immutable source and destination identity for one archive row."""

    source_key: str
    source_uri: str
    destination_relative: str
    expected_size: int
    expected_etag: str
    expected_version_id: str | None = None


@dataclass(frozen=True, slots=True)
class ManifestBinding:
    """Manifest identity persisted in the ledger."""

    sha256: str
    artifact_sha256: str
    record_count: int
    bound_at: str
    last_validated_at: str


@dataclass(frozen=True, slots=True)
class StateRecord:
    """One archive ledger row."""

    source_key: str
    source_uri: str
    destination_relative: str
    expected_size: int
    expected_etag: str
    expected_version_id: str | None
    status: str
    attempts: int
    source_sha256: str | None
    output_sha256: str | None
    source_bytes: int | None
    output_bytes: int | None
    shape: tuple[int, ...] | None
    dtype: str | None
    error: str | None


class ArchiveState:
    """Main-thread interface to a schema-v4 archive ledger."""

    def __init__(self, path: Path, *, read_only: bool = False) -> None:
        self.path = Path(path)
        self._read_only = read_only
        if read_only:
            if not self.path.is_file():
                raise FileNotFoundError(self.path)
            uri = f"{self.path.resolve().as_uri()}?mode=ro"
            connection = sqlite3.connect(uri, uri=True, timeout=60.0)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=60.0)
        self._connection: sqlite3.Connection | None = connection
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 60000")
            if read_only:
                self._require_schema()
            else:
                connection.execute("PRAGMA synchronous = FULL")
                connection.execute("PRAGMA journal_mode = WAL")
                self._create_schema()
                self.path.chmod(0o660)
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        self.close()

    def initialize(
        self,
        records: Iterable[ManifestIdentity],
        *,
        artifact_sha256: str,
        record_count: int,
    ) -> int:
        """Create an empty ledger, or fast-check its existing manifest binding."""
        digest = _digest(artifact_sha256, "artifact_sha256")
        count = _nonnegative(record_count, "record_count")
        if self.manifest_binding() is not None:
            self.require_manifest_binding(digest, count)
            return 0

        connection = self._connection_required()
        if connection.execute("SELECT COUNT(*) FROM archive_records").fetchone()[0]:
            raise StateConflictError("unbound archive ledger is not empty")
        connection.execute("DROP TABLE IF EXISTS archive_manifest_stage")
        connection.execute(
            """
            CREATE TEMP TABLE archive_manifest_stage (
                source_key TEXT PRIMARY KEY,
                source_uri TEXT NOT NULL UNIQUE,
                destination_relative TEXT NOT NULL UNIQUE,
                expected_size INTEGER NOT NULL,
                expected_etag TEXT NOT NULL,
                expected_version_id TEXT
            ) WITHOUT ROWID
            """,
        )
        rows: list[tuple[str, str, str, int, str, str | None]] = []
        sql = "INSERT INTO archive_manifest_stage VALUES (?, ?, ?, ?, ?, ?)"
        try:
            for record in records:
                rows.append(_identity_values(record))
                if len(rows) == _BATCH_SIZE:
                    connection.executemany(sql, rows)
                    rows.clear()
            if rows:
                connection.executemany(sql, rows)
            staged = int(connection.execute("SELECT COUNT(*) FROM archive_manifest_stage").fetchone()[0])
            if staged != count:
                raise StateConflictError(f"manifest row count differs: artifact={count}, identities={staged}")
            identity_sha256 = _manifest_digest(connection)
            now = _utc_now()
            connection.commit()
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO archive_records (
                    source_key, source_uri, destination_relative, expected_size,
                    expected_etag, expected_version_id, created_at, updated_at
                )
                SELECT source_key, source_uri, destination_relative, expected_size,
                       expected_etag, expected_version_id, ?, ?
                FROM archive_manifest_stage ORDER BY source_key
                """,
                (now, now),
            )
            connection.execute(
                """
                INSERT INTO archive_manifest_binding
                    (singleton, sha256, artifact_sha256, record_count, bound_at, last_validated_at)
                VALUES (1, ?, ?, ?, ?, ?)
                """,
                (identity_sha256, digest, count, now, now),
            )
            connection.commit()
        except sqlite3.IntegrityError as error:
            connection.rollback()
            raise StateConflictError(f"manifest contains duplicate identities: {error}") from error
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.execute("DROP TABLE IF EXISTS archive_manifest_stage")
            connection.commit()
        return count

    def require_manifest_binding(self, artifact_sha256: str, record_count: int) -> ManifestBinding:
        """Require an exact manifest artifact and row-count match."""
        supplied = (_digest(artifact_sha256, "artifact_sha256"), _nonnegative(record_count, "record_count"))
        binding = self.manifest_binding()
        if binding is None:
            raise StateConflictError("archive ledger is not bound to a manifest")
        persisted = (binding.artifact_sha256, binding.record_count)
        if supplied != persisted:
            raise StateConflictError(f"manifest differs from ledger: persisted={persisted!r}, supplied={supplied!r}")
        return binding

    def manifest_binding(self) -> ManifestBinding | None:
        row = (
            self._connection_required()
            .execute(
                """
            SELECT sha256, artifact_sha256, record_count, bound_at, last_validated_at
            FROM archive_manifest_binding WHERE singleton = 1
            """,
            )
            .fetchone()
        )
        if row is None:
            return None
        if row["artifact_sha256"] is None:
            raise StateConflictError("archive ledger lacks its manifest artifact SHA-256")
        return ManifestBinding(
            sha256=str(row["sha256"]),
            artifact_sha256=str(row["artifact_sha256"]),
            record_count=int(row["record_count"]),
            bound_at=str(row["bound_at"]),
            last_validated_at=str(row["last_validated_at"]),
        )

    def recover_running(self) -> int:
        """Return interrupted rows to pending without trusting partial outputs."""
        now = _utc_now()
        with self._connection_required() as connection:
            cursor = connection.execute(
                """
                UPDATE archive_records
                SET status = 'pending', error = NULL, started_at = NULL, updated_at = ?
                WHERE status = 'running'
                """,
                (now,),
            )
        return cursor.rowcount

    def pending(self, *, max_attempts: int) -> Iterator[StateRecord]:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        sql = """
            SELECT * FROM archive_records INDEXED BY sqlite_autoindex_archive_records_1
            WHERE (status = 'pending' OR (status = 'error' AND attempts < ?))
        """
        return self._records(sql, (max_attempts,))

    def verified_records(self) -> Iterator[StateRecord]:
        sql = """
            SELECT * FROM archive_records INDEXED BY sqlite_autoindex_archive_records_1
            WHERE status = 'verified'
        """
        return self._records(sql, ())

    def mark_running(self, source_key: str) -> StateRecord:
        now = _utc_now()
        with self._connection_required() as connection:
            cursor = connection.execute(
                """
                UPDATE archive_records
                SET status = 'running', attempts = attempts + 1, error = NULL,
                    started_at = ?, verified_at = NULL, updated_at = ?
                WHERE source_key = ? AND status IN ('pending', 'error')
                """,
                (now, now, source_key),
            )
        if cursor.rowcount != 1:
            self._transition_error(source_key, "running")
        return self._record(source_key)

    def mark_verified(
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
        current = self._record(source_key)
        source_digest = _digest(source_sha256, "source_sha256")
        output_digest = _digest(output_sha256, "output_sha256")
        source_count = _nonnegative(source_bytes, "source_bytes")
        output_count = _nonnegative(output_bytes, "output_bytes")
        encoded_shape = json.dumps(tuple(_positive(value, "shape") for value in shape), separators=(",", ":"))
        if source_count != current.expected_size:
            raise StateConflictError(f"source byte count changed for {source_key!r}")
        if current.source_sha256 not in {None, source_digest} or current.source_bytes not in {None, source_count}:
            raise StateConflictError(f"source evidence changed for {source_key!r}")
        if current.status != "running":
            self._transition_error(source_key, "verified")
        now = _utc_now()
        with self._connection_required() as connection:
            connection.execute(
                """
                UPDATE archive_records
                SET status = 'verified', source_sha256 = ?, output_sha256 = ?,
                    source_bytes = ?, output_bytes = ?, shape = ?, dtype = ?, error = NULL,
                    verified_at = ?, updated_at = ?
                WHERE source_key = ? AND status = 'running'
                """,
                (
                    source_digest,
                    output_digest,
                    source_count,
                    output_count,
                    encoded_shape,
                    _text(dtype, "dtype"),
                    now,
                    now,
                    source_key,
                ),
            )
        return self._record(source_key)

    def mark_error(self, source_key: str, error: str) -> StateRecord:
        message = _text(error, "error")
        connection = self._connection_required()
        now = _utc_now()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT status, attempts FROM archive_records WHERE source_key = ?",
                (source_key,),
            ).fetchone()
            if current is None:
                raise KeyError(source_key)
            if current["status"] != "running":
                self._transition_error(source_key, "error")
            connection.execute(
                "UPDATE archive_records SET status = 'error', error = ?, updated_at = ? WHERE source_key = ?",
                (message, now, source_key),
            )
            connection.execute(
                """
                INSERT INTO archive_errors (source_key, attempt, kind, error, created_at)
                VALUES (?, ?, 'error', ?, ?)
                """,
                (source_key, current["attempts"], message, now),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        return self._record(source_key)

    def requeue(self, source_key: str, reason: str) -> StateRecord:
        """Invalidate output evidence while retaining the source identity hash."""
        connection = self._connection_required()
        current = self._record(source_key)
        now = _utc_now()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE archive_records
                SET status = 'pending', output_sha256 = NULL, output_bytes = NULL,
                    shape = NULL, dtype = NULL, error = ?, started_at = NULL,
                    verified_at = NULL, updated_at = ?
                WHERE source_key = ?
                """,
                (_text(reason, "reason"), now, source_key),
            )
            connection.execute(
                """
                INSERT INTO archive_errors (source_key, attempt, kind, error, created_at)
                VALUES (?, ?, 'requeue', ?, ?)
                """,
                (source_key, current.attempts, reason, now),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        return self._record(source_key)

    def counts(self, *, max_attempts: int = 5) -> dict[str, int]:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        row = (
            self._connection_required()
            .execute(
                """
            SELECT
                COUNT(*) AS total,
                SUM(status = 'pending') AS pending,
                SUM(status = 'running') AS running,
                SUM(status = 'verified') AS verified,
                SUM(status = 'error') AS error,
                SUM(status = 'error' AND attempts < ?) AS retryable_errors,
                SUM(status = 'error' AND attempts >= ?) AS terminal_errors
            FROM archive_records
            """,
                (max_attempts, max_attempts),
            )
            .fetchone()
        )
        counts = {name: int(value or 0) for name, value in dict(row).items()}
        counts["unresolved"] = counts["total"] - counts["verified"]
        return counts

    def byte_totals(self) -> dict[str, int]:
        row = (
            self._connection_required()
            .execute(
                """
            SELECT COALESCE(SUM(source_bytes), 0) AS source_bytes,
                   COALESCE(SUM(output_bytes), 0) AS output_bytes
            FROM archive_records WHERE status = 'verified'
            """,
            )
            .fetchone()
        )
        return {name: int(value) for name, value in dict(row).items()}

    def close(self) -> None:
        connection = self._connection
        if connection is None:
            return
        if not self._read_only:
            connection.commit()
        connection.close()
        self._connection = None

    def _create_schema(self) -> None:
        connection = self._connection_required()
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version not in {0, SCHEMA_VERSION}:
            raise ArchiveStateError(f"unsupported archive ledger schema {version}; expected {SCHEMA_VERSION}")
        with connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS archive_records (
                    source_key TEXT PRIMARY KEY,
                    source_uri TEXT NOT NULL,
                    destination_relative TEXT NOT NULL,
                    expected_size INTEGER NOT NULL CHECK (expected_size >= 0),
                    expected_etag TEXT NOT NULL,
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
                );
                CREATE INDEX IF NOT EXISTS archive_errors_source_key_event
                    ON archive_errors (source_key, event_id);
                CREATE TABLE IF NOT EXISTS archive_manifest_binding (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
                    artifact_sha256 TEXT NOT NULL CHECK (length(artifact_sha256) = 64),
                    record_count INTEGER NOT NULL CHECK (record_count >= 0),
                    bound_at TEXT NOT NULL,
                    last_validated_at TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS archive_records_identity_immutable
                BEFORE UPDATE OF source_key, source_uri, destination_relative,
                                 expected_size, expected_etag, expected_version_id
                ON archive_records
                WHEN EXISTS (SELECT 1 FROM archive_manifest_binding WHERE singleton = 1)
                BEGIN
                    SELECT RAISE(ABORT, 'bound archive manifest identities are immutable');
                END;
                CREATE TRIGGER IF NOT EXISTS archive_records_bound_insert_forbidden
                BEFORE INSERT ON archive_records
                WHEN EXISTS (SELECT 1 FROM archive_manifest_binding WHERE singleton = 1)
                BEGIN
                    SELECT RAISE(ABORT, 'cannot insert into a bound archive manifest');
                END;
                CREATE TRIGGER IF NOT EXISTS archive_records_bound_delete_forbidden
                BEFORE DELETE ON archive_records
                WHEN EXISTS (SELECT 1 FROM archive_manifest_binding WHERE singleton = 1)
                BEGIN
                    SELECT RAISE(ABORT, 'cannot delete from a bound archive manifest');
                END;
                """,
            )
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._require_schema()

    def _require_schema(self) -> None:
        version = int(self._connection_required().execute("PRAGMA user_version").fetchone()[0])
        if version != SCHEMA_VERSION:
            raise ArchiveStateError(f"unsupported archive ledger schema {version}; expected {SCHEMA_VERSION}")

    def _records(self, sql: str, parameters: Sequence[object]) -> Iterator[StateRecord]:
        last_key: str | None = None
        while True:
            suffix = "" if last_key is None else " AND source_key > ?"
            values = [*parameters]
            if last_key is not None:
                values.append(last_key)
            values.append(1_000)
            rows = (
                self._connection_required()
                .execute(
                    f"{sql}{suffix} ORDER BY source_key LIMIT ?",
                    values,
                )
                .fetchall()
            )
            if not rows:
                return
            yield from map(_record_from_row, rows)
            last_key = str(rows[-1]["source_key"])

    def _record(self, source_key: str) -> StateRecord:
        row = (
            self._connection_required()
            .execute(
                "SELECT * FROM archive_records WHERE source_key = ?",
                (source_key,),
            )
            .fetchone()
        )
        if row is None:
            raise KeyError(source_key)
        return _record_from_row(row)

    def _transition_error(self, source_key: str, target: str) -> None:
        row = (
            self._connection_required()
            .execute(
                "SELECT status FROM archive_records WHERE source_key = ?",
                (source_key,),
            )
            .fetchone()
        )
        if row is None:
            raise KeyError(source_key)
        raise ArchiveStateError(f"cannot transition {source_key!r} from {row['status']!r} to {target!r}")

    def _connection_required(self) -> sqlite3.Connection:
        if self._connection is None:
            raise ArchiveStateError("archive ledger is closed")
        return self._connection


def _identity_values(record: ManifestIdentity) -> tuple[str, str, str, int, str, str | None]:
    if not isinstance(record, ManifestIdentity):
        raise TypeError("manifest rows must be ManifestIdentity values")
    return (
        _text(record.source_key, "source_key"),
        _text(record.source_uri, "source_uri"),
        _text(record.destination_relative, "destination_relative"),
        _nonnegative(record.expected_size, "expected_size"),
        _text(record.expected_etag, "expected_etag"),
        None if record.expected_version_id is None else _text(record.expected_version_id, "expected_version_id"),
    )


def _manifest_digest(connection: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    rows = connection.execute(
        """
        SELECT source_key, source_uri, destination_relative, expected_size,
               expected_etag, expected_version_id
        FROM archive_manifest_stage ORDER BY source_key
        """,
    )
    for row in rows:
        payload = json.dumps(list(row), ensure_ascii=True, separators=(",", ":"), allow_nan=False)
        digest.update(f"{payload}\n".encode("ascii"))
    return digest.hexdigest()


def _record_from_row(row: sqlite3.Row) -> StateRecord:
    shape = None if row["shape"] is None else tuple(int(value) for value in json.loads(row["shape"]))
    return StateRecord(
        source_key=str(row["source_key"]),
        source_uri=str(row["source_uri"]),
        destination_relative=str(row["destination_relative"]),
        expected_size=int(row["expected_size"]),
        expected_etag=str(row["expected_etag"]),
        expected_version_id=row["expected_version_id"],
        status=str(row["status"]),
        attempts=int(row["attempts"]),
        source_sha256=row["source_sha256"],
        output_sha256=row["output_sha256"],
        source_bytes=row["source_bytes"],
        output_bytes=row["output_bytes"],
        shape=shape,
        dtype=row["dtype"],
        error=row["error"],
    )


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be non-empty text")
    return value


def _nonnegative(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _positive(value: object, name: str) -> int:
    result = _nonnegative(value, name)
    if result == 0:
        raise ValueError(f"{name} must be positive")
    return result


def _digest(value: object, name: str) -> str:
    text = _text(value, name)
    if _SHA256.fullmatch(text) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return text


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
