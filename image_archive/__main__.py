# ruff: noqa: CPY001, EM101, EM102, TRY003
"""Command-line interface for the JPEG XL image archive."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Final

from .archive import DEFAULT_MAX_CONSECUTIVE_FAILURES, print_json, run_archive, state_report, validate_archive
from .contract import Contract, load_contract
from .inventory import build_inventory, require_remote_inventory
from .io import atomic_write_json, ensure_group_directories, exclusive_workflow_lock
from .receipt import verify_receipt

DEFAULT_CONTRACT: Final = Path("image_archive/axiom/source.toml")
METADATA_DIRECTORY: Final = "_archive"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m image_archive",
        description="Run the canonical-manifest JPEG XL archive engine; Axiom is the default contract.",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    inventory = commands.add_parser(
        "inventory",
        help="run the Axiom-only index compiler and optional public S3 snapshot",
    )
    _add_contract_and_work_dir(inventory)
    inventory.add_argument("--index", type=Path, help="reuse an exact local copy of the pinned index")
    inventory.add_argument(
        "--remote-snapshot",
        action="store_true",
        help="paginate S3, require every indexed object, and report prefix extras",
    )

    archive = commands.add_parser("archive", help="start or resume bounded TIFF-to-JPEG-XL conversion")
    _add_contract_and_work_dir(archive)
    archive.add_argument("--workers", type=int, default=_default_workers())
    archive.add_argument("--max-in-flight", type=int)
    archive.add_argument("--max-attempts", type=int, default=5)
    archive.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=DEFAULT_MAX_CONSECUTIVE_FAILURES,
        help="stop scheduling after this many consecutive failed conversion attempts",
    )
    archive.add_argument(
        "--audit-verified",
        action="store_true",
        help="hash and decode all prior verified outputs before resuming (expensive)",
    )

    status = commands.add_parser("status", help="show durable conversion progress")
    _add_contract_and_work_dir(status)
    status.add_argument("--max-attempts", type=int, default=5)
    status.add_argument("--write", action="store_true", help="also write progress.json")

    validate = commands.add_parser("validate", help="hash and decode verified outputs")
    _add_contract_and_work_dir(validate)
    validate.add_argument("--workers", type=int, default=_default_workers())
    validate.add_argument("--max-attempts", type=int, default=5)

    receipt = commands.add_parser(
        "verify-receipt",
        help="verify the Axiom-only historical receipt",
    )
    receipt.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_CONTRACT,
        help="archive contract (default: Axiom OASIS)",
    )
    receipt.add_argument("--receipt", type=Path, required=True)
    return parser


def _add_contract_and_work_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_CONTRACT,
        help="archive contract (default: Axiom OASIS)",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        help="metadata directory (default: <destination-root>/_archive)",
    )


def main(arguments: list[str] | None = None) -> int:  # noqa: PLR0911
    """Run one archive command and return a process exit status."""
    parser = _parser()
    parsed = parser.parse_args(arguments)
    logging.basicConfig(
        level=getattr(logging, parsed.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        if parsed.command == "verify-receipt":
            return _verify_receipt_command(parsed)
        contract = load_contract(parsed.contract)
        work_dir = parsed.work_dir or contract.destination.root / METADATA_DIRECTORY
        if parsed.command == "inventory":
            return _inventory_command(parsed, contract, work_dir)
        if parsed.command == "archive":
            return _archive_command(parsed, contract, work_dir)
        if parsed.command == "status":
            return _status_command(parsed, contract, work_dir)
        if parsed.command == "validate":
            return _validate_command(parsed, contract, work_dir)
        parser.error(f"unknown command: {parsed.command}")
    except KeyboardInterrupt:
        logging.getLogger(__name__).warning("interrupted; running rows will be recovered on resume")
        return 130
    except Exception as error:  # noqa: BLE001 - CLI must fail closed with one clear error
        logging.getLogger(__name__).error(  # noqa: TRY400
            "%s: %s",
            type(error).__name__,
            error,
        )
        return 1
    return 2


def _inventory_command(parsed: argparse.Namespace, contract: Contract, work_dir: Path) -> int:
    destination_root = contract.destination.root
    work_is_in_destination = work_dir.resolve().is_relative_to(destination_root.resolve())
    if work_is_in_destination or destination_root.exists():
        _require_destination_storage(contract.destination.root)
    if work_is_in_destination:
        ensure_group_directories(contract.destination.root, work_dir)
        ensure_group_directories(contract.destination.root, work_dir / "cache")
    with exclusive_workflow_lock(_workflow_lock_path(contract, work_dir), "inventory"):
        if destination_root.exists():
            _require_destination_storage(destination_root)
        artifacts = build_inventory(
            contract,
            work_dir=work_dir,
            index_path=parsed.index,
            remote_snapshot=parsed.remote_snapshot,
        )
    print_json(
        {
            "index": str(artifacts.index_path),
            "inventory": str(artifacts.inventory_path),
            "rejected": str(artifacts.rejected_path),
            "remote_snapshot": parsed.remote_snapshot,
            "summary": str(artifacts.summary_path),
        },
    )
    return 0


def _archive_command(parsed: argparse.Namespace, contract: Contract, work_dir: Path) -> int:
    _require_destination_storage(contract.destination.root)
    if work_dir.resolve().is_relative_to(contract.destination.root.resolve()):
        ensure_group_directories(contract.destination.root, work_dir)
    with exclusive_workflow_lock(_workflow_lock_path(contract, work_dir), "archive"):
        _require_destination_storage(contract.destination.root)
        require_remote_inventory(contract, work_dir)
        max_in_flight = parsed.max_in_flight or parsed.workers * 2
        result = run_archive(
            contract,
            inventory_path=work_dir / "inventory.parquet",
            state_path=work_dir / "state.sqlite3",
            workers=parsed.workers,
            max_in_flight=max_in_flight,
            max_attempts=parsed.max_attempts,
            max_consecutive_failures=parsed.max_consecutive_failures,
            audit_verified=parsed.audit_verified,
        )
    print_json(result)
    if result.failed or result.state_counts["error"] or result.state_counts["running"]:
        return 1
    if result.state_counts["unresolved"]:
        return 1
    return 0


def _status_command(
    parsed: argparse.Namespace,
    contract: Contract,
    work_dir: Path,
) -> int:
    progress = state_report(work_dir / "state.sqlite3", max_attempts=parsed.max_attempts)
    progress["expected_complete"] = contract.inventory.complete_unique_tiff_uris
    counts = progress["counts"]
    if not isinstance(counts, dict):
        raise TypeError("state report counts are not a dictionary")
    binding = progress.get("manifest_binding")
    binding_matches = (
        isinstance(binding, dict)
        and binding.get("artifact_sha256") == contract.inventory.manifest_sha256
        and binding.get("record_count") == contract.inventory.complete_unique_tiff_uris
    )
    progress["ledger_complete"] = (
        binding_matches
        and counts["verified"] == contract.inventory.complete_unique_tiff_uris
        and counts["unresolved"] == 0
    )
    if parsed.write:
        progress_path = work_dir / "progress.json"
        atomic_write_json(progress_path, progress)
        progress["progress_path"] = str(progress_path)
    print_json(progress)
    return 0


def _validate_command(parsed: argparse.Namespace, contract: Contract, work_dir: Path) -> int:
    _require_destination_storage(contract.destination.root)
    with exclusive_workflow_lock(_workflow_lock_path(contract, work_dir), "validate"):
        _require_destination_storage(contract.destination.root)
        require_remote_inventory(contract, work_dir)
        result = validate_archive(
            contract,
            inventory_path=work_dir / "inventory.parquet",
            rejected_path=work_dir / "rejected.parquet",
            state_path=work_dir / "state.sqlite3",
            workers=parsed.workers,
            max_attempts=parsed.max_attempts,
            report_path=work_dir / "validation.json",
        )
    print_json(result)
    return 0 if result.complete else 1


def _verify_receipt_command(parsed: argparse.Namespace) -> int:
    result = verify_receipt(parsed.contract, parsed.receipt)
    print_json(result)
    return 0 if result["matches"] else 1


def _require_destination_storage(destination_root: Path) -> None:
    """Require a pre-created, unsymlinked destination on a non-root mount."""
    if not destination_root.is_absolute():
        raise ValueError(f"archive root must be absolute: {destination_root}")
    current = Path(destination_root.anchor)
    for component in destination_root.parts[1:]:
        current /= component
        if current.is_symlink():
            raise RuntimeError(f"archive root path contains a symlink: {current}")
    if not destination_root.is_dir():
        raise FileNotFoundError(f"archive root must be provisioned before use: {destination_root}")
    if not os.access(destination_root, os.W_OK | os.X_OK):
        raise PermissionError(f"archive root is not writable: {destination_root}")
    mount = destination_root
    while mount != mount.parent and not mount.is_mount():
        mount = mount.parent
    if mount == Path(mount.anchor):
        raise RuntimeError(f"archive root is on the root filesystem: {destination_root}")


def _workflow_lock_path(contract: Contract, work_dir: Path) -> Path:
    """Use one destination-scoped lock once the canonical archive root exists.

    The ``.oasis-images`` name is deliberately not renamed with the package. A
    lock only excludes processes that agree on its path, so changing the name
    would let a checkout of the pre-rename code and a checkout of this code hold
    different locks and mutate one destination at the same time. Existing
    archives already carry a lock under this name.
    """
    if contract.destination.root.exists():
        return contract.destination.root / ".oasis-images.lock"
    return work_dir / ".oasis-images.lock"


def _default_workers() -> int:
    cpu_count = os.cpu_count() or 4
    return max(1, min(32, cpu_count // 4))


if __name__ == "__main__":
    sys.exit(main())
