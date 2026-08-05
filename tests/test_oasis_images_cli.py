# ruff: noqa: CPY001, PT009, SLF001
"""Focused tests for archive CLI storage-policy parsing."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from oasis_images import __main__ as cli
from oasis_images.__main__ import _registry_owner


class OasisImagesCliTest(unittest.TestCase):
    """Keep the dataset registration gate scoped to the exact entry."""

    def test_registry_owner_is_read_from_the_matching_dataset(self) -> None:
        """Do not accept an owner attached to a different registry entry."""
        registry = """datasets:
  - name: unrelated
    owner: shsingh
  - name: "cpg0037-oasis/axiom/images-jxl/v1"
    owner: "archive-owner"
"""

        self.assertEqual(
            _registry_owner(registry, "cpg0037-oasis/axiom/images-jxl/v1"),
            "archive-owner",
        )
        self.assertIsNone(_registry_owner(registry, "absent"))

    def test_destination_storage_rejects_symlinked_dataset_root(self) -> None:
        """The canonical shared dataset path cannot redirect through a symlink."""
        with TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            real_dataset_root = temporary_root / "real-datasets"
            real_dataset_root.mkdir()
            dataset_root = temporary_root / "datasets"
            dataset_root.symlink_to(real_dataset_root, target_is_directory=True)
            destination_root = dataset_root / cli.DATASET_NAME

            with (
                patch.object(cli, "DATASET_ROOT", dataset_root),
                patch.object(cli, "DATASET_REGISTRY", dataset_root / "REGISTRY.yaml"),
                patch.object(cli, "EXPECTED_DESTINATION_ROOT", destination_root),
                pytest.raises(RuntimeError, match="dataset root must not be a symlink"),
            ):
                cli._require_destination_storage(destination_root)

    def test_destination_storage_rejects_root_filesystem_device(self) -> None:
        """A same-device dataset directory must not consume the root filesystem."""
        with TemporaryDirectory() as temporary_directory:
            dataset_root = Path(temporary_directory) / "datasets"
            dataset_root.mkdir()
            destination_root = dataset_root / cli.DATASET_NAME

            with (
                patch.object(cli, "DATASET_ROOT", dataset_root),
                patch.object(cli, "DATASET_REGISTRY", dataset_root / "REGISTRY.yaml"),
                patch.object(cli, "EXPECTED_DESTINATION_ROOT", destination_root),
                pytest.raises(RuntimeError, match="not a distinct mounted filesystem"),
            ):
                cli._require_destination_storage(destination_root)


if __name__ == "__main__":
    unittest.main()
