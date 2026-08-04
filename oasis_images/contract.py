# ruff: noqa: CPY001, EM101, EM102, TRY003
"""Fail-closed source contract for the OASIS JPEG XL image archive."""

from __future__ import annotations

import re
import string
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Never
from urllib.parse import urlsplit

import tomllib

if TYPE_CHECKING:
    from collections.abc import Mapping

INDEX_RECORD_ID: Final = 17_067_683
INDEX_FILENAME: Final = "index.parquet"
INDEX_URL: Final = "https://zenodo.org/api/records/17067683/files/index.parquet/content"
INDEX_SIZE_BYTES: Final = 2_524_798
INDEX_MD5: Final = "b56e249504f76bc2f6025f90abc8608c"
INDEX_SHA256: Final = "f83a16fa21a5ec20df433706ef889dc7cc8003ff5aabb057e9e54d6903be73f9"
SOURCE_BUCKET: Final = "cellpainting-gallery"
SOURCE_PREFIX: Final = "cpg0037-oasis/axiom/images"
SOURCE_ANONYMOUS: Final = True
EXPECTED_ROW_COUNT: Final = 2_019_342
EXPECTED_COMPLETE_URIS: Final = 2_017_182
EXPECTED_INCOMPLETE_ROWS: Final = 2_160
EXPECTED_FIELD_COUNT: Final = 336_197
EXPECTED_PLATE_COUNT: Final = 68
EXPECTED_CHANNEL_COUNT: Final = 6
EXPECTED_MANIFEST_SHA256: Final = "b8c20a37213831b55161a8ed9fe0a1c60522c8951f2b5e19713c7105c8200381"
EXPECTED_REJECTED_SHA256: Final = "0bd61c7b852530c8d3ec491f2a99bab2f4cf15bbf1b015389c571ca7c768a66a"
CODEC_ID: Final = "jpegxl-d1-e5"
CODEC_NAME: Final = "jpegxl"
CODEC_PROFILE: Final = "hq"
CODEC_LOSSLESS: Final = False
CODEC_DISTANCE: Final = 1.0
CODEC_EFFORT: Final = 5
CODEC_REFERENCE_REPOSITORY: Final = "https://github.com/afermg/JUMP_lite"
CODEC_REFERENCE_COMMIT: Final = "5f0fc9be6135e74cfee0b3504fd20a35a9531a22"
CODEC_REFERENCE_PATH: Final = "src/compress_tif.py"
CODEC_REFERENCE_SHA256: Final = "9bb6bec0a23a8fb091c1e1990f62690c55b74e34d1a49165b21bbb1aabaa54bf"
CODEC_REFERENCE_TIER: Final = "jpegxl_lossy_hq"
DESTINATION_ROOT: Final = Path("/work/datasets/cpg0037-oasis/axiom/images-jxl/v1")
DESTINATION_TEMPLATE: Final = "{codec_id}/{batch}/images/{plate}/{stem}.jxl"
EXPECTED_BATCHES: Final = ("prod_25", "prod_26", "prod_27", "prod_30")
EXPECTED_CHANNELS: Final = (
    ("DNA", 1),
    ("ER", 2),
    ("AGP", 3),
    ("RNA", 4),
    ("Mito", 5),
    ("Brightfield", 6),
)


class ContractError(ValueError):
    """Raised when a source contract differs from the frozen archive contract."""


class FrozenDict(dict[str, int]):
    """Small immutable dictionary used by the frozen contract dataclass."""

    @staticmethod
    def _immutable() -> Never:
        raise TypeError("contract channel mapping is immutable")

    def __setitem__(self, _key: str, _value: int) -> Never:
        """Reject item assignment."""
        self._immutable()

    def __delitem__(self, _key: str) -> Never:
        """Reject item deletion."""
        self._immutable()

    def clear(self) -> Never:
        """Reject clearing the mapping."""
        self._immutable()

    def pop(self, _key: str, _default: object = None) -> Never:
        """Reject removing an item."""
        self._immutable()

    def popitem(self) -> Never:
        """Reject removing an arbitrary item."""
        self._immutable()

    def setdefault(self, _key: str, _default: int | None = None) -> Never:
        """Reject inserting a default item."""
        self._immutable()

    def update(self, *_args: object, **_kwargs: int) -> Never:
        """Reject bulk mutation."""
        self._immutable()

    def __ior__(self, _value: object) -> Never:
        """Reject in-place union."""
        self._immutable()


