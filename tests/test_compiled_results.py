# ruff: noqa: PT009, PT027
"""Synthetic tests for the read-only compiled-results verifier."""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from verification import compiled_results as verifier

if TYPE_CHECKING:
    from collections.abc import Iterator

POD_FIXTURE_ROWS = 20
ENRICHMENT_FIXTURE_ROWS = 8_858


def _metric_frame(row_count: int) -> pd.DataFrame:
    agg_types = ("all", "allpod", "allpodcc")
    rows_per_agg = row_count // len(agg_types)
    rows: list[dict[str, object]] = []
    for agg_type in agg_types:
        rows.extend(
            {
                "Metadata_AggType": agg_type,
                "Metadata_Label": f"label_{index:04d}",
                "Model_type": "Actual",
                "AUROC": 0.5 + (index % 100) / 1_000,
                "PRAUC": 0.25 + (index % 100) / 1_000,
                "Metadata_Count_0": 100 + (index % 10),
                "Metadata_Count_1": 20 + (index % 5),
                "Feat_type": "dino",
            }
            for index in range(rows_per_agg)
        )
    return pd.DataFrame(rows)


def _pod_frame(*, bioactivity: bool) -> pd.DataFrame:
    rows = []
    for index in range(POD_FIXTURE_ROWS):
        pod = float(index + 1)
        row: dict[str, object] = {
            "OASIS_ID": "" if index == 0 else f"OASIS{index:04d}",
            "Compound_name": f"compound_{index:04d}",
            "Assay_Endpoint": f"endpoint_{index % 3}",
            "POD_um": pod,
            "POD_um_l": pod * 0.9,
            "POD_um_u": pod * 1.1,
        }
        if bioactivity:
            row["Bioactivity_POD"] = index % 2 == 0
        rows.append(row)
    return pd.DataFrame(rows)


def _hit_summary_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "OASIS_ID": ["", "OASIS0001", "OASIS0002", "OASIS0003"],
            "Compound_name": ["compound_0000", "compound_0001", "compound_0002", "compound_0003"],
            "Cell_count_hit": ["Yes", "No", "Yes", "No"],
            "MT_hit": ["Yes", "No", "No", "No"],
            "LDH_hit": ["Yes", "No", "No", "No"],
            "Cell_Painting_hit": ["Yes", "Yes", "No", "No"],
            "Hit_in_all_assays": ["Yes", "No", "No", "No"],
        },
    )


def _enrichment_frame(hit_list_size: int, *, reverse_hits: bool) -> pd.DataFrame:
    first_hit = "Drug_A_1.0_A01_plate_100"
    comma_hit = "2,2'-Oxybis(ethan-1-ol)_0.48_P18_plate_101"
    overlap_hits = f"{comma_hit},{first_hit}" if reverse_hits else f"{first_hit},{comma_hit}"
    return pd.DataFrame(
        {
            "target_set": [f"target_{index:05d}" for index in range(ENRICHMENT_FIXTURE_ROWS)],
            "overlap_size": [2] * ENRICHMENT_FIXTURE_ROWS,
            "target_set_size": [20] * ENRICHMENT_FIXTURE_ROWS,
            "hit_list_size": [hit_list_size] * ENRICHMENT_FIXTURE_ROWS,
            "universe_size": [13_176] * ENRICHMENT_FIXTURE_ROWS,
            "p_value": [(index % 100) / 200 for index in range(ENRICHMENT_FIXTURE_ROWS)],
            "overlap_hits": [overlap_hits] * ENRICHMENT_FIXTURE_ROWS,
            "fdr": [(index % 100) / 100 for index in range(ENRICHMENT_FIXTURE_ROWS)],
        },
    )


