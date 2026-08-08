# ruff: noqa: INP001
"""Tests for deterministic distance-table compilation."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "1_snakemake" / "concresponse" / "compile_dist.py"
SPEC = importlib.util.spec_from_file_location("compile_dist", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CompileDistanceOrderingTest(unittest.TestCase):
    """Exercise ordering at the boundary between Polars and R curve fitting."""

    def test_shuffled_long_inputs_produce_identical_wide_parquet(self) -> None:
        """Canonicalize shuffled rows, columns, and exact duplicate inputs."""
        metadata = {
            "Metadata_well_id": ["well_b", "well_a"],
            "Metadata_Plate": ["plate_2", "plate_1"],
            "Metadata_Concentration": [1.0, 0.0],
            "Metadata_Compound": ["compound_b", "DMSO"],
        }
        gmd = pl.DataFrame(
            {
                **metadata,
                "Metadata_Distance": ["gmd", "gmd"],
                "Distance": [2.0, 1.0],
            },
        )
        cmd = pl.DataFrame(
            {
                "Metadata_well_id": ["well_a", "well_b", "well_a", "well_b"],
                "Metadata_Plate": ["plate_1", "plate_2", "plate_1", "plate_2"],
                "Metadata_Concentration": [0.0, 1.0, 0.0, 1.0],
                "Metadata_Compound": ["DMSO", "compound_b", "DMSO", "compound_b"],
                "Metadata_Distance": ["Cells_DNA", "Cells_DNA", "Cells_AGP", "Cells_AGP"],
                "Distance": [3.0, 4.0, 5.0, 6.0],
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first_gmd = root / "first_gmd.parquet"
            first_cmd = root / "first_cmd.parquet"
            second_gmd = root / "second_gmd.parquet"
            second_cmd = root / "second_cmd.parquet"
            pl.concat([gmd, gmd.head(1)]).write_parquet(first_gmd)
            cmd.reverse().write_parquet(first_cmd)
            pl.concat([gmd.reverse(), gmd.tail(1)]).write_parquet(second_gmd)
            cmd[[0, 2, 1, 3]].write_parquet(second_cmd)

            for transform in ["none", "log10"]:
                first_output = root / f"{transform}_first_output.parquet"
                second_output = root / f"{transform}_second_output.parquet"
                MODULE.compile_dist([first_gmd, first_cmd], transform, first_output)
                MODULE.compile_dist([second_gmd, second_cmd], transform, second_output)
                assert first_output.read_bytes() == second_output.read_bytes()  # noqa: S101

            result = pl.read_parquet(root / "none_first_output.parquet")
            assert result.columns == [  # noqa: S101
                "Metadata_well_id",
                "Metadata_Plate",
                "Metadata_Concentration",
                "Metadata_Compound",
                "Cells_AGP",
                "Cells_DNA",
                "gmd",
            ]
            assert result["Metadata_well_id"].to_list() == ["well_a", "well_b"]  # noqa: S101


if __name__ == "__main__":
    unittest.main()
