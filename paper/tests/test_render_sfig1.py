# ruff: noqa: PT009, PT027
"""Fast synthetic tests for the supplemental Figure S1 renderer."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import polars as pl
from PIL import Image

from paper import render_sfig1 as renderer


def _source_rows() -> list[dict[str, object]]:
    return [
        {
            "Metadata_Batch": "prod_test",
            "Metadata_Plate": renderer.TARGET_PLATE,
            "Metadata_Well": renderer.TARGET_WELL,
            "Metadata_Site": float(renderer.TARGET_SITE),
            "Channel": channel,
            "Filename": f"https://example.test/images/{channel.lower()}.tiff",
        }
        for channel in renderer.CHANNELS
    ]


def _target_metadata() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "Metadata_Plate": [renderer.TARGET_PLATE],
            "Metadata_Well": [renderer.TARGET_WELL],
            "Metadata_Compound": ["DMSO"],
        },
    )


def _seed_tiffs(output_dir: Path, sources: tuple[renderer.ChannelSource, ...]) -> None:
    size = 256
    gradient = np.arange(size * size, dtype=np.uint32).reshape(size, size)
    for index, source in enumerate(sources, start=1):
        pixels = ((gradient * index) % 14_000).astype(np.uint16)
        path = renderer.cache_path(output_dir, source)
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(pixels).save(path)


class FigureS1RendererTests(unittest.TestCase):
    """Exercise identity resolution, inventory, caching, and rendering."""

    def test_exact_identity_resolution_requires_unique_channels_and_uris(self) -> None:
        """Reject ambiguous channels and duplicate source identities."""
        index = pl.DataFrame(
            [
                *_source_rows(),
                {
                    "Metadata_Batch": "prod_test",
                    "Metadata_Plate": renderer.TARGET_PLATE,
                    "Metadata_Well": renderer.TARGET_WELL,
                    "Metadata_Site": float(renderer.TARGET_SITE),
                    "Channel": "Brightfield",
                    "Filename": "https://example.test/images/brightfield.tiff",
                },
                {
                    "Metadata_Batch": "prod_test",
                    "Metadata_Plate": renderer.TARGET_PLATE,
                    "Metadata_Well": renderer.TARGET_WELL,
                    "Metadata_Site": float(renderer.TARGET_SITE + 1),
                    "Channel": "DNA",
                    "Filename": "https://example.test/images/other-dna.tiff",
                },
            ],
        )
        sources = renderer.resolve_channel_sources(index)
        self.assertEqual([source.channel for source in sources], list(renderer.CHANNELS))
        self.assertEqual({source.batch for source in sources}, {"prod_test"})

        duplicate_channel = pl.concat([index, pl.DataFrame([_source_rows()[0]])])
        with self.assertRaisesRegex(renderer.FigureS1Error, "expected one DNA row"):
            renderer.resolve_channel_sources(duplicate_channel)

        duplicate_uri_rows = _source_rows()
        duplicate_uri_rows[1]["Filename"] = duplicate_uri_rows[0]["Filename"]
        with self.assertRaisesRegex(renderer.FigureS1Error, "five distinct TIFF URIs"):
            renderer.resolve_channel_sources(pl.DataFrame(duplicate_uri_rows))

    def test_inventory_counts_distinct_joined_fields_and_reports_deviation(self) -> None:
        """Count joined fields without fabricating the published site filter."""
        index = pl.DataFrame(
            {
                "Metadata_Plate": [renderer.TARGET_PLATE, "plate_2", "plate_2", "plate_unmatched"],
                "Metadata_Well": [renderer.TARGET_WELL, "A01", "A01", "B01"],
                "Metadata_Site": [6.0, 1.0, 2.0, 1.0],
            },
        )
        metadata = pl.DataFrame(
            {
                "Metadata_Plate": [renderer.TARGET_PLATE, "plate_2", "plate_2"],
                "Metadata_Well": [renderer.TARGET_WELL, "A01", "A01"],
                "Metadata_Compound": ["DMSO", "compound", "compound"],
            },
        )
        inventory = renderer.count_inventory(index, metadata)
        self.assertEqual(inventory["current_total"], 3)
        self.assertEqual(inventory["current_dmso"], 1)
        self.assertEqual(inventory["published_total"], 191_754)
        self.assertEqual(inventory["published_dmso"], 43_641)
        self.assertEqual(inventory["outcome"], "reproduced-with-deviation")
        self.assertFalse(inventory["matches_published"])
        self.assertIn("9-site rule", inventory["deviation"])

    def test_cached_tiffs_never_call_network_opener(self) -> None:
        """Use nonempty cache files without invoking the supplied opener."""
        sources = renderer.resolve_channel_sources(pl.DataFrame(_source_rows()))
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            for source in sources:
                path = renderer.cache_path(output_dir, source)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(f"cached-{source.channel}".encode())

            def fail_if_called(*_args: object, **_kwargs: object) -> None:
                self.fail("network opener was called for a cached TIFF")

            paths = renderer.acquire_tiffs(sources, output_dir, offline=False, opener=fail_if_called)
            self.assertEqual(set(paths), set(renderer.CHANNELS))

    def test_render_and_report_are_deterministic(self) -> None:
        """Produce identical PNG and ASCII JSON bytes from identical inputs."""
        index = pl.DataFrame(_source_rows())
        metadata = _target_metadata()
        sources = renderer.resolve_channel_sources(index)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            index_path = root / "index.parquet"
            metadata_path = root / "metadata.parquet"
            index.write_parquet(index_path)
            metadata.write_parquet(metadata_path)
            outputs = (root / "first", root / "second")
            for output_dir in outputs:
                _seed_tiffs(output_dir, sources)
                renderer.reproduce(
                    index_path,
                    metadata_path,
                    output_dir,
                    offline=True,
                    dpi=40,
                )

            first_png = outputs[0] / renderer.DEFAULT_PNG_NAME
            second_png = outputs[1] / renderer.DEFAULT_PNG_NAME
            first_report = outputs[0] / renderer.DEFAULT_REPORT_NAME
            second_report = outputs[1] / renderer.DEFAULT_REPORT_NAME
            self.assertEqual(first_png.read_bytes(), second_png.read_bytes())
            self.assertEqual(first_report.read_bytes(), second_report.read_bytes())

            report = json.loads(first_report.read_text(encoding="ascii"))
            self.assertEqual(report["target"], "SFIG-1")
            self.assertEqual(report["identity"]["compound"], "DMSO")
            self.assertEqual([row["channel"] for row in report["channels"]], list(renderer.CHANNELS))
            self.assertEqual(report["output"]["sha256"], hashlib.sha256(first_png.read_bytes()).hexdigest())
            first_report.read_text(encoding="ascii").encode("ascii")


if __name__ == "__main__":
    unittest.main()
