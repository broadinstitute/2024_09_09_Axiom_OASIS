# ruff: noqa: CPY001, SLF001
"""Focused tests for the generic destination safety check."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from oasis_images import __main__ as cli


class OasisImagesCliTest(unittest.TestCase):
    """Reject wrong-filesystem targets without encoding site policy."""

    def test_destination_storage_rejects_a_symlinked_path(self) -> None:
        """Reject a destination reached through any symlink."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / "real"
            real.mkdir()
            destination = root / "archive"
            destination.symlink_to(real, target_is_directory=True)

            with pytest.raises(RuntimeError, match="contains a symlink"):
                cli._require_destination_storage(destination)

    def test_destination_storage_rejects_the_root_filesystem(self) -> None:
        """Refuse a multi-terabyte run on the root filesystem."""
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "archive"
            destination.mkdir()

            with pytest.raises(RuntimeError, match="root filesystem"):
                cli._require_destination_storage(destination)

    def test_destination_storage_accepts_a_precreated_nonroot_mount(self) -> None:
        """Accept an ordinary writable path on a non-root mount."""
        with TemporaryDirectory() as directory:
            mount = Path(directory)
            destination = mount / "archive"
            destination.mkdir()

            with patch.object(Path, "is_mount", autospec=True, side_effect=lambda path: path == mount):
                cli._require_destination_storage(destination)


if __name__ == "__main__":
    unittest.main()
