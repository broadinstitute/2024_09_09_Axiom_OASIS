# ruff: noqa: CPY001, EM101, EM102, TRY003
"""Small runtime plan shared by dataset adapters and the archive engine."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import partial
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from .contract import CodecContract, Contract, SourceContract

_SHA256 = re.compile(r"[0-9a-f]{64}")
_IMAGE_DIMENSIONS = 2
_AXIOM_SOURCE_PARTS = 4


@dataclass(frozen=True, slots=True)
class ArchivePlan:
    """Everything the generic conversion loop needs from one dataset."""

    source: SourceContract
    destination_root: Path
    codec: CodecContract
    manifest_sha256: str
    manifest_rows: int
    rejected_sha256: str
    rejected_rows: int
    image_shape: tuple[int, int]
    image_dtype: str
    validate_row: Callable[[str, str, str], None]

    def __post_init__(self) -> None:
        """Reject incomplete plans before any ledger or object access."""
        if not self.destination_root.is_absolute():
            raise ValueError("destination_root must be absolute")
        for name, digest in (
            ("manifest_sha256", self.manifest_sha256),
            ("rejected_sha256", self.rejected_sha256),
        ):
            if _SHA256.fullmatch(digest) is None:
                raise ValueError(f"{name} must be 64 lowercase hexadecimal characters")
        for name, count in (("manifest_rows", self.manifest_rows), ("rejected_rows", self.rejected_rows)):
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if (
            type(self.image_shape) is not tuple
            or len(self.image_shape) != _IMAGE_DIMENSIONS
            or any(type(dimension) is not int or dimension < 1 for dimension in self.image_shape)
        ):
            raise ValueError("image_shape must be a pair of positive integers")
        if self.image_dtype != "uint16":
            raise ValueError("the current archive codec requires uint16 images")
        if not callable(self.validate_row):
            raise TypeError("validate_row must be callable")


def axiom_archive_plan(contract: Contract) -> ArchivePlan:
    """Adapt the frozen Axiom contract to the small generic runtime plan."""
    manifest_sha256 = contract.inventory.manifest_sha256
    rejected_sha256 = contract.inventory.rejected_sha256
    if manifest_sha256 is None or rejected_sha256 is None:
        raise ValueError("archive execution requires pinned manifest and rejected artifacts")
    return ArchivePlan(
        source=contract.source,
        destination_root=contract.destination.root,
        codec=contract.codec,
        manifest_sha256=manifest_sha256,
        manifest_rows=contract.inventory.complete_unique_tiff_uris,
        rejected_sha256=rejected_sha256,
        rejected_rows=contract.inventory.incomplete_rows,
        image_shape=(2160, 2160),
        image_dtype="uint16",
        validate_row=partial(_validate_axiom_row, contract),
    )


def _validate_axiom_row(
    contract: Contract,
    source_key: str,
    _source_uri: str,
    destination_relative: str,
) -> None:
    relative = PurePosixPath(source_key.removeprefix(f"{contract.source.prefix}/"))
    if len(relative.parts) != _AXIOM_SOURCE_PARTS or relative.parts[1] != "images":
        raise ValueError(f"source key has an invalid Axiom layout: {source_key}")
    batch, _, plate, filename = relative.parts
    if batch not in contract.batches or not filename.endswith(".tiff"):
        raise ValueError(f"source key has an invalid Axiom batch or TIFF suffix: {source_key}")
    expected = contract.destination.relative_path(
        codec_id=contract.codec.id,
        batch=batch,
        plate=plate,
        stem=filename.removesuffix(".tiff"),
    ).as_posix()
    if destination_relative != expected:
        raise ValueError(
            f"destination does not match its source TIFF: actual={destination_relative!r}, expected={expected!r}",
        )


__all__ = ["ArchivePlan", "axiom_archive_plan"]
