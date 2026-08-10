# Copyright (c) 2026 Broad Institute.
# ruff: noqa: T201
"""Write a small rate-distortion receipt for an existing conversion."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import math
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from .codec import decode_tiff, verify_jxl
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
    from collections.abc import Iterator
    from typing import Any


def _distortion(source: np.ndarray, output: np.ndarray) -> float | None:
    """Return RMSE divided by the source's 0.1-99.9 percentile span."""
    residual = source.astype(np.float64) - output.astype(np.float64)
    rmse = math.sqrt(float(np.mean(residual * residual)))
    lower, upper = np.quantile(source, (0.001, 0.999))
    span = float(upper - lower)
    return rmse / span if span else None


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


def _summary(measured: list[tuple[ManifestRow, float | None]]) -> dict[str, Any]:
    defined = [(row, value) for row, value in measured if value is not None]
    if not defined:
        return {"defined": 0, "median": None, "worst": None}
    row, value = max(defined, key=lambda item: item[1])
    return {
        "defined": len(defined),
        "median": float(np.median([item[1] for item in defined])),
        "worst": {"source_uri": row.source_uri, "destination_relative": row.destination_relative, "value": value},
    }


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
    if not rows:
        message = "manifest contains no image rows"
        raise ValueError(message)

    reader = source_reader or _default_reader(1)
    measured: list[tuple[ManifestRow, float | None]] = []
    source_digest, output_digest = hashlib.sha256(), hashlib.sha256()
    output_bytes = pixels = 0
    with _exclusive_lock(root / ".jxl-convert.lock"):
        for row in rows:
            source_payload = reader(row.source_uri)
            source = decode_tiff(source_payload)
            output_payload = _destination(root, row).read_bytes()
            shape = int(source.shape[0]), int(source.shape[1])
            output = verify_jxl(output_payload, expected_shape=shape, expected_dtype=source.dtype)
            measured.append((row, _distortion(source, output)))
            source_digest.update(row.source_uri.encode() + b"\0" + hashlib.sha256(source_payload).digest())
            output_digest.update(
                row.destination_relative.encode() + b"\0" + hashlib.sha256(output_payload).digest(),
            )
            output_bytes += len(output_payload)
            pixels += int(source.size)

    sample_tsv = "source_uri\tdestination_relative\n" + "".join(
        f"{row.source_uri}\t{row.destination_relative}\n" for row in rows
    )
    return {
        "manifest": {"rows": total, "sha256": _sha256_file(manifest)},
        "sample": {
            "rows": len(rows),
            "sha256": hashlib.sha256(sample_tsv.encode()).hexdigest(),
            "selection": "lowest_sha256_source_nul_destination",
            "source_content_sha256": source_digest.hexdigest(),
            "output_content_sha256": output_digest.hexdigest(),
            "output_bits_per_pixel": 8 * output_bytes / pixels,
            "rmse_over_p001_p999_span": _summary(measured),
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