def _mtt_enrichment_frame(*, p_value: float, overlap_size: int) -> pd.DataFrame:
    hits = ["Drug_A_1.0_A01_plate_100", "Drug_B_2.0_A02_plate_100"][:overlap_size]
    return pd.DataFrame(
        {
            "target_set": [f"target_{index:05d}" for index in range(ENRICHMENT_FIXTURE_ROWS)],
            "overlap_size": [overlap_size] * ENRICHMENT_FIXTURE_ROWS,
            "target_set_size": [20] * ENRICHMENT_FIXTURE_ROWS,
            "p_value": [p_value] * ENRICHMENT_FIXTURE_ROWS,
            "overlap_hits": [",".join(hits)] * ENRICHMENT_FIXTURE_ROWS,
            "fdr": [p_value] * ENRICHMENT_FIXTURE_ROWS,
        },
    )


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _build_fixture(root: Path) -> tuple[Path, Path]:
    reference = root / "reference"
    candidate = root / "candidate"
    reference.mkdir()
    for filename, row_count in verifier.EXPECTED_METRIC_ROWS.items():
        frame = _metric_frame(row_count)
        frame.to_parquet(reference / filename, index=False)

    for filename in verifier.POD_FILES:
        _write_csv(
            _pod_frame(bioactivity="cellpainting_" in filename),
            reference / filename,
        )
    _write_csv(_hit_summary_frame(), reference / verifier.HIT_SUMMARY_FILE)
    for filename in verifier.ENRICHMENT_FILES:
        _write_csv(_enrichment_frame(10, reverse_hits=False), reference / filename)
    for filename in verifier.MTT_ENRICHMENT_FILES:
        _write_csv(_mtt_enrichment_frame(p_value=0.5, overlap_size=2), reference / filename)

    shutil.copytree(reference, candidate)
    for filename in verifier.EXPECTED_METRIC_ROWS:
        frame = pd.read_parquet(candidate / filename)
        frame.iloc[::-1].to_parquet(candidate / filename, index=False)
    for filename in verifier.POD_FILES:
        frame = pd.read_csv(candidate / filename, keep_default_na=False)
        frame.iloc[::-1].to_csv(candidate / filename, index=False)
    hit_summary = pd.read_csv(candidate / verifier.HIT_SUMMARY_FILE, keep_default_na=False)
    hit_summary.loc[0, "Cell_count_hit"] = "No"
    hit_summary.iloc[::-1].to_csv(candidate / verifier.HIT_SUMMARY_FILE, index=False)
    for filename in verifier.ENRICHMENT_FILES:
        enrichment = _enrichment_frame(11, reverse_hits=True)
        enrichment.loc[0, "fdr"] = 0.123
        _write_csv(enrichment, candidate / filename)
    for filename in verifier.MTT_ENRICHMENT_FILES:
        _write_csv(_mtt_enrichment_frame(p_value=0.25, overlap_size=1), candidate / filename)
    return reference, candidate


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


@contextlib.contextmanager
def _read_only_trees(*roots: Path) -> Iterator[None]:
    for root in roots:
        for path in root.rglob("*"):
            path.chmod(0o555 if path.is_dir() else 0o444)
        root.chmod(0o555)
    try:
        yield
    finally:
        for root in roots:
            root.chmod(0o755)
            for path in root.rglob("*"):
                if path.is_dir():
                    path.chmod(0o755)
                else:
                    path.chmod(0o644)


