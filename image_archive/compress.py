# Copyright (c) 2026 Broad Institute.
# ruff: noqa: BLE001, EM101, EM102, PERF203, PLR0913, T201, TRY003
"""Convert a two-column TIFF manifest into verified JPEG XL files."""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import logging
import os
import tempfile
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from functools import partial
from itertools import islice
from pathlib import Path, PurePosixPath
from typing import Final
from urllib.parse import unquote, urlsplit

import boto3
from botocore import UNSIGNED
from botocore.config import Config

from .codec import JPEGXL_DISTANCE, JPEGXL_EFFORT, decode_tiff, encode_jxl, verify_jxl

LOGGER = logging.getLogger(__name__)
MANIFEST_COLUMNS: Final = ("source_uri", "destination_relative")
MAX_REPORTED_FAILURES: Final = 100
SourceReader = Callable[[str], bytes]


@dataclass(frozen=True, slots=True)
class ManifestRow:
    """One source TIFF and its relative output path."""

    number: int
    source_uri: str
    destination_relative: str


@dataclass(frozen=True, slots=True)
class Failure:
    """One failed manifest row."""

    row: int
    source_uri: str
    destination_relative: str
    reason: str


@dataclass(frozen=True, slots=True)
class _Conversion:
    row: ManifestRow
    source_bytes: int
    output_bytes: int
    failure: Failure | None


@dataclass(frozen=True, slots=True)
class ConvertResult:
    """Summary of one conversion invocation."""

    complete: bool
    interrupted: bool
    manifest_sha256: str
    total: int
    selected: int
    skipped: int
    converted: int
    failed: int
    source_bytes: int
    output_bytes: int
    failure_limit_reached: bool
    failures: tuple[Failure, ...]


@dataclass(frozen=True, slots=True)
class VerifyResult:
    """Summary of one full output verification pass."""

    complete: bool
    interrupted: bool
    manifest_sha256: str
    total: int
    checked: int
    invalid: int
    output_bytes: int
    failures: tuple[Failure, ...]


def iter_manifest(path: Path) -> Iterator[ManifestRow]:
    """Read a destination-sorted, two-column TSV manifest."""
    if not path.is_file():
        raise FileNotFoundError(f"manifest does not exist: {path}")
    previous_destination: str | None = None
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if tuple(reader.fieldnames or ()) != MANIFEST_COLUMNS:
            raise ValueError(
                f"manifest columns differ: actual={reader.fieldnames!r}, expected={MANIFEST_COLUMNS!r}",
            )
        for number, raw in enumerate(reader, start=2):
            source_uri = str(raw["source_uri"]).strip()
            destination_relative = str(raw["destination_relative"]).strip()
            _validate_source(source_uri, number)
            _safe_destination(destination_relative, number)
            if previous_destination is not None and destination_relative <= previous_destination:
                raise ValueError(
                    "manifest destinations must be strictly sorted and unique: "
                    f"row={number}, previous={previous_destination!r}, current={destination_relative!r}",
                )
            previous_destination = destination_relative
            yield ManifestRow(number, source_uri, destination_relative)


def convert_manifest(
    manifest: Path,
    output_root: Path,
    *,
    workers: int,
    max_attempts: int = 5,
    max_consecutive_failures: int = 32,
    max_in_flight: int | None = None,
    source_reader: SourceReader | None = None,
) -> ConvertResult:
    """Convert every absent destination and return a resumable run summary."""
    _positive(workers, "workers")
    _positive(max_attempts, "max_attempts")
    _positive(max_consecutive_failures, "max_consecutive_failures")
    in_flight_limit = max_in_flight or workers * 2
    _positive(in_flight_limit, "max_in_flight")
    if in_flight_limit < workers:
        raise ValueError("max_in_flight must be at least workers")
    root = _output_root(output_root, create=True)
    manifest_path = manifest.resolve()
    manifest_sha256 = _sha256_file(manifest_path)
    total = sum(1 for _ in iter_manifest(manifest_path))
    reader = source_reader or _default_reader(in_flight_limit)

    selected = skipped = converted = failed = source_bytes = output_bytes = 0
    consecutive_failures = 0
    failure_limit_reached = False
    interrupted = False
    failures: list[Failure] = []
    try:
        with _exclusive_lock(root / ".jxl-convert.lock"):
            worker = partial(_convert_row, root=root, reader=reader, max_attempts=max_attempts)
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="tiff-jxl") as executor:
                for batch in _batches(iter_manifest(manifest_path), in_flight_limit):
                    pending = [row for row in batch if not _destination(root, row).is_file()]
                    skipped += len(batch) - len(pending)
                    selected += len(pending)
                    for outcome in executor.map(worker, pending):
                        if outcome.failure is None:
                            converted += 1
                            source_bytes += outcome.source_bytes
                            output_bytes += outcome.output_bytes
                            consecutive_failures = 0
                        else:
                            failed += 1
                            consecutive_failures += 1
                            if len(failures) < MAX_REPORTED_FAILURES:
                                failures.append(outcome.failure)
                            if consecutive_failures >= max_consecutive_failures:
                                failure_limit_reached = True
                                break
                        if (converted + failed) % 1_000 == 0:
                            LOGGER.info(
                                "progress converted=%d failed=%d selected=%d skipped=%d",
                                converted,
                                failed,
                                selected,
                                skipped,
                            )
                    if failure_limit_reached:
                        break
    except KeyboardInterrupt:
        interrupted = True
        LOGGER.warning("interrupted; completed atomic outputs will be skipped on the next run")

    complete = not interrupted and not failure_limit_reached and failed == 0 and converted + skipped == total
    return ConvertResult(
        complete=complete,
        interrupted=interrupted,
        manifest_sha256=manifest_sha256,
        total=total,
        selected=selected,
        skipped=skipped,
        converted=converted,
        failed=failed,
        source_bytes=source_bytes,
        output_bytes=output_bytes,
        failure_limit_reached=failure_limit_reached,
        failures=tuple(failures),
    )


