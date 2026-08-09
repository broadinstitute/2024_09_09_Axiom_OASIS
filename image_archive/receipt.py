# Copyright (c) 2026 Broad Institute.
# ruff: noqa: EM101, EM102, PLR0915, TRY003, TRY301
"""Read-only comparison of a reconstructed archive with a historical receipt."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import pyarrow.parquet as pq
import tomllib

from .archive import iter_manifest_identities
from .contract import Contract, load_contract
from .io import read_only_workflow_lock, sha256_file
from .state import SCHEMA_VERSION

if TYPE_CHECKING:
    from collections.abc import Mapping

_EVIDENCE_FIELDS: Final = (
    "source_key",
    "source_uri",
    "destination_relative",
    "expected_size",
    "expected_etag",
    "expected_version_id",
    "status",
    "source_sha256",
    "output_sha256",
    "source_bytes",
    "output_bytes",
    "shape",
    "dtype",
)
_EVIDENCE_SQL: Final = (
    "SELECT source_key, source_uri, destination_relative, expected_size, "
    "expected_etag, expected_version_id, status, source_sha256, output_sha256, "
    "source_bytes, output_bytes, shape, dtype FROM archive_records ORDER BY source_key ASC"
)
_FINAL_COUNT_FIELDS: Final = ("total", "verified", "pending", "running", "error", "unresolved")
_VALIDATION_FIELDS: Final = (
    "audit_passed",
    "complete",
    "checked",
    "expected_complete",
    "invalid",
    "failure_details_truncated",
    "inventory_rows",
    "rejected_rows",
)


def verify_receipt(contract_path: Path, receipt_path: Path) -> dict[str, Any]:
    """Compare deterministic archive evidence without changing archive state."""
    contract_path = Path(contract_path)
    receipt_path = Path(receipt_path)
    if not contract_path.is_file():
        raise FileNotFoundError(f"contract does not exist: {contract_path}")
    if not receipt_path.is_file():
        raise FileNotFoundError(f"receipt does not exist: {receipt_path}")

    receipt = _load_receipt(receipt_path)
    contract_sha256 = sha256_file(contract_path)
    contract = load_contract(contract_path)
    mismatches: list[str] = []

    _compare(mismatches, "receipt schema version", receipt.get("schema_version"), 1)
    receipt_id = receipt.get("receipt_id")
    if not isinstance(receipt_id, str) or not receipt_id:
        _compare(mismatches, "receipt ID", receipt_id, "non-empty text")
    _compare(mismatches, "contract SHA-256", contract_sha256, receipt.get("contract_sha256"))
    index = _table(receipt, "index")
    for field in ("record_id", "filename", "url", "size_bytes", "md5", "sha256"):
        _compare(mismatches, f"index {field}", getattr(contract.index, field), index.get(field))

    manifest = _table(receipt, "manifest")
    ledger = _table(receipt, "ledger")
    conversion_result = _table(_table(receipt, "conversion"), "result")
    validation = _table(receipt, "validation")
    validation_result = _table(validation, "result")
    validation_receipt_report = _table(validation, "report")

    work_dir = contract.destination.root / "_archive"
    inventory_path = work_dir / "inventory.parquet"
    rejected_path = work_dir / "rejected.parquet"
    state_path = work_dir / "state.sqlite3"
    validation_path = work_dir / "validation.json"
    lock_path = contract.destination.root / ".oasis-images.lock"

    with read_only_workflow_lock(lock_path):
        inventory_sha256 = sha256_file(inventory_path)
        rejected_sha256 = sha256_file(rejected_path)
        inventory_rows = _parquet_rows(inventory_path)
        rejected_rows = _parquet_rows(rejected_path)
        manifest_identity_sha256 = _manifest_identity_sha256(inventory_path, contract)

        _compare(mismatches, "inventory SHA-256 against contract", inventory_sha256, contract.inventory.manifest_sha256)
        _compare(mismatches, "inventory SHA-256 against receipt", inventory_sha256, manifest.get("inventory_sha256"))
        _compare(
            mismatches,
            "inventory row count against contract",
            inventory_rows,
            contract.inventory.complete_unique_tiff_uris,
        )
        _compare(
            mismatches,
            "inventory row count against receipt",
            inventory_rows,
            manifest.get("complete_unique_tiff_uris"),
        )
        _compare(mismatches, "rejected SHA-256 against contract", rejected_sha256, contract.inventory.rejected_sha256)
        _compare(mismatches, "rejected SHA-256 against receipt", rejected_sha256, manifest.get("rejected_sha256"))
        _compare(
            mismatches,
            "rejected row count against contract",
            rejected_rows,
            contract.inventory.incomplete_rows,
        )
        _compare(mismatches, "rejected row count against receipt", rejected_rows, manifest.get("rejected_rows"))
        _compare(
            mismatches,
            "manifest identity SHA-256",
            manifest_identity_sha256,
            manifest.get("identity_sha256"),
        )

        with closing(_open_immutable_ledger(state_path)) as connection:
            ledger_schema = int(connection.execute("PRAGMA user_version").fetchone()[0])
            ledger_rows = int(connection.execute("SELECT COUNT(*) FROM archive_records").fetchone()[0])
            binding = connection.execute(
                "SELECT sha256, artifact_sha256, record_count FROM archive_manifest_binding WHERE singleton = 1",
            ).fetchone()
            counts = _ledger_counts(connection)
            byte_totals = _ledger_byte_totals(connection)
            ledger_evidence_sha256 = _ledger_evidence_sha256(connection, ledger, mismatches)

        _compare(mismatches, "ledger schema against implementation", ledger_schema, SCHEMA_VERSION)
        _compare(mismatches, "ledger schema against receipt", ledger_schema, ledger.get("schema_version"))
        _compare(mismatches, "ledger record count against inventory", ledger_rows, inventory_rows)
        _compare(mismatches, "ledger record count against receipt", ledger_rows, ledger.get("record_count"))
        if binding is None:
            mismatches.append("ledger manifest binding: expected one binding row, actual=None")
        else:
            _compare(mismatches, "ledger manifest identity binding", str(binding[0]), manifest_identity_sha256)
            _compare(mismatches, "ledger manifest artifact binding", str(binding[1]), inventory_sha256)
            _compare(mismatches, "ledger manifest record binding", int(binding[2]), inventory_rows)
        _compare(
            mismatches,
            "ledger evidence SHA-256",
            ledger_evidence_sha256,
            ledger.get("evidence_sha256"),
        )
        for field in _FINAL_COUNT_FIELDS:
            _compare(mismatches, f"final ledger count {field}", counts[field], conversion_result.get(field))
        for field in ("source_bytes", "output_bytes"):
            _compare(mismatches, f"final ledger {field}", byte_totals[field], conversion_result.get(field))

        validation_report_sha256 = sha256_file(validation_path)
        validation_report = _load_json(validation_path)
        _compare(
            mismatches,
            "validation report SHA-256",
            validation_report_sha256,
            validation_receipt_report.get("sha256"),
        )
        _compare(
            mismatches,
            "validation verified_only",
            validation_report.get("verified_only"),
            validation.get("verified_only"),
        )
        for field in _VALIDATION_FIELDS:
            _compare(
                mismatches,
                f"validation result {field}",
                validation_report.get(field),
                validation_result.get(field),
            )
        failures = validation_report.get("failures")
        failure_count = len(failures) if isinstance(failures, list) else None
        _compare(mismatches, "validation result failure_count", failure_count, validation_result.get("failure_count"))
        validation_counts = validation_report.get("state_counts")
        for field in _FINAL_COUNT_FIELDS:
            actual = validation_counts.get(field) if isinstance(validation_counts, dict) else None
            _compare(mismatches, f"validation result {field}", actual, validation_result.get(field))

    return {
        "checked": {
            "contract_sha256": contract_sha256,
            "inventory_rows": inventory_rows,
            "inventory_sha256": inventory_sha256,
            "ledger_evidence_sha256": ledger_evidence_sha256,
            "ledger_record_count": ledger_rows,
            "ledger_schema_version": ledger_schema,
            "manifest_identity_sha256": manifest_identity_sha256,
            "rejected_rows": rejected_rows,
            "rejected_sha256": rejected_sha256,
            "validation_report_sha256": validation_report_sha256,
        },
        "historical_context": _historical_context(receipt),
        "matches": not mismatches,
        "mismatches": mismatches,
        "receipt_id": receipt_id,
    }


def _load_receipt(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            return tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"cannot read receipt {path}: {error}") from error


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read validation report {path}: {error}") from error
    if not isinstance(value, dict):
        raise TypeError(f"validation report is not a JSON object: {path}")
    return value


def _table(value: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    table = value.get(name)
    if not isinstance(table, dict):
        raise TypeError(f"receipt [{name}] is missing or is not a table")
    return table


def _compare(mismatches: list[str], label: str, actual: object, expected: object) -> None:
    if actual != expected:
        mismatches.append(f"{label}: expected={expected!r}, actual={actual!r}")


def _parquet_rows(path: Path) -> int:
    if not path.is_file():
        raise FileNotFoundError(f"required Parquet artifact is absent: {path}")
    return pq.ParquetFile(path).metadata.num_rows


def _manifest_identity_sha256(path: Path, contract: Contract) -> str:
    digest = hashlib.sha256()
    for record in iter_manifest_identities(path, contract):
        values = (
            record.source_key,
            record.source_uri,
            record.destination_relative,
            record.expected_size,
            record.expected_etag,
            record.expected_version_id,
        )
        payload = json.dumps(values, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
        digest.update(f"{payload}\n".encode("ascii"))
    return digest.hexdigest()


def _open_immutable_ledger(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(f"archive ledger does not exist: {path}")
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro&immutable=1", uri=True)
    try:
        connection.execute("PRAGMA query_only = ON")
        if int(connection.execute("PRAGMA query_only").fetchone()[0]) != 1:
            raise RuntimeError("SQLite query_only could not be enabled")
    except BaseException:
        connection.close()
        raise
    return connection


def _ledger_counts(connection: sqlite3.Connection) -> dict[str, int]:
    row = connection.execute(
        """
        SELECT COUNT(*) AS total,
               COALESCE(SUM(status = 'pending'), 0) AS pending,
               COALESCE(SUM(status = 'running'), 0) AS running,
               COALESCE(SUM(status = 'verified'), 0) AS verified,
               COALESCE(SUM(status = 'error'), 0) AS error
        FROM archive_records
        """,
    ).fetchone()
    counts = {
        "total": int(row[0]),
        "pending": int(row[1]),
        "running": int(row[2]),
        "verified": int(row[3]),
        "error": int(row[4]),
    }
    counts["unresolved"] = counts["total"] - counts["verified"]
    return counts


def _ledger_byte_totals(connection: sqlite3.Connection) -> dict[str, int]:
    row = connection.execute(
        """
        SELECT COALESCE(SUM(source_bytes), 0), COALESCE(SUM(output_bytes), 0)
        FROM archive_records WHERE status = 'verified'
        """,
    ).fetchone()
    return {"source_bytes": int(row[0]), "output_bytes": int(row[1])}


def _ledger_evidence_sha256(
    connection: sqlite3.Connection,
    ledger: Mapping[str, Any],
    mismatches: list[str],
) -> str:
    _compare(
        mismatches,
        "ledger evidence scope",
        ledger.get("evidence_sha256_scope"),
        "archive_record_evidence_canonical_json_lines_v1",
    )
    _compare(mismatches, "ledger evidence order", ledger.get("evidence_sha256_order"), "source_key ASC")
    _compare(mismatches, "ledger evidence fields", ledger.get("evidence_sha256_fields"), list(_EVIDENCE_FIELDS))
    _compare(mismatches, "ledger evidence SQL", ledger.get("evidence_sql"), _EVIDENCE_SQL)
    _compare(
        mismatches,
        "ledger evidence row serialization",
        ledger.get("evidence_row_serialization"),
        "CPython 3.11.15 json.dumps(list(row), ensure_ascii=True, separators=(',', ':'), allow_nan=False)",
    )
    _compare(
        mismatches,
        "ledger evidence value types",
        ledger.get("evidence_value_types"),
        "SQLite NULL becomes JSON null, INTEGER becomes a JSON integer, and TEXT becomes a JSON string; "
        "selected columns contain no REAL or BLOB values",
    )
    _compare(mismatches, "ledger evidence encoding", ledger.get("evidence_encoding"), "ASCII")
    _compare(
        mismatches,
        "ledger evidence line terminator",
        ledger.get("evidence_line_terminator"),
        "one LF byte after every row, including the final row",
    )
    digest = hashlib.sha256()
    for row in connection.execute(_EVIDENCE_SQL):
        payload = json.dumps(list(row), ensure_ascii=True, separators=(",", ":"), allow_nan=False)
        digest.update(f"{payload}\n".encode("ascii"))
    return digest.hexdigest()


def _historical_context(receipt: Mapping[str, Any]) -> dict[str, Any]:
    ledger = receipt.get("ledger")
    execution = receipt.get("execution")
    validation = receipt.get("validation")
    report = validation.get("report") if isinstance(validation, dict) else None
    return {
        "attempt_1_rows": ledger.get("attempt_1_rows") if isinstance(ledger, dict) else None,
        "attempt_2_rows": ledger.get("attempt_2_rows") if isinstance(ledger, dict) else None,
        "contract_path": receipt.get("contract_path"),
        "created_at_utc": receipt.get("created_at_utc"),
        "host": receipt.get("host"),
        "implementation_commit": receipt.get("implementation_commit"),
        "ledger_path": ledger.get("path") if isinstance(ledger, dict) else None,
        "total_attempts": ledger.get("total_attempts") if isinstance(ledger, dict) else None,
        "validation_report_path": report.get("path") if isinstance(report, dict) else None,
        "working_directory": execution.get("working_directory") if isinstance(execution, dict) else None,
    }
