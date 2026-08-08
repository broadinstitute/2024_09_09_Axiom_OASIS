# ruff: noqa: CPY001, PT009
"""Tests for the dataset-configured image archive contract."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from image_archive.contract import ContractError, load_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_CONTRACT = REPO_ROOT / "image_archive" / "axiom" / "source.toml"


def _load_text(text: str):  # noqa: ANN202
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "source.toml"
        path.write_text(text)
        return load_contract(path)


class OasisImageSourceContractTest(unittest.TestCase):
    """Keep configuration authoritative and reject structural mistakes."""

    def test_tracked_contract_is_internally_consistent(self) -> None:
        """Load the tracked description and check only generic relationships."""
        contract = load_contract(SOURCE_CONTRACT)

        self.assertEqual(
            contract.inventory.complete_unique_tiff_uris + contract.inventory.incomplete_rows,
            contract.inventory.row_count,
        )
        self.assertEqual(
            contract.inventory.field_count * contract.inventory.channel_count,
            contract.inventory.complete_unique_tiff_uris,
        )
        self.assertEqual(contract.inventory.channel_count, len(contract.channels))
        self.assertTrue(contract.destination.root.is_absolute())

    def test_contract_values_can_describe_another_dataset(self) -> None:
        """Treat changed dataset values as configuration rather than tampering."""
        changed = (
            SOURCE_CONTRACT.read_text()
            .replace('prefix = "cpg0037-oasis/axiom/images"', 'prefix = "another-dataset/images"')
            .replace('id = "jpegxl-d1-e5"', 'id = "jpegxl-d2-e4"')
            .replace("distance = 1.0", "distance = 2.0")
            .replace("effort = 5", "effort = 4")
            .replace(
                'root = "/work/datasets/cpg0037-oasis/axiom/images-jxl/v1"',
                'root = "/archive/another-dataset"',
            )
            .replace('name = "prod_30"', 'name = "new_batch"')
        )

        contract = _load_text(changed)

        self.assertEqual(contract.source.prefix, "another-dataset/images")
        self.assertEqual(contract.codec.id, "jpegxl-d2-e4")
        self.assertEqual(contract.codec.distance, 2.0)
        self.assertEqual(contract.destination.root, Path("/archive/another-dataset"))
        self.assertIn("new_batch", contract.batches)

    def test_object_template_renders_a_safe_relative_jxl_path(self) -> None:
        """Keep every rendered output below the configured archive root."""
        contract = load_contract(SOURCE_CONTRACT)
        relative = contract.destination.relative_path(
            codec_id=contract.codec.id,
            batch="batch",
            plate="plate",
            stem="image",
        )

        self.assertFalse(relative.is_absolute())
        self.assertEqual(relative.suffix, ".jxl")
        self.assertNotIn("..", relative.parts)

    def test_loaded_contract_is_immutable(self) -> None:
        """Prevent accidental mutation after contract validation."""
        contract = load_contract(SOURCE_CONTRACT)

        with pytest.raises(FrozenInstanceError):
            contract.codec.distance = 3.0  # type: ignore[misc]
        with pytest.raises(TypeError):
            contract.channels["DNA"] = 9  # type: ignore[index]

    def test_loader_rejects_structural_and_consistency_errors(self) -> None:
        """Reject malformed descriptions while allowing different values."""
        original = SOURCE_CONTRACT.read_text()
        invalid = {
            "count relationship": original.replace("row_count = 2019342", "row_count = 2019343"),
            "unsafe prefix": original.replace(
                'prefix = "cpg0037-oasis/axiom/images"',
                'prefix = "../images"',
            ),
            "duplicate channel": original.replace("channel_number = 2", "channel_number = 1"),
            "unsafe template": original.replace(
                'object_template = "{codec_id}/{batch}/images/{plate}/{stem}.jxl"',
                'object_template = "../{codec_id}/{batch}/{plate}/{stem}.jxl"',
            ),
            "bad digest": original.replace(
                "f83a16fa21a5ec20df433706ef889dc7cc8003ff5aabb057e9e54d6903be73f9",
                "not-a-digest",
            ),
        }

        for label, text in invalid.items():
            with self.subTest(label=label), pytest.raises(ContractError):
                _load_text(text)


if __name__ == "__main__":
    unittest.main()
