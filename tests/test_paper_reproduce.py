# ruff: noqa: PT009, PT027
"""Contract tests for the archive-safe paper reproduction runner."""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import io
import json
import os
import re
import shutil
import socket
import tempfile
import unittest
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import NoReturn
from unittest import mock
from zipfile import ZIP_DEFLATED, ZipFile

_MPL_CONFIG_DIRECTORY = tempfile.TemporaryDirectory(prefix="oasis-paper-test-mpl-")
os.environ.setdefault("MPLCONFIGDIR", _MPL_CONFIG_DIRECTORY.name)

reproduce = importlib.import_module("paper.reproduce")

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SHA256_HEX_LENGTH = 64
ZIP_CENTRAL_CRC_OFFSET = 16
ZIP_CENTRAL_HEADER_SIGNATURE = b"PK\x01\x02"
ZIP_CRC_SIZE = 4
ZIP_LOCAL_EXTRA_LENGTH_OFFSET = 28
ZIP_LOCAL_FILENAME_LENGTH_OFFSET = 26
ZIP_LOCAL_HEADER_SIZE = 30
ZIP_UINT16_SIZE = 2
EXPECTED_LEDGER_STATUS_COUNTS = {
    "blocked": 3,
    "reproduced": 7,
    "reproduced-with-deviation": 43,
}
EXPECTED_EXECUTION_OUTCOME_COUNTS = {
    "blocked": 3,
    "checked": 32,
    "documentary-only": 17,
    "out-of-scope": 1,
}
EXPECTED_ACCEPTANCE_CLASS_COUNTS = {
    "close": 19,
    "exact": 13,
    "qualitative": 19,
    "trace-only": 2,
}
TARGET_FIELDS = {
    "acceptance",
    "acceptance_class",
    "artifacts",
    "availability",
    "checks",
    "description",
    "deviation",
    "evidence",
    "evidence_strength",
    "expected",
    "execution_outcome",
    "group",
    "id",
    "inputs",
    "kind",
    "ledger_status",
    "limitations",
    "producer",
    "source",
    "summary",
}
CHECK_FIELDS = {"id", "target_id", "name", "observed", "expected", "passed"}
EXPECTED_OUTPUTS = {
    "classifier-summary.svg",
    "enrichment-summary.svg",
    "evidence-coverage.svg",
    "pod-summary.svg",
    "report.json",
    "report.md",
    "toxcast-summary.svg",
}
FOCUSED_SFIG1_OUTPUTS = {"evidence-coverage.svg", "report.json", "report.md"}
LEDGER_RESULT_FIELDS = {
    "source": "source",
    "kind": "kind",
    "description": "description",
    "expected": "expected",
    "acceptance": "acceptance",
    "producer": "producer",
    "evidence": "evidence",
    "deviation": "deviation",
    "ledger_status": "status",
}