@dataclass(frozen=True, slots=True)
class IndexContract:
    """Pinned Zenodo image-index artifact."""

    record_id: int
    filename: str
    url: str
    size_bytes: int
    md5: str
    sha256: str


@dataclass(frozen=True, slots=True)
class SourceContract:
    """Pinned public S3 source namespace."""

    bucket: str
    prefix: str
    anonymous: bool

    @property
    def uri_prefix(self) -> str:
        """Return the canonical absolute S3 URI prefix."""
        return f"s3://{self.bucket}/{self.prefix}/"


@dataclass(frozen=True, slots=True)
class InventoryContract:
    """Expected long-form image-index inventory."""

    row_count: int
    complete_unique_tiff_uris: int
    incomplete_rows: int
    field_count: int
    plate_count: int
    channel_count: int
    manifest_sha256: str | None = None
    rejected_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class CodecContract:
    """Pinned JPEG XL encoding tier."""

    id: str
    name: str
    profile: str
    lossless: bool
    distance: float
    effort: int
    reference_repository: str = CODEC_REFERENCE_REPOSITORY
    reference_commit: str = CODEC_REFERENCE_COMMIT
    reference_path: str = CODEC_REFERENCE_PATH
    reference_sha256: str = CODEC_REFERENCE_SHA256
    reference_tier: str = CODEC_REFERENCE_TIER


@dataclass(frozen=True, slots=True)
class DestinationContract:
    """Pinned local archive layout."""

    root: Path
    object_template: str

    def relative_path(self, *, codec_id: str, batch: str, plate: str, stem: str) -> Path:
        """Render one relative archive object path from validated identifiers."""
        values = {
            "codec_id": codec_id,
            "batch": batch,
            "plate": plate,
            "stem": stem,
        }
        if any(not value or "/" in value or value in {".", ".."} for value in values.values()):
            raise ContractError("destination identifiers must be non-empty path components")
        relative = Path(self.object_template.format(**values))
        if relative.is_absolute() or ".." in relative.parts:
            raise ContractError("destination template produced an unsafe relative path")
        return relative


@dataclass(frozen=True, slots=True)
class Contract:
    """Complete immutable contract for one OASIS JPEG XL archive version."""

    index: IndexContract
    source: SourceContract
    inventory: InventoryContract
    codec: CodecContract
    destination: DestinationContract
    batches: tuple[str, ...]
    channels: FrozenDict

    @property
    def channel_numbers(self) -> dict[str, int]:
        """Return an immutable channel-name-to-number mapping."""
        return self.channels

    @property
    def index_url(self) -> str:
        """Return the pinned index URL."""
        return self.index.url

    @property
    def index_size_bytes(self) -> int:
        """Return the pinned index size."""
        return self.index.size_bytes

    @property
    def index_md5(self) -> str:
        """Return the pinned index MD5."""
        return self.index.md5

    @property
    def index_sha256(self) -> str:
        """Return the pinned index SHA-256."""
        return self.index.sha256

    @property
    def source_bucket(self) -> str:
        """Return the pinned source bucket."""
        return self.source.bucket

    @property
    def source_prefix(self) -> str:
        """Return the pinned source prefix."""
        return self.source.prefix

    @property
    def source_anonymous(self) -> bool:
        """Return whether source access is anonymous."""
        return self.source.anonymous

    @property
    def codec_id(self) -> str:
        """Return the pinned codec identifier."""
        return self.codec.id

    @property
    def destination_root(self) -> Path:
        """Return the pinned archive root."""
        return self.destination.root

    @property
    def destination_template(self) -> str:
        """Return the pinned relative object template."""
        return self.destination.object_template


ArchiveContract = Contract


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
    if type(value) is not str:
        raise ContractError(f"[{section}].{key} must be a string")
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


def _require_equal(label: str, actual: object, expected: object) -> None:
    if actual != expected or type(actual) is not type(expected):
        raise ContractError(f"{label} differs from the pinned value: {actual!r}")


def _parse_channels(raw_channels: object) -> tuple[tuple[str, int], ...]:
    if not isinstance(raw_channels, list):
        raise ContractError("[[channels]] must be an array of tables")
    pairs: list[tuple[str, int]] = []
    for position, entry in enumerate(raw_channels):
        if not isinstance(entry, dict) or set(entry) != {"source", "destination", "channel_number"}:
            raise ContractError(f"channels[{position}] has unexpected keys or type")
        source = _string(entry, "source", f"channels[{position}]")
        destination = _string(entry, "destination", f"channels[{position}]")
        number = _integer(entry, "channel_number", f"channels[{position}]")
        if source != destination:
            raise ContractError(f"channels[{position}] renames {source!r} to {destination!r}")
        pairs.append((source, number))
    result = tuple(pairs)
    _require_equal("channel mapping", result, EXPECTED_CHANNELS)
    return result