def verify_manifest(
    manifest: Path,
    output_root: Path,
    *,
    workers: int,
    max_in_flight: int | None = None,
) -> VerifyResult:
    """Decode every expected JPEG XL output."""
    _positive(workers, "workers")
    in_flight_limit = max_in_flight or workers * 4
    _positive(in_flight_limit, "max_in_flight")
    root = _output_root(output_root, create=False)
    manifest_path = manifest.resolve()
    manifest_sha256 = _sha256_file(manifest_path)
    total = sum(1 for _ in iter_manifest(manifest_path))
    checked = invalid = output_bytes = 0
    interrupted = False
    failures: list[Failure] = []

    try:
        with _exclusive_lock(root / ".jxl-convert.lock"):
            worker = partial(_verify_row, root=root)
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="jxl-verify") as executor:
                for batch in _batches(iter_manifest(manifest_path), in_flight_limit):
                    for size, failure in executor.map(worker, batch):
                        if failure is None:
                            checked += 1
                            output_bytes += size
                        else:
                            invalid += 1
                            if len(failures) < MAX_REPORTED_FAILURES:
                                failures.append(failure)
    except KeyboardInterrupt:
        interrupted = True
        LOGGER.warning("verification interrupted")

    return VerifyResult(
        complete=not interrupted and invalid == 0 and checked == total,
        interrupted=interrupted,
        manifest_sha256=manifest_sha256,
        total=total,
        checked=checked,
        invalid=invalid,
        output_bytes=output_bytes,
        failures=tuple(failures),
    )


def _convert_row(
    row: ManifestRow,
    *,
    root: Path,
    reader: SourceReader,
    max_attempts: int,
) -> _Conversion:
    destination = _destination(root, row)
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            source = reader(row.source_uri)
            image = decode_tiff(source)
            encoded = encode_jxl(image)
            expected_shape = int(image.shape[0]), int(image.shape[1])
            verify_jxl(encoded, expected_shape=expected_shape, expected_dtype=image.dtype)
            _atomic_write(destination, encoded)
            on_disk = destination.read_bytes()
            verify_jxl(on_disk, expected_shape=expected_shape, expected_dtype=image.dtype)
            return _Conversion(row, len(source), len(encoded), None)
        except Exception as error:
            destination.unlink(missing_ok=True)
            last_error = error
            LOGGER.warning(
                "attempt %d/%d failed for %s: %s: %s",
                attempt,
                max_attempts,
                row.source_uri,
                type(error).__name__,
                error,
            )
    reason = "conversion failed"
    if last_error is not None:
        reason = f"{type(last_error).__name__}: {last_error}"
    return _Conversion(
        row,
        0,
        0,
        Failure(row.number, row.source_uri, row.destination_relative, reason),
    )


def _verify_row(row: ManifestRow, *, root: Path) -> tuple[int, Failure | None]:
    destination = _destination(root, row)
    try:
        payload = destination.read_bytes()
        verify_jxl(payload)
        return len(payload), None
    except Exception as error:
        return 0, Failure(
            row.number,
            row.source_uri,
            row.destination_relative,
            f"{type(error).__name__}: {error}",
        )


def _batches(rows: Iterator[ManifestRow], size: int) -> Iterator[list[ManifestRow]]:
    while batch := list(islice(rows, size)):
        yield batch


def _default_reader(max_pool_connections: int) -> SourceReader:
    client = boto3.client(
        "s3",
        region_name="us-east-1",
        config=Config(
            signature_version=UNSIGNED,
            max_pool_connections=max_pool_connections,
            connect_timeout=15,
            read_timeout=120,
            retries={"max_attempts": 10, "mode": "adaptive"},
        ),
    )

    def read(source_uri: str) -> bytes:
        parsed = urlsplit(source_uri)
        if parsed.scheme == "s3":
            response = client.get_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))
            body = response["Body"]
            try:
                payload = body.read()
            finally:
                body.close()
            if not isinstance(payload, bytes):
                raise TypeError(f"S3 body is not bytes: {source_uri}")
            return payload
        return _local_path(source_uri).read_bytes()

    return read


