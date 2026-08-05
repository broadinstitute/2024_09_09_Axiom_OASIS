# ruff: noqa: CPY001, PT009, PT027
"""Contract tests for the OASIS JPEG XL image archive."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from oasis_images.contract import ContractError, load_contract

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CONTRACT = REPO_ROOT / "images" / "source.toml"


class OasisImageSourceContractTest(unittest.TestCase):
    """Keep the tracked source and archive identity reviewable."""

    def test_tracked_contract_is_parseable_and_pins_the_complete_inventory(self) -> None:
        """Require exact source, inventory, channel, codec, and layout values."""
        contract = load_contract(SOURCE_CONTRACT)

        self.assertEqual(contract.index.record_id, 17067683)
        self.assertEqual(contract.index.filename, "index.parquet")
        self.assertEqual(
            contract.index.url,
            "https://zenodo.org/api/records/17067683/files/index.parquet/content",
        )
        self.assertEqual(contract.index.size_bytes, 2_524_798)
        self.assertEqual(contract.index.md5, "b56e249504f76bc2f6025f90abc8608c")
        self.assertEqual(
            contract.index.sha256,
            "f83a16fa21a5ec20df433706ef889dc7cc8003ff5aabb057e9e54d6903be73f9",
        )

        inventory = contract.inventory
        self.assertEqual(inventory.row_count, 2_019_342)
        self.assertEqual(inventory.complete_unique_tiff_uris, 2_017_182)
        self.assertEqual(inventory.incomplete_rows, 2_160)
        self.assertEqual(inventory.field_count, 336_197)
        self.assertEqual(inventory.plate_count, 68)
        self.assertEqual(inventory.channel_count, 6)
        self.assertEqual(
            inventory.manifest_sha256,
            "b8c20a37213831b55161a8ed9fe0a1c60522c8951f2b5e19713c7105c8200381",
        )
        self.assertEqual(
            inventory.rejected_sha256,
            "0bd61c7b852530c8d3ec491f2a99bab2f4cf15bbf1b015389c571ca7c768a66a",
        )
        self.assertEqual(
            inventory.complete_unique_tiff_uris + inventory.incomplete_rows,
            inventory.row_count,
        )
        self.assertEqual(
            inventory.field_count * inventory.channel_count,
            inventory.complete_unique_tiff_uris,
        )

        self.assertEqual(
            dict(contract.channels),
            {"DNA": 1, "ER": 2, "AGP": 3, "RNA": 4, "Mito": 5, "Brightfield": 6},
        )
        self.assertEqual(
            contract.batches,
            ("prod_25", "prod_26", "prod_27", "prod_30"),
        )
        self.assertEqual(contract.source.bucket, "cellpainting-gallery")
        self.assertEqual(contract.source.prefix, "cpg0037-oasis/axiom/images")
        self.assertTrue(contract.source.anonymous)
        self.assertEqual(contract.codec.id, "jpegxl-d1-e5")
        self.assertEqual(contract.codec.name, "jpegxl")
        self.assertEqual(contract.codec.profile, "hq")
        self.assertFalse(contract.codec.lossless)
        self.assertEqual(contract.codec.distance, 1.0)
        self.assertEqual(contract.codec.effort, 5)
        self.assertEqual(
            contract.codec.reference_commit,
            "5f0fc9be6135e74cfee0b3504fd20a35a9531a22",
        )
        self.assertEqual(
            contract.codec.reference_sha256,
            "9bb6bec0a23a8fb091c1e1990f62690c55b74e34d1a49165b21bbb1aabaa54bf",
        )
        self.assertEqual(contract.codec.reference_tier, "jpegxl_lossy_hq")
        self.assertEqual(
            contract.destination.root,
            Path("/work/datasets/cpg0037-oasis/axiom/images-jxl/v1"),
        )
        self.assertEqual(
            contract.destination.object_template,
            "{codec_id}/{batch}/images/{plate}/{stem}.jxl",
        )

    def test_object_template_maps_one_tiff_to_the_required_archive_path(self) -> None:
        """Keep the codec, batch, plate, and source stem in every object key."""
        contract = load_contract(SOURCE_CONTRACT)
        relative = contract.destination.relative_path(
            codec_id=contract.codec.id,
            batch="prod_25",
            plate="plate_00000001",
            stem="r01c01f01p01-ch1sk1fk1fl1",
        )
        destination = contract.destination.root / relative
        self.assertEqual(
            destination,
            Path(
                "/work/datasets/cpg0037-oasis/axiom/images-jxl/v1/"
                "jpegxl-d1-e5/prod_25/images/plate_00000001/"
                "r01c01f01p01-ch1sk1fk1fl1.jxl",
            ),
        )

    def test_loaded_contract_is_immutable(self) -> None:
        """Prevent callers from silently changing validated pins in memory."""
        contract = load_contract(SOURCE_CONTRACT)

        with self.assertRaises(FrozenInstanceError):
            contract.codec.distance = 3.0  # type: ignore[misc]
        with self.assertRaises(TypeError):
            contract.channels["DNA"] = 9

    def test_loader_fails_closed_when_any_contract_layer_is_tampered(self) -> None:
        """Reject changed source identity, counts, layout, and channel semantics."""
        original = SOURCE_CONTRACT.read_text()
        replacements = {
            "index URL": (
                "https://zenodo.org/api/records/17067683/files/index.parquet/content",
                "https://zenodo.org/api/records/17067684/files/index.parquet/content",
            ),
            "source prefix": (
                'prefix = "cpg0037-oasis/axiom/images"',
                'prefix = "cpg0037-oasis/axiom/images-v2"',
            ),
            "inventory count": ("row_count = 2019342", "row_count = 2019343"),
            "codec tier": ('id = "jpegxl-d1-e5"', 'id = "jpegxl-d2-e5"'),
            "destination template": (
                'object_template = "{codec_id}/{batch}/images/{plate}/{stem}.jxl"',
                'object_template = "{batch}/{plate}/{stem}.jxl"',
            ),
            "channel mapping": ("channel_number = 1", "channel_number = 9"),
            "batch inventory": ('name = "prod_30"', 'name = "prod_31"'),
        }

        for label, (old, new) in replacements.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary_directory:
                tampered_path = Path(temporary_directory) / "source.toml"
                tampered_path.write_text(original.replace(old, new, 1))
                with self.assertRaises(ContractError):
                    load_contract(tampered_path)


if __name__ == "__main__":
    unittest.main()