def _parse_batches(raw_batches: object) -> tuple[str, ...]:
    if not isinstance(raw_batches, list):
        raise ContractError("[[batches]] must be an array of tables")
    batches: list[str] = []
    for position, entry in enumerate(raw_batches):
        if not isinstance(entry, dict) or set(entry) != {"name"}:
            raise ContractError(f"batches[{position}] has unexpected keys or type")
        batches.append(_string(entry, "name", f"batches[{position}]"))
    result = tuple(batches)
    _require_equal("batch inventory", result, EXPECTED_BATCHES)
    return result


def _validate_template(template: str) -> None:
    parsed = tuple(string.Formatter().parse(template))
    fields = tuple(field for _, field, spec, conversion in parsed if field is not None and not spec and not conversion)
    if fields != ("codec_id", "batch", "plate", "stem"):
        raise ContractError("destination template placeholders or formatting differ")
    sample = template.format(codec_id="jpegxl-d1-e5", batch="prod_25", plate="plate_00000001", stem="image")
    if sample != "jpegxl-d1-e5/prod_25/images/plate_00000001/image.jxl":
        raise ContractError("destination template does not produce the required object layout")


def _validate_index_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "zenodo.org"
        or parsed.path != "/api/records/17067683/files/index.parquet/content"
        or parsed.query
        or parsed.fragment
    ):
        raise ContractError("index URL is not the pinned Zenodo content endpoint")