def _input_snapshot() -> tuple[tuple[str, str], ...]:
    paths = {REPOSITORY_ROOT / relative for relative in reproduce.ALLOWED_INPUTS}
    for relative in reproduce.PROTECTED_INPUT_TREES:
        paths.update(path for path in (REPOSITORY_ROOT / relative).rglob("*") if path.is_file())
    return tuple(
        (
            path.relative_to(REPOSITORY_ROOT).as_posix(),
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(paths)
    )


def _rendered_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


class _NonStandardJsonConstantError(ValueError):
    """A JSON document contains NaN or Infinity."""


def _reject_json_constant(value: str) -> NoReturn:
    raise _NonStandardJsonConstantError(value)


def _mapping_keys(value: object) -> Iterator[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key)
            yield from _mapping_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _mapping_keys(child)


def _expected_execution_outcome(recipe: object, *, checks_passed: bool) -> str:
    if not checks_passed:
        return "check-failed"
    availability = recipe.availability
    if availability == "available":
        return "checked"
    if availability == "documentary-only":
        return "documentary-only"
    if availability == "blocked":
        return "blocked"
    if availability == "out-of-scope":
        return "out-of-scope"
    return "invalid-availability"


def _copy_inputs(root: Path, relatives: Iterator[str], overrides: Mapping[str, bytes]) -> None:
    for relative in relatives:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if relative in overrides:
            destination.write_bytes(overrides[relative])
        else:
            shutil.copyfile(REPOSITORY_ROOT / relative, destination)


def _run_main_with_overrides(
    validated_inputs: list[str],
    overrides: Mapping[str, bytes],
    *,
    target: str = "TABLE-S1",
) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        _copy_inputs(root, iter(validated_inputs), overrides)
        output = root / "output"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(reproduce, "REPOSITORY_ROOT", root),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            exit_code = reproduce.main(["--target", target, "--output", os.fspath(output)])
        return exit_code, stderr.getvalue()


def _corrupt_first_central_crc(workbook_bytes: bytes) -> bytes:
    payload = bytearray(workbook_bytes)
    with ZipFile(io.BytesIO(workbook_bytes)) as archive:
        central_offset = archive.start_dir
    if payload[central_offset : central_offset + len(ZIP_CENTRAL_HEADER_SIGNATURE)] != ZIP_CENTRAL_HEADER_SIGNATURE:
        message = "XLSX central directory was not found at the declared offset"
        raise ValueError(message)
    crc_offset = central_offset + ZIP_CENTRAL_CRC_OFFSET
    crc = int.from_bytes(payload[crc_offset : crc_offset + ZIP_CRC_SIZE], "little")
    payload[crc_offset : crc_offset + ZIP_CRC_SIZE] = (crc ^ 1).to_bytes(ZIP_CRC_SIZE, "little")
    return bytes(payload)


def _corrupt_first_deflated_stream(workbook_bytes: bytes) -> bytes:
    payload = bytearray(workbook_bytes)
    with ZipFile(io.BytesIO(workbook_bytes)) as archive:
        member = next(
            info for info in archive.infolist() if info.compress_type == ZIP_DEFLATED and info.compress_size > 0
        )
    local_offset = member.header_offset
    filename_length = int.from_bytes(
        payload[
            local_offset + ZIP_LOCAL_FILENAME_LENGTH_OFFSET : local_offset
            + ZIP_LOCAL_FILENAME_LENGTH_OFFSET
            + ZIP_UINT16_SIZE
        ],
        "little",
    )
    extra_length = int.from_bytes(
        payload[
            local_offset + ZIP_LOCAL_EXTRA_LENGTH_OFFSET : local_offset
            + ZIP_LOCAL_EXTRA_LENGTH_OFFSET
            + ZIP_UINT16_SIZE
        ],
        "little",
    )
    stream_offset = local_offset + ZIP_LOCAL_HEADER_SIZE + filename_length + extra_length
    payload[stream_offset] ^= 0xFF
    return bytes(payload)


class PaperReproductionRunnerTest(unittest.TestCase):
    """Exercise the public report and rendering contracts on tracked inputs."""

    @classmethod
    def setUpClass(cls) -> None:
        """Build one canonical report and record input bytes around the build."""
        cls.before_build = _input_snapshot()
        cls.report = reproduce.build_report(REPOSITORY_ROOT)
        cls.after_build = _input_snapshot()

    def test_registry_inventory_and_target_results_match_ledger(self) -> None:
        """Bind every ledger row to one recipe, checks, inputs, and outcome."""
        ledger = reproduce.load_targets(REPOSITORY_ROOT)
        ledger_by_id = {row["id"]: row for row in ledger}
        recipe_ids = list(reproduce.TARGET_RECIPES)

        self.assertEqual(len(ledger), 53)
        self.assertEqual(len(recipe_ids), 53)
        self.assertEqual(len(set(recipe_ids)), 53)
        self.assertEqual(set(recipe_ids), set(ledger_by_id))
        self.assertEqual(
            set(reproduce.TargetRecipe.__dataclass_fields__),
            {"group", "evidence_strength", "availability", "inputs", "check_builder"},
        )
        for obsolete_name in ("REPRODUCED_IDS", "BLOCKED_IDS", "OUT_OF_SCOPE_IDS"):
            self.assertFalse(hasattr(reproduce, obsolete_name), obsolete_name)
        self.assertFalse(hasattr(reproduce, "_derive_run_result"))

        self.assertEqual(self.report["schema_version"], 3)
        self.assertEqual(self.report["summary"]["total"], 53)
        self.assertEqual(self.report["summary"]["ledger_status_counts"], EXPECTED_LEDGER_STATUS_COUNTS)
        self.assertEqual(
            self.report["summary"]["execution_outcome_counts"],
            EXPECTED_EXECUTION_OUTCOME_COUNTS,
        )
        self.assertNotIn("run_result_counts", self.report["summary"])
        self.assertEqual(self.report["summary"]["acceptance_class_counts"], EXPECTED_ACCEPTANCE_CLASS_COUNTS)
        self.assertEqual(
            set(self.report["executed_groups"]),
            {"sources_design", "activity_pods", "regression_enrichment", "toxcast", "classifier", "external_image"},
        )
        for group in self.report["groups"].values():
            self.assertNotIn("run_result_counts", group)
            self.assertEqual(sum(group["execution_outcome_counts"].values()), group["target_count"])

        targets = {target["id"]: target for target in self.report["targets"]}
        self.assertEqual(set(targets), set(ledger_by_id))
        validated_inputs = set(self.report["validated_inputs"])
        all_check_ids: list[str] = []
        target_check_signatures: set[tuple[str, ...]] = set()
        for target_id, target in targets.items():
            self.assertEqual(set(target), TARGET_FIELDS)
            ledger_row = ledger_by_id[target_id]
            recipe = reproduce.TARGET_RECIPES[target_id]
            for report_field, ledger_field in LEDGER_RESULT_FIELDS.items():
                self.assertEqual(target[report_field], ledger_row[ledger_field])
            self.assertEqual(target["inputs"], list(recipe.inputs))
            self.assertEqual(target["availability"], recipe.availability)
            self.assertTrue(target["checks"])
            self.assertTrue(all(check["passed"] for check in target["checks"]))
            self.assertEqual(
                target["execution_outcome"],
                _expected_execution_outcome(
                    recipe,
                    checks_passed=all(check["passed"] for check in target["checks"]),
                ),
            )
            check_ids = tuple(check["id"] for check in target["checks"])
            target_check_signatures.add(check_ids)
            all_check_ids.extend(check_ids)
            for check in target["checks"]:
                self.assertEqual(set(check), CHECK_FIELDS)
                self.assertEqual(check["target_id"], target_id)
                self.assertTrue(check["id"].startswith(f"{target_id}:"))
            self.assertTrue(set(target["inputs"]) <= validated_inputs)
            for relative in target["inputs"]:
                self.assertTrue((REPOSITORY_ROOT / relative).is_file(), relative)

        self.assertEqual(len(all_check_ids), len(set(all_check_ids)))
        self.assertEqual(len(target_check_signatures), 53)
        for relative in validated_inputs:
            self.assertTrue((REPOSITORY_ROOT / relative).is_file(), relative)

        covered_nonpromoted = {
            "BIOACTIVITY-002": "blocked",
            "ENRICH-001": "blocked",
            "ENRICH-002": "blocked",
            "SFIG-1": "out-of-scope",
        }
        for target_id, expected_outcome in covered_nonpromoted.items():
            self.assertEqual(targets[target_id]["execution_outcome"], expected_outcome)
        self.assertEqual(targets["FILTER-002"]["ledger_status"], "reproduced-with-deviation")
        self.assertEqual(targets["FILTER-002"]["execution_outcome"], "checked")

    def test_selected_unknown_and_malformed_target_modes(self) -> None:
        """Execute only SFIG-1 and fail closed on unknown or malformed targets."""
        selected = reproduce.build_report(REPOSITORY_ROOT, selected_ids={"SFIG-1"})
        self.assertEqual(selected["summary"]["total"], 1)
        self.assertEqual([target["id"] for target in selected["targets"]], ["SFIG-1"])
        self.assertEqual(selected["executed_groups"], ["external_image"])
        self.assertEqual(set(selected["analyses"]), {"external_image"})
        self.assertEqual(set(selected["groups"]), {"external_image"})
        self.assertEqual(
            set(selected["validated_inputs"]),
            {
                "paper/targets.tsv",
                "paper/paper.md",
                "paper/figures/figure-s1.jpg",
                "paper/evidence/figure-s1.md",
                "paper/render_sfig1.py",
            },
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "selected"
            written = reproduce.render_outputs(selected, output)
            self.assertEqual({path.name for path in written}, FOCUSED_SFIG1_OUTPUTS)
            self.assertEqual(set(_rendered_files(output)), FOCUSED_SFIG1_OUTPUTS)

        with self.assertRaisesRegex(reproduce.InputValidationError, "unknown selected target IDs"):
            reproduce.build_report(REPOSITORY_ROOT, selected_ids={"UNKNOWN-999"})

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paper = root / "paper"
            paper.mkdir()
            ledger_text = (REPOSITORY_ROOT / "paper/targets.tsv").read_text(encoding="ascii")
            malformed = ledger_text.replace("\treproduced-with-deviation\t", "\tinvalid-status\t", 1)
            self.assertNotEqual(malformed, ledger_text)
            (paper / "targets.tsv").write_text(malformed, encoding="ascii")
            with self.assertRaisesRegex(reproduce.InputValidationError, "invalid ledger status"):
                reproduce.load_targets(root)

    def test_main_returns_two_for_malformed_xlsx_and_ascii(self) -> None:
        """Translate malformed workbook and ASCII inputs into CLI exit code 2."""
        selected = reproduce.build_report(REPOSITORY_ROOT, selected_ids={"TABLE-S1"})
        validated_inputs = selected["validated_inputs"]
        self.assertIn("paper/sources/table-s1.xlsx", validated_inputs)
        self.assertIn("paper/sources/SHA256SUMS", validated_inputs)

        xlsx_code, xlsx_stderr = _run_main_with_overrides(
            validated_inputs,
            {"paper/sources/table-s1.xlsx": b"not an Office ZIP archive"},
        )
        self.assertEqual(xlsx_code, 2)
        self.assertIn("malformed input", xlsx_stderr)

        ascii_code, ascii_stderr = _run_main_with_overrides(
            validated_inputs,
            {"paper/sources/SHA256SUMS": b"\xff\xfe"},
        )
        self.assertEqual(ascii_code, 2)
        self.assertIn("malformed input", ascii_stderr)

    def test_main_returns_two_for_activity_xlsx_crc_and_stream_corruption(self) -> None:
        """Classify activity-workbook CRC and compressed-stream failures as malformed."""
        selected = reproduce.build_report(REPOSITORY_ROOT, selected_ids={"TABLE-S2"})
        validated_inputs = selected["validated_inputs"]
        relative = "paper/sources/table-s2.xlsx"
        workbook_bytes = (REPOSITORY_ROOT / relative).read_bytes()
        corruptions = {
            "central CRC": _corrupt_first_central_crc(workbook_bytes),
            "compressed stream": _corrupt_first_deflated_stream(workbook_bytes),
        }

        for label, corrupted_bytes in corruptions.items():
            with self.subTest(corruption=label):
                exit_code, stderr = _run_main_with_overrides(
                    validated_inputs,
                    {relative: corrupted_bytes},
                    target="TABLE-S2",
                )
                self.assertEqual(exit_code, 2)
                self.assertIn("malformed input", stderr)
                self.assertNotIn("Traceback", stderr)

    def test_rendering_is_deterministic_strict_json_and_read_only(self) -> None:
        """Render identical safe bytes without mutating any input tree."""
        self.assertEqual(self.before_build, self.after_build)
        before_render = _input_snapshot()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = root / "first"
            second = root / "second"
            reproduce.render_outputs(self.report, first)
            reproduce.render_outputs(self.report, second)
            first_files = _rendered_files(first)
            second_files = _rendered_files(second)

            self.assertEqual(set(first_files), EXPECTED_OUTPUTS)
            self.assertEqual(first_files, second_files)
            self.assertEqual(len([name for name in first_files if name.endswith(".svg")]), 5)
            for name, payload in first_files.items():
                if name.endswith(".svg"):
                    self.assertTrue(all(line == line.rstrip(" \t") for line in payload.decode("utf-8").splitlines()))
            self.assertEqual(
                (first / "report.md").read_bytes().decode("ascii").encode("ascii"),
                first_files["report.md"],
            )

            json_bytes = first_files["report.json"]
            json_text = json_bytes.decode("ascii")
            parsed = json.loads(json_text, parse_constant=_reject_json_constant)
            self.assertEqual(parsed, self.report)
            self.assertNotIn(str(REPOSITORY_ROOT.resolve()), json_text)
            self.assertNotIn(socket.gethostname(), json_text)
            self.assertIsNone(re.search(r"\b20\d{2}-\d{2}-\d{2}[T ][0-2]\d:[0-5]\d", json_text))
            forbidden_keys = {
                "timestamp",
                "generated_at",
                "created_at",
                "hostname",
                "commit",
                "branch",
                "head",
                "dirty",
            }
            for key in _mapping_keys(parsed):
                normalized = key.casefold()
                self.assertNotIn(normalized, forbidden_keys)
                self.assertFalse(normalized.startswith("git_"))

        self.assertEqual(_input_snapshot(), before_render)

    def test_rendering_reconciles_known_outputs_and_preserves_unknown_files(self) -> None:
        """Remove stale known outputs while preserving unknown files across scopes."""
        selected = reproduce.build_report(REPOSITORY_ROOT, selected_ids={"SFIG-1"})
        sentinel_bytes = b"unknown artifact stays untouched\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "shared"
            reproduce.render_outputs(self.report, output)
            sentinel = output / "sentinel.txt"
            sentinel.write_bytes(sentinel_bytes)

            reproduce.render_outputs(selected, output)
            focused_files = _rendered_files(output)
            self.assertEqual(set(focused_files), FOCUSED_SFIG1_OUTPUTS | {"sentinel.txt"})
            self.assertEqual(focused_files["sentinel.txt"], sentinel_bytes)

            reproduce.render_outputs(self.report, output)
            full_files = _rendered_files(output)
            self.assertEqual(set(full_files), EXPECTED_OUTPUTS | {"sentinel.txt"})
            self.assertEqual(full_files["sentinel.txt"], sentinel_bytes)

    def test_committed_outputs_are_fresh(self) -> None:
        """Keep the checked-in executable-paper report synchronized with the runner."""
        committed = REPOSITORY_ROOT / "paper/reproduction"
        self.assertEqual(set(_rendered_files(committed)), EXPECTED_OUTPUTS)
        with tempfile.TemporaryDirectory() as temporary_directory:
            generated = Path(temporary_directory) / "generated"
            reproduce.render_outputs(self.report, generated)
            self.assertEqual(_rendered_files(committed), _rendered_files(generated))

    def test_protected_output_patterns_are_rejected_without_writes(self) -> None:
        """Reject every protected input-tree pattern inside a temporary root."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for relative in (*reproduce.PROTECTED_INPUT_TREES, *reproduce.FORBIDDEN_OUTPUT_TREES):
                output = root / relative / "generated"
                with self.subTest(relative=relative):
                    with self.assertRaisesRegex(reproduce.InputValidationError, "protected input tree"):
                        reproduce.render_outputs(self.report, output)
                    self.assertFalse(output.exists())

    def test_source_activity_pod_enrichment_and_toxcast_values(self) -> None:
        """Pin representative source and scientific reanalysis values."""
        analyses = self.report["analyses"]
        sources = analyses["sources_design"]
        self.assertEqual(sources["source_count"], 8)
        self.assertEqual(sources["office_archive_count"], 6)
        self.assertEqual(len(sources["sources"]), 8)
        self.assertTrue(all(len(source["sha256"]) == SHA256_HEX_LENGTH for source in sources["sources"]))
        self.assertTrue(all(archive["crc_passed"] for archive in sources["office_archives"]))

        activity = analyses["activity_pods"]
        self.assertEqual(
            activity["table_s2_counts"],
            {"MT": 429, "Cell count": 220, "LDH": 147, "unique_compounds": 437},
        )
        figure_2d = activity["figure_2d"]
        self.assertEqual(figure_2d["complete_case_count"], 121)
        expected_medians = {
            "Morphology": 5.05543414478975,
            "MT": 8.95705965699234,
            "Cell count": 23.8188547870137,
            "LDH": 40.5354608552776,
        }
        expected_folds = {"mt": 1.78550470485347, "cellcount": 4.28127228016061, "ldh": 8.15371968189112}
        for name, expected in expected_medians.items():
            self.assertAlmostEqual(figure_2d["median_pod_um"][name], expected, places=12)
        for name, expected in expected_folds.items():
            self.assertAlmostEqual(figure_2d["geometric_fold_ratio_vs_morphology"][name], expected, places=12)

        enrichment = analyses["regression_enrichment"]["files"]
        self.assertEqual(
            {name: values["significant_count"] for name, values in enrichment.items()},
            {
                "err_higher_targets.csv": 178,
                "err_lower_targets.csv": 0,
                "mtt_higher_targets.csv": 147,
                "mtt_lower_targets.csv": 107,
            },
        )
        toxcast = analyses["toxcast"]
        self.assertEqual(toxcast["source_endpoint_counts"], {"cellbased": 292, "cellfree": 72, "cytotox": 48})
        self.assertEqual(toxcast["binary_endpoint_counts"], {"cellbased": 292, "cellfree": 72, "cytotox": 38})

    def test_classifier_denominators_and_table_2_values(self) -> None:
        """Pin endpoint counts, Table 2, and the FILTER-002 contrast."""
        classifier = self.report["analyses"]["classifier"]
        self.assertEqual(
            classifier["modeled_endpoint_counts"],
            {"axiom": 2, "toxcast_cytotox": 34, "toxcast_cellbased": 267, "toxcast_cellfree": 53},
        )
        expected = {
            ("LDH", "Cell count"): (0.730446194225722, 0.418537755354911, 840, 127),
            ("LDH", "Random"): (0.500543682039745, 0.137194940827752, 840, 127),
            ("LDH", "CellProfiler"): (0.932395950506187, 0.768307081802129, 840, 127),
            ("LDH", "CP-CNN"): (0.925928008998875, 0.721697609100053, 840, 127),
            ("LDH", "DINO"): (0.939551209257365, 0.769631728263681, 839, 127),
            ("MTT", "Cell count"): (0.688951320954717, 0.639079036992903, 589, 378),
            ("MTT", "Random"): (0.50539431014813, 0.396563421811497, 589, 378),
            ("MTT", "CellProfiler"): (0.870698251003854, 0.842825856470077, 589, 378),
            ("MTT", "CP-CNN"): (0.858888410245365, 0.834197186534911, 588, 379),
            ("MTT", "DINO"): (0.875944822373394, 0.837959459995157, 588, 378),
        }
        rows = {(row["endpoint"], row["row"]): row for row in classifier["table2"]["rows"]}
        self.assertEqual(set(rows), set(expected))
        for key, (auroc, prauc, count_0, count_1) in expected.items():
            self.assertAlmostEqual(rows[key]["auroc"], auroc, places=12)
            self.assertAlmostEqual(rows[key]["prauc"], prauc, places=12)
            self.assertEqual((rows[key]["count_0"], rows[key]["count_1"]), (count_0, count_1))

        filter_effects = classifier["filter_effects"]
        self.assertAlmostEqual(
            filter_effects["toxcast_cellbased"]["auroc"]["mean_difference"],
            -0.007970189040984989,
            places=12,
        )
        self.assertAlmostEqual(
            filter_effects["toxcast_cellfree"]["auroc"]["mean_difference"],
            0.013429166433284439,
            places=12,
        )


if __name__ == "__main__":
    unittest.main()
