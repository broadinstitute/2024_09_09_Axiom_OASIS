# ruff: noqa: CPY001, PT009
"""Focused tests for archive filesystem coordination helpers."""

from __future__ import annotations

import json
import os
import socket
import stat
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from image_archive.io import exclusive_workflow_lock


class ExclusiveWorkflowLockTest(unittest.TestCase):
    """Require a single writer and leave useful holder evidence on disk."""

    def test_nested_acquisition_fails_with_holder_metadata(self) -> None:
        """A second open of the same lock cannot enter until the holder exits."""
        with TemporaryDirectory() as temporary_directory:
            lock_path = Path(temporary_directory) / "metadata" / ".archive.lock"

            with exclusive_workflow_lock(lock_path, "archive"):
                metadata = json.loads(lock_path.read_text())
                self.assertEqual(metadata["hostname"], socket.gethostname())
                self.assertEqual(metadata["operation"], "archive")
                self.assertEqual(metadata["pid"], os.getpid())
                self.assertIsNotNone(datetime.fromisoformat(metadata["started_at"]).tzinfo)
                self.assertEqual(stat.S_IMODE(lock_path.stat().st_mode), 0o660)

                with (
                    pytest.raises(
                        RuntimeError,
                        match=r"archive workflow lock is already held.*archive",
                    ),
                    exclusive_workflow_lock(lock_path, "validate"),
                ):
                    self.fail("a nested lock acquisition unexpectedly succeeded")

            with exclusive_workflow_lock(lock_path, "validate"):
                metadata = json.loads(lock_path.read_text())
                self.assertEqual(metadata["operation"], "validate")


if __name__ == "__main__":
    unittest.main()
