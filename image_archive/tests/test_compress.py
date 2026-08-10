# Copyright (c) 2026 Broad Institute.
# ruff: noqa: D103, EM101, PLR2004, S101, TC003, TRY003
"""End-to-end tests for the small image converter."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
import tifffile

from image_archive.codec import decode_jxl
from image_archive.compress import convert_manifest, iter_manifest, main, verify_manifest


def _tiff(path: Path, value: int) -> bytes:
    array = np.full((8, 10), value, dtype=np.uint16)
    stream = io.BytesIO()
    tifffile.imwrite(stream, array)
    payload = stream.getvalue()
    path.write_bytes(payload)
    return payload


def _manifest(path: Path, rows: list[tuple[Path, str]]) -> Path:
    lines = ["source_uri\tdestination_relative"]
    lines.extend(f"{source}\t{destination}" for source, destination in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_convert_resume_noop_and_verify(tmp_path: Path) -> None:
    source_one = tmp_path / "one.tif"
    source_two = tmp_path / "two.tif"
    _tiff(source_one, 100)
    _tiff(source_two, 200)
    manifest = _manifest(
        tmp_path / "images.tsv",
        [(source_one, "plate/one.jxl"), (source_two, "plate/two.jxl")],
    )
    output = tmp_path / "output"

    first = convert_manifest(manifest, output, workers=2)
    assert first.complete
    assert first.converted == 2
    assert first.skipped == 0
    assert decode_jxl((output / "plate/one.jxl").read_bytes()).shape == (8, 10)

    second = convert_manifest(manifest, output, workers=2)
    assert second.complete
    assert second.converted == 0
    assert second.skipped == 2

    verified = verify_manifest(manifest, output, workers=2)
    assert verified.complete
    assert verified.checked == 2
    assert verified.invalid == 0


def test_retry_then_success(tmp_path: Path) -> None:
    source = tmp_path / "retry.tif"
    payload = _tiff(source, 300)
    manifest = _manifest(tmp_path / "images.tsv", [(source, "retry.jxl")])
    attempts = 0

    def flaky_reader(_: str) -> bytes:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("temporary source failure")
        return payload

    result = convert_manifest(manifest, tmp_path / "output", workers=1, max_attempts=2, source_reader=flaky_reader)
    assert result.complete
    assert result.converted == 1
    assert attempts == 2


def test_failed_conversion_leaves_no_final_output(tmp_path: Path) -> None:
    source = tmp_path / "broken.tif"
    source.write_bytes(b"not a tiff")
    manifest = _manifest(tmp_path / "images.tsv", [(source, "broken.jxl")])
    output = tmp_path / "output"

    result = convert_manifest(manifest, output, workers=1, max_attempts=1)
    assert not result.complete
    assert result.failed == 1
    assert not (output / "broken.jxl").exists()


def test_interruption_resumes_from_atomic_outputs(tmp_path: Path) -> None:
    source_one = tmp_path / "one.tif"
    source_two = tmp_path / "two.tif"
    first_payload = _tiff(source_one, 100)
    _tiff(source_two, 200)
    manifest = _manifest(
        tmp_path / "images.tsv",
        [(source_one, "one.jxl"), (source_two, "two.jxl")],
    )
    output = tmp_path / "output"

    def interrupted_reader(uri: str) -> bytes:
        if uri == str(source_two):
            raise KeyboardInterrupt
        return first_payload

    interrupted = convert_manifest(
        manifest,
        output,
        workers=1,
        max_in_flight=1,
        source_reader=interrupted_reader,
    )
    assert interrupted.interrupted
    assert (output / "one.jxl").is_file()
    assert not (output / "two.jxl").exists()

    resumed = convert_manifest(manifest, output, workers=1, max_in_flight=1)
    assert resumed.complete
    assert resumed.skipped == 1
    assert resumed.converted == 1


def test_verify_reports_corrupt_output(tmp_path: Path) -> None:
    source = tmp_path / "source.tif"
    _tiff(source, 100)
    manifest = _manifest(tmp_path / "images.tsv", [(source, "source.jxl")])
    output = tmp_path / "output"
    assert convert_manifest(manifest, output, workers=1).complete
    (output / "source.jxl").write_bytes(b"not jpeg xl")

    result = verify_manifest(manifest, output, workers=1)
    assert not result.complete
    assert result.checked == 0
    assert result.invalid == 1


def test_cli_writes_small_run_records(tmp_path: Path) -> None:
    source = tmp_path / "source.tif"
    _tiff(source, 100)
    manifest = _manifest(tmp_path / "images.tsv", [(source, "source.jxl")])
    output = tmp_path / "output"

    assert main(["convert", "--manifest", str(manifest), "--output-root", str(output), "--workers", "1"]) == 0
    assert (output / "jxl-run.json").is_file()
    assert main(["verify", "--manifest", str(manifest), "--output-root", str(output), "--workers", "1"]) == 0
    assert (output / "jxl-validation.json").is_file()


@pytest.mark.parametrize(
    "destination",
    ["../escape.jxl", "/absolute.jxl", "not-jxl.tif"],
)
def test_manifest_rejects_unsafe_destination(tmp_path: Path, destination: str) -> None:
    source = tmp_path / "source.tif"
    _tiff(source, 100)
    manifest = _manifest(tmp_path / "images.tsv", [(source, destination)])
    with pytest.raises(ValueError, match="unsafe destination"):
        list(iter_manifest(manifest))


def test_manifest_requires_sorted_unique_destinations(tmp_path: Path) -> None:
    source_one = tmp_path / "one.tif"
    source_two = tmp_path / "two.tif"
    _tiff(source_one, 100)
    _tiff(source_two, 200)
    manifest = _manifest(
        tmp_path / "images.tsv",
        [(source_one, "two.jxl"), (source_two, "one.jxl")],
    )
    with pytest.raises(ValueError, match="strictly sorted and unique"):
        list(iter_manifest(manifest))