def load_contract(path: Path) -> Contract:  # noqa: C901, PLR0912, PLR0915
    """Load and fully validate the frozen archive contract at ``path``."""
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
        record_id=_integer(index_raw, "record_id", "index"),
        filename=_string(index_raw, "filename", "index"),
        url=_string(index_raw, "url", "index"),
        size_bytes=_integer(index_raw, "size_bytes", "index"),
        md5=_string(index_raw, "md5", "index"),
        sha256=_string(index_raw, "sha256", "index"),
    )
    _require_equal("index.record_id", index.record_id, INDEX_RECORD_ID)
    _require_equal("index.filename", index.filename, INDEX_FILENAME)
    _require_equal("index.url", index.url, INDEX_URL)
    _require_equal("index.size_bytes", index.size_bytes, INDEX_SIZE_BYTES)
    _require_equal("index.md5", index.md5, INDEX_MD5)
    _require_equal("index.sha256", index.sha256, INDEX_SHA256)
    if re.fullmatch(r"[0-9a-f]{32}", index.md5) is None:
        raise ContractError("index.md5 must be lowercase hexadecimal")
    if re.fullmatch(r"[0-9a-f]{64}", index.sha256) is None:
        raise ContractError("index.sha256 must be lowercase hexadecimal")
    _validate_index_url(index.url)

    source_raw = _section(raw, "source", {"bucket", "prefix", "anonymous"})
    source = SourceContract(
        bucket=_string(source_raw, "bucket", "source"),
        prefix=_string(source_raw, "prefix", "source"),
        anonymous=_boolean(source_raw, "anonymous", "source"),
    )
    _require_equal("source.bucket", source.bucket, SOURCE_BUCKET)
    _require_equal("source.prefix", source.prefix, SOURCE_PREFIX)
    _require_equal("source.anonymous", source.anonymous, SOURCE_ANONYMOUS)
    if source.prefix.startswith("/") or source.prefix.endswith("/") or ".." in source.prefix.split("/"):
        raise ContractError("source.prefix must be a safe relative S3 key prefix")
    if source.uri_prefix != "s3://cellpainting-gallery/cpg0037-oasis/axiom/images/":
        raise ContractError("source URI shape differs from the pinned S3 namespace")

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
        row_count=_integer(inventory_raw, "row_count", "inventory"),
        complete_unique_tiff_uris=_integer(inventory_raw, "complete_unique_tiff_uris", "inventory"),
        incomplete_rows=_integer(inventory_raw, "incomplete_rows", "inventory"),
        field_count=_integer(inventory_raw, "field_count", "inventory"),
        plate_count=_integer(inventory_raw, "plate_count", "inventory"),
        channel_count=_integer(inventory_raw, "channel_count", "inventory"),
        manifest_sha256=_string(inventory_raw, "manifest_sha256", "inventory"),
        rejected_sha256=_string(inventory_raw, "rejected_sha256", "inventory"),
    )
    expected_inventory = (
        EXPECTED_ROW_COUNT,
        EXPECTED_COMPLETE_URIS,
        EXPECTED_INCOMPLETE_ROWS,
        EXPECTED_FIELD_COUNT,
        EXPECTED_PLATE_COUNT,
        EXPECTED_CHANNEL_COUNT,
    )
    actual_inventory = (
        inventory.row_count,
        inventory.complete_unique_tiff_uris,
        inventory.incomplete_rows,
        inventory.field_count,
        inventory.plate_count,
        inventory.channel_count,
    )
    _require_equal("inventory counts", actual_inventory, expected_inventory)
    _require_equal("inventory.manifest_sha256", inventory.manifest_sha256, EXPECTED_MANIFEST_SHA256)
    _require_equal("inventory.rejected_sha256", inventory.rejected_sha256, EXPECTED_REJECTED_SHA256)
    if inventory.manifest_sha256 is None or re.fullmatch(r"[0-9a-f]{64}", inventory.manifest_sha256) is None:
        raise ContractError("inventory.manifest_sha256 must be lowercase hexadecimal")
    if inventory.rejected_sha256 is None or re.fullmatch(r"[0-9a-f]{64}", inventory.rejected_sha256) is None:
        raise ContractError("inventory.rejected_sha256 must be lowercase hexadecimal")
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
        reference_repository=_string(codec_raw, "reference_repository", "codec"),
        reference_commit=_string(codec_raw, "reference_commit", "codec"),
        reference_path=_string(codec_raw, "reference_path", "codec"),
        reference_sha256=_string(codec_raw, "reference_sha256", "codec"),
        reference_tier=_string(codec_raw, "reference_tier", "codec"),
    )
    _require_equal("codec.id", codec.id, CODEC_ID)
    _require_equal("codec.name", codec.name, CODEC_NAME)
    _require_equal("codec.profile", codec.profile, CODEC_PROFILE)
    _require_equal("codec.lossless", codec.lossless, CODEC_LOSSLESS)
    _require_equal("codec.distance", codec.distance, CODEC_DISTANCE)
    _require_equal("codec.effort", codec.effort, CODEC_EFFORT)
    _require_equal("codec.reference_repository", codec.reference_repository, CODEC_REFERENCE_REPOSITORY)
    _require_equal("codec.reference_commit", codec.reference_commit, CODEC_REFERENCE_COMMIT)
    _require_equal("codec.reference_path", codec.reference_path, CODEC_REFERENCE_PATH)
    _require_equal("codec.reference_sha256", codec.reference_sha256, CODEC_REFERENCE_SHA256)
    _require_equal("codec.reference_tier", codec.reference_tier, CODEC_REFERENCE_TIER)
    if re.fullmatch(r"[0-9a-f]{40}", codec.reference_commit) is None:
        raise ContractError("codec.reference_commit must be a full lowercase Git commit")
    if re.fullmatch(r"[0-9a-f]{64}", codec.reference_sha256) is None:
        raise ContractError("codec.reference_sha256 must be lowercase hexadecimal")

    destination_raw = _section(raw, "destination", {"root", "object_template"})
    destination = DestinationContract(
        root=Path(_string(destination_raw, "root", "destination")),
        object_template=_string(destination_raw, "object_template", "destination"),
    )
    _require_equal("destination.root", destination.root, DESTINATION_ROOT)
    _require_equal("destination.object_template", destination.object_template, DESTINATION_TEMPLATE)
    if not destination.root.is_absolute():
        raise ContractError("destination.root must be absolute")
    _validate_template(destination.object_template)

    channel_pairs = _parse_channels(raw["channels"])
    batches = _parse_batches(raw["batches"])
    if inventory.channel_count != len(channel_pairs):
        raise ContractError("inventory.channel_count differs from the channel mapping")

    return Contract(
        index=index,
        source=source,
        inventory=inventory,
        codec=codec,
        destination=destination,
        batches=batches,
        channels=FrozenDict(channel_pairs),
    )


__all__ = [
    "ArchiveContract",
    "CodecContract",
    "Contract",
    "ContractError",
    "DestinationContract",
    "FrozenDict",
    "IndexContract",
    "InventoryContract",
    "SourceContract",
    "load_contract",
]
