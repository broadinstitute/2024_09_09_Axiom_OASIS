# Copyright (c) 2026 Broad Institute.
# ruff: noqa: D101, D102, PT009, PT027
"""Regression tests for deterministic, read-only receipt verification."""

from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from unittest.mock import patch

from image_archive.__main__ import main
from image_archive.archive import iter_manifest_identities, run_archive, validate_archive
from image_archive.io import exclusive_workflow_lock, sha256_file
from image_archive.receipt import verify_receipt
from image_archive.tests.test_image_archive import _inventory

if TYPE_CHECKING:
    from image_archive.contract import Contract

_EVIDENCE_SQL = (
    "SELECT source_key, source_uri, destination_relative, expected_size, "
    "expected_etag, expected_version_id, status, source_sha256, output_sha256, "
    "source_bytes, output_bytes, shape, dtype FROM archive_records ORDER BY source_key ASC"
)
_EVIDENCE_ROW_SERIALIZATION = (
    "CPython 3.11.15 json.dumps(list(row), ensure_ascii=True, separators=(',', ':'), allow_nan=False)"
)
_EVIDENCE_VALUE_TYPES = (
    "SQLite NULL becomes JSON null, INTEGER becomes a JSON integer, and TEXT becomes a JSON string; "
    "selected columns contain no REAL or BLOB values"
)


def _write_contract(path: Path, contract: Contract) -> None:
    channels = "\n".join(
        f"[[channels]]\nsource = {json.dumps(source)}\ndestination = {json.dumps(source)}\nchannel_number = {number}"
        for source, number in contract.channels.items()
    )
    batches = "\n".join(f"[[batches]]\nname = {json.dumps(name)}" for name in contract.batches)
    path.write_text(
        f"""[index]
record_id = {contract.index.record_id}
filename = {json.dumps(contract.index.filename)}
url = {json.dumps(contract.index.url)}
size_bytes = {contract.index.size_bytes}
md5 = {json.dumps(contract.index.md5)}
sha256 = {json.dumps(contract.index.sha256)}

[source]
bucket = {json.dumps(contract.source.bucket)}
prefix = {json.dumps(contract.source.prefix)}
anonymous = true

[inventory]
row_count = {contract.inventory.row_count}
complete_unique_tiff_uris = {contract.inventory.complete_unique_tiff_uris}
incomplete_rows = {contract.inventory.incomplete_rows}
field_count = {contract.inventory.field_count}
plate_count = {contract.inventory.plate_count}
channel_count = {contract.inventory.channel_count}
manifest_sha256 = {json.dumps(contract.inventory.manifest_sha256)}
rejected_sha256 = {json.dumps(contract.inventory.rejected_sha256)}

[codec]
id = {json.dumps(contract.codec.id)}
name = {json.dumps(contract.codec.name)}
profile = {json.dumps(contract.codec.profile)}
lossless = false
distance = {contract.codec.distance}
effort = {contract.codec.effort}
reference_repository = {json.dumps(contract.codec.reference_repository)}
reference_commit = {json.dumps(contract.codec.reference_commit)}
reference_path = {json.dumps(contract.codec.reference_path)}
reference_sha256 = {json.dumps(contract.codec.reference_sha256)}
reference_tier = {json.dumps(contract.codec.reference_tier)}

[destination]
root = {json.dumps(str(contract.destination.root))}
object_template = {json.dumps(contract.destination.object_template)}

{channels}

{batches}
""",
        encoding="utf-8",
    )


