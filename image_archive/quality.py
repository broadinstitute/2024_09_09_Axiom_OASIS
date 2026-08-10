# Copyright (c) 2026 Broad Institute.
# ruff: noqa: T201
"""Write a small intrinsic-quality receipt for an existing conversion."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import math
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from .codec import JPEGXL_DISTANCE, JPEGXL_EFFORT, decode_tiff, verify_jxl
from .compress import (
    ManifestRow,
    SourceReader,
    _default_reader,
    _destination,
    _exclusive_lock,
    _output_root,
    _positive,
    _sha256_file,
    _write_json,
    iter_manifest,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from typing import Any

MetricValue = float | None


def _metrics(source: np.ndarray, output: np.ndarray) -> dict[str, MetricValue]:
    residual = source.astype(np.float64) - output.astype(np.float64)
    rmse = math.sqrt(float(np.mean(residual * residual)))
    lower, upper = np.quantile(source, (0.001, 0.999))
    span = float(upper - lower)
    source_edges, output_edges = _tenengrad(source), _tenengrad(output)
    return {
        "robust_nrmse": rmse / span if span else None,
        "psnr_db": 20.0 * math.log10(65535.0 / rmse) if rmse else None,
        "tenengrad_ratio": output_edges / source_edges if source_edges else None,
        "conditional_entropy_bits_per_pixel": _conditional_entropy(source, output),
    }


def _tenengrad(image: np.ndarray) -> float:
    values = np.pad(image.astype(np.float64), 1, mode="reflect")
    horizontal = (
        values[:-2, 2:]
        + 2 * values[1:-1, 2:]
        + values[2:, 2:]
        - values[:-2, :-2]
        - 2 * values[1:-1, :-2]
        - values[2:, :-2]
    )
    vertical = (
        values[2:, :-2]
        + 2 * values[2:, 1:-1]
        + values[2:, 2:]
        - values[:-2, :-2]
        - 2 * values[:-2, 1:-1]
        - values[:-2, 2:]
    )
    return float(np.mean(horizontal * horizontal + vertical * vertical))


def _conditional_entropy(source: np.ndarray, output: np.ndarray) -> float:
    source_values = source.reshape(-1).astype(np.uint64)
    output_values = output.reshape(-1).astype(np.uint64)
    pair_counts = np.unique((source_values << 16) | output_values, return_counts=True)[1]
    output_counts = np.unique(output_values, return_counts=True)[1]

    def entropy(counts: np.ndarray) -> float:
        values = counts.astype(np.float64)
        total = float(values.sum())
        return math.log2(total) - float(np.sum(values * np.log2(values)) / total)

    return max(0.0, entropy(pair_counts) - entropy(output_counts))


def _sample(path: Path, size: int) -> tuple[list[ManifestRow], int]:
    total = 0

    def rows() -> Iterator[ManifestRow]:
        nonlocal total
        for row in iter_manifest(path):
            total += 1
            yield row

    def rank(row: ManifestRow) -> bytes:
        return hashlib.sha256(f"{row.source_uri}\0{row.destination_relative}".encode()).digest()

    return sorted(heapq.nsmallest(size, rows(), key=rank), key=lambda row: row.destination_relative), total


def _summaries(measured: list[tuple[ManifestRow, dict[str, MetricValue]]]) -> dict[str, Any]:
    scores: dict[str, Callable[[float], float]] = {
        "robust_nrmse": lambda value: value,
        "psnr_db": lambda value: -value,
        "tenengrad_ratio": lambda value: abs(value - 1),
        "conditional_entropy_bits_per_pixel": lambda value: value,
    }
    summaries: dict[str, object] = {}
    for name, score in scores.items():
        candidates = [(row, value) for row, metrics in measured if (value := metrics[name]) is not None]
        if not candidates:
            summaries[name] = {"median": None, "worst": None}
            continue
        row, value = max(candidates, key=lambda candidate: score(candidate[1]))
        summaries[name] = {
            "median": float(np.median([candidate[1] for candidate in candidates])),
            "worst": {"source_uri": row.source_uri, "destination_relative": row.destination_relative, "value": value},
        }
    return summaries


def evaluate(
    manifest: Path,
    output_root: Path,
    *,
    sample_size: int = 64,
    source_reader: SourceReader | None = None,
) -> dict[str, Any]:
    """Compare a deterministic source sample with its existing outputs."""
    _positive(sample_size, "sample_size")
    manifest = manifest.resolve()
    root = _output_root(output_root, create=False)
    rows, total = _sample(manifest, sample_size)
    reader = source_reader or _default_reader(1)
    measured: list[tuple[ManifestRow, dict[str, MetricValue]]] = []
    source_bytes = output_bytes = pixels = 0
    with _exclusive_lock(root / ".jxl-convert.lock"):
        for row in rows:
            source_payload = reader(row.source_uri)
            source = decode_tiff(source_payload)
            output_payload = _destination(root, row).read_bytes()
            shape = int(source.shape[0]), int(source.shape[1])
            output = verify_jxl(output_payload, expected_shape=shape, expected_dtype=source.dtype)
            measured.append((row, _metrics(source, output)))
            source_bytes += len(source_payload)
            output_bytes += len(output_payload)
            pixels += int(source.size)

    sample_tsv = "source_uri\tdestination_relative\n" + "".join(
        f"{row.source_uri}\t{row.destination_relative}\n" for row in rows
    )
    return {
        "codec": {"name": "jpegxl", "distance": JPEGXL_DISTANCE, "effort": JPEGXL_EFFORT},
        "result": {
            "complete": True,
            "manifest_sha256": _sha256_file(manifest),
            "sample_sha256": hashlib.sha256(sample_tsv.encode()).hexdigest(),
            "selection": "lowest_sha256_source_nul_destination",
            "total": total,
            "checked": len(rows),
            "invalid": 0,
            "source_bytes": source_bytes,
            "output_bytes": output_bytes,
            "compression_ratio": source_bytes / output_bytes,
            "output_bits_per_pixel": 8 * output_bytes / pixels,
            "metrics": _summaries(measured),
        },
    }


def main(arguments: list[str] | None = None) -> int:
    """Write and print one quality receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=64)
    parsed = parser.parse_args(arguments)
    receipt = evaluate(parsed.manifest, parsed.output_root, sample_size=parsed.sample_size)
    _write_json(parsed.output_root / "jxl-quality.json", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