def _validate_source(source_uri: str, row: int) -> None:
    if not source_uri:
        raise ValueError(f"manifest row {row} has an empty source_uri")
    parsed = urlsplit(source_uri)
    if parsed.scheme == "s3":
        if not parsed.netloc or not parsed.path or parsed.query or parsed.fragment:
            raise ValueError(f"manifest row {row} has an invalid S3 URI: {source_uri!r}")
        suffix = PurePosixPath(parsed.path).suffix.lower()
    elif parsed.scheme in {"", "file"}:
        suffix = _local_path(source_uri).suffix.lower()
    else:
        raise ValueError(f"manifest row {row} uses an unsupported source scheme: {source_uri!r}")
    if suffix not in {".tif", ".tiff"}:
        raise ValueError(f"manifest row {row} source is not a TIFF: {source_uri!r}")


def _local_path(source_uri: str) -> Path:
    parsed = urlsplit(source_uri)
    if parsed.scheme == "file":
        if parsed.netloc not in {"", "localhost"} or parsed.query or parsed.fragment:
            raise ValueError(f"invalid local file URI: {source_uri!r}")
        path = Path(unquote(parsed.path))
    elif parsed.scheme == "":
        path = Path(source_uri)
    else:
        raise ValueError(f"source is not a local path: {source_uri!r}")
    if not path.is_absolute():
        raise ValueError(f"local source path must be absolute: {source_uri!r}")
    return path


def _safe_destination(value: str, row: int) -> PurePosixPath:
    destination = PurePosixPath(value)
    if (
        not value
        or value == "."
        or destination.is_absolute()
        or destination.as_posix() != value
        or ".." in destination.parts
        or destination.suffix != ".jxl"
    ):
        raise ValueError(f"manifest row {row} has an unsafe destination: {value!r}")
    return destination


def _destination(root: Path, row: ManifestRow) -> Path:
    return root.joinpath(*_safe_destination(row.destination_relative, row.number).parts)


def _output_root(path: Path, *, create: bool) -> Path:
    if not path.is_absolute():
        raise ValueError(f"output root must be absolute: {path}")
    if create:
        path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise FileNotFoundError(f"output root does not exist: {path}")
    return path.resolve()


def _atomic_write(destination: Path, payload: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o660)
        temporary.replace(destination)
        directory = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    """Exclude concurrent conversion or verification under one output root."""
    with path.open("a", encoding="utf-8") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"another image conversion or verification holds {path}") from error
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n"
    _atomic_write(path, payload)


def _print_json(value: ConvertResult | VerifyResult) -> None:
    print(json.dumps(asdict(value), indent=2, sort_keys=True, allow_nan=False))


def _record(result: ConvertResult | VerifyResult) -> dict[str, object]:
    return {
        "codec": {
            "name": "jpegxl",
            "lossless": False,
            "distance": JPEGXL_DISTANCE,
            "effort": JPEGXL_EFFORT,
            "bitspersample": 16,
        },
        "result": asdict(result),
    }


def _positive(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _default_workers() -> int:
    return max(1, min(32, (os.cpu_count() or 4) // 4))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")
    commands = parser.add_subparsers(dest="command", required=True)
    convert = commands.add_parser("convert", help="convert absent manifest outputs")
    verify = commands.add_parser("verify", help="decode every manifest output")
    for command in (convert, verify):
        command.add_argument("--manifest", type=Path, required=True)
        command.add_argument("--output-root", type=Path, required=True)
        command.add_argument("--workers", type=int, default=_default_workers())
    convert.add_argument("--max-attempts", type=int, default=5)
    convert.add_argument("--max-consecutive-failures", type=int, default=32)
    return parser


def main(arguments: list[str] | None = None) -> int:
    """Run conversion or verification and return a process exit status."""
    parsed = _parser().parse_args(arguments)
    logging.basicConfig(
        level=getattr(logging, parsed.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        if parsed.command == "convert":
            result = convert_manifest(
                parsed.manifest,
                parsed.output_root,
                workers=parsed.workers,
                max_attempts=parsed.max_attempts,
                max_consecutive_failures=parsed.max_consecutive_failures,
            )
            _write_json(parsed.output_root / "jxl-run.json", _record(result))
        else:
            result = verify_manifest(parsed.manifest, parsed.output_root, workers=parsed.workers)
            _write_json(parsed.output_root / "jxl-validation.json", _record(result))
    except Exception:
        LOGGER.exception("image conversion command failed")
        return 1
    _print_json(result)
    if result.interrupted:
        return 130
    return 0 if result.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