class CompiledResultsVerifierTest(unittest.TestCase):
    """Exercise gate behavior using only temporary synthetic artifacts."""

    def setUp(self) -> None:
        """Create a fresh pair of complete compiled-result trees."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.reference, self.candidate = _build_fixture(self.root)

    def _main_output(self, *arguments: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = verifier.main(list(arguments))
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def _main(self, *arguments: str) -> int:
        return self._main_output(*arguments)[0]

    def test_pass_is_semantic_deterministic_and_read_only(self) -> None:
        """Ignore row/set order and allowed hit-list drift without writes."""
        report_path = self.root / "report.json"
        before_reference = _tree_digest(self.reference)
        before_candidate = _tree_digest(self.candidate)
        with _read_only_trees(self.reference, self.candidate):
            first_code, first_stdout, first_stderr = self._main_output(
                "--reference",
                os.fspath(self.reference),
                "--candidate",
                os.fspath(self.candidate),
                "--json-report",
                os.fspath(report_path),
            )
            first_report = report_path.read_bytes()
            second_code = self._main(
                "--reference",
                os.fspath(self.reference),
                "--candidate",
                os.fspath(self.candidate),
                "--json-report",
                os.fspath(report_path),
            )
            second_report = report_path.read_bytes()

        self.assertEqual(first_code, 0)
        self.assertEqual(second_code, 0)
        self.assertIn(
            "non-core metric payloads, hit calls, and enrichment hit-list, overlap, p-value, and FDR differences "
            "are diagnostic",
            first_stdout,
        )
        self.assertNotIn("FAIL:", first_stderr)
        self.assertEqual(first_report, second_report)
        self.assertEqual(_tree_digest(self.reference), before_reference)
        self.assertEqual(_tree_digest(self.candidate), before_candidate)
        report = verifier.verify_compiled_results(self.reference, self.candidate).report
        self.assertEqual(report["status"], "pass")
        pod_report = report["pods"]["SI_tables/cellcount_pods.csv"]
        self.assertEqual(pod_report["matched_keys"], POD_FIXTURE_ROWS - 1)
        self.assertEqual(pod_report["reference_only_keys"], 1)
        self.assertEqual(pod_report["candidate_only_keys"], 1)
        self.assertEqual(pod_report["comparable_pod_rows"], POD_FIXTURE_ROWS - 1)
        self.assertEqual(pod_report["excluded_nonpositive_pod_point_rows"], 0)
        self.assertNotIn("within_observed_pre_fix_run_to_run_noise", pod_report)
        enrichment = report["enrichment"]
        self.assertIsInstance(enrichment, dict)
        for filename in verifier.ENRICHMENT_FILES:
            file_report = enrichment[filename]
            self.assertEqual(file_report["overlap_hit_sets_exact_rows"], ENRICHMENT_FIXTURE_ROWS)
            self.assertEqual(file_report["fdr_exact_rows"], ENRICHMENT_FIXTURE_ROWS - 1)
        mtt_enrichment = report["mtt_enrichment"]
        self.assertIsInstance(mtt_enrichment, dict)
        for filename in verifier.MTT_ENRICHMENT_FILES:
            file_report = mtt_enrichment[filename]
            self.assertEqual(file_report["target_set_size_exact_rows"], ENRICHMENT_FIXTURE_ROWS)
            self.assertEqual(file_report["overlap_hit_sets_exact_rows"], 0)
            self.assertEqual(file_report["candidate_validity"]["fdr_matches_p_values"], True)

    def test_core_metric_payload_drift_fails(self) -> None:
        """Gate a one-value change in the 2,709-row deterministic core."""
        filename = "compiled_toxcast_cellbased_metrics.parquet"
        frame = pd.read_parquet(self.candidate / filename)
        core_index = frame.index[frame["Metadata_AggType"] == "all"][0]
        frame.loc[core_index, "AUROC"] += 0.001
        frame.to_parquet(self.candidate / filename, index=False)

        result = verifier.verify_compiled_results(self.reference, self.candidate)

        self.assertFalse(result.passed)
        self.assertTrue(any("2709" in failure for failure in result.gate_failures))
        core = result.report["metrics"]["toxcast_all_core"]
        self.assertEqual(core["payload_exact_rows"], 2_708)

    def test_core_metric_payload_is_ieee_bit_exact(self) -> None:
        """Distinguish positive and negative zero in the deterministic payload."""
        filename = "compiled_toxcast_cytotox_metrics.parquet"
        for root, value in ((self.reference, 0.0), (self.candidate, -0.0)):
            frame = pd.read_parquet(root / filename)
            key = (frame["Metadata_AggType"] == "all") & (frame["Metadata_Label"] == "label_0000")
            frame.loc[key, "AUROC"] = value
            frame.to_parquet(root / filename, index=False)

        result = verifier.verify_compiled_results(self.reference, self.candidate)

        self.assertFalse(result.passed)
        core = result.report["metrics"]["toxcast_all_core"]
        self.assertEqual(core["payload_exact_rows"], 2_708)

    def test_pod_requires_bidirectional_coverage(self) -> None:
        """Fail when fewer than 80 percent of reference POD keys match."""
        filename = "SI_tables/cellcount_pods.csv"
        frame = pd.read_csv(self.candidate / filename, keep_default_na=False)
        frame.iloc[:15].to_csv(self.candidate / filename, index=False)

        result = verifier.verify_compiled_results(self.reference, self.candidate)

        self.assertFalse(result.passed)
        self.assertTrue(any("covers 75.000%" in failure for failure in result.gate_failures))

    def test_pod_requires_small_median_relative_difference(self) -> None:
        """Gate median numerical drift even when every POD is within one percent."""
        filename = "SI_tables/mt_pods.csv"
        frame = pd.read_csv(self.candidate / filename, keep_default_na=False)
        frame.loc[:10, "POD_um"] *= 1.0001
        frame.to_csv(self.candidate / filename, index=False)

        result = verifier.verify_compiled_results(self.reference, self.candidate)

        self.assertFalse(result.passed)
        self.assertTrue(any("median reference-relative" in failure for failure in result.gate_failures))

    def test_pod_one_percent_gate_is_reference_relative(self) -> None:
        """Apply the one-percent threshold relative to the reference value."""
        filename = "SI_tables/cellpainting_dino_pods.csv"
        frame = pd.read_csv(self.candidate / filename, keep_default_na=False)
        frame.loc[1:3, "POD_um"] *= 1.01005
        frame.loc[4, "POD_um"] *= 0.99
        frame.to_csv(self.candidate / filename, index=False)

        result = verifier.verify_compiled_results(self.reference, self.candidate)

        self.assertFalse(result.passed)
        self.assertTrue(
            any("comparable POD point estimates are within 1%" in failure for failure in result.gate_failures),
        )

    def test_invalid_pod_interval_fails(self) -> None:
        """Reject a lower confidence bound above the point estimate."""
        filename = "SI_tables/ldh_pods.csv"
        frame = pd.read_csv(self.candidate / filename, keep_default_na=False)
        frame.loc[0, "POD_um_l"] = frame.loc[0, "POD_um"] * 2
        frame.to_csv(self.candidate / filename, index=False)

        result = verifier.verify_compiled_results(self.reference, self.candidate)

        self.assertFalse(result.passed)
        self.assertTrue(any("invalid POD bounds" in failure for failure in result.gate_failures))

    def test_nonpositive_pod_is_excluded_from_relative_difference_denominators(self) -> None:
        """Keep diagnostic fractions coherent when a positivity gate fails."""
        filename = "SI_tables/ldh_pods.csv"
        frame = pd.read_csv(self.candidate / filename, keep_default_na=False)
        frame.loc[1, ["POD_um", "POD_um_l", "POD_um_u"]] = 0.0
        frame.to_csv(self.candidate / filename, index=False)

        result = verifier.verify_compiled_results(self.reference, self.candidate)

        self.assertFalse(result.passed)
        self.assertTrue(any("non-positive POD" in failure for failure in result.gate_failures))
        pod_report = result.report["pods"][filename]
        self.assertEqual(pod_report["matched_keys"], POD_FIXTURE_ROWS - 1)
        self.assertEqual(pod_report["comparable_pod_rows"], POD_FIXTURE_ROWS - 2)
        self.assertEqual(pod_report["excluded_nonpositive_pod_point_rows"], 1)
        self.assertEqual(pod_report["within_one_percent_rows"], POD_FIXTURE_ROWS - 2)
        self.assertEqual(pod_report["within_one_percent_fraction"], 1.0)
        self.assertEqual(pod_report["over_ten_percent_rows"], 0)
        self.assertEqual(pod_report["over_ten_percent_fraction"], 0.0)

    def test_enrichment_target_size_mismatch_fails(self) -> None:
        """Gate target definition drift while allowing hit-list-size drift."""
        filename = "err_higher_targets.csv"
        frame = pd.read_csv(self.candidate / filename, keep_default_na=False)
        frame.loc[0, "target_set_size"] += 1
        frame.to_csv(self.candidate / filename, index=False)

        result = verifier.verify_compiled_results(self.reference, self.candidate)

        self.assertFalse(result.passed)
        self.assertTrue(any("target_set_size values do not match" in failure for failure in result.gate_failures))

    def test_mtt_enrichment_target_size_mismatch_fails(self) -> None:
        """Gate drift in the MT target-library definition."""
        filename = "mtt_higher_targets.csv"
        frame = pd.read_csv(self.candidate / filename, keep_default_na=False)
        frame.loc[0, "target_set_size"] += 1
        frame.to_csv(self.candidate / filename, index=False)

        result = verifier.verify_compiled_results(self.reference, self.candidate)

        self.assertFalse(result.passed)
        self.assertTrue(any(filename in failure and "target_set_size" in failure for failure in result.gate_failures))

    def test_mtt_enrichment_fdr_must_match_its_p_values(self) -> None:
        """Reject internally inconsistent MT multiple-testing output."""
        filename = "mtt_lower_targets.csv"
        frame = pd.read_csv(self.candidate / filename, keep_default_na=False)
        frame.loc[0, "fdr"] = 0.9
        frame.to_csv(self.candidate / filename, index=False)

        result = verifier.verify_compiled_results(self.reference, self.candidate)

        self.assertFalse(result.passed)
        self.assertTrue(
            any(filename in failure and "Benjamini-Hochberg" in failure for failure in result.gate_failures),
        )

    def test_duplicate_null_safe_pod_key_is_invalid(self) -> None:
        """Treat two empty OASIS IDs on the same compound/endpoint as duplicates."""
        filename = "SI_tables/cellpainting_cpcnn_pods.csv"
        frame = pd.read_csv(self.candidate / filename, keep_default_na=False)
        pd.concat([frame, frame.iloc[[0]]], ignore_index=True).to_csv(self.candidate / filename, index=False)

        with self.assertRaisesRegex(verifier.InputValidationError, "duplicate semantic key"):
            verifier.verify_compiled_results(self.reference, self.candidate)

    def test_same_directory_and_nested_json_report_are_invalid(self) -> None:
        """Reject self-comparison and any report write inside an input tree."""
        same_directory_code = self._main(
            "--reference",
            os.fspath(self.reference),
            "--candidate",
            os.fspath(self.reference),
        )
        nested_report = self.candidate / "report.json"
        nested_report_code = self._main(
            "--reference",
            os.fspath(self.reference),
            "--candidate",
            os.fspath(self.candidate),
            "--json-report",
            os.fspath(nested_report),
        )

        self.assertEqual(same_directory_code, 2)
        self.assertEqual(nested_report_code, 2)
        self.assertFalse(nested_report.exists())


if __name__ == "__main__":
    unittest.main()