def _canonical_rows_digest(connection: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    for row in connection.execute(_EVIDENCE_SQL):
        payload = json.dumps(list(row), ensure_ascii=True, separators=(",", ":"), allow_nan=False)
        digest.update(f"{payload}\n".encode("ascii"))
    return digest.hexdigest()


def _manifest_digest(contract: Contract, inventory_path: Path) -> str:
    digest = hashlib.sha256()
    for row in iter_manifest_identities(inventory_path, contract):
        values = [
            row.source_key,
            row.source_uri,
            row.destination_relative,
            row.expected_size,
            row.expected_etag,
            row.expected_version_id,
        ]
        payload = json.dumps(values, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
        digest.update(f"{payload}\n".encode("ascii"))
    return digest.hexdigest()


def _write_receipt(
    path: Path,
    contract_path: Path,
    contract: Contract,
    work_dir: Path,
    *,
    overrides: dict[str, object] | None = None,
) -> None:
    values = overrides or {}

    def expected(name: str, default: object) -> object:
        return values.get(name, default)

    inventory_path = work_dir / "inventory.parquet"
    rejected_path = work_dir / "rejected.parquet"
    state_path = work_dir / "state.sqlite3"
    validation_path = work_dir / "validation.json"
    validation = json.loads(validation_path.read_text())
    with sqlite3.connect(state_path) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*), SUM(status = 'verified'), SUM(status = 'pending'),
                   SUM(status = 'running'), SUM(status = 'error'),
                   SUM(source_bytes), SUM(output_bytes)
            FROM archive_records
            """,
        ).fetchone()
        evidence_sha256 = _canonical_rows_digest(connection)
    total, verified, pending, running, error, source_bytes, output_bytes = map(int, row)
    unresolved = total - verified
    manifest_sha256 = sha256_file(inventory_path)
    rejected_sha256 = sha256_file(rejected_path)
    manifest_identity = _manifest_digest(contract, inventory_path)
    failures = validation["failures"]
    state_counts = validation["state_counts"]
    path.write_text(
        f"""schema_version = 1
receipt_id = "synthetic-reconstruction"
created_at_utc = "1900-01-01T00:00:00Z"
host = "historical-host"
implementation_commit = "historical-commit"
contract_path = "/historical/checkout/images/source.toml"
contract_sha256 = {json.dumps(expected("contract_sha256", sha256_file(contract_path)))}

[index]
record_id = {contract.index.record_id}
filename = {json.dumps(contract.index.filename)}
url = {json.dumps(contract.index.url)}
size_bytes = {contract.index.size_bytes}
md5 = {json.dumps(contract.index.md5)}
sha256 = {json.dumps(contract.index.sha256)}

[manifest]
inventory_sha256 = {json.dumps(expected("inventory_sha256", manifest_sha256))}
identity_sha256 = {json.dumps(expected("identity_sha256", manifest_identity))}
complete_unique_tiff_uris = {contract.inventory.complete_unique_tiff_uris}
rejected_sha256 = {json.dumps(expected("rejected_sha256", rejected_sha256))}
rejected_rows = {contract.inventory.incomplete_rows}

[ledger]
path = "/historical/archive/state.sqlite3"
schema_version = 4
record_count = {total}
evidence_sha256_scope = "archive_record_evidence_canonical_json_lines_v1"
evidence_sha256_order = "source_key ASC"
evidence_sha256_fields = [
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
]
evidence_sql = {json.dumps(_EVIDENCE_SQL)}
evidence_row_serialization = {json.dumps(_EVIDENCE_ROW_SERIALIZATION)}
evidence_value_types = {json.dumps(_EVIDENCE_VALUE_TYPES)}
evidence_encoding = "ASCII"
evidence_line_terminator = "one LF byte after every row, including the final row"
evidence_sha256 = {json.dumps(expected("evidence_sha256", evidence_sha256))}
total_attempts = 999
attempt_1_rows = 998
attempt_2_rows = 1

[execution]
working_directory = "/historical/checkout"

[conversion]
service_completed_at_utc = "1900-01-02T00:00:00Z"
historical_command = ["old-package", "archive", "--old-path"]

[conversion.result]
total = {total}
verified = {verified}
pending = {pending}
running = {running}
error = {error}
unresolved = {unresolved}
source_bytes = {source_bytes}
output_bytes = {expected("output_bytes", output_bytes)}

[validation]
verified_only = false
command = ["old-package", "validate", "--old-path"]

[validation.result]
audit_passed = {str(validation["audit_passed"]).lower()}
complete = {str(expected("validation_complete", validation["complete"])).lower()}
checked = {validation["checked"]}
expected_complete = {validation["expected_complete"]}
invalid = {validation["invalid"]}
failure_count = {len(failures)}
failure_details_truncated = {str(validation["failure_details_truncated"]).lower()}
inventory_rows = {validation["inventory_rows"]}
rejected_rows = {validation["rejected_rows"]}
total = {state_counts["total"]}
verified = {state_counts["verified"]}
pending = {state_counts["pending"]}
running = {state_counts["running"]}
error = {state_counts["error"]}
unresolved = {state_counts["unresolved"]}

[validation.report]
path = "/historical/archive/validation.json"
sha256 = {json.dumps(expected("validation_sha256", sha256_file(validation_path)))}
mtime_utc = "1900-01-03T00:00:00Z"
""",
        encoding="utf-8",
    )


def _completed_fixture(root: Path) -> tuple[Contract, Path, Path]:
    contract, work_dir, client = _inventory(root)
    inventory_path = work_dir / "inventory.parquet"
    state_path = work_dir / "state.sqlite3"
    with patch("image_archive.archive._s3_client", return_value=client):
        result = run_archive(
            contract,
            inventory_path=inventory_path,
            state_path=state_path,
            workers=1,
            max_in_flight=1,
        )
    if result.state_counts["verified"] != 1:
        raise AssertionError(result)
    validation = validate_archive(
        contract,
        inventory_path=inventory_path,
        rejected_path=work_dir / "rejected.parquet",
        state_path=state_path,
        workers=1,
        report_path=work_dir / "validation.json",
    )
    if not validation.complete:
        raise AssertionError(validation)
    (contract.destination.root / ".oasis-images.lock").write_text("{}\n", encoding="utf-8")
    contract_path = root / "source.toml"
    receipt_path = root / "receipt.toml"
    _write_contract(contract_path, contract)
    _write_receipt(receipt_path, contract_path, contract, work_dir)
    return contract, contract_path, receipt_path


def _snapshot(root: Path) -> dict[str, tuple[int, str]]:
    return {
        path.relative_to(root).as_posix(): (path.stat().st_mtime_ns, sha256_file(path))
        for path in root.rglob("*")
        if path.is_file()
    }


class ReceiptVerificationTest(unittest.TestCase):
    def test_success_is_deterministic_and_changes_no_files(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _, contract_path, receipt_path = _completed_fixture(root)
            before = _snapshot(root)

            result = verify_receipt(contract_path, receipt_path)

            self.assertTrue(result["matches"])
            self.assertEqual(result["mismatches"], [])
            self.assertEqual(_snapshot(root), before)

    def test_cli_aggregates_deterministic_mismatches(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            contract, contract_path, receipt_path = _completed_fixture(root)
            work_dir = contract.destination.root / "_archive"
            _write_receipt(
                receipt_path,
                contract_path,
                contract,
                work_dir,
                overrides={
                    "contract_sha256": "0" * 64,
                    "evidence_sha256": "4" * 64,
                    "identity_sha256": "3" * 64,
                    "inventory_sha256": "1" * 64,
                    "output_bytes": 999,
                    "rejected_sha256": "2" * 64,
                    "validation_complete": False,
                    "validation_sha256": "5" * 64,
                },
            )
            with sqlite3.connect(work_dir / "state.sqlite3") as connection:
                connection.execute("PRAGMA user_version = 3")
                connection.execute(
                    "UPDATE archive_manifest_binding SET artifact_sha256 = ? WHERE singleton = 1",
                    ("6" * 64,),
                )
                connection.commit()
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                status = main(
                    [
                        "verify-receipt",
                        "--contract",
                        str(contract_path),
                        "--receipt",
                        str(receipt_path),
                    ],
                )

            report = json.loads(stdout.getvalue())
            self.assertEqual(status, 1)
            self.assertFalse(report["matches"])
            joined = "\n".join(report["mismatches"])
            for label in (
                "contract SHA-256",
                "inventory SHA-256 against receipt",
                "rejected SHA-256 against receipt",
                "manifest identity SHA-256",
                "ledger schema against implementation",
                "ledger manifest artifact binding",
                "ledger evidence SHA-256",
                "final ledger output_bytes",
                "validation report SHA-256",
                "validation result complete",
            ):
                self.assertIn(label, joined)

    def test_historical_execution_metadata_is_ignored(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _, contract_path, receipt_path = _completed_fixture(root)
            text = receipt_path.read_text()
            text = text.replace('host = "historical-host"', 'host = "another-host"')
            text = text.replace("1900-01-01T00:00:00Z", "2099-01-01T00:00:00Z")
            text = text.replace(
                'contract_path = "/historical/checkout/images/source.toml"',
                'contract_path = "old/path"',
            )
            text = text.replace("total_attempts = 999", "total_attempts = 123456")
            text = text.replace("attempt_1_rows = 998", "attempt_1_rows = 1")
            text = text.replace("attempt_2_rows = 1", "attempt_2_rows = 123455")
            text = text.replace('working_directory = "/historical/checkout"', 'working_directory = "/elsewhere"')
            text = text.replace("1900-01-02T00:00:00Z", "2099-01-02T00:00:00Z")
            text = text.replace(
                'historical_command = ["old-package", "archive", "--old-path"]',
                'historical_command = ["other"]',
            )
            text = text.replace('command = ["old-package", "validate", "--old-path"]', 'command = ["other"]')
            text = text.replace("1900-01-03T00:00:00Z", "2099-01-03T00:00:00Z")
            receipt_path.write_text(text, encoding="utf-8")

            result = verify_receipt(contract_path, receipt_path)

            self.assertTrue(result["matches"])
            self.assertEqual(result["historical_context"]["host"], "another-host")

    def test_refuses_to_read_while_mutating_lock_is_held(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            contract, contract_path, receipt_path = _completed_fixture(root)
            lock_path = contract.destination.root / ".oasis-images.lock"

            with (
                exclusive_workflow_lock(lock_path, "archive"),
                self.assertRaisesRegex(RuntimeError, "already held"),
            ):
                verify_receipt(contract_path, receipt_path)


if __name__ == "__main__":
    unittest.main()
