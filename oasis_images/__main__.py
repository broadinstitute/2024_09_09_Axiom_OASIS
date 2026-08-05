# ruff: noqa: CPY001, EM101, EM102, TRY003
"""Command-line interface for the OASIS JPEG XL image archive."""

from __future__ import annotations

import argparse
import grp
import logging
import os
import stat
import sys
from pathlib import Path
from typing import Final

from .archive import DEFAULT_MAX_CONSECUTIVE_FAILURES, print_json, run_archive, state_report, validate_archive
from .contract import Contract, load_contract
from .inventory import build_inventory, verify_inventory_artifacts
from .io import atomic_write_json, ensure_group_directories, exclusive_workflow_lock
from .plan import axiom_archive_plan

DEFAULT_CONTRACT: Final = Path("images/source.toml")
METADATA_DIRECTORY: Final = "_archive"
DATASET_NAME: Final = "cpg0037-oasis/axiom/images-jxl/v1"
DATASET_ROOT: Final = Path("/work/datasets")
DATASET_REGISTRY: Final = DATASET_ROOT / "REGISTRY.yaml"
EXPECTED_DESTINATION_ROOT: Final = DATASET_ROOT / DATASET_NAME
REQUIRED_DESTINATION_MODE: Final = stat.S_ISGID | stat.S_IRWXG


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m oasis_images",
        description="Build and verify the local Axiom OASIS JPEG XL archive.",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    inventory = commands.add_parser(
        "inventory",
        help="verify the pinned index and optionally snapshot public S3 metadata",
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
    archive.add_argument("--limit", type=int, help="convert at most this many pending images")
    archive.add_argument(
        "--audit-verified",
        action="store_true",
        help="hash and decode all prior verified outputs before resuming (expensive)",
    )

    status = commands.add_parser("status", help="show durable conversion progress")
    _add_contract_and_work_dir(status)
    status.add_argument("--max-attempts", type=int, default=5)

    report = commands.add_parser("report", help="write and show a durable progress report")
    _add_contract_and_work_dir(report)
    report.add_argument("--max-attempts", type=int, default=5)

    validate = commands.add_parser("validate", help="hash and decode verified outputs")
    _add_contract_and_work_dir(validate)
    validate.add_argument("--workers", type=int, default=_default_workers())
    validate.add_argument("--max-attempts", type=int, default=5)
    validate.add_argument(
        "--verified-only",
        action="store_true",
        help="engineering audit of current verified rows without claiming archive completeness",
    )
    return parser


def _add_contract_and_work_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
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
        contract = load_contract(parsed.contract)
        work_dir = parsed.work_dir or contract.destination.root / METADATA_DIRECTORY
        if parsed.command == "inventory":
            return _inventory_command(parsed, contract, work_dir)
        if parsed.command == "archive":
            return _archive_command(parsed, contract, work_dir)
        if parsed.command == "status":
            return _status_command(parsed, contract, work_dir, write=False)
        if parsed.command == "report":
            return _status_command(parsed, contract, work_dir, write=True)
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
        _require_remote_preflight(contract, work_dir / "summary.json")
        max_in_flight = parsed.max_in_flight or parsed.workers * 2
        result = run_archive(
            axiom_archive_plan(contract),
            inventory_path=work_dir / "inventory.parquet",
            state_path=work_dir / "state.sqlite3",
            workers=parsed.workers,
            max_in_flight=max_in_flight,
            max_attempts=parsed.max_attempts,
            max_consecutive_failures=parsed.max_consecutive_failures,
            limit=parsed.limit,
            audit_verified=parsed.audit_verified,
        )
    print_json(result)
    if result.failed or result.state_counts["error"] or result.state_counts["running"]:
        return 1
    if parsed.limit is None and result.state_counts["unresolved"]:
        return 1
    return 0


def _status_command(
    parsed: argparse.Namespace,
    contract: Contract,
    work_dir: Path,
    *,
    write: bool,
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
    if write:
        progress_path = work_dir / "progress.json"
        atomic_write_json(progress_path, progress)
        progress["progress_path"] = str(progress_path)
    print_json(progress)
    return 0


def _validate_command(parsed: argparse.Namespace, contract: Contract, work_dir: Path) -> int:
    _require_destination_storage(contract.destination.root)
    with exclusive_workflow_lock(_workflow_lock_path(contract, work_dir), "validate"):
        _require_destination_storage(contract.destination.root)
        _require_remote_preflight(contract, work_dir / "summary.json")
        result = validate_archive(
            axiom_archive_plan(contract),
            inventory_path=work_dir / "inventory.parquet",
            rejected_path=work_dir / "rejected.parquet",
            state_path=work_dir / "state.sqlite3",
            workers=parsed.workers,
            max_attempts=parsed.max_attempts,
            verified_only=parsed.verified_only,
            report_path=work_dir / "validation.json",
        )
    print_json(result)
    passed = result.audit_passed if parsed.verified_only else result.complete
    return 0 if passed else 1


def _require_remote_preflight(contract: Contract, summary_path: Path) -> None:
    if not summary_path.is_file():
        raise FileNotFoundError(
            f"metadata preflight is absent: {summary_path}; run inventory --remote-snapshot first",
        )
    summary = verify_inventory_artifacts(summary_path, contract)
    remote = summary.get("remote_snapshot")
    if not isinstance(remote, dict):
        raise TypeError("summary lacks the required remote_snapshot result")
    missing = remote.get("indexed_missing_count")
    extra = remote.get("prefix_extra_count")
    if missing != 0:
        raise ValueError(f"remote snapshot is missing {missing!r} indexed source objects")
    if isinstance(extra, bool) or not isinstance(extra, int) or extra < 0:
        raise TypeError(f"invalid prefix_extra_count in remote snapshot: {extra!r}")


def _require_destination_storage(destination_root: Path) -> None:
    destination_stat = _require_destination_location(destination_root)
    _require_dataset_registration()
    _require_destination_permissions(destination_root, destination_stat)


def _require_destination_location(destination_root: Path) -> os.stat_result:
    """Require the exact archive path to remain on shared dataset storage."""
    dataset_root = DATASET_ROOT
    if destination_root != EXPECTED_DESTINATION_ROOT:
        raise ValueError(f"unexpected archive root: {destination_root}")
    _require_unsymlinked_destination_path(dataset_root, destination_root)
    if not dataset_root.is_dir():
        raise FileNotFoundError(f"shared dataset root is absent: {dataset_root}")
    if dataset_root.stat().st_dev == dataset_root.parent.stat().st_dev:
        raise RuntimeError(
            "/work/datasets is not a distinct mounted filesystem; refusing to write the root disk",
        )
    if not destination_root.is_dir():
        raise FileNotFoundError(
            f"archive root has not been provisioned and registered: {destination_root}",
        )
    resolved_dataset_root = dataset_root.resolve()
    resolved_destination_root = destination_root.resolve()
    if not resolved_destination_root.is_relative_to(resolved_dataset_root):
        raise RuntimeError(
            f"archive root resolves outside the shared dataset root: {resolved_destination_root}",
        )
    if destination_root.stat().st_dev == dataset_root.parent.stat().st_dev:
        raise RuntimeError(
            f"archive root is on the /work root filesystem; refusing to write: {destination_root}",
        )
    return destination_root.stat()


def _require_unsymlinked_destination_path(dataset_root: Path, destination_root: Path) -> None:
    """Reject symlinks in the canonical archive path below the dataset root."""
    if dataset_root.is_symlink():
        raise RuntimeError(f"shared dataset root must not be a symlink: {dataset_root}")
    current = dataset_root
    for component in destination_root.relative_to(dataset_root).parts:
        current /= component
        if current.is_symlink():
            raise RuntimeError(f"archive root path contains a symlink: {current}")


def _require_dataset_registration() -> None:
    """Require the canonical dataset name and owner in the shared registry."""
    if not DATASET_REGISTRY.is_file():
        raise FileNotFoundError(f"shared dataset registry is absent: {DATASET_REGISTRY}")
    registered_owner = _registry_owner(DATASET_REGISTRY.read_text(), DATASET_NAME)
    if registered_owner != "shsingh":
        raise RuntimeError(
            f"archive registry entry must name owner 'shsingh': "
            f"dataset={DATASET_NAME!r}, observed_owner={registered_owner!r}",
        )


def _require_destination_permissions(destination_root: Path, destination_stat: os.stat_result) -> None:
    """Require a root-owned, setgid, group-writable archive root."""
    try:
        destination_group = grp.getgrgid(destination_stat.st_gid).gr_name
    except KeyError as error:
        raise RuntimeError(f"archive root has unknown group id {destination_stat.st_gid}") from error
    destination_mode = stat.S_IMODE(destination_stat.st_mode)
    if (
        destination_stat.st_uid != 0
        or destination_group != "imaging"
        or destination_mode & REQUIRED_DESTINATION_MODE != REQUIRED_DESTINATION_MODE
    ):
        raise PermissionError(
            "archive root must be owned by root:imaging with setgid group access: "
            f"uid={destination_stat.st_uid}, group={destination_group!r}, mode={destination_mode:o}",
        )
    if not os.access(destination_root, os.W_OK | os.X_OK):
        raise PermissionError(f"archive root is not writable: {destination_root}")


def _workflow_lock_path(contract: Contract, work_dir: Path) -> Path:
    """Use one destination-scoped lock once the canonical archive root exists."""
    if contract.destination.root.exists():
        return contract.destination.root / ".oasis-images.lock"
    return work_dir / ".oasis-images.lock"


def _default_workers() -> int:
    cpu_count = os.cpu_count() or 4
    return max(1, min(32, cpu_count // 4))


def _registry_owner(registry: str, dataset_name: str) -> str | None:
    current_name: str | None = None
    for raw_line in registry.splitlines():
        line = raw_line.strip().removeprefix("- ")
        if line.startswith("name:"):
            current_name = line.removeprefix("name:").strip().strip("'\"")
        elif current_name == dataset_name and line.startswith("owner:"):
            return line.removeprefix("owner:").strip().strip("'\"") or None
    return None


if __name__ == "__main__":
    sys.exit(main())
