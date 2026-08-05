# /// script
# requires-python = "==3.11.*"
# dependencies = [
#   "matplotlib==3.9.2",
#   "numpy==1.24.3",
#   "pillow==12.3.0",
#   "polars==1.43.2",
# ]
# ///
# ruff: noqa: EM101, EM102, PLR0913, PLR2004, T201, TRY003
"""Recover the external source image for supplemental Figure S1.

The script resolves the exact published plate, well, and site from the image
index, acquires the five Cell Painting TIFFs, and renders the channel strip and
composite used by the original notebook.  It also reports the image inventory
that can be counted directly from the current index and metadata inputs.

Run it with ``uv run paper/render_sfig1.py --output-dir reproduction/sfig1``.
Add ``--offline`` to prohibit network access.

The offline form never contacts the network.  It requires the TIFF cache under
OUTPUT_DIR/tiffs to have been populated by an earlier run or by the caller.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "oasis-sfig1-matplotlib"))

import matplotlib as mpl

mpl.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Rectangle
from PIL import Image

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = REPOSITORY_ROOT / "1_snakemake/inputs/images/index.parquet"
DEFAULT_METADATA = REPOSITORY_ROOT / "1_snakemake/inputs/metadata/metadata.parquet"

TARGET_PLATE = "plate_41002889"
TARGET_WELL = "L12"
TARGET_SITE = 6
CHANNELS = ("DNA", "ER", "AGP", "RNA", "Mito")
CHANNEL_NORMALIZATION = {
    "DNA": 11_000.0,
    "ER": 13_000.0,
    "AGP": 8_000.0,
    "RNA": 7_000.0,
    "Mito": 11_000.0,
}
PUBLISHED_TOTAL_IMAGES = 191_754
PUBLISHED_DMSO_IMAGES = 43_641
DEFAULT_PNG_NAME = "figure-s1-reproduced.png"
DEFAULT_REPORT_NAME = "figure-s1-report.json"
COPY_BUFFER_BYTES = 1024 * 1024
MICRONS_PER_PIXEL = 323 / 2160
SCALE_BAR_MICRONS = 20


class FigureS1Error(RuntimeError):
    """Raised when Figure S1 cannot be reproduced without guessing."""


@dataclass(frozen=True)
class ChannelSource:
    """One resolved channel and its exact source URI."""

    channel: str
    batch: str
    uri: str


def _require_columns(frame: pl.DataFrame, columns: Sequence[str], label: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise FigureS1Error(f"{label} is missing required columns: {', '.join(missing)}")


def resolve_channel_sources(index: pl.DataFrame) -> tuple[ChannelSource, ...]:
    """Resolve exactly one URI for each published Figure S1 channel."""
    required = (
        "Metadata_Batch",
        "Metadata_Plate",
        "Metadata_Well",
        "Metadata_Site",
        "Channel",
        "Filename",
    )
    _require_columns(index, required, "image index")

    selected = index.filter(
        (pl.col("Metadata_Plate") == TARGET_PLATE)
        & (pl.col("Metadata_Well") == TARGET_WELL)
        & (pl.col("Metadata_Site").cast(pl.Float64) == float(TARGET_SITE))
        & pl.col("Channel").is_in(CHANNELS),
    ).select("Metadata_Batch", "Channel", "Filename")

    sources: list[ChannelSource] = []
    for channel in CHANNELS:
        rows = selected.filter(pl.col("Channel") == channel)
        if rows.height != 1:
            raise FigureS1Error(
                f"expected one {channel} row for {TARGET_PLATE}/{TARGET_WELL}/site {TARGET_SITE}, found {rows.height}",
            )
        row = rows.row(0, named=True)
        batch = row["Metadata_Batch"]
        uri = row["Filename"]
        if not isinstance(batch, str) or not batch:
            raise FigureS1Error(f"{channel} has no image batch")
        if not isinstance(uri, str) or not uri:
            raise FigureS1Error(f"{channel} has no source URI")
        _download_url(uri)
        sources.append(ChannelSource(channel=channel, batch=batch, uri=uri))

    if len({source.uri for source in sources}) != len(CHANNELS):
        raise FigureS1Error("the five channels do not resolve to five distinct TIFF URIs")
    if len({source.batch for source in sources}) != 1:
        raise FigureS1Error("the five channels resolve to more than one image batch")
    return tuple(sources)


def resolve_target_metadata(metadata: pl.DataFrame) -> dict[str, object]:
    """Confirm that the requested plate and well are a DMSO control."""
    required = ("Metadata_Plate", "Metadata_Well", "Metadata_Compound")
    _require_columns(metadata, required, "metadata")
    selected = metadata.filter(
        (pl.col("Metadata_Plate") == TARGET_PLATE) & (pl.col("Metadata_Well") == TARGET_WELL),
    )
    compounds = sorted(
        value
        for value in selected.get_column("Metadata_Compound").drop_nulls().cast(pl.String).unique().to_list()
        if value
    )
    if compounds != ["DMSO"]:
        rendered = ", ".join(compounds) if compounds else "none"
        raise FigureS1Error(f"target metadata must resolve only to DMSO, found: {rendered}")
    return {"compound": "DMSO", "metadata_rows": selected.height}


def count_inventory(index: pl.DataFrame, metadata: pl.DataFrame) -> dict[str, object]:
    """Count distinct image fields after joining the current metadata."""
    identity = ("Metadata_Plate", "Metadata_Well", "Metadata_Site")
    metadata_columns = ("Metadata_Plate", "Metadata_Well", "Metadata_Compound")
    _require_columns(index, identity, "image index")
    _require_columns(metadata, metadata_columns, "metadata")

    fields = index.select(identity).unique()
    compounds = metadata.select(metadata_columns).unique()
    joined = fields.join(compounds, on=("Metadata_Plate", "Metadata_Well"), how="inner")
    current_total = joined.select(identity).unique().height
    current_dmso = (
        joined.filter(
            pl.col("Metadata_Compound").cast(pl.String).str.to_uppercase() == "DMSO",
        )
        .select(identity)
        .unique()
        .height
    )
    exact = current_total == PUBLISHED_TOTAL_IMAGES and current_dmso == PUBLISHED_DMSO_IMAGES
    deviation = None
    if not exact:
        deviation = (
            "The current index-to-metadata join does not equal the published inventory. "
            "The published counts appear to use an unexplained 9-site rule that is not encoded in the repository, "
            "so this reproduction counts every distinct plate/well/site and does not invent that filter."
        )
    return {
        "counting_method": "distinct plate/well/site after inner join on plate/well",
        "current_total": current_total,
        "current_dmso": current_dmso,
        "published_total": PUBLISHED_TOTAL_IMAGES,
        "published_dmso": PUBLISHED_DMSO_IMAGES,
        "total_difference": current_total - PUBLISHED_TOTAL_IMAGES,
        "dmso_difference": current_dmso - PUBLISHED_DMSO_IMAGES,
        "matches_published": exact,
        "outcome": "reproduced" if exact else "reproduced-with-deviation",
        "nine_site_rule_encoded": False,
        "deviation": deviation,
    }


def _download_url(uri: str) -> str:
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme == "s3":
        if not parsed.netloc or not parsed.path.strip("/"):
            raise FigureS1Error(f"invalid S3 URI: {uri}")
        key = urllib.parse.quote(parsed.path.lstrip("/"), safe="/")
        return f"https://{parsed.netloc}.s3.amazonaws.com/{key}"
    if parsed.scheme == "https" and parsed.netloc:
        return uri
    raise FigureS1Error(f"unsupported TIFF URI: {uri}")


def cache_path(output_dir: Path, source: ChannelSource) -> Path:
    """Return the deterministic local cache path for a source TIFF."""
    basename = Path(urllib.parse.urlparse(source.uri).path).name
    if not basename or Path(basename).suffix.lower() not in {".tif", ".tiff"}:
        raise FigureS1Error(f"source URI does not name a TIFF: {source.uri}")
    return output_dir / "tiffs" / f"{source.channel.lower()}-{basename}"


def _copy_response(response: BinaryIO, destination: BinaryIO) -> None:
    while chunk := response.read(COPY_BUFFER_BYTES):
        destination.write(chunk)


def acquire_tiffs(
    sources: Sequence[ChannelSource],
    output_dir: Path,
    *,
    offline: bool,
    timeout_seconds: float = 120.0,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Path]:
    """Populate the TIFF cache, using atomic replacement for downloads."""
    if opener is None:
        opener = urllib.request.urlopen
    tiff_dir = output_dir / "tiffs"
    tiff_dir.mkdir(parents=True, exist_ok=True)
    acquired: dict[str, Path] = {}
    for source in sources:
        destination = cache_path(output_dir, source)
        if destination.is_file() and destination.stat().st_size > 0:
            acquired[source.channel] = destination
            continue
        if offline:
            raise FigureS1Error(f"offline TIFF is missing or empty: {destination}")

        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=tiff_dir,
                prefix=f".{destination.name}.",
                suffix=".part",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                with opener(_download_url(source.uri), timeout=timeout_seconds) as response:
                    _copy_response(response, handle)
                handle.flush()
                os.fsync(handle.fileno())
            if temporary.stat().st_size == 0:
                raise FigureS1Error(f"downloaded TIFF is empty: {source.uri}")
            temporary.replace(destination)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        acquired[source.channel] = destination
    return acquired


def _read_and_normalize(tiff_paths: Mapping[str, Path]) -> dict[str, np.ndarray[Any, Any]]:
    normalized: dict[str, np.ndarray[Any, Any]] = {}
    expected_shape: tuple[int, int] | None = None
    for channel in CHANNELS:
        path = tiff_paths.get(channel)
        if path is None:
            raise FigureS1Error(f"no local TIFF was provided for {channel}")
        try:
            with Image.open(path) as image:
                pixels = np.asarray(image)
        except Exception as error:
            raise FigureS1Error(f"cannot read {channel} TIFF {path}: {error}") from error
        if pixels.ndim != 2:
            raise FigureS1Error(f"{channel} TIFF is not a two-dimensional grayscale image")
        shape = (int(pixels.shape[0]), int(pixels.shape[1]))
        if expected_shape is None:
            expected_shape = shape
        elif shape != expected_shape:
            raise FigureS1Error(f"{channel} TIFF shape {shape} does not match {expected_shape}")
        normalized[channel] = pixels.astype(np.float32) / CHANNEL_NORMALIZATION[channel]
    return normalized


def render_figure(tiff_paths: Mapping[str, Path], png_path: Path, *, dpi: int = 300) -> None:
    """Render five grayscale channels and the notebook-equivalent composite."""
    channels = _read_and_normalize(tiff_paths)
    height, width = channels[CHANNELS[0]].shape
    rgb = np.zeros((height, width, 3), dtype=np.float32)
    rgb[:, :, 0] = channels["Mito"] + channels["AGP"] + channels["RNA"]
    rgb[:, :, 1] = channels["ER"] + channels["AGP"]
    rgb[:, :, 2] = channels["DNA"] + channels["RNA"]
    rgb = np.clip(rgb, 0.0, 1.0)

    figure = plt.figure(figsize=(10, 12))
    grid = GridSpec(2, 5, figure=figure, height_ratios=[1, 4], hspace=0.01, wspace=0.01)
    for index, channel in enumerate(CHANNELS):
        axis = figure.add_subplot(grid[0, index])
        axis.imshow(channels[channel], cmap="gray")
        axis.set_title(channel, fontsize=10)
        axis.axis("off")

    combined = figure.add_subplot(grid[1, :])
    combined.imshow(rgb, vmin=0.0, vmax=1.0)
    combined.axis("off")
    scale_bar_pixels = SCALE_BAR_MICRONS / MICRONS_PER_PIXEL
    bar_height = 12
    padding = 50
    x_position = width - scale_bar_pixels - padding
    y_position = height - bar_height - padding
    combined.add_patch(
        Rectangle((x_position, y_position), scale_bar_pixels, bar_height, color="white"),
    )
    combined.text(
        x_position + scale_bar_pixels / 2,
        y_position - 10,
        f"{SCALE_BAR_MICRONS} um",
        color="white",
        ha="center",
        va="bottom",
        fontsize=10,
    )
    figure.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)

    png_path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=png_path.parent,
            prefix=f".{png_path.name}.",
            suffix=".png",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
        figure.savefig(
            temporary,
            dpi=dpi,
            bbox_inches="tight",
            pad_inches=0,
            metadata={"Software": "paper/render_sfig1.py"},
        )
        temporary.replace(png_path)
        temporary = None
    finally:
        plt.close(figure)
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _file_record(path: Path, *, relative_to: Path | None = None) -> dict[str, object]:
    local_path = path.name if relative_to is None else path.relative_to(relative_to).as_posix()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(COPY_BUFFER_BYTES):
            digest.update(chunk)
    return {
        "path": local_path,
        "bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def _atomic_write_json(path: Path, report: Mapping[str, object]) -> None:
    text = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="ascii",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def reproduce(
    index_path: Path,
    metadata_path: Path,
    output_dir: Path,
    *,
    offline: bool,
    dpi: int = 300,
    png_name: str = DEFAULT_PNG_NAME,
    report_name: str = DEFAULT_REPORT_NAME,
    opener: Callable[..., Any] | None = None,
) -> dict[str, object]:
    """Run the complete Figure S1 recovery and return its report."""
    for label, path in (("image index", index_path), ("metadata", metadata_path)):
        if not path.is_file():
            raise FigureS1Error(f"{label} does not exist: {path}")
    if Path(png_name).name != png_name or Path(report_name).name != report_name:
        raise FigureS1Error("output names must be plain filenames")
    if dpi <= 0:
        raise FigureS1Error("DPI must be positive")

    index = pl.read_parquet(index_path)
    metadata = pl.read_parquet(metadata_path)
    sources = resolve_channel_sources(index)
    target_metadata = resolve_target_metadata(metadata)
    inventory = count_inventory(index, metadata)
    output_dir.mkdir(parents=True, exist_ok=True)
    tiff_paths = acquire_tiffs(sources, output_dir, offline=offline, opener=opener)
    png_path = output_dir / png_name
    render_figure(tiff_paths, png_path, dpi=dpi)

    channel_records = []
    for source in sources:
        record = {
            "channel": source.channel,
            "batch": source.batch,
            "source_uri": source.uri,
            "download_url": _download_url(source.uri),
            "normalization_divisor": CHANNEL_NORMALIZATION[source.channel],
        }
        record.update(_file_record(tiff_paths[source.channel], relative_to=output_dir))
        channel_records.append(record)

    report: dict[str, object] = {
        "schema_version": 1,
        "target": "SFIG-1",
        "identity": {
            "plate": TARGET_PLATE,
            "well": TARGET_WELL,
            "site": TARGET_SITE,
            **target_metadata,
        },
        "channels": channel_records,
        "grayscale": {
            "channels": list(CHANNELS),
            "display_scaling": "per-channel automatic min/max after normalization, matching the notebook",
        },
        "composite": {
            "red": ["Mito", "AGP", "RNA"],
            "green": ["ER", "AGP"],
            "blue": ["DNA", "RNA"],
            "clip_range": [0.0, 1.0],
        },
        "inventory": inventory,
        "inputs": {
            "index": _file_record(index_path),
            "metadata": _file_record(metadata_path),
        },
        "output": _file_record(png_path, relative_to=output_dir),
    }
    _atomic_write_json(output_dir / report_name, report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX, help="Zenodo image index Parquet")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA, help="Zenodo metadata Parquet")
    parser.add_argument("--output-dir", type=Path, required=True, help="directory for cached TIFFs, PNG, and JSON")
    parser.add_argument("--offline", action="store_true", help="require preseeded TIFFs and make no network requests")
    parser.add_argument("--dpi", type=int, default=300, help="PNG resolution (default: 300)")
    parser.add_argument("--png-name", default=DEFAULT_PNG_NAME, help="PNG filename within the output directory")
    parser.add_argument("--report-name", default=DEFAULT_REPORT_NAME, help="JSON filename within the output directory")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run Figure S1 reproduction from command-line arguments."""
    args = _parser().parse_args(argv)
    try:
        report = reproduce(
            args.index,
            args.metadata,
            args.output_dir,
            offline=args.offline,
            dpi=args.dpi,
            png_name=args.png_name,
            report_name=args.report_name,
        )
    except FigureS1Error as error:
        raise SystemExit(f"Figure S1 reproduction failed: {error}") from error
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
