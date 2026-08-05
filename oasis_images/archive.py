# ruff: noqa: CPY001, EM101, EM102, TC001, TRY003
"""Bounded, restartable TIFF-to-JPEG-XL archive execution."""

from __future__ import annotations

import json
import logging
import traceback
from collections.abc import Iterator, Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

import pyarrow as pa
import pyarrow.parquet as pq

from .codec import decode_tiff, encode_jxl, verify_jxl
from .io import (
    atomic_write_bytes,
    atomic_write_json,
    ensure_group_directories,
    safe_destination,
    sha256_bytes,
    sha256_file,
)
from .plan import ArchivePlan
from .s3 import S3Client, download_object, public_s3_client
from .state import ArchiveState, ManifestIdentity, StateRecord

LOGGER = logging.getLogger(__name__)
DEFAULT_MAX_CONSECUTIVE_FAILURES = 32
_MAX_REPORTED_FAILURES = 100


@dataclass(frozen=True, slots=True)
class ConversionResult:
    """Verification evidence returned by one conversion worker."""

    source_key: str
    source_sha256: str
    output_sha256: str
    source_bytes: int
    output_bytes: int
    shape: tuple[int, int]
    dtype: str


@dataclass(frozen=True, slots=True)
class ArchiveRunResult:
    """Summary of one bounded archive invocation."""

    selected: int
    retried: int
    verified: int
    failed: int
    failure_attempts: int
    failure_limit_reached: bool
    recovered_running: int
    requeued_verified: int
    state_counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Summary of an on-disk verification pass."""

    complete: bool
    audit_passed: bool
    checked: int
    invalid: int
    inventory_rows: int
    rejected_rows: int
    state_counts: dict[str, int]
    failures: tuple[dict[str, str], ...]


@dataclass(slots=True)
class _QueueProgress:
    """Mutable counters and stop state for one bounded archive invocation."""

    selected: int = 0
    retried: int = 0
    verified: int = 0
    failed: int = 0
    failure_attempts: int = 0
    consecutive_failures: int = 0
    failure_limit_reached: bool = False
    exhausted: bool = False


def run_archive(  # noqa: PLR0913
    plan: ArchivePlan,
    *,
    inventory_path: Path,
    state_path: Path,
    workers: int,
    max_in_flight: int,
    max_attempts: int = 5,
    max_consecutive_failures: int = DEFAULT_MAX_CONSECUTIVE_FAILURES,
    limit: int | None = None,
    audit_verified: bool = False,
) -> ArchiveRunResult:
    """Initialize state, audit prior outputs, and convert a bounded work queue."""
    _positive(workers, "workers")
    _positive(max_in_flight, "max_in_flight")
    _positive(max_attempts, "max_attempts")
    _positive(max_consecutive_failures, "max_consecutive_failures")
    if max_in_flight < workers:
        raise ValueError("max_in_flight must be at least workers")
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative or None")
    if not inventory_path.is_file():
        raise FileNotFoundError(f"inventory does not exist: {inventory_path}")

    manifest_rows = _parquet_rows(inventory_path)
    manifest_sha256 = _require_artifact_pin(
        inventory_path,
        plan.manifest_sha256,
        "inventory manifest",
    )
    if manifest_rows != plan.manifest_rows:
        raise ValueError(
            "inventory row count differs from the contract: "
            f"actual={manifest_rows}, expected={plan.manifest_rows}",
        )
    client = public_s3_client(max_pool_connections=max_in_flight)
    with ArchiveState(state_path) as state:
        binding = state.manifest_binding()
        if binding is None or binding.artifact_sha256 is None:
            initialized = state.initialize(
                iter_manifest_identities(inventory_path, plan),
                artifact_sha256=manifest_sha256,
                artifact_record_count=manifest_rows,
            )
            LOGGER.info(
                "state initialized: inserted=%d existing=%d",
                initialized.inserted,
                initialized.existing,
            )
        else:
            state.require_manifest_binding(manifest_sha256, manifest_rows)
            LOGGER.info("state manifest binding verified without row replay")
        initialized_counts = state.counts(max_attempts=max_attempts)
        if initialized_counts["total"] != plan.manifest_rows:
            raise ValueError(
                "archive state row count differs from the contracted complete inventory: "
                f"state={initialized_counts['total']}, "
                f"expected={plan.manifest_rows}",
            )
        recovered = state.recover_running()
        requeued = (
            audit_verified_outputs(state, plan=plan, workers=workers) if audit_verified else 0
        )
        pending = state.pending(limit=limit, max_attempts=max_attempts)
        selected, retried, verified, failed, failure_attempts, failure_limit_reached = _run_queue(
            state,
            pending,
            plan=plan,
            client=client,
            workers=workers,
            max_in_flight=max_in_flight,
            max_attempts=max_attempts,
            max_consecutive_failures=max_consecutive_failures,
        )
        counts = state.counts(max_attempts=max_attempts)
    return ArchiveRunResult(
        selected=selected,
        retried=retried,
        verified=verified,
        failed=failed,
        failure_attempts=failure_attempts,
        failure_limit_reached=failure_limit_reached,
        recovered_running=recovered,
        requeued_verified=requeued,
        state_counts=counts,
    )


def iter_manifest_identities(inventory_path: Path, plan: ArchivePlan) -> Iterator[ManifestIdentity]:
    """Stream immutable state identities from the deterministic inventory."""
    parquet = pq.ParquetFile(inventory_path)
    names = set(parquet.schema_arrow.names)
    required = {"source_key", "source_uri", "destination_relative", "source_size", "etag"}
    missing = required - names
    if missing:
        raise ValueError(f"inventory lacks required columns: {sorted(missing)}")

    version_column = "version_id" if "version_id" in names else None
    columns = ["source_key", "source_uri", "destination_relative", "source_size", "etag"]
    if version_column:
        columns.append(version_column)

    for batch in parquet.iter_batches(batch_size=65_536, columns=columns):
        values = batch.to_pydict()
        for position, source_key in enumerate(values["source_key"]):
            key = str(source_key)
            source_uri = str(values["source_uri"][position])
            destination_relative = str(values["destination_relative"][position])
            _validate_source_destination(plan, key, source_uri, destination_relative)
            expected_size = _optional_int(values["source_size"][position])
            expected_etag = _optional_str(values["etag"][position])
            expected_version_id = (
                _optional_str(values[version_column][position]) if version_column is not None else None
            )
            if expected_size is None or expected_etag is None:
                raise ValueError(f"remote metadata is incomplete for source key {source_key!r}")
            yield ManifestIdentity(
                source_key=key,
                source_uri=source_uri,
                destination_relative=destination_relative,
                expected_size=expected_size,
                expected_etag=expected_etag,
                expected_version_id=expected_version_id,
            )


def audit_verified_outputs(
    state: ArchiveState,
    *,
    plan: ArchivePlan,
    workers: int,
) -> int:
    """Requeue verified rows unless the exact previously decoded bytes remain."""
    records = state.verified_records()
    requeued = 0
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="jxl-audit") as executor:
        futures: dict[Future[str | None], StateRecord] = {}
        exhausted = False
        while futures or not exhausted:
            while len(futures) < workers * 4 and not exhausted:
                try:
                    record = next(records)
                except StopIteration:
                    exhausted = True
                    break
                future = executor.submit(_audit_verified_record, record, plan)
                futures[future] = record
            if not futures:
                continue
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                record = futures.pop(future)
                reason = future.result()
                if reason is not None:
                    state.requeue(record.source_key, reason)
                    requeued += 1
    if requeued:
        LOGGER.warning("requeued %d invalid previously verified outputs", requeued)
    return requeued


def validate_archive(  # noqa: PLR0913
    plan: ArchivePlan,
    *,
    inventory_path: Path,
    rejected_path: Path,
    state_path: Path,
    workers: int,
    max_attempts: int = 5,
    verified_only: bool = False,
    report_path: Path | None = None,
) -> ValidationResult:
    """Decode and hash every verified output, then enforce full completeness."""
    _positive(workers, "workers")
    inventory_rows = _parquet_rows(inventory_path)
    rejected_rows = _parquet_rows(rejected_path)
    manifest_sha256 = _require_artifact_pin(
        inventory_path,
        plan.manifest_sha256,
        "inventory manifest",
    )
    _require_artifact_pin(
        rejected_path,
        plan.rejected_sha256,
        "rejected-row artifact",
    )
    failures: list[dict[str, str]] = []
    checked = 0
    invalid = 0
    with ArchiveState(state_path) as state:
        state.validate_manifest(
            iter_manifest_identities(inventory_path, plan),
            artifact_sha256=manifest_sha256,
            artifact_record_count=inventory_rows,
        )
        records = state.verified_records()
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="jxl-validate") as executor:
            futures: dict[Future[str | None], StateRecord] = {}
            exhausted = False
            while futures or not exhausted:
                while len(futures) < workers * 4 and not exhausted:
                    try:
                        record = next(records)
                    except StopIteration:
                        exhausted = True
                        break
                    future = executor.submit(_validate_verified_record, record, plan)
                    futures[future] = record
                if not futures:
                    continue
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    record = futures.pop(future)
                    checked += 1
                    reason = future.result()
                    if reason is None:
                        continue
                    invalid += 1
                    if len(failures) < _MAX_REPORTED_FAILURES:
                        failures.append({"source_key": record.source_key, "reason": reason})
        counts = state.counts(max_attempts=max_attempts)

    expected = plan.manifest_rows
    complete = (
        invalid == 0
        and checked == expected
        and inventory_rows == expected
        and rejected_rows == plan.rejected_rows
        and counts["verified"] == expected
        and counts["unresolved"] == 0
    )
    audit_passed = (
        checked > 0
        and invalid == 0
        and inventory_rows == expected
        and rejected_rows == plan.rejected_rows
        and counts["total"] == expected
        and checked == counts["verified"]
    )
    result = ValidationResult(
        complete=complete,
        audit_passed=audit_passed,
        checked=checked,
        invalid=invalid,
        inventory_rows=inventory_rows,
        rejected_rows=rejected_rows,
        state_counts=counts,
        failures=tuple(failures),
    )
    if report_path is not None:
        report = asdict(result)
        report["verified_only"] = verified_only
        report["expected_complete"] = expected
        report["failure_details_truncated"] = invalid > len(failures)
        atomic_write_json(report_path, report)
    return result


def state_report(state_path: Path, *, max_attempts: int = 5) -> dict[str, Any]:
    """Return a compact machine-readable snapshot of durable progress."""
    if not state_path.is_file():
        return {
            "exists": False,
            "state_path": str(state_path),
            "counts": {
                "pending": 0,
                "running": 0,
                "verified": 0,
                "error": 0,
                "retryable_errors": 0,
                "terminal_errors": 0,
                "total": 0,
                "unresolved": 0,
            },
            "manifest_binding": None,
            "verified_bytes": {"source_bytes": 0, "output_bytes": 0},
            "size_reduction_fraction": None,
            "source_to_output_ratio": None,
        }
    with ArchiveState(state_path) as state:
        counts = state.counts(max_attempts=max_attempts)
        byte_totals = state.byte_totals()
        binding = state.manifest_binding()
    source_bytes = byte_totals["source_bytes"]
    output_bytes = byte_totals["output_bytes"]
    size_reduction_fraction = None if source_bytes == 0 else 1 - (output_bytes / source_bytes)
    source_to_output_ratio = None if output_bytes == 0 else source_bytes / output_bytes
    return {
        "exists": True,
        "state_path": str(state_path),
        "counts": counts,
        "manifest_binding": None if binding is None else asdict(binding),
        "verified_bytes": byte_totals,
        "size_reduction_fraction": size_reduction_fraction,
        "source_to_output_ratio": source_to_output_ratio,
    }


def print_json(value: Mapping[str, Any] | ArchiveRunResult | ValidationResult) -> None:
    """Print a dataclass or mapping as stable JSON for logs and automation."""
    payload = asdict(value) if not isinstance(value, Mapping) else dict(value)
    print(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))  # noqa: T201


def _run_queue(  # noqa: PLR0913
    state: ArchiveState,
    pending: Iterator[StateRecord],
    *,
    plan: ArchivePlan,
    client: S3Client,
    workers: int,
    max_in_flight: int,
    max_attempts: int,
    max_consecutive_failures: int,
) -> tuple[int, int, int, int, int, bool]:
    progress = _QueueProgress()
    futures: dict[Future[ConversionResult], StateRecord] = {}
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="tiff-jxl") as executor:
        while futures or not progress.exhausted:
            while len(futures) < max_in_flight and not progress.exhausted and not progress.failure_limit_reached:
                try:
                    record = next(pending)
                except StopIteration:
                    progress.exhausted = True
                    break
                running = state.mark_running(record.source_key)
                future = executor.submit(
                    _convert_one,
                    running,
                    plan,
                    client,
                )
                futures[future] = running
                progress.selected += 1
            if not futures:
                continue
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                record = futures.pop(future)
                try:
                    result = future.result()
                    state.mark_verified(
                        result.source_key,
                        source_sha256=result.source_sha256,
                        output_sha256=result.output_sha256,
                        source_bytes=result.source_bytes,
                        output_bytes=result.output_bytes,
                        shape=result.shape,
                        dtype=result.dtype,
                    )
                except Exception as error:  # noqa: BLE001 - every worker failure must enter the ledger
                    _handle_conversion_failure(
                        state,
                        record,
                        error,
                        progress=progress,
                        futures=futures,
                        executor=executor,
                        plan=plan,
                        client=client,
                        max_attempts=max_attempts,
                        max_consecutive_failures=max_consecutive_failures,
                    )
                else:
                    progress.consecutive_failures = 0
                    progress.verified += 1
                    completed = progress.verified + progress.failed
                    if completed % 1_000 == 0:
                        LOGGER.info(
                            "archive progress: completed=%d verified=%d failed=%d selected=%d",
                            completed,
                            progress.verified,
                            progress.failed,
                            progress.selected,
                        )
    return (
        progress.selected,
        progress.retried,
        progress.verified,
        progress.failed,
        progress.failure_attempts,
        progress.failure_limit_reached,
    )


def _handle_conversion_failure(  # noqa: PLR0913
    state: ArchiveState,
    record: StateRecord,
    error: Exception,
    *,
    progress: _QueueProgress,
    futures: dict[Future[ConversionResult], StateRecord],
    executor: ThreadPoolExecutor,
    plan: ArchivePlan,
    client: S3Client,
    max_attempts: int,
    max_consecutive_failures: int,
) -> None:
    """Persist one failure, retry it when safe, or trip the run circuit breaker."""
    progress.failure_attempts += 1
    progress.consecutive_failures += 1
    error_text = "".join(traceback.format_exception(error))
    errored = state.mark_error(record.source_key, error_text)
    LOGGER.error(
        "failed %s on attempt %d",
        record.source_uri,
        errored.attempts,
        exc_info=(type(error), error, error.__traceback__),
    )
    if not progress.failure_limit_reached and progress.consecutive_failures >= max_consecutive_failures:
        progress.failure_limit_reached = True
        progress.exhausted = True
        LOGGER.warning(
            "run failure limit reached after %d consecutive failed attempts; "
            "stopping new work after %d in-flight conversions",
            progress.consecutive_failures,
            len(futures),
        )
    if progress.failure_limit_reached or errored.attempts >= max_attempts:
        progress.failed += 1
        return
    running = state.mark_running(record.source_key)
    retry = executor.submit(
        _convert_one,
        running,
        plan,
        client,
    )
    futures[retry] = running
    progress.retried += 1


def _convert_one(
    record: StateRecord,
    plan: ArchivePlan,
    client: S3Client,
) -> ConversionResult:
    _validate_source_destination(
        plan,
        record.source_key,
        record.source_uri,
        record.destination_relative,
    )
    source, _, _ = download_object(
        client,
        bucket=plan.source.bucket,
        key=record.source_key,
        expected_size=record.expected_size,
        expected_etag=record.expected_etag,
        version_id=record.expected_version_id,
    )
    source_sha256 = sha256_bytes(source)
    if record.source_sha256 is not None and source_sha256 != record.source_sha256:
        raise ValueError(f"source SHA-256 changed since prior verification: {record.source_uri}")
    image = decode_tiff(source, expected_shape=plan.image_shape)
    image_shape = (int(image.shape[0]), int(image.shape[1]))
    encoded = encode_jxl(image, plan.codec)
    decoded = verify_jxl(encoded, expected_shape=image_shape, expected_dtype=image.dtype)
    destination = safe_destination(plan.destination_root, record.destination_relative)
    ensure_group_directories(plan.destination_root, destination.parent)
    output_sha256 = sha256_bytes(encoded)
    atomic_write_bytes(destination, encoded)

    on_disk = destination.read_bytes()
    if len(on_disk) != len(encoded) or sha256_bytes(on_disk) != output_sha256:
        raise ValueError(f"on-disk output identity check failed: {destination}")
    verify_jxl(on_disk, expected_shape=image_shape, expected_dtype=decoded.dtype)
    return ConversionResult(
        source_key=record.source_key,
        source_sha256=source_sha256,
        output_sha256=output_sha256,
        source_bytes=len(source),
        output_bytes=len(encoded),
        shape=image_shape,
        dtype=str(image.dtype),
    )


def _audit_verified_record(record: StateRecord, plan: ArchivePlan) -> str | None:  # noqa: PLR0911
    try:
        destination = safe_destination(plan.destination_root, record.destination_relative)
        if record.source_bytes is None or record.source_sha256 is None:
            return "verified state lacks source byte count or SHA-256"
        if record.expected_size is not None and record.source_bytes != record.expected_size:
            return "verified source byte count differs from its metadata snapshot"
        if record.output_bytes is None or record.output_sha256 is None:
            return "verified state lacks output byte count or SHA-256"
        if record.shape is None or tuple(record.shape) != plan.image_shape or record.dtype != plan.image_dtype:
            return "verified state lacks the contracted decoded shape or dtype"
        if not destination.is_file():
            return f"verified output is absent: {destination}"
        payload = destination.read_bytes()
        if len(payload) != record.output_bytes:
            return f"verified output size changed: {destination}"
        if sha256_bytes(payload) != record.output_sha256:
            return f"verified output SHA-256 changed: {destination}"
        verify_jxl(payload, expected_shape=plan.image_shape, expected_dtype=plan.image_dtype)
    except Exception as error:  # noqa: BLE001 - convert audit failures into requeue reasons
        return f"verified output audit failed: {type(error).__name__}: {error}"
    return None


def _validate_verified_record(  # noqa: PLR0911
    record: StateRecord,
    plan: ArchivePlan,
) -> str | None:
    if record.shape is None or tuple(record.shape) != plan.image_shape or record.dtype != plan.image_dtype:
        return "verified state lacks the contracted decoded shape or dtype"
    if record.source_bytes is None or record.source_sha256 is None:
        return "verified state lacks source byte count or SHA-256"
    if record.expected_size is not None and record.source_bytes != record.expected_size:
        return "verified source byte count differs from its metadata snapshot"
    if record.output_bytes is None or record.output_sha256 is None:
        return "verified state lacks output byte count or SHA-256"
    try:
        destination = safe_destination(plan.destination_root, record.destination_relative)
        if not destination.is_file():
            return f"verified output is absent: {destination}"
        payload = destination.read_bytes()
        if len(payload) != record.output_bytes:
            return f"verified output size changed: {destination}"
        if sha256_bytes(payload) != record.output_sha256:
            return f"verified output SHA-256 changed: {destination}"
        verify_jxl(payload, expected_shape=plan.image_shape, expected_dtype=plan.image_dtype)
    except Exception as error:  # noqa: BLE001 - collect validation failures for the report
        return f"JPEG XL decode validation failed: {type(error).__name__}: {error}"
    return None


def _validate_source_destination(
    plan: ArchivePlan,
    source_key: str,
    source_uri: str,
    destination_relative: str,
) -> None:
    parsed = urlsplit(source_uri)
    if parsed.scheme != "s3" or parsed.netloc != plan.source.bucket or parsed.query or parsed.fragment:
        raise ValueError(f"source URI left the contract bucket: {source_uri}")
    if parsed.path.lstrip("/") != source_key or not source_key.startswith(f"{plan.source.prefix}/"):
        raise ValueError(f"source URI/key identity mismatch: {source_uri}")
    destination = PurePosixPath(destination_relative)
    if (
        destination.is_absolute()
        or destination.as_posix() != destination_relative
        or destination_relative in {"", "."}
        or ".." in destination.parts
        or destination.suffix != ".jxl"
    ):
        raise ValueError(f"destination is not a safe relative JPEG XL path: {destination_relative!r}")
    plan.validate_row(source_key, source_uri, destination_relative)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"invalid optional integer: {value!r}")
    return value


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"invalid optional string: {value!r}")
    return value


def _positive(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _parquet_rows(path: Path) -> int:
    if not path.is_file():
        raise FileNotFoundError(f"required Parquet artifact is absent: {path}")
    return pq.ParquetFile(path).metadata.num_rows


def _require_artifact_pin(path: Path, expected_sha256: str | None, label: str) -> str:
    actual_sha256 = sha256_file(path)
    if expected_sha256 is not None and actual_sha256 != expected_sha256:
        raise ValueError(
            f"{label} SHA-256 differs: expected={expected_sha256}, actual={actual_sha256}, path={path}",
        )
    return actual_sha256


def write_inventory_fixture(path: Path, records: list[dict[str, object]]) -> None:
    """Write a tiny inventory for integration tests without touching real data."""
    table = pa.Table.from_pylist(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


__all__ = [
    "DEFAULT_MAX_CONSECUTIVE_FAILURES",
    "ArchiveRunResult",
    "ConversionResult",
    "ValidationResult",
    "audit_verified_outputs",
    "iter_manifest_identities",
    "print_json",
    "run_archive",
    "state_report",
    "validate_archive",
    "write_inventory_fixture",
]
