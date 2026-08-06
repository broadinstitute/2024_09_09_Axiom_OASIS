# ruff: noqa: CPY001, EM102, TRY003
"""Small filesystem helpers shared by the archive commands."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import socket
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

_HASH_BLOCK_SIZE = 8 * 1024 * 1024


@contextmanager
def exclusive_workflow_lock(path: Path, operation: str) -> Iterator[None]:
    """Hold one non-blocking advisory lock for a mutating archive workflow."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as stream:
        path.chmod(0o660)
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            stream.seek(0)
            holder = stream.read().strip() or "holder metadata unavailable"
            raise RuntimeError(f"archive workflow lock is already held at {path}: {holder}") from error

        metadata = {
            "hostname": socket.gethostname(),
            "operation": operation,
            "pid": os.getpid(),
            "started_at": datetime.now(UTC).isoformat(),
        }
        stream.seek(0)
        stream.truncate()
        json.dump(metadata, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase SHA-256 digest for in-memory bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Hash a file without loading the whole object into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(_HASH_BLOCK_SIZE):
            digest.update(block)
    return digest.hexdigest()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Durably replace a file after writing and syncing a sibling temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.chmod(0o660)
        temporary_path.replace(path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, value: object) -> None:
    """Write deterministic, human-readable JSON through the atomic byte helper."""
    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False)
    atomic_write_bytes(path, f"{payload}\n".encode())


def safe_destination(root: Path, relative: str) -> Path:
    """Resolve a contract path while rejecting absolute paths and traversal."""
    relative_path = PurePosixPath(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(f"unsafe destination path: {relative!r}")
    resolved_root = root.resolve()
    resolved_path = (resolved_root / Path(*relative_path.parts)).resolve()
    if not resolved_path.is_relative_to(resolved_root):
        raise ValueError(f"destination escapes archive root: {relative!r}")
    return resolved_path


def ensure_group_directories(root: Path, directory: Path) -> None:
    """Create an in-root directory chain with shared setgid permissions."""
    resolved_root = root.resolve()
    resolved_directory = directory.resolve()
    if not resolved_directory.is_relative_to(resolved_root):
        raise ValueError(f"directory escapes archive root: {directory}")
    current = resolved_root
    for component in resolved_directory.relative_to(resolved_root).parts:
        current /= component
        current.mkdir(exist_ok=True)
        current.chmod(0o2770)
