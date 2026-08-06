# ruff: noqa: CPY001, EM101, EM102, TRY003
"""Load the dataset description used by the image archive workflow."""

from __future__ import annotations

import re
import string
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

import tomllib

if TYPE_CHECKING:
    from collections.abc import Mapping

_MD5 = re.compile(r"[0-9a-f]{32}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_GIT_COMMIT = re.compile(r"[0-9a-f]{40}")
_TEMPLATE_FIELDS = {"codec_id", "batch", "plate", "stem"}
_MAX_CODEC_EFFORT = 10


class ContractError(ValueError):
    """Raised when a dataset description is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class IndexContract:
    """Pinned input index artifact."""

    record_id: int
    filename: str
    url: str
    size_bytes: int
    md5: str
    sha256: str


@dataclass(frozen=True, slots=True)
class SourceContract:
    """S3 source namespace."""

    bucket: str
    prefix: str
    anonymous: bool

    @property
    def uri_prefix(self) -> str:
        """Return the absolute S3 URI prefix."""
        return f"s3://{self.bucket}/{self.prefix}/"


@dataclass(frozen=True, slots=True)
class InventoryContract:
    """Expected input and generated-manifest inventory."""

    row_count: int
    complete_unique_tiff_uris: int
    incomplete_rows: int
    field_count: int
    plate_count: int
    channel_count: int
    manifest_sha256: str | None
    rejected_sha256: str | None


@dataclass(frozen=True, slots=True)
class CodecContract:
    """JPEG XL encoding settings and their provenance."""

    id: str
    name: str
    profile: str
    lossless: bool
    distance: float
    effort: int
    reference_repository: str
    reference_commit: str
    reference_path: str
    reference_sha256: str
    reference_tier: str


@dataclass(frozen=True, slots=True)
class DestinationContract:
    """Local archive root and relative object layout."""

    root: Path
    object_template: str

    def relative_path(self, *, codec_id: str, batch: str, plate: str, stem: str) -> Path:
        """Render one safe relative output path."""
        values = {"codec_id": codec_id, "batch": batch, "plate": plate, "stem": stem}
        if any(not _safe_component(value) for value in values.values()):
            raise ContractError("destination identifiers must be safe path components")
        relative = Path(self.object_template.format(**values))
        if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".jxl":
            raise ContractError("destination template produced an unsafe JPEG XL path")
        return relative


@dataclass(frozen=True, slots=True)
class Contract:
    """Authoritative description of one Axiom-style image archive."""

    index: IndexContract
    source: SourceContract
    inventory: InventoryContract
    codec: CodecContract
    destination: DestinationContract
    batches: tuple[str, ...]
    channels: Mapping[str, int]


def _section(raw: Mapping[str, Any], name: str, keys: set[str]) -> Mapping[str, Any]:
    value = raw.get(name)
    if not isinstance(value, dict):
        raise ContractError(f"[{name}] must be a TOML table")
    actual = set(value)
    if actual != keys:
        raise ContractError(
            f"[{name}] keys differ: missing={sorted(keys - actual)}, extra={sorted(actual - keys)}",
        )
    return value


def _string(table: Mapping[str, Any], key: str, section: str) -> str:
    value = table[key]
    if type(value) is not str or not value:
        raise ContractError(f"[{section}].{key} must be a non-empty string")
    return value


def _integer(table: Mapping[str, Any], key: str, section: str) -> int:
    value = table[key]
    if type(value) is not int:
        raise ContractError(f"[{section}].{key} must be an integer")
    return value


def _float(table: Mapping[str, Any], key: str, section: str) -> float:
    value = table[key]
    if type(value) is not float:
        raise ContractError(f"[{section}].{key} must be a float")
    return value


def _boolean(table: Mapping[str, Any], key: str, section: str) -> bool:
    value = table[key]
    if type(value) is not bool:
        raise ContractError(f"[{section}].{key} must be a boolean")
    return value


def _positive(value: int, label: str) -> int:
    if value < 1:
        raise ContractError(f"{label} must be positive")
    return value


def _nonnegative(value: int, label: str) -> int:
    if value < 0:
        raise ContractError(f"{label} must be non-negative")
    return value


def _digest(value: str, pattern: re.Pattern[str], label: str) -> str:
    if pattern.fullmatch(value) is None:
        raise ContractError(f"{label} must be lowercase hexadecimal")
    return value


def _optional_sha256(table: Mapping[str, Any], key: str, section: str) -> str | None:
    value = table[key]
    if type(value) is not str:
        raise ContractError(f"[{section}].{key} must be a string")
    return _digest(value, _SHA256, f"[{section}].{key}") if value else None


def _safe_component(value: str) -> bool:
    return bool(value) and "/" not in value and value not in {".", ".."}


def _safe_relative(value: str, label: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value.endswith("/"):
        raise ContractError(f"{label} must be a safe relative path")
    return value


def _https_url(value: str, label: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ContractError(f"{label} must be an HTTPS URL without credentials")
    return value


def _parse_channels(raw_channels: object) -> Mapping[str, int]:
    if not isinstance(raw_channels, list) or not raw_channels:
        raise ContractError("[[channels]] must contain at least one table")
    channels: dict[str, int] = {}
    numbers: set[int] = set()
    for position, entry in enumerate(raw_channels):
        if not isinstance(entry, dict) or set(entry) != {"source", "destination", "channel_number"}:
            raise ContractError(f"channels[{position}] has unexpected keys or type")
        source = _string(entry, "source", f"channels[{position}]")
        destination = _string(entry, "destination", f"channels[{position}]")
        number = _positive(_integer(entry, "channel_number", f"channels[{position}]"), "channel number")
        if source != destination:
            raise ContractError(f"channels[{position}] renames {source!r} to {destination!r}")
        if source in channels or number in numbers:
            raise ContractError("channel names and numbers must be unique")
        channels[source] = number
        numbers.add(number)
    return MappingProxyType(channels)


def _parse_batches(raw_batches: object) -> tuple[str, ...]:
    if not isinstance(raw_batches, list) or not raw_batches:
        raise ContractError("[[batches]] must contain at least one table")
    batches: list[str] = []
    for position, entry in enumerate(raw_batches):
        if not isinstance(entry, dict) or set(entry) != {"name"}:
            raise ContractError(f"batches[{position}] has unexpected keys or type")
        name = _string(entry, "name", f"batches[{position}]")
        if not _safe_component(name):
            raise ContractError(f"batches[{position}].name must be a safe path component")
        batches.append(name)
    if len(batches) != len(set(batches)):
        raise ContractError("batch names must be unique")
    return tuple(batches)


def _validate_template(destination: DestinationContract) -> None:
    parsed = tuple(string.Formatter().parse(destination.object_template))
    fields = [field for _, field, spec, conversion in parsed if field is not None and not spec and not conversion]
    if len(fields) != len(_TEMPLATE_FIELDS) or set(fields) != _TEMPLATE_FIELDS:
        raise ContractError(
            "destination template must contain codec_id, batch, plate, and stem exactly once",
        )
    destination.relative_path(codec_id="codec", batch="batch", plate="plate", stem="image")


def load_contract(path: Path) -> Contract:  # noqa: C901
    """Load and validate one dataset description without hidden pinned values."""
    try:
        with Path(path).open("rb") as stream:
            raw = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ContractError(f"cannot read contract {path}: {error}") from error

    expected_sections = {"index", "source", "inventory", "codec", "destination", "channels", "batches"}
    actual_sections = set(raw)
    if actual_sections != expected_sections:
        raise ContractError(
            "top-level contract sections differ: "
            f"missing={sorted(expected_sections - actual_sections)}, "
            f"extra={sorted(actual_sections - expected_sections)}",
        )

    index_raw = _section(raw, "index", {"record_id", "filename", "url", "size_bytes", "md5", "sha256"})
    index = IndexContract(
        record_id=_positive(_integer(index_raw, "record_id", "index"), "index.record_id"),
        filename=_string(index_raw, "filename", "index"),
        url=_https_url(_string(index_raw, "url", "index"), "index.url"),
        size_bytes=_positive(_integer(index_raw, "size_bytes", "index"), "index.size_bytes"),
        md5=_digest(_string(index_raw, "md5", "index"), _MD5, "index.md5"),
        sha256=_digest(_string(index_raw, "sha256", "index"), _SHA256, "index.sha256"),
    )
    if Path(index.filename).name != index.filename:
        raise ContractError("index.filename must be a basename")

    source_raw = _section(raw, "source", {"bucket", "prefix", "anonymous"})
    source = SourceContract(
        bucket=_string(source_raw, "bucket", "source"),
        prefix=_safe_relative(_string(source_raw, "prefix", "source"), "source.prefix"),
        anonymous=_boolean(source_raw, "anonymous", "source"),
    )
    if "/" in source.bucket:
        raise ContractError("source.bucket must be an S3 bucket name")

    inventory_raw = _section(
        raw,
        "inventory",
        {
            "row_count",
            "complete_unique_tiff_uris",
            "incomplete_rows",
            "field_count",
            "plate_count",
            "channel_count",
            "manifest_sha256",
            "rejected_sha256",
        },
    )
    inventory = InventoryContract(
        row_count=_nonnegative(_integer(inventory_raw, "row_count", "inventory"), "inventory.row_count"),
        complete_unique_tiff_uris=_nonnegative(
            _integer(inventory_raw, "complete_unique_tiff_uris", "inventory"),
            "inventory.complete_unique_tiff_uris",
        ),
        incomplete_rows=_nonnegative(
            _integer(inventory_raw, "incomplete_rows", "inventory"),
            "inventory.incomplete_rows",
        ),
        field_count=_nonnegative(_integer(inventory_raw, "field_count", "inventory"), "inventory.field_count"),
        plate_count=_nonnegative(_integer(inventory_raw, "plate_count", "inventory"), "inventory.plate_count"),
        channel_count=_positive(_integer(inventory_raw, "channel_count", "inventory"), "inventory.channel_count"),
        manifest_sha256=_optional_sha256(inventory_raw, "manifest_sha256", "inventory"),
        rejected_sha256=_optional_sha256(inventory_raw, "rejected_sha256", "inventory"),
    )
    if inventory.complete_unique_tiff_uris + inventory.incomplete_rows != inventory.row_count:
        raise ContractError("complete URI and incomplete row counts do not sum to row_count")
    if inventory.field_count * inventory.channel_count != inventory.complete_unique_tiff_uris:
        raise ContractError("field_count times channel_count does not equal complete URI count")

    codec_raw = _section(
        raw,
        "codec",
        {
            "id",
            "name",
            "profile",
            "lossless",
            "distance",
            "effort",
            "reference_repository",
            "reference_commit",
            "reference_path",
            "reference_sha256",
            "reference_tier",
        },
    )
    codec = CodecContract(
        id=_string(codec_raw, "id", "codec"),
        name=_string(codec_raw, "name", "codec"),
        profile=_string(codec_raw, "profile", "codec"),
        lossless=_boolean(codec_raw, "lossless", "codec"),
        distance=_float(codec_raw, "distance", "codec"),
        effort=_integer(codec_raw, "effort", "codec"),
        reference_repository=_https_url(
            _string(codec_raw, "reference_repository", "codec"),
            "codec.reference_repository",
        ),
        reference_commit=_digest(
            _string(codec_raw, "reference_commit", "codec"),
            _GIT_COMMIT,
            "codec.reference_commit",
        ),
        reference_path=_safe_relative(
            _string(codec_raw, "reference_path", "codec"),
            "codec.reference_path",
        ),
        reference_sha256=_digest(
            _string(codec_raw, "reference_sha256", "codec"),
            _SHA256,
            "codec.reference_sha256",
        ),
        reference_tier=_string(codec_raw, "reference_tier", "codec"),
    )
    if not _safe_component(codec.id) or codec.name != "jpegxl":
        raise ContractError("codec.id must be a safe component and codec.name must be 'jpegxl'")
    if codec.distance < 0 or not 1 <= codec.effort <= _MAX_CODEC_EFFORT:
        raise ContractError("codec distance must be non-negative and effort must be between 1 and 10")

    destination_raw = _section(raw, "destination", {"root", "object_template"})
    destination = DestinationContract(
        root=Path(_string(destination_raw, "root", "destination")),
        object_template=_string(destination_raw, "object_template", "destination"),
    )
    if not destination.root.is_absolute():
        raise ContractError("destination.root must be absolute")
    _validate_template(destination)

    channels = _parse_channels(raw["channels"])
    batches = _parse_batches(raw["batches"])
    if inventory.channel_count != len(channels):
        raise ContractError("inventory.channel_count differs from the channel mapping")

    return Contract(index, source, inventory, codec, destination, batches, channels)


__all__ = [
    "CodecContract",
    "Contract",
    "ContractError",
    "DestinationContract",
    "IndexContract",
    "InventoryContract",
    "SourceContract",
    "load_contract",
]
