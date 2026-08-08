# /// script
# requires-python = "==3.11.*"
# dependencies = [
#   "matplotlib==3.9.2",
#   "numpy==1.24.3",
#   "pandas==2.2.2",
#   "pyarrow==14.0.1",
#   "scipy==1.13.1",
#   "statsmodels==0.14.3",
# ]
# ///
# ruff: noqa: ANN401, C901, COM812, E402, E501, EM101, EM102, FBT001, FBT003, I001, ICN001, PD008, PD010, PD101, PERF401, PLR0912, PLR0915, PLR2004, PTH105, S314, T201, TRY003, TRY203, TRY300, TRY301
"""Run the archive-safe, tracked-artifact paper audit.

This program deliberately reanalyzes only explicit, committed inputs.
It does not run notebooks or workflows, inspect ignored outputs, query Git, or
contact external services.  The resulting figures describe tracked-artifact
reanalysis and are not publisher-figure reproductions.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import posixpath
import re
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ET
import zlib
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, LargeZipFile, ZipFile

# ``uv run paper/reproduce.py`` puts paper/, rather than the checkout root, on
# sys.path.  Add the root before importing the repository verifier constants.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

# Some archive and sandbox environments make the user's normal Matplotlib
# config directory read-only.  Keep this process cache explicit and outside
# the repository so importing the runner never inspects or writes a repo cache.
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "oasis-paper-matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import hypergeom, ttest_rel
from statsmodels.stats.multitest import multipletests

from paper.verification.compiled_results import (
    EXPECTED_AGG_TYPES,
    EXPECTED_ENRICHMENT_ROWS,
    EXPECTED_ENRICHMENT_UNIVERSE,
    EXPECTED_METRIC_ROWS,
    HIT_COLUMNS,
    HIT_SUMMARY_COLUMNS,
    METRIC_COLUMNS,
    METRIC_KEY,
    POD_FILES,
)

SCHEMA_VERSION = 3

# The registry is intentionally explicit.  A new ledger row must be assigned
# deliberately instead of inheriting a result from a filename or prefix.
TARGET_GROUPS: dict[str, tuple[str, ...]] = {
    "sources_design": (
        "DESIGN-001",
        "DESIGN-002",
        "DESIGN-003",
        "FIG-1",
        "TABLE-S1",
        "TABLE-KEY-RESOURCES",
        "METHOD-STATS",
        "RESOURCE-001",
    ),
    "activity_pods": (
        "ACTIVITY-001",
        "ACTIVITY-002",
        "ACTIVITY-003",
        "FIG-2A",
        "BIOACTIVITY-001",
        "FIG-2B",
        "BIOACTIVITY-002",
        "FIG-2C",
        "BIOACTIVITY-003",
        "FIG-2D",
        "TABLE-S2",
        "TABLE-S3",
        "TABLE-S4",
        "METHOD-POD",
        "CONCLUSION-001",
    ),
    "regression_enrichment": (
        "TABLE-1",
        "REGRESSION-001",
        "REGRESSION-002",
        "ENRICH-001",
        "ENRICH-002",
        "ENRICH-003",
        "ENRICH-004",
        "SFIG-2",
        "METHOD-REGRESSION",
        "INTERPRETATION-001",
    ),
    "toxcast": (
        "TOXCAST-001",
        "TOXCAST-002",
        "TOXCAST-003",
        "SFIG-3",
        "TABLE-S5",
        "METHOD-TOXCAST",
    ),
    "classifier": (
        "TABLE-2",
        "CLASSIFIER-001",
        "FIG-3AB",
        "FIG-3C",
        "FILTER-001",
        "FILTER-002",
        "FIG-4A",
        "REPRESENTATION-001",
        "FIG-4B",
        "SFIG-4",
        "METHOD-CLASSIFIER",
        "CONCLUSION-002",
        "CONCLUSION-003",
    ),
    "external_image": ("SFIG-1",),
}

SOURCE_INPUTS = (
    "paper/sources/manifest.toml",
    "paper/sources/SHA256SUMS",
    "paper/sources/main.pdf",
    "paper/sources/supplemental-figures.pdf",
    "paper/sources/table-s1.xlsx",
    "paper/sources/table-s2.xlsx",
    "paper/sources/table-s3.xlsx",
    "paper/sources/table-s4.xlsx",
    "paper/sources/table-s5.xlsx",
    "paper/sources/manuscript-source.docx",
)
ANNOTATION_INPUTS = (
    "1_snakemake/inputs/annotations/arevalo_input/compound_gene.parquet",
    "1_snakemake/inputs/annotations/cg_motive.parquet",
    "1_snakemake/inputs/annotations/motive_binary.parquet",
    "1_snakemake/inputs/annotations/toxcast_cellbased_binary.parquet",
    "1_snakemake/inputs/annotations/toxcast_cellbased_info.parquet",
    "1_snakemake/inputs/annotations/toxcast_cellfree_binary.parquet",
    "1_snakemake/inputs/annotations/toxcast_cellfree_info.parquet",
    "1_snakemake/inputs/annotations/toxcast_cytotox_binary.parquet",
    "1_snakemake/inputs/annotations/toxcast_cytotox_info.parquet",
    "1_snakemake/inputs/annotations/v5_oasis_03Sept2024_simple.csv",
)
COMPILED_INPUTS = (
    "2_downstream_analysis/compiled_results/compiled_axiom_metrics.parquet",
    "2_downstream_analysis/compiled_results/compiled_toxcast_cellbased_metrics.parquet",
    "2_downstream_analysis/compiled_results/compiled_toxcast_cellfree_metrics.parquet",
    "2_downstream_analysis/compiled_results/compiled_toxcast_cytotox_metrics.parquet",
    "2_downstream_analysis/compiled_results/err_higher_targets.csv",
    "2_downstream_analysis/compiled_results/err_lower_targets.csv",
    "2_downstream_analysis/compiled_results/mtt_higher_targets.csv",
    "2_downstream_analysis/compiled_results/mtt_lower_targets.csv",
    "2_downstream_analysis/compiled_results/motive_highexp_PHH.parquet",
    "2_downstream_analysis/compiled_results/SI_tables/cellcount_pods.csv",
    "2_downstream_analysis/compiled_results/SI_tables/cellpainting_cellprofiler_pods.csv",
    "2_downstream_analysis/compiled_results/SI_tables/cellpainting_cpcnn_pods.csv",
    "2_downstream_analysis/compiled_results/SI_tables/cellpainting_dino_pods.csv",
    "2_downstream_analysis/compiled_results/SI_tables/hit_summary.csv",
    "2_downstream_analysis/compiled_results/SI_tables/ldh_pods.csv",
    "2_downstream_analysis/compiled_results/SI_tables/mt_pods.csv",
    "2_downstream_analysis/compiled_results/SI_tables/readme.txt",
)
TRACE_INPUTS = (
    "README.md",
    "paper/REPRODUCING.md",
    "paper/paper.md",
    "paper/targets.tsv",
    "paper/evidence/activity-and-figure-2a.md",
    "paper/evidence/bioactivity-and-figure-2b-d.md",
    "paper/evidence/classifier-results.md",
    "paper/evidence/experimental-design-and-figure-1.md",
    "paper/evidence/figure-s1.md",
    "paper/evidence/method-deviations.md",
    "paper/evidence/mt-discrepancy-enrichment.md",
    "paper/evidence/prediction-error-enrichment.md",
    "paper/evidence/published-table-bridge.md",
    "paper/evidence/regression-and-figure-s2.md",
    "paper/evidence/remaining-paper-reproduction-targets.md",
    "paper/evidence/toxcast-curation-and-figure-s3.md",
    "paper/figures/figure-1.jpg",
    "paper/figures/figure-s1.jpg",
    "paper/render_sfig1.py",
    "0_prepare_data/4A_download_compiled_inputs.py",
    "1_snakemake/Snakefile",
    "1_snakemake/concresponse/fit_curves.R",
    "1_snakemake/concresponse/fit_curves_meta.R",
    "1_snakemake/concresponse/select_pod.R",
    "1_snakemake/classifier/aggregate_profiles.py",
    "1_snakemake/classifier/classify.py",
    "1_snakemake/classifier/hitcalls.py",
    "1_snakemake/classifier/metrics.py",
    "1_snakemake/classifier/regression.py",
    "1_snakemake/rules/classifier.smk",
    "1_snakemake/rules/concresponse.smk",
    "2_downstream_analysis/manuscript_notebooks/2_1_predict_continuous_assays.ipynb",
    "2_downstream_analysis/manuscript_notebooks/3_1_toxcast_endpoints.ipynb",
    "2_downstream_analysis/other_notebooks/01_checkwelleffects.ipynb",
)
ALLOWED_INPUTS = frozenset((*SOURCE_INPUTS, *ANNOTATION_INPUTS, *COMPILED_INPUTS, *TRACE_INPUTS))

PROTECTED_INPUT_TREES = (
    "paper/sources",
    "paper/figures",
    "paper/evidence",
    "2_downstream_analysis/compiled_results",
    "1_snakemake/inputs/annotations",
)
FORBIDDEN_OUTPUT_TREES = (
    "1_snakemake/inputs/metadata",
    "1_snakemake/inputs/profiles",
    "1_snakemake/outputs",
    ".git",
    ".pixi",
    ".cache",
    "__pycache__",
)
KNOWN_OUTPUT_FILENAMES = frozenset(
    {
        "report.json",
        "report.md",
        "evidence-coverage.svg",
        "pod-summary.svg",
        "enrichment-summary.svg",
        "toxcast-summary.svg",
        "classifier-summary.svg",
    }
)
ANALYSIS_FIGURE_FILENAMES = {
    "activity_pods": "pod-summary.svg",
    "regression_enrichment": "enrichment-summary.svg",
    "toxcast": "toxcast-summary.svg",
    "classifier": "classifier-summary.svg",
}

LEDGER_HEADER = (
    "id",
    "source",
    "kind",
    "description",
    "expected",
    "acceptance",
    "producer",
    "evidence",
    "status",
    "deviation",
)
LEDGER_STATUSES = frozenset({"reproduced", "reproduced-with-deviation", "blocked", "out-of-scope"})
EVIDENCE_STRENGTHS = frozenset(
    {"source-recomputation", "derived-artifact-reanalysis", "documentary-trace", "unavailable"}
)
ACCEPTANCE_CLASSES = frozenset({"exact", "close", "qualitative", "trace-only"})

_XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_OFFICE_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

_VALIDATED_INPUTS: ContextVar[set[str] | None] = ContextVar("validated_inputs", default=None)


@dataclass(frozen=True)
class TargetRecipe:
    """One explicit tracked-only execution contract for a ledger target."""

    group: str
    evidence_strength: str
    availability: str
    inputs: tuple[str, ...]
    check_builder: Callable[[Mapping[str, Any]], list[dict[str, object]]]


class InputValidationError(ValueError):
    """An input is missing, malformed, unsafe, or outside registry coverage."""


class ScientificContradictionError(RuntimeError):
    """Tracked evidence contradicts the pinned scientific or ledger contract."""


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _input_path(root: Path, relative: str) -> Path:
    if relative not in ALLOWED_INPUTS:
        raise InputValidationError(f"input is not allowlisted: {relative}")
    root_resolved = root.resolve()
    path = (root_resolved / relative).resolve()
    if not _inside(path, root_resolved):
        raise InputValidationError(f"input escapes repository root: {relative}")
    if not path.is_file():
        raise InputValidationError(f"missing tracked input: {relative}")
    validated = _VALIDATED_INPUTS.get()
    if validated is not None:
        validated.add(relative)
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InputValidationError(message)


def _confirm(condition: bool, message: str) -> None:
    if not condition:
        raise ScientificContradictionError(message)


def _native_float(value: object, *, digits: int = 15) -> float:
    result = float(value)
    if not np.isfinite(result):
        raise InputValidationError("report value is not finite")
    return float(f"{result:.{digits}g}")


def _check(name: str, observed: object, expected: object, passed: bool | None = None) -> dict[str, object]:
    return {
        "name": name,
        "passed": bool(observed == expected) if passed is None else bool(passed),
        "observed": observed,
        "expected": expected,
    }


def load_targets(root: Path) -> list[dict[str, str]]:
    """Load and structurally validate the paper target ledger."""
    path = _input_path(root, "paper/targets.tsv")
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if tuple(reader.fieldnames or ()) != LEDGER_HEADER:
                raise InputValidationError(
                    f"paper/targets.tsv has header {tuple(reader.fieldnames or ())!r}; expected {LEDGER_HEADER!r}"
                )
            rows = [dict(row) for row in reader]
    except UnicodeDecodeError as exc:
        raise InputValidationError("paper/targets.tsv is not UTF-8") from exc

    _require(bool(rows), "paper/targets.tsv is empty")
    seen: set[str] = set()
    for line_number, row in enumerate(rows, start=2):
        _require(set(row) == set(LEDGER_HEADER), f"ledger row {line_number} has unexpected fields")
        _require(all(value is not None for value in row.values()), f"ledger row {line_number} is incomplete")
        target_id = row["id"]
        _require(bool(re.fullmatch(r"[A-Z]+(?:-[A-Z0-9]+)+", target_id)), f"invalid target ID {target_id!r}")
        _require(target_id not in seen, f"duplicate target ID {target_id}")
        seen.add(target_id)
        _require(row["status"] in LEDGER_STATUSES, f"{target_id}: invalid ledger status {row['status']!r}")
        acceptance_class = row["acceptance"].partition(":")[0]
        _require(acceptance_class in ACCEPTANCE_CLASSES, f"{target_id}: invalid acceptance class")
        _require(bool(row["description"] and row["expected"]), f"{target_id}: empty description or expectation")
    return rows


def _column_index(reference: str) -> int:
    index = 0
    for character in reference:
        if not character.isalpha():
            break
        index = index * 26 + ord(character.upper()) - ord("A") + 1
    if index == 0:
        raise InputValidationError(f"invalid XLSX cell reference {reference!r}")
    return index - 1


def _xlsx_tables(path: Path) -> list[tuple[str, list[dict[str, object]]]]:
    """Read simple worksheet tables with only the Python standard library."""
    try:
        with ZipFile(path) as archive:
            bad_member = archive.testzip()
            if bad_member is not None:
                raise InputValidationError(f"{path.name}: corrupt Office member {bad_member}")
            names = set(archive.namelist())
            _require("xl/workbook.xml" in names, f"{path.name}: missing xl/workbook.xml")

            shared: list[str] = []
            if "xl/sharedStrings.xml" in names:
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                shared = ["".join(node.text or "" for node in item.iter(f"{_XLSX_NS}t")) for item in root]

            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            rel_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            relationships = {item.attrib["Id"]: item.attrib["Target"] for item in rel_root}
            sheets = workbook.find(f"{_XLSX_NS}sheets")
            _require(sheets is not None, f"{path.name}: workbook has no sheets")
            result: list[tuple[str, list[dict[str, object]]]] = []
            for sheet in sheets:
                relationship_id = sheet.attrib[f"{_OFFICE_REL_NS}id"]
                target = relationships.get(relationship_id)
                _require(target is not None, f"{path.name}: unresolved worksheet relationship")
                member = target.lstrip("/") if target.startswith("/") else posixpath.normpath(f"xl/{target}")
                _require(member in names, f"{path.name}: missing worksheet {member}")
                xml_root = ET.fromstring(archive.read(member))
                raw_rows: list[list[object]] = []
                for row in xml_root.iter(f"{_XLSX_NS}row"):
                    values: list[object] = []
                    for cell in row.findall(f"{_XLSX_NS}c"):
                        column = _column_index(cell.attrib.get("r", ""))
                        while len(values) <= column:
                            values.append("")
                        cell_type = cell.attrib.get("t")
                        value_node = cell.find(f"{_XLSX_NS}v")
                        if cell_type == "inlineStr":
                            inline = cell.find(f"{_XLSX_NS}is")
                            value: object = (
                                "".join(node.text or "" for node in inline.iter(f"{_XLSX_NS}t"))
                                if inline is not None
                                else ""
                            )
                        elif value_node is None or value_node.text is None:
                            value = ""
                        elif cell_type == "s":
                            try:
                                value = shared[int(value_node.text)]
                            except (IndexError, ValueError) as exc:
                                raise InputValidationError(f"{path.name}: invalid shared-string index") from exc
                        elif cell_type == "b":
                            value = value_node.text == "1"
                        else:
                            value = value_node.text
                        values[column] = value
                    if any(value not in ("", None) for value in values):
                        raw_rows.append(values)
                _require(bool(raw_rows), f"{path.name}: worksheet {sheet.attrib['name']} is empty")
                header = [str(value) for value in raw_rows[0]]
                _require(all(header), f"{path.name}: worksheet has blank header cells")
                _require(len(header) == len(set(header)), f"{path.name}: worksheet has duplicate headers")
                table = [
                    {column: row[index] if index < len(row) else "" for index, column in enumerate(header)}
                    for row in raw_rows[1:]
                ]
                result.append((sheet.attrib["name"], table))
            return result
    except (BadZipFile, LargeZipFile, ET.ParseError, KeyError, UnicodeDecodeError, zlib.error) as exc:
        raise InputValidationError(f"cannot parse Office archive {path.name}: {exc}") from exc


def _first_xlsx_table(root: Path, relative: str) -> list[dict[str, object]]:
    tables = _xlsx_tables(_input_path(root, relative))
    _require(len(tables) == 1, f"{relative}: expected exactly one worksheet")
    return tables[0][1]


def _norm_string(value: object) -> str | None:
    if value in (None, "") or value is pd.NA:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    return str(value)


def _read_csv(root: Path, relative: str) -> pd.DataFrame:
    try:
        return pd.read_csv(_input_path(root, relative))
    except Exception as exc:
        raise InputValidationError(f"cannot read CSV {relative}: {exc}") from exc


def _read_parquet(root: Path, relative: str) -> pd.DataFrame:
    try:
        return pd.read_parquet(_input_path(root, relative), engine="pyarrow")
    except Exception as exc:
        raise InputValidationError(f"cannot read Parquet {relative}: {exc}") from exc


def _validate_columns(frame: pd.DataFrame, expected: set[str] | frozenset[str], label: str) -> None:
    actual = set(frame.columns)
    _require(actual == set(expected), f"{label}: unexpected columns; got {sorted(actual)!r}")
    _require(not frame.empty, f"{label}: table is empty")


def _analyze_sources_design(root: Path) -> dict[str, object]:
    manifest_path = _input_path(root, "paper/sources/manifest.toml")
    sums_path = _input_path(root, "paper/sources/SHA256SUMS")
    try:
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise InputValidationError(f"cannot parse paper/sources/manifest.toml: {exc}") from exc
    records = manifest.get("source")
    _require(isinstance(records, list), "source manifest has no source records")
    _confirm(len(records) == 8, f"source manifest has {len(records)} records; expected 8")

    checksums: dict[str, str] = {}
    try:
        checksum_lines = sums_path.read_text(encoding="ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise InputValidationError("paper/sources/SHA256SUMS is not ASCII") from exc
    for line in checksum_lines:
        parts = line.split()
        _require(len(parts) == 2 and re.fullmatch(r"[0-9a-f]{64}", parts[0]) is not None, "malformed SHA256SUMS")
        _require(parts[1] not in checksums, f"duplicate checksum entry {parts[1]}")
        checksums[parts[1]] = parts[0]

    source_rows: list[dict[str, object]] = []
    office_rows: list[dict[str, object]] = []
    for raw_record in records:
        _require(isinstance(raw_record, dict), "malformed source manifest record")
        filename = raw_record.get("path")
        expected_sha = raw_record.get("sha256")
        expected_bytes = raw_record.get("bytes")
        _require(isinstance(filename, str) and "/" not in filename, "unsafe source manifest path")
        _require(
            isinstance(expected_sha, str) and re.fullmatch(r"[0-9a-f]{64}", expected_sha) is not None,
            "invalid source SHA-256",
        )
        _require(isinstance(expected_bytes, int) and expected_bytes > 0, "invalid source byte count")
        relative = f"paper/sources/{filename}"
        path = _input_path(root, relative)
        actual_sha = _sha256(path)
        actual_bytes = path.stat().st_size
        if path.suffix.lower() in {".xlsx", ".docx"}:
            try:
                with ZipFile(path) as archive:
                    bad_member = archive.testzip()
                    member_count = len(archive.infolist())
            except (BadZipFile, LargeZipFile, KeyError, zlib.error) as exc:
                raise InputValidationError(f"{filename}: invalid Office archive") from exc
            if bad_member is not None:
                raise InputValidationError(f"{filename}: Office ZIP CRC failed for {bad_member}")
            office_rows.append({"path": relative, "members": member_count, "crc_passed": True})
        _confirm(checksums.get(filename) == expected_sha, f"{filename}: manifest and SHA256SUMS disagree")
        _confirm(actual_sha == expected_sha, f"{filename}: SHA-256 differs from source manifest")
        _confirm(actual_bytes == expected_bytes, f"{filename}: byte count differs from source manifest")
        source_rows.append(
            {
                "id": str(raw_record.get("id")),
                "path": relative,
                "sha256": actual_sha,
                "bytes": actual_bytes,
                "canonical": bool(raw_record.get("canonical")),
            }
        )
    _confirm(
        set(checksums) == {str(record["path"]) for record in records}, "source checksum inventory differs from manifest"
    )
    _confirm(len(office_rows) == 6, f"found {len(office_rows)} Office archives; expected 6")

    table_s1 = _first_xlsx_table(root, "paper/sources/table-s1.xlsx")
    _confirm(len(table_s1) == 1_085, f"Table S1 has {len(table_s1)} rows; expected 1085")
    stable_rows = [row for row in table_s1 if _norm_string(row.get("OASIS_ID")) is not None]
    blank_rows = [row for row in table_s1 if _norm_string(row.get("OASIS_ID")) is None]
    stable_ids = [_norm_string(row["OASIS_ID"]) for row in stable_rows]
    _require(len(stable_ids) == len(set(stable_ids)), "Table S1 contains duplicate stable IDs")

    catalog = _read_csv(root, "1_snakemake/inputs/annotations/v5_oasis_03Sept2024_simple.csv")
    required_catalog = {"OASIS_ID", "PREFERRED_NAME", "Purchased_Axiom_Medchemxpress"}
    _require(required_catalog <= set(catalog.columns), "annotation catalog is missing Table S1 join fields")
    # The catalog has 1,494 rows for 1,477 stable IDs.  Repeated IDs are an
    # established source-layer property, so collapse only after confirming
    # that the fields used by this audit are internally consistent.
    for target_id, group in catalog.groupby("OASIS_ID", dropna=False):
        _require(
            group["PREFERRED_NAME"].nunique(dropna=False) == 1
            and group["Purchased_Axiom_Medchemxpress"].nunique(dropna=False) == 1,
            f"annotation catalog has conflicting Table S1 fields for {target_id}",
        )
    catalog_by_id = catalog.drop_duplicates("OASIS_ID").set_index("OASIS_ID")
    covered_ids = [target_id for target_id in stable_ids if target_id in catalog_by_id.index]
    purchased_ids = [
        target_id
        for target_id in covered_ids
        if str(catalog_by_id.at[target_id, "Purchased_Axiom_Medchemxpress"]) == "Yes"
    ]
    preferred_matches = sum(
        str(row["Compound Name"]) == str(catalog_by_id.at[str(row["OASIS_ID"]), "PREFERRED_NAME"])
        for row in stable_rows
        if str(row["OASIS_ID"]) in catalog_by_id.index
    )
    table_s1_report = {
        "rows": len(table_s1),
        "unique_compound_names": len({str(row["Compound Name"]) for row in table_s1}),
        "stable_id_count": len(stable_ids),
        "blank_id_count": len(blank_rows),
        "annotation_rows": len(catalog),
        "annotation_unique_ids": int(catalog["OASIS_ID"].nunique()),
        "annotation_covered_ids": len(covered_ids),
        "purchased_annotation_ids": len(purchased_ids),
        "preferred_name_matches": preferred_matches,
        "url_count": sum(bool(_norm_string(row.get("Compound URL"))) for row in table_s1),
    }
    expected_s1 = {
        "rows": 1_085,
        "stable_id_count": 966,
        "blank_id_count": 119,
        "annotation_covered_ids": 966,
        "purchased_annotation_ids": 966,
        "preferred_name_matches": 790,
    }
    for field, expected in expected_s1.items():
        _confirm(
            table_s1_report[field] == expected, f"Table S1 {field} is {table_s1_report[field]}; expected {expected}"
        )

    paper_text = _input_path(root, "paper/paper.md").read_text(encoding="utf-8")
    design_evidence = _input_path(root, "paper/evidence/experimental-design-and-figure-1.md").read_text(
        encoding="utf-8"
    )
    remaining_evidence = _input_path(root, "paper/evidence/remaining-paper-reproduction-targets.md").read_text(
        encoding="utf-8"
    )
    readme_text = _input_path(root, "README.md").read_text(encoding="utf-8")
    reproducing_text = _input_path(root, "paper/REPRODUCING.md").read_text(encoding="utf-8")
    figure_1_bytes = _input_path(root, "paper/figures/figure-1.jpg").read_bytes()
    _require(
        figure_1_bytes.startswith(b"\xff\xd8") and figure_1_bytes.endswith(b"\xff\xd9"),
        "paper/figures/figure-1.jpg is not a complete JPEG",
    )
    key_resources_section = paper_text.split("## Key Resources Table", maxsplit=1)
    _require(len(key_resources_section) == 2, "paper transcription has no Key Resources Table")
    key_resource_lines = key_resources_section[1].split("\n## ", maxsplit=1)[0].splitlines()
    key_resource_rows = [
        line
        for line in key_resource_lines
        if line.startswith("|") and not line.startswith("| ---") and not line.startswith("| **")
    ]
    _confirm(
        len(key_resource_rows) == 35, f"Key Resources table has {len(key_resource_rows) - 1} data rows; expected 34"
    )
    trace = {
        "experimental_design": all(
            token in paper_text
            for token in ("1,085 compounds", "0.01 to 100 uM", "two biological replicates", "384-well", "44 hours")
        ),
        "feature_count_claims": all(token in paper_text for token in ("5,640", "672", "4,608")),
        "assay_and_exposure_design": all(token in paper_text for token in ("44 hours", "Cell Painting", "LDH", "MT")),
        "figure_1_workflow": all(
            token in design_evidence for token in ("connect the exposures", "Cell Painting", "cell count", "LDH", "MT")
        ),
        "statistical_thresholds": all(
            token in paper_text for token in ("p \\< 0.05", "FDR cutoff of \\< 0.05", "5,500 cells")
        ),
        "resource_locations": all(
            token in paper_text + readme_text for token in ("cpg0037-oasis/axiom", "10.5281/zenodo.18242918")
        ),
        "table_key_resources": len(key_resource_rows) - 1 == 34,
        "tracked_only_boundary": "normal clone" in reproducing_text
        and "ignored inputs and outputs" in reproducing_text
        and "five are ignored" in remaining_evidence,
    }
    _confirm(all(trace.values()), "paper or workflow documentary trace is incomplete")
    return {
        "source_count": len(source_rows),
        "office_archive_count": len(office_rows),
        "sources": source_rows,
        "office_archives": office_rows,
        "table_s1": table_s1_report,
        "key_resources_data_rows": len(key_resource_rows) - 1,
        "documentary_trace": trace,
    }


def _semantic_key(frame: pd.DataFrame, columns: Sequence[str]) -> list[tuple[str | None, ...]]:
    return [
        tuple(_norm_string(value) for value in values)
        for values in frame.loc[:, list(columns)].itertuples(index=False, name=None)
    ]


def _rows_to_frame(rows: list[dict[str, object]], columns: Sequence[str], label: str) -> pd.DataFrame:
    _require(bool(rows), f"{label}: workbook table is empty")
    _require(set(rows[0]) == set(columns), f"{label}: unexpected workbook columns")
    return pd.DataFrame(rows, columns=list(columns))


def _supplemental_table_audit(
    root: Path, pods: Mapping[str, pd.DataFrame], hit_summary: pd.DataFrame
) -> dict[str, object]:
    s2_columns = ("OASIS_ID", "Assay", "Compound_name", "POD_um", "POD_um_l", "POD_um_u")
    s2_book = _rows_to_frame(_first_xlsx_table(root, "paper/sources/table-s2.xlsx"), s2_columns, "Table S2")
    s2_parts: list[pd.DataFrame] = []
    for assay, key in (("MT", "mt"), ("Cell count", "cellcount"), ("LDH", "ldh")):
        part = pods[key].copy()
        part.insert(1, "Assay", assay)
        s2_parts.append(part.loc[:, list(s2_columns)])
    s2_compiled = pd.concat(s2_parts, ignore_index=True)
    s2_key_columns = ("OASIS_ID", "Assay", "Compound_name")
    s2_book_keys = _semantic_key(s2_book, s2_key_columns)
    s2_compiled_keys = _semantic_key(s2_compiled, s2_key_columns)
    _require(len(s2_book_keys) == len(set(s2_book_keys)), "Table S2 workbook has duplicate semantic keys")
    _require(len(s2_compiled_keys) == len(set(s2_compiled_keys)), "Table S2 compiled data have duplicate semantic keys")
    _confirm(set(s2_book_keys) == set(s2_compiled_keys), "Table S2 workbook and compiled semantic keys differ")
    s2_book_index = {key: index for index, key in enumerate(s2_book_keys)}
    s2_compiled_index = {key: index for index, key in enumerate(s2_compiled_keys)}
    s2_max_difference = 0.0
    for key in s2_book_index:
        for column in ("POD_um", "POD_um_l", "POD_um_u"):
            difference = abs(
                float(s2_book.iloc[s2_book_index[key]][column])
                - float(s2_compiled.iloc[s2_compiled_index[key]][column])
            )
            s2_max_difference = max(s2_max_difference, difference)
    _confirm(s2_max_difference <= 1e-12, f"Table S2 numeric drift is {s2_max_difference}")

    s3_columns = (
        "OASIS_ID",
        "Cell_representation",
        "Compound_name",
        "Assay_Endpoint",
        "POD_um",
        "POD_um_l",
        "POD_um_u",
        "Bioactivity_POD",
    )
    s3_book = _rows_to_frame(_first_xlsx_table(root, "paper/sources/table-s3.xlsx"), s3_columns, "Table S3")
    # Style-only spreadsheet rows are removed by _xlsx_tables; every retained
    # row must contain its representation and numerical payload.
    _require(not (s3_book["Cell_representation"] == "").any(), "Table S3 contains an incomplete data row")
    s3_parts = []
    for representation, key in (("CellProfiler", "cellprofiler"), ("CP-CNN", "cpcnn"), ("DINO", "dino")):
        part = pods[key].copy()
        part.insert(1, "Cell_representation", representation)
        s3_parts.append(part.loc[:, list(s3_columns)])
    s3_compiled = pd.concat(s3_parts, ignore_index=True)
    s3_key_columns = ("OASIS_ID", "Cell_representation", "Compound_name", "Assay_Endpoint")
    s3_book_keys = _semantic_key(s3_book, s3_key_columns)
    s3_compiled_keys = _semantic_key(s3_compiled, s3_key_columns)
    _require(len(s3_book_keys) == len(set(s3_book_keys)), "Table S3 workbook has duplicate semantic keys")
    _require(len(s3_compiled_keys) == len(set(s3_compiled_keys)), "Table S3 compiled data have duplicate semantic keys")
    _confirm(set(s3_book_keys) == set(s3_compiled_keys), "Table S3 workbook and compiled semantic keys differ")
    s3_book_index = {key: index for index, key in enumerate(s3_book_keys)}
    s3_compiled_index = {key: index for index, key in enumerate(s3_compiled_keys)}
    s3_max_difference = 0.0
    s3_bioactivity_matches = 0
    for key in s3_book_index:
        left = s3_book.iloc[s3_book_index[key]]
        right = s3_compiled.iloc[s3_compiled_index[key]]
        for column in ("POD_um", "POD_um_l", "POD_um_u"):
            s3_max_difference = max(s3_max_difference, abs(float(left[column]) - float(right[column])))
        workbook_flag = left["Bioactivity_POD"] in (True, "1", 1)
        s3_bioactivity_matches += int(workbook_flag == bool(right["Bioactivity_POD"]))
    _confirm(s3_max_difference <= 1e-12, f"Table S3 numeric drift is {s3_max_difference}")
    _confirm(s3_bioactivity_matches == len(s3_book), "Table S3 Bioactivity_POD flags differ")

    s4_columns = (
        "OASIS_ID",
        "Compound_name",
        "Cell_count_hit",
        "MT_hit",
        "LDH_hit",
        "Cell_Painting_hit",
        "Hit_in_all_assays",
    )
    s4_book = _rows_to_frame(_first_xlsx_table(root, "paper/sources/table-s4.xlsx"), s4_columns, "Table S4")
    s4_keys = ("OASIS_ID", "Compound_name")
    book_keys = _semantic_key(s4_book, s4_keys)
    compiled_keys = _semantic_key(hit_summary, s4_keys)
    _require(len(book_keys) == len(set(book_keys)), "Table S4 workbook has duplicate semantic keys")
    _require(len(compiled_keys) == len(set(compiled_keys)), "Table S4 compiled data have duplicate semantic keys")
    _confirm(set(book_keys) == set(compiled_keys), "Table S4 workbook and compiled semantic keys differ")
    book_index = {key: index for index, key in enumerate(book_keys)}
    compiled_index = {key: index for index, key in enumerate(compiled_keys)}
    exact_rows = 0
    for key in book_index:
        left = s4_book.iloc[book_index[key]]
        right = hit_summary.iloc[compiled_index[key]]
        exact_rows += int(all(str(left[column]) == str(right[column]) for column in HIT_COLUMNS))
    _confirm(exact_rows == len(s4_book), "Table S4 hit calls differ from compiled hit summary")
    return {
        "table_s2": {
            "workbook_rows": len(s2_book),
            "compiled_rows": len(s2_compiled),
            "matched_semantic_keys": len(s2_book_keys),
            "maximum_absolute_pod_difference": _native_float(s2_max_difference),
        },
        "table_s3": {
            "workbook_rows": len(s3_book),
            "compiled_rows": len(s3_compiled),
            "matched_semantic_keys": len(s3_book_keys),
            "bioactivity_flag_exact_rows": s3_bioactivity_matches,
            "maximum_absolute_pod_difference": _native_float(s3_max_difference),
        },
        "table_s4": {
            "workbook_rows": len(s4_book),
            "compiled_rows": len(hit_summary),
            "matched_semantic_keys": len(book_keys),
            "all_hit_calls_exact_rows": exact_rows,
        },
    }


def _pod_series(frame: pd.DataFrame, endpoint_mode: str) -> pd.Series:
    if endpoint_mode == "global":
        selected = frame[frame["Assay_Endpoint"] == "gmd"]
    elif endpoint_mode == "categorical":
        selected = frame[frame["Assay_Endpoint"] != "gmd"]
    elif endpoint_mode == "general":
        selected = frame
    else:
        raise AssertionError(endpoint_mode)
    return selected.groupby(["OASIS_ID", "Compound_name"], dropna=False)["POD_um"].min().sort_index()


def _paired_effect(left: pd.Series, right: pd.Series, *, log10: bool = False) -> dict[str, object]:
    matched = pd.concat([left.rename("left"), right.rename("right")], axis=1, join="inner").dropna()
    _require(not matched.empty, "paired analysis has no matched rows")
    left_values = matched["left"].to_numpy(dtype=float)
    right_values = matched["right"].to_numpy(dtype=float)
    if log10:
        _require(
            bool((left_values > 0).all() and (right_values > 0).all()), "paired POD analysis has nonpositive values"
        )
        left_test = np.log10(left_values)
        right_test = np.log10(right_values)
    else:
        left_test = left_values
        right_test = right_values
    test = ttest_rel(left_test, right_test)
    statistic = None if not np.isfinite(test.statistic) else _native_float(test.statistic)
    p_value = None if not np.isfinite(test.pvalue) else _native_float(test.pvalue)
    return {
        "matched_rows": len(matched),
        "paired_t_statistic": statistic,
        "paired_t_p_value": p_value,
        "mean_difference": _native_float(np.mean(right_values - left_values)),
        "median_difference": _native_float(np.median(right_values - left_values)),
    }


def _analyze_activity_pods(root: Path) -> dict[str, object]:
    pod_paths = {
        "mt": "2_downstream_analysis/compiled_results/SI_tables/mt_pods.csv",
        "cellcount": "2_downstream_analysis/compiled_results/SI_tables/cellcount_pods.csv",
        "ldh": "2_downstream_analysis/compiled_results/SI_tables/ldh_pods.csv",
        "cellprofiler": "2_downstream_analysis/compiled_results/SI_tables/cellpainting_cellprofiler_pods.csv",
        "cpcnn": "2_downstream_analysis/compiled_results/SI_tables/cellpainting_cpcnn_pods.csv",
        "dino": "2_downstream_analysis/compiled_results/SI_tables/cellpainting_dino_pods.csv",
    }
    pods: dict[str, pd.DataFrame] = {}
    for key, relative in pod_paths.items():
        frame = _read_csv(root, relative)
        expected_columns = POD_FILES[relative.split("compiled_results/")[1]]
        _validate_columns(frame, expected_columns, relative)
        semantic_keys = _semantic_key(frame, ("OASIS_ID", "Compound_name", "Assay_Endpoint"))
        _require(len(semantic_keys) == len(set(semantic_keys)), f"{relative}: duplicate semantic key")
        for column in ("POD_um", "POD_um_l", "POD_um_u"):
            values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
            _require(bool(np.isfinite(values).all() and (values > 0).all()), f"{relative}: invalid {column}")
        pods[key] = frame

    hit_relative = "2_downstream_analysis/compiled_results/SI_tables/hit_summary.csv"
    hit_summary = _read_csv(root, hit_relative)
    _validate_columns(hit_summary, HIT_SUMMARY_COLUMNS, hit_relative)
    _require(
        all(set(hit_summary[column].dropna().unique()) <= {"Yes", "No"} for column in HIT_COLUMNS),
        "hit summary contains a value other than Yes/No",
    )
    hit_keys = _semantic_key(hit_summary, ("OASIS_ID", "Compound_name"))
    _require(len(hit_keys) == len(set(hit_keys)), "hit summary contains duplicate semantic keys")

    activity_evidence = _input_path(root, "paper/evidence/activity-and-figure-2a.md").read_text(encoding="utf-8")
    bioactivity_evidence = _input_path(root, "paper/evidence/bioactivity-and-figure-2b-d.md").read_text(
        encoding="utf-8"
    )
    method_evidence = _input_path(root, "paper/evidence/method-deviations.md").read_text(encoding="utf-8")
    paper_text = _input_path(root, "paper/paper.md").read_text(encoding="utf-8")
    fit_curves_text = _input_path(root, "1_snakemake/concresponse/fit_curves.R").read_text(encoding="utf-8")
    fit_meta_text = _input_path(root, "1_snakemake/concresponse/fit_curves_meta.R").read_text(encoding="utf-8")
    select_pod_text = _input_path(root, "1_snakemake/concresponse/select_pod.R").read_text(encoding="utf-8")

    table_s2_counts = {
        "MT": len(pods["mt"]),
        "Cell count": len(pods["cellcount"]),
        "LDH": len(pods["ldh"]),
        "unique_compounds": len(
            set(pods["mt"]["Compound_name"])
            | set(pods["cellcount"]["Compound_name"])
            | set(pods["ldh"]["Compound_name"])
        ),
    }
    expected_s2_counts = {"MT": 429, "Cell count": 220, "LDH": 147, "unique_compounds": 437}
    _confirm(
        table_s2_counts == expected_s2_counts, f"Table S2 counts are {table_s2_counts}; expected {expected_s2_counts}"
    )

    figure_2a_expected = {
        "Benzarone": 69.337144,
        "Tiratricol": 25.860426,
        "Tolcapone": 23.606292,
        "2-Ethylanthracene-9,10-dione": 8.660848,
    }
    mt_by_name = pods["mt"].set_index("Compound_name")
    figure_2a_rows: list[dict[str, object]] = []
    for compound, expected_pod in figure_2a_expected.items():
        _require(compound in mt_by_name.index, f"Figure 2A compound is absent from Table S2: {compound}")
        row = mt_by_name.loc[compound]
        _require(isinstance(row, pd.Series), f"Figure 2A compound is duplicated in Table S2: {compound}")
        observed_pod = float(row["POD_um"])
        _confirm(
            abs(observed_pod - expected_pod) <= 1e-6,
            f"Figure 2A Table S2 POD differs for {compound}: {observed_pod}",
        )
        figure_2a_rows.append(
            {
                "compound": compound,
                "pod_um": _native_float(observed_pod),
                "expected_published_pod_um": expected_pod,
            }
        )
    _confirm(
        all(compound in activity_evidence for compound in figure_2a_expected)
        and "increasing direction" in activity_evidence,
        "Figure 2A compound or direction trace is incomplete",
    )

    direction_aware_trace = {
        "count": 429,
        "definition": "decreased MT union decreased cell count union increased LDH",
        "documented_in_tracked_evidence": all(
            token in activity_evidence
            for token in (
                "identical 429-compound direction-aware cytotoxic set",
                "decreased MT, decreased cell count, and increased LDH",
            )
        ),
        "directly_encoded_in_hit_summary": False,
        "mt_increasing_count": 10,
        "mt_increasing_count_documented": "MT increasing |" in activity_evidence
        and "| Camera-ready text | 430 | 221 | 144 | 438 | 429 | 10 |" in activity_evidence,
    }
    _confirm(
        bool(direction_aware_trace["documented_in_tracked_evidence"]),
        "direction-aware 429-compound trace is missing",
    )

    morphology_counts: dict[str, object] = {}
    morphology_series: dict[str, pd.Series] = {}
    for representation in ("cellprofiler", "cpcnn", "dino"):
        morphology_counts[representation] = {}
        for mode in ("global", "categorical", "general"):
            series = _pod_series(pods[representation], mode)
            morphology_series[f"{representation}_{mode}"] = series
            morphology_counts[representation][mode] = {
                "count": len(series),
                "median_pod_um": None if series.empty else _native_float(series.median()),
            }
    expected_morphology = {
        "cellprofiler": {"global": 169, "categorical": 598, "general": 607},
        "cpcnn": {"global": 539, "categorical": 0, "general": 539},
        "dino": {"global": 545, "categorical": 626, "general": 644},
    }
    observed_morphology = {
        representation: {
            mode: int(morphology_counts[representation][mode]["count"]) for mode in expected_morphology[representation]
        }
        for representation in expected_morphology
    }
    _confirm(observed_morphology == expected_morphology, "morphology activity counts differ from tracked SI contract")
    morphology_activity_summary = {
        representation: {
            mode: {
                "count": observed_morphology[representation][mode],
                "fraction_of_1085": _native_float(observed_morphology[representation][mode] / 1_085),
            }
            for mode in ("global", "categorical", "general")
        }
        for representation in ("cellprofiler", "cpcnn", "dino")
    }
    published_si_count_order = [
        f"{representation}_{mode}"
        for representation, mode in sorted(
            (
                (representation, mode)
                for representation in ("cellprofiler", "cpcnn", "dino")
                for mode in ("global", "categorical", "general")
            ),
            key=lambda item: observed_morphology[item[0]][item[1]],
        )
    ]

    complete = pd.concat(
        {
            key: morphology_series[key]
            for key in (
                "cellprofiler_global",
                "cellprofiler_categorical",
                "dino_global",
                "dino_categorical",
                "cpcnn_global",
            )
        },
        axis=1,
        join="inner",
    ).dropna()
    _confirm(len(complete) == 156, f"Figure 2C tracked complete-case count is {len(complete)}; expected 156")
    representation_complete_case = {
        "count": len(complete),
        "median_pod_um": {column: _native_float(complete[column].median()) for column in complete.columns},
        "paired_log10_tests": {
            "cellprofiler_global_vs_dino_global": _paired_effect(
                complete["cellprofiler_global"], complete["dino_global"], log10=True
            ),
            "cellprofiler_categorical_vs_dino_categorical": _paired_effect(
                complete["cellprofiler_categorical"], complete["dino_categorical"], log10=True
            ),
            "dino_global_vs_cpcnn_global": _paired_effect(
                complete["dino_global"], complete["cpcnn_global"], log10=True
            ),
        },
        "camera_ready_count_trace": 342,
        "source_si_count_deviation": 342 - len(complete),
    }
    expected_five_series_order = [
        "cellprofiler_categorical",
        "dino_categorical",
        "dino_global",
        "cpcnn_global",
        "cellprofiler_global",
    ]
    representation_complete_case["median_order"] = sorted(
        representation_complete_case["median_pod_um"],
        key=lambda name: representation_complete_case["median_pod_um"][name],
    )
    representation_complete_case["finite_nonempty_pod_summaries"] = bool(
        len(complete) > 0
        and len(representation_complete_case["median_pod_um"]) == 5
        and all(np.isfinite(value) and value > 0 for value in representation_complete_case["median_pod_um"].values())
    )
    representation_complete_case["camera_ready_order_trace"] = expected_five_series_order
    representation_complete_case["ordering_preserved"] = (
        representation_complete_case["median_order"] == expected_five_series_order
        and "reports 342 compounds" in bioactivity_evidence
    )
    _confirm(
        bool(representation_complete_case["ordering_preserved"])
        and bool(representation_complete_case["finite_nonempty_pod_summaries"]),
        "Figure 2C source-SI ordering or camera-ready trace differs",
    )

    general_complete = pd.concat(
        {
            "cellprofiler": morphology_series["cellprofiler_general"],
            "cpcnn": morphology_series["cpcnn_general"],
            "dino": morphology_series["dino_general"],
        },
        axis=1,
        join="inner",
    ).dropna()
    _confirm(len(general_complete) == 488, f"three-general complete count is {len(general_complete)}; expected 488")
    cpcnn_cellprofiler_ratio = float(
        10 ** np.mean(np.log10(general_complete["cpcnn"]) - np.log10(general_complete["cellprofiler"]))
    )
    cpcnn_dino_ratio = float(10 ** np.mean(np.log10(general_complete["cpcnn"]) - np.log10(general_complete["dino"])))
    general_cp_dino_test = _paired_effect(general_complete["cellprofiler"], general_complete["dino"], log10=True)
    _confirm(abs(cpcnn_cellprofiler_ratio - 1.8181) <= 5e-5, "three-general CP-CNN/CellProfiler ratio drifted")
    _confirm(abs(cpcnn_dino_ratio - 1.6865) <= 5e-5, "three-general CP-CNN/DINO ratio drifted")
    _confirm(
        general_cp_dino_test["paired_t_p_value"] is not None
        and abs(float(general_cp_dino_test["paired_t_p_value"]) - 0.261) <= 5e-4,
        "three-general CellProfiler/DINO paired test drifted",
    )
    three_general = {
        "count": len(general_complete),
        "geometric_fold_ratios": {
            "cpcnn_over_cellprofiler": _native_float(cpcnn_cellprofiler_ratio),
            "cpcnn_over_dino": _native_float(cpcnn_dino_ratio),
        },
        "cellprofiler_vs_dino_paired_log10": general_cp_dino_test,
    }

    all_hits = hit_summary.loc[hit_summary["Hit_in_all_assays"] == "Yes", ["OASIS_ID", "Compound_name"]]
    dino_general = morphology_series["dino_general"].rename("Morphology").reset_index()
    figure_2d_frame = all_hits.merge(dino_general, on=["OASIS_ID", "Compound_name"], validate="one_to_one")
    assay_columns: dict[str, str] = {}
    for key, display in (("mt", "MT"), ("cellcount", "Cell count"), ("ldh", "LDH")):
        assay_columns[key] = display
        frame = pods[key].loc[:, ["OASIS_ID", "Compound_name", "POD_um"]].rename(columns={"POD_um": display})
        figure_2d_frame = figure_2d_frame.merge(frame, on=["OASIS_ID", "Compound_name"], validate="one_to_one")
    _confirm(len(figure_2d_frame) == 121, f"Figure 2D complete-case count is {len(figure_2d_frame)}; expected 121")
    medians = {
        column: _native_float(figure_2d_frame[column].median()) for column in ("Morphology", *assay_columns.values())
    }
    fold_ratios: dict[str, float] = {}
    paired_tests: dict[str, object] = {}
    for key, display in assay_columns.items():
        log_difference = np.log10(figure_2d_frame[display]) - np.log10(figure_2d_frame["Morphology"])
        fold_ratios[key] = _native_float(10 ** log_difference.mean())
        paired_tests[key] = _paired_effect(figure_2d_frame["Morphology"], figure_2d_frame[display], log10=True)
    expected_folds = {"mt": 1.7855047048534651, "cellcount": 4.281272280160607, "ldh": 8.153719681891124}
    _confirm(
        all(abs(fold_ratios[key] - expected) <= 1e-12 for key, expected in expected_folds.items()),
        f"Figure 2D fold ratios differ from tracked contract: {fold_ratios}",
    )
    figure_2d = {
        "complete_case_count": len(figure_2d_frame),
        "median_pod_um": medians,
        "geometric_fold_ratio_vs_morphology": fold_ratios,
        "paired_log10_t_tests": paired_tests,
    }
    supplemental_tables = _supplemental_table_audit(root, pods, hit_summary)
    pod_method_trace = {
        "morphology_residual_sd_selection": 'filt.var = "SDres"' in fit_curves_text,
        "paired_assay_scorespod_default": "scoresPOD(cc, dose" in fit_meta_text,
        "dmso_control": 'ctrl <- "DMSO"' in fit_curves_text and 'ctrl <- "DMSO"' in fit_meta_text,
        "compound_minimum_pod": "Select POD as minimum BMD" in select_pod_text,
        "known_selection_deviation_traced": "lowest residual standard deviation" in method_evidence
        and "rounded-AIC" in method_evidence,
        "documented_eight_model_names": all(
            model in paper_text for model in ("Exp2", "Exp3", "Exp4", "Exp5", "Poly2", "Lin", "Power", "Hill")
        )
        and "eight model families" in method_evidence,
        "documented_dmso_95th_percentile_benchmark": "95th percentile of Mahalanobis distances (MDs) from DMSO controls"
        in paper_text
        and "DMSO 95th-percentile benchmark response" in method_evidence,
        "documented_ci_ratio_threshold_40": "ratio between the upper and lower 95th confidence intervals was greater than 40"
        in paper_text
        and "confidence-interval ratio filtering" in method_evidence,
        "documented_highest_tested_concentration_filter": "benchmark dose was higher than the highest tested concentration"
        in paper_text
        and "tested-concentration filtering" in method_evidence,
    }
    _confirm(all(pod_method_trace.values()), "POD method implementation trace is incomplete")
    conclusion_gates = {
        "general_morphology_count_exceeds_mt": min(
            int(morphology_counts[name]["general"]["count"]) for name in ("cellprofiler", "cpcnn", "dino")
        )
        > table_s2_counts["MT"],
        "complete_case_median_order": medians["Morphology"] < medians["MT"] < medians["Cell count"] < medians["LDH"],
    }
    _confirm(all(conclusion_gates.values()), "morphology sensitivity conclusion inequality failed")
    return {
        "table_s2_counts": table_s2_counts,
        "morphology_counts": morphology_counts,
        "morphology_activity_summary": morphology_activity_summary,
        "published_si_count_order": published_si_count_order,
        "figure_2a": {
            "rows": figure_2a_rows,
            "compound_names": list(figure_2a_expected),
            "direction": "increasing MT",
        },
        "direction_aware_cytotoxicity": direction_aware_trace,
        "figure_2c_complete_case": representation_complete_case,
        "figure_2c_three_general": three_general,
        "figure_2d": figure_2d,
        "supplemental_tables": supplemental_tables,
        "hit_summary_counts": {column: int((hit_summary[column] == "Yes").sum()) for column in HIT_COLUMNS},
        "pod_method_trace": pod_method_trace,
        "conclusion_gates": conclusion_gates,
    }


def _analyze_regression_enrichment(root: Path) -> dict[str, object]:
    configurations = (
        ("err_higher_targets.csv", 304),
        ("err_lower_targets.csv", 138),
        ("mtt_higher_targets.csv", 261),
        ("mtt_lower_targets.csv", 131),
    )
    expected_significant = {
        "err_higher_targets.csv": 178,
        "err_lower_targets.csv": 0,
        "mtt_higher_targets.csv": 147,
        "mtt_lower_targets.csv": 107,
    }
    reports: dict[str, object] = {}
    significant_targets: dict[str, set[str]] = {}
    for filename, configured_hit_size in configurations:
        relative = f"2_downstream_analysis/compiled_results/{filename}"
        frame = _read_csv(root, relative)
        base_columns = {"target_set", "overlap_size", "target_set_size", "p_value", "fdr", "overlap_hits"}
        expected_columns = (
            base_columns | {"hit_list_size", "universe_size"} if filename.startswith("err_") else base_columns
        )
        _validate_columns(frame, expected_columns, relative)
        _require(not frame["target_set"].duplicated().any(), f"{filename}: duplicate target_set")
        _confirm(len(frame) == EXPECTED_ENRICHMENT_ROWS, f"{filename}: row count is {len(frame)}; expected 8858")

        overlap = pd.to_numeric(frame["overlap_size"], errors="coerce").to_numpy(dtype=float)
        target_size = pd.to_numeric(frame["target_set_size"], errors="coerce").to_numpy(dtype=float)
        stored_p = pd.to_numeric(frame["p_value"], errors="coerce").to_numpy(dtype=float)
        stored_fdr = pd.to_numeric(frame["fdr"], errors="coerce").to_numpy(dtype=float)
        _require(
            bool(np.isfinite(overlap).all() and np.equal(overlap, np.floor(overlap)).all()),
            f"{filename}: invalid overlap_size",
        )
        _require(
            bool(np.isfinite(target_size).all() and np.equal(target_size, np.floor(target_size)).all()),
            f"{filename}: invalid target_set_size",
        )
        _require(
            bool(np.isfinite(stored_p).all() and ((stored_p >= 0) & (stored_p <= 1)).all()),
            f"{filename}: invalid p_value",
        )
        _require(
            bool(np.isfinite(stored_fdr).all() and ((stored_fdr >= 0) & (stored_fdr <= 1)).all()),
            f"{filename}: invalid fdr",
        )
        universe_size = EXPECTED_ENRICHMENT_UNIVERSE
        hit_list_size = configured_hit_size
        if filename.startswith("err_"):
            universe_values = pd.to_numeric(frame["universe_size"], errors="coerce").to_numpy(dtype=float)
            hit_values = pd.to_numeric(frame["hit_list_size"], errors="coerce").to_numpy(dtype=float)
            _require(
                bool(np.isfinite(universe_values).all() and len(set(universe_values)) == 1),
                f"{filename}: invalid universe_size",
            )
            _require(
                bool(np.isfinite(hit_values).all() and len(set(hit_values)) == 1), f"{filename}: invalid hit_list_size"
            )
            universe_size = int(universe_values[0])
            hit_list_size = int(hit_values[0])
        _confirm(
            universe_size == EXPECTED_ENRICHMENT_UNIVERSE, f"{filename}: universe is {universe_size}; expected 13176"
        )
        _confirm(
            hit_list_size == configured_hit_size,
            f"{filename}: hit-list size is {hit_list_size}; expected {configured_hit_size}",
        )
        _require(
            bool(
                ((overlap >= 0) & (target_size >= 1) & (target_size <= universe_size)).all()
                and (overlap <= target_size).all()
                and (overlap <= hit_list_size).all()
            ),
            f"{filename}: invalid hypergeometric cardinalities",
        )
        recomputed_p = hypergeom.sf(
            overlap.astype(np.int64) - 1,
            universe_size,
            target_size.astype(np.int64),
            hit_list_size,
        )
        recomputed_fdr = multipletests(recomputed_p, method="fdr_bh", is_sorted=False)[1]
        max_p_error = float(np.max(np.abs(stored_p - recomputed_p)))
        max_fdr_error = float(np.max(np.abs(stored_fdr - recomputed_fdr)))
        _confirm(max_p_error <= 2e-14, f"{filename}: hypergeometric p-values do not reproduce")
        _confirm(max_fdr_error <= 2e-14, f"{filename}: BH FDR values do not reproduce")
        significant_count = int((stored_fdr < 0.05).sum())
        _confirm(
            significant_count == expected_significant[filename],
            f"{filename}: significant count is {significant_count}; expected {expected_significant[filename]}",
        )
        significant_targets[filename] = set(frame.loc[stored_fdr < 0.05, "target_set"].astype(str))
        reports[filename] = {
            "rows": len(frame),
            "hit_list_size": hit_list_size,
            "universe_size": universe_size,
            "significant_count": significant_count,
            "minimum_p_value": _native_float(stored_p.min()),
            "minimum_fdr": _native_float(stored_fdr.min()),
            "maximum_p_value_recomputation_error": _native_float(max_p_error),
            "maximum_fdr_recomputation_error": _native_float(max_fdr_error),
        }
    regression_text = _input_path(root, "1_snakemake/classifier/regression.py").read_text(encoding="utf-8")
    paper_text = _input_path(root, "paper/paper.md").read_text(encoding="utf-8")
    regression_notebook = _input_path(
        root, "2_downstream_analysis/manuscript_notebooks/2_1_predict_continuous_assays.ipynb"
    ).read_text(encoding="utf-8")
    well_effects_notebook = _input_path(
        root, "2_downstream_analysis/other_notebooks/01_checkwelleffects.ipynb"
    ).read_text(encoding="utf-8")
    regression_evidence = _input_path(root, "paper/evidence/regression-and-figure-s2.md").read_text(encoding="utf-8")
    prediction_evidence = _input_path(root, "paper/evidence/prediction-error-enrichment.md").read_text(encoding="utf-8")
    mt_evidence = _input_path(root, "paper/evidence/mt-discrepancy-enrichment.md").read_text(encoding="utf-8")
    method_evidence = _input_path(root, "paper/evidence/method-deviations.md").read_text(encoding="utf-8")

    higher = significant_targets["mtt_higher_targets.csv"]
    lower = significant_targets["mtt_lower_targets.csv"]
    transporters = [target for target in ("ABCB1", "ABCG2", "SLCO1B1", "SLCO1B3") if target in higher]
    significant_classes = {
        "mtt_higher": {
            "cyp_prefix_count": sum(target.startswith("CYP") for target in higher),
            "htr_prefix_count": sum(target.startswith("HTR") for target in higher),
            "transporters_present": transporters,
        },
        "mtt_lower": {
            "psm_prefix_count": sum(target.startswith("PSM") for target in lower),
            "cyp_prefix_count": sum(target.startswith("CYP") for target in lower),
        },
    }
    _confirm(
        significant_classes["mtt_higher"]
        == {
            "cyp_prefix_count": 8,
            "htr_prefix_count": 6,
            "transporters_present": ["ABCB1", "ABCG2", "SLCO1B1", "SLCO1B3"],
        },
        "MT-higher significant target classes differ",
    )
    _confirm(
        significant_classes["mtt_lower"] == {"psm_prefix_count": 18, "cyp_prefix_count": 3},
        "MT-lower significant target classes differ",
    )
    regression_trace = {
        "group_shuffle_split_count": 10,
        "test_fraction": 0.2,
        "compound_group_isolation": "GroupShuffleSplit(n_splits=10, test_size=0.2, random_state=42)" in regression_text
        and '"Metadata_Compound"' in regression_text,
        "prediction_artifacts_available": False,
        "numerical_acceptance_rerun": False,
        "table_1_documentary": all(
            token in paper_text + regression_notebook + regression_evidence
            for token in ("Prediction of paired cytotoxicity", "Metadata_ldh_ridge_norm", "Metadata_mtt_ridge_norm")
        ),
        "relative_performance_documentary": all(
            token in regression_evidence for token in ("practically similar", "technical baseline", "LDH MAE")
        ),
        "replicate_effect_documentary": all(
            token in regression_evidence for token in ("0.2037579853", "1.88446103266e-14")
        ),
        "sfig2_documentary": all(
            token in paper_text + regression_notebook + well_effects_notebook + regression_evidence
            for token in ("well", "cell count", "DINO", "cluster")
        ),
        "err_480_acceptance_available": False,
        "err_304_acceptance_available": False,
        "mechanism_claim_is_hypothesis": "testable hypotheses rather than definitive mechanisms" in paper_text,
        "historical_enrichment_provenance": "304 historical" in prediction_evidence and "261 Higher" in mt_evidence,
        "method_deviation_traced": "GroupShuffleSplit" in method_evidence,
    }
    _confirm(
        all(
            bool(regression_trace[key])
            for key in (
                "compound_group_isolation",
                "table_1_documentary",
                "relative_performance_documentary",
                "replicate_effect_documentary",
                "sfig2_documentary",
                "mechanism_claim_is_hypothesis",
                "historical_enrichment_provenance",
                "method_deviation_traced",
            )
        ),
        "regression or enrichment documentary trace is missing",
    )
    return {
        "files": reports,
        "significant_classes": significant_classes,
        "regression_trace": regression_trace,
        "limitations": [
            "Tracked enrichment tables permit direct reanalysis; regression predictions and metrics are not tracked.",
            "Enrichment is an association conditional on selected exposure wells and does not establish mechanism.",
        ],
    }


def _binary_summary(frame: pd.DataFrame, label: str) -> dict[str, object]:
    _require(frame.columns[0] == "OASIS_ID", f"{label}: first column must be OASIS_ID")
    _require(not frame["OASIS_ID"].isna().any(), f"{label}: null OASIS_ID")
    _require(not frame["OASIS_ID"].duplicated().any(), f"{label}: duplicate OASIS_ID")
    values = frame.iloc[:, 1:].to_numpy(dtype=float)
    observed = np.isfinite(values)
    _require(bool(np.isin(values[observed], [0.0, 1.0]).all()), f"{label}: binary matrix has values outside 0/1/null")
    active = int(values[observed].sum())
    observed_count = int(observed.sum())
    endpoint_fractions = [
        float(frame[column].dropna().mean()) for column in frame.columns[1:] if frame[column].notna().any()
    ]
    endpoint_observed = [int(frame[column].notna().sum()) for column in frame.columns[1:]]
    return {
        "compound_rows": len(frame),
        "unique_ids": int(frame["OASIS_ID"].nunique()),
        "endpoint_count": frame.shape[1] - 1,
        "observed_values": observed_count,
        "active_values": active,
        "active_fraction": _native_float(active / observed_count),
        "median_endpoint_observed_compounds": _native_float(np.median(endpoint_observed)),
        "median_endpoint_active_fraction": _native_float(np.median(endpoint_fractions)),
    }


def _analyze_table_s5(
    root: Path, cellbased_info: pd.DataFrame, cytotox_info: pd.DataFrame, cytotox_binary: pd.DataFrame
) -> dict[str, object]:
    rows = _first_xlsx_table(root, "paper/sources/table-s5.xlsx")
    required = {"NAME", "GENE_SYMBOL", "HIT_CALL", "AC50", "INTENDED_TARGET_FAMILY", "REPR"}
    _require(bool(rows) and required <= set(rows[0]), "Table S5 is missing required columns")
    _confirm(len(rows) == 22, f"Table S5 has {len(rows)} rows; expected 22")
    _confirm(all(str(row["HIT_CALL"]) == "Active" for row in rows), "Table S5 contains a non-active row")
    _confirm(all(row["REPR"] in (True, "1", 1) for row in rows), "Table S5 contains REPR != TRUE")
    nuclear = [row for row in rows if str(row["INTENDED_TARGET_FAMILY"]) == "nuclear receptor"]
    _confirm(len(nuclear) == 12, f"Table S5 has {len(nuclear)} nuclear-receptor assays; expected 12")
    nuclear_ac50 = np.asarray([float(row["AC50"]) for row in nuclear], dtype=float)
    workbook_by_endpoint = {str(row["NAME"]): row for row in rows}
    _require(len(workbook_by_endpoint) == len(rows), "Table S5 contains duplicate endpoint names")

    compound_info = cellbased_info[cellbased_info["OASIS_ID"] == "OASIS483"].copy()
    _confirm(len(compound_info) == 87, f"OASIS483 has {len(compound_info)} pinned cell-based endpoints; expected 87")
    _require(
        not compound_info["assay_component_endpoint_name"].duplicated().any(), "OASIS483 has duplicate pinned endpoints"
    )
    info_by_endpoint = compound_info.set_index("assay_component_endpoint_name")
    retained = sorted(set(workbook_by_endpoint) & set(info_by_endpoint.index))
    retained_nuclear = sorted({str(row["NAME"]) for row in nuclear} & set(info_by_endpoint.index))
    ac50_differences = [
        abs(float(workbook_by_endpoint[endpoint]["AC50"]) - float(info_by_endpoint.at[endpoint, "ac50"]))
        for endpoint in retained
    ]
    _confirm(len(retained) == 15, f"Table S5 retains {len(retained)} pinned endpoints; expected 15")
    _confirm(
        len(retained_nuclear) == 8, f"Table S5 retains {len(retained_nuclear)} nuclear-receptor endpoints; expected 8"
    )
    _confirm(
        all(float(info_by_endpoint.at[endpoint, "hitcall"]) > 0.9 for endpoint in retained),
        "retained Table S5 endpoint has hitcall <= 0.9",
    )
    max_ac50_difference = max(ac50_differences)
    _confirm(max_ac50_difference <= 1e-6, "Table S5 and pinned endpoint AC50 values differ materially")

    cytotox_rows = cytotox_info[cytotox_info["OASIS_ID"] == "OASIS483"]
    source_tests = int(cytotox_rows["ntested"].sum())
    source_hits = int(cytotox_rows["nhit"].sum())
    _confirm(source_tests == 102 and source_hits == 0, "OASIS483 cytotoxicity source-test audit differs")
    binary_row = cytotox_binary[cytotox_binary["OASIS_ID"] == "OASIS483"]
    _confirm(len(binary_row) == 1, "OASIS483 is absent or duplicated in cytotoxicity binary matrix")
    binary_values = binary_row.iloc[0, 1:].dropna().to_numpy(dtype=float)
    _confirm(len(binary_values) == 19 and int(binary_values.sum()) == 0, "OASIS483 cytotoxicity binary audit differs")
    _confirm("TOX21_MMP_ratio" in info_by_endpoint.index, "OASIS483 MMP endpoint is absent")
    mmp = info_by_endpoint.loc["TOX21_MMP_ratio"]
    _confirm(float(mmp["hitcall"]) > 0.9, "OASIS483 MMP endpoint is not active")
    return {
        "workbook_rows": len(rows),
        "nuclear_receptor_assays": len(nuclear),
        "nuclear_receptor_ac50_min_um": _native_float(nuclear_ac50.min()),
        "nuclear_receptor_ac50_max_um": _native_float(nuclear_ac50.max()),
        "retained_endpoints": len(retained),
        "retained_nuclear_receptor_assays": len(retained_nuclear),
        "maximum_shared_ac50_difference_um": _native_float(max_ac50_difference),
        "cytotoxicity_categories": len(cytotox_rows),
        "cytotoxicity_source_tests": source_tests,
        "cytotoxicity_source_hits": source_hits,
        "cytotoxicity_binary_observed": len(binary_values),
        "cytotoxicity_binary_active": int(binary_values.sum()),
        "mmp_hitcall": _native_float(mmp["hitcall"]),
        "mmp_ac50_um": _native_float(mmp["ac50"]),
    }


def _analyze_toxcast(root: Path) -> dict[str, object]:
    binary_frames: dict[str, pd.DataFrame] = {}
    info_frames: dict[str, pd.DataFrame] = {}
    matrix_summaries: dict[str, object] = {}
    source_activity: dict[str, object] = {}
    for category in ("cellbased", "cellfree", "cytotox"):
        binary_relative = f"1_snakemake/inputs/annotations/toxcast_{category}_binary.parquet"
        info_relative = f"1_snakemake/inputs/annotations/toxcast_{category}_info.parquet"
        binary = _read_parquet(root, binary_relative)
        info = _read_parquet(root, info_relative)
        binary_frames[category] = binary
        info_frames[category] = info
        matrix_summaries[category] = _binary_summary(binary, binary_relative)
        if category == "cytotox":
            required = {"OASIS_ID", "assay_label", "ntested", "nhit", "cytotox_median_ac50"}
            _require(required <= set(info.columns), "cytotoxicity info is missing required columns")
            positive_ac50 = info.loc[info["cytotox_median_ac50"].notna(), "cytotox_median_ac50"]
            source_activity[category] = {
                "rows": len(info),
                "endpoint_count": int(info["assay_label"].nunique()),
                "rows_with_source_hits": int((info["nhit"] > 0).sum()),
                "positive_consensus_ac50_count": len(positive_ac50),
                "median_positive_ac50_um": _native_float(positive_ac50.median()),
            }
        else:
            required = {"OASIS_ID", "assay_component_endpoint_name", "hitcall", "ac50"}
            _require(required <= set(info.columns), f"{category} info is missing required columns")
            active = info["hitcall"] > 0.9
            positive_ac50 = info.loc[active & info["ac50"].notna(), "ac50"]
            source_activity[category] = {
                "rows": len(info),
                "endpoint_count": int(info["assay_component_endpoint_name"].nunique()),
                "active_rows": int(active.sum()),
                "positive_ac50_count": len(positive_ac50),
                "median_positive_ac50_um": _native_float(positive_ac50.median()),
            }

    source_endpoint_counts = {
        "cellbased": int(info_frames["cellbased"]["assay_component_endpoint_name"].nunique()),
        "cellfree": int(info_frames["cellfree"]["assay_component_endpoint_name"].nunique()),
        "cytotox": int(info_frames["cytotox"]["assay_label"].nunique()),
    }
    binary_endpoint_counts = {category: frame.shape[1] - 1 for category, frame in binary_frames.items()}
    expected_source = {"cellbased": 292, "cellfree": 72, "cytotox": 48}
    expected_binary = {"cellbased": 292, "cellfree": 72, "cytotox": 38}
    _confirm(
        source_endpoint_counts == expected_source, f"ToxCast source endpoint counts differ: {source_endpoint_counts}"
    )
    _confirm(
        binary_endpoint_counts == expected_binary, f"ToxCast binary endpoint counts differ: {binary_endpoint_counts}"
    )
    union_ids = len(set().union(*(set(frame["OASIS_ID"].astype(str)) for frame in binary_frames.values())))
    _confirm(union_ids == 963, f"ToxCast binary ID union is {union_ids}; expected 963")

    cellbased_info = info_frames["cellbased"]
    cellfree_info = info_frames["cellfree"]
    cellbased_tissue_counts = cellbased_info.groupby("tissue")["assay_component_endpoint_name"].nunique().to_dict()
    cellfree_type_counts = (
        cellfree_info.groupby("assay_function_type")["assay_component_endpoint_name"].nunique().to_dict()
    )
    cellfree_family_counts = (
        cellfree_info.groupby("intended_target_family")["assay_component_endpoint_name"].nunique().to_dict()
    )
    composition = {
        "cellbased_tissues": {name: int(cellbased_tissue_counts[name]) for name in ("liver", "vascular", "kidney")},
        "cellfree_assay_types": {name: int(cellfree_type_counts[name]) for name in ("binding", "enzymatic activity")},
        "cellfree_target_families": {
            name: int(cellfree_family_counts[name]) for name in ("gpcr", "cyp", "nuclear receptor")
        },
    }
    expected_composition = {
        "cellbased_tissues": {"liver": 151, "vascular": 63, "kidney": 35},
        "cellfree_assay_types": {"binding": 37, "enzymatic activity": 35},
        "cellfree_target_families": {"gpcr": 21, "cyp": 11, "nuclear receptor": 10},
    }
    _confirm(composition == expected_composition, f"ToxCast endpoint composition differs: {composition}")

    endpoint_medians = {
        "observed_compounds": {
            category: int(matrix_summaries[category]["median_endpoint_observed_compounds"])
            for category in ("cytotox", "cellbased", "cellfree")
        },
        "active_fraction": {
            category: matrix_summaries[category]["median_endpoint_active_fraction"]
            for category in ("cytotox", "cellbased", "cellfree")
        },
    }
    _confirm(
        endpoint_medians["observed_compounds"] == {"cytotox": 346, "cellbased": 306, "cellfree": 33},
        "ToxCast median endpoint coverage differs",
    )
    expected_fractions = {
        "cytotox": 0.20683488012374324,
        "cellbased": 0.071161355334425,
        "cellfree": 0.4134295227524972,
    }
    _confirm(
        all(
            abs(float(endpoint_medians["active_fraction"][category]) - expected) <= 1e-12
            for category, expected in expected_fractions.items()
        ),
        "ToxCast median endpoint activity fractions differ",
    )

    cytotox_binary = binary_frames["cytotox"]
    heatmap_columns = [
        column for column in cytotox_binary.columns[1:] if int(cytotox_binary[column].notna().sum()) > 800
    ]
    heatmap_summary = {
        "cell_categories": sum(column.startswith("cell_type__") for column in heatmap_columns),
        "tissue_categories": sum(column.startswith("tissue__") for column in heatmap_columns),
        "complete_compounds": int(cytotox_binary[heatmap_columns].notna().all(axis=1).sum()),
    }
    _confirm(
        heatmap_summary == {"cell_categories": 12, "tissue_categories": 6, "complete_compounds": 839},
        f"ToxCast heatmap substrate differs: {heatmap_summary}",
    )

    paper_text = _input_path(root, "paper/paper.md").read_text(encoding="utf-8")
    toxcast_notebook = _input_path(
        root, "2_downstream_analysis/manuscript_notebooks/3_1_toxcast_endpoints.ipynb"
    ).read_text(encoding="utf-8")
    toxcast_evidence = _input_path(root, "paper/evidence/toxcast-curation-and-figure-s3.md").read_text(encoding="utf-8")
    documented_tested_intersection = {
        "ids": 670,
        "percent_of_published_library": _native_float(100 * 670 / 1_085),
        "documented_in_tracked_evidence": all(
            token in toxcast_evidence
            for token in ("Only 670 tested OASIS IDs", "`670 / 1,085 = 61.751152%`", "not 89%")
        ),
    }
    annotation_union_not_tested_library_join = all(
        token in toxcast_evidence
        for token in (
            "does not intersect that 963-ID union with the tested-compound metadata",
            "not a tested-library intersection",
        )
    )
    _confirm(
        bool(documented_tested_intersection["documented_in_tracked_evidence"])
        and annotation_union_not_tested_library_join,
        "ToxCast annotation-union and tested-library-intersection trace is incomplete",
    )
    method_trace = {
        "hitcall_strictly_above_0_9": "hitcall > 0.9" in toxcast_evidence,
        "cytotoxicity_consensus_20_percent": "nhit / ntested >= 0.2" in toxcast_evidence,
        "median_positive_ac50": "median AC50" in paper_text and "median AC50" in toxcast_evidence,
        "minimum_five_positive_and_negative": "fewer than five positive and negative" in paper_text
        and "minimum 5 positive" in toxcast_evidence,
        "notebook_reads_pinned_parquets": "toxcast_cellbased" in toxcast_notebook
        and "toxcast_cellfree" in toxcast_notebook,
        "specific_endpoint_100_um_deviation_traced": "100 uM rule" in toxcast_evidence,
    }
    _confirm(all(method_trace.values()), "ToxCast method trace is incomplete")
    table_s5 = _analyze_table_s5(root, info_frames["cellbased"], info_frames["cytotox"], binary_frames["cytotox"])
    return {
        "source_endpoint_counts": source_endpoint_counts,
        "binary_endpoint_counts": binary_endpoint_counts,
        "union_ids": union_ids,
        "union_fraction_of_published_library": _native_float(union_ids / 1_085),
        "documented_tested_intersection": documented_tested_intersection,
        "annotation_union_not_tested_library_join": annotation_union_not_tested_library_join,
        "binary_activity": matrix_summaries,
        "source_activity": source_activity,
        "composition": composition,
        "endpoint_medians": endpoint_medians,
        "heatmap_summary": heatmap_summary,
        "method_trace": method_trace,
        "table_s5": table_s5,
    }


def _effect_summary(reference: pd.Series, comparison: pd.Series, contrast: str) -> dict[str, object]:
    matched = pd.concat([reference.rename("reference"), comparison.rename("comparison")], axis=1, join="inner").dropna()
    _require(not matched.empty, f"classifier contrast has no matched endpoints: {contrast}")
    difference = matched["comparison"] - matched["reference"]
    test = ttest_rel(matched["comparison"], matched["reference"])
    return {
        "contrast": contrast,
        "matched_endpoints": len(matched),
        "mean_difference": _native_float(difference.mean()),
        "median_difference": _native_float(difference.median()),
        "paired_t_statistic": None if not np.isfinite(test.statistic) else _native_float(test.statistic),
        "paired_t_p_value": None if not np.isfinite(test.pvalue) else _native_float(test.pvalue),
    }


def _classifier_subset(frame: pd.DataFrame, category: str) -> pd.DataFrame:
    if category == "axiom":
        return frame[frame["Metadata_Label"] != "cell_count"]
    return frame


def _analyze_classifier(root: Path) -> dict[str, object]:
    category_files = {
        "axiom": "compiled_axiom_metrics.parquet",
        "toxcast_cytotox": "compiled_toxcast_cytotox_metrics.parquet",
        "toxcast_cellbased": "compiled_toxcast_cellbased_metrics.parquet",
        "toxcast_cellfree": "compiled_toxcast_cellfree_metrics.parquet",
    }
    frames: dict[str, pd.DataFrame] = {}
    file_rows: dict[str, int] = {}
    modeled_endpoint_counts: dict[str, int] = {}
    for category, filename in category_files.items():
        relative = f"2_downstream_analysis/compiled_results/{filename}"
        frame = _read_parquet(root, relative)
        _validate_columns(frame, METRIC_COLUMNS, relative)
        keys = _semantic_key(frame, METRIC_KEY)
        _require(len(keys) == len(set(keys)), f"{filename}: duplicate metric semantic key")
        _confirm(len(frame) == EXPECTED_METRIC_ROWS[filename], f"{filename}: row count is {len(frame)}")
        _require(
            set(frame["Metadata_AggType"]) == set(EXPECTED_AGG_TYPES),
            f"{filename}: invalid aggregation-type domain",
        )
        _require(
            set(frame["Model_type"]) == {"Actual", "Random_baseline", "Cellcount_baseline"},
            f"{filename}: invalid model domain",
        )
        _require(set(frame["Feat_type"]) == {"cellprofiler", "cpcnn", "dino"}, f"{filename}: invalid feature domain")
        for metric in ("AUROC", "PRAUC"):
            values = pd.to_numeric(frame[metric], errors="coerce").to_numpy(dtype=float)
            _require(
                bool(np.isfinite(values).all() and ((values >= 0) & (values <= 1)).all()),
                f"{filename}: invalid {metric}",
            )
        for column in ("Metadata_Count_0", "Metadata_Count_1"):
            values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
            _require(
                bool(np.isfinite(values).all() and (values > 0).all() and np.equal(values, np.floor(values)).all()),
                f"{filename}: invalid {column}",
            )
        frames[category] = frame
        file_rows[filename] = len(frame)
        modeled = frame[
            (frame["Metadata_AggType"] == "all")
            & (frame["Model_type"] == "Actual")
            & (frame["Feat_type"] == "cellprofiler")
        ]
        modeled = _classifier_subset(modeled, category)
        modeled_endpoint_counts[category] = int(modeled["Metadata_Label"].nunique())
    expected_modeled = {"axiom": 2, "toxcast_cytotox": 34, "toxcast_cellbased": 267, "toxcast_cellfree": 53}
    _confirm(modeled_endpoint_counts == expected_modeled, f"modeled endpoint counts differ: {modeled_endpoint_counts}")

    table2_rows: list[dict[str, object]] = []
    axiom = frames["axiom"]
    table_models = (
        ("Cell count", "Cellcount_baseline", "cellprofiler"),
        ("Random", "Random_baseline", "cellprofiler"),
        ("CellProfiler", "Actual", "cellprofiler"),
        ("CP-CNN", "Actual", "cpcnn"),
        ("DINO", "Actual", "dino"),
    )
    for endpoint in ("LDH", "MTT"):
        for display, model_type, feature_type in table_models:
            selected = axiom[
                (axiom["Metadata_AggType"] == "all")
                & (axiom["Metadata_Label"] == endpoint)
                & (axiom["Model_type"] == model_type)
                & (axiom["Feat_type"] == feature_type)
            ]
            _require(len(selected) == 1, f"Table 2 key is absent or duplicated: {endpoint}/{display}")
            row = selected.iloc[0]
            table2_rows.append(
                {
                    "endpoint": endpoint,
                    "row": display,
                    "auroc": _native_float(row["AUROC"]),
                    "prauc": _native_float(row["PRAUC"]),
                    "count_0": int(row["Metadata_Count_0"]),
                    "count_1": int(row["Metadata_Count_1"]),
                }
            )

    ldh_table_rows = [row for row in table2_rows if row["endpoint"] == "LDH"]
    ldh_morphology_rows = [row for row in ldh_table_rows if row["row"] in {"CellProfiler", "CP-CNN", "DINO"}]
    ldh_baseline_rows = [row for row in ldh_table_rows if row["row"] in {"Cell count", "Random"}]
    classifier_001 = {
        "endpoint": "LDH",
        "morphology_mean_auroc": _native_float(np.mean([row["auroc"] for row in ldh_morphology_rows])),
        "morphology_mean_prauc": _native_float(np.mean([row["prauc"] for row in ldh_morphology_rows])),
        "all_representations_above_both_baselines": all(
            morphology[metric] > baseline[metric]
            for morphology in ldh_morphology_rows
            for baseline in ldh_baseline_rows
            for metric in ("auroc", "prauc")
        ),
    }
    _confirm(
        abs(float(classifier_001["morphology_mean_auroc"]) - 0.932625) <= 5e-7
        and abs(float(classifier_001["morphology_mean_prauc"]) - 0.753212) <= 5e-7
        and bool(classifier_001["all_representations_above_both_baselines"]),
        f"LDH classifier target summary differs: {classifier_001}",
    )

    baseline_effects: dict[str, object] = {}
    strategy_effects: dict[str, object] = {}
    filter_effects: dict[str, object] = {}
    representation_effects: dict[str, object] = {}
    distributions: dict[str, object] = {}
    for category, frame in frames.items():
        baseline_effects[category] = {}
        strategy_effects[category] = {}
        filter_effects[category] = {}
        representation_effects[category] = {}
        distributions[category] = {}
        base = frame[(frame["Metadata_AggType"] == "all") & (frame["Feat_type"] == "cellprofiler")]
        base = _classifier_subset(base, category)
        for metric in ("AUROC", "PRAUC"):
            metric_key = metric.lower()
            baseline_effects[category][metric_key] = {}
            actual = base[base["Model_type"] == "Actual"].set_index("Metadata_Label")[metric]
            for report_key, model_type in (("random", "Random_baseline"), ("cell_count", "Cellcount_baseline")):
                baseline = base[base["Model_type"] == model_type].set_index("Metadata_Label")[metric]
                baseline_effects[category][metric_key][report_key] = _effect_summary(
                    baseline,
                    actual,
                    f"Actual - {model_type}",
                )

            strategy_effects[category][metric_key] = {}
            strategies = frame[(frame["Model_type"] == "Actual") & (frame["Feat_type"] == "cellprofiler")]
            strategies = _classifier_subset(strategies, category)
            strategy_pivot = strategies.pivot(index="Metadata_Label", columns="Metadata_AggType", values=metric)
            for alternative in ("allpod", "allpodcc"):
                strategy_effects[category][metric_key][alternative] = _effect_summary(
                    strategy_pivot["all"],
                    strategy_pivot[alternative],
                    f"{alternative} - all",
                )
            filter_effects[category][metric_key] = _effect_summary(
                strategy_pivot["allpod"],
                strategy_pivot["allpodcc"],
                "allpodcc - allpod",
            )

            representation_effects[category][metric_key] = {}
            representations = frame[(frame["Model_type"] == "Actual") & (frame["Metadata_AggType"] == "all")]
            representations = _classifier_subset(representations, category)
            representation_pivot = representations.pivot(index="Metadata_Label", columns="Feat_type", values=metric)
            for alternative in ("cpcnn", "dino"):
                representation_effects[category][metric_key][alternative] = _effect_summary(
                    representation_pivot["cellprofiler"],
                    representation_pivot[alternative],
                    f"{alternative} - cellprofiler",
                )
            representation_effects[category][metric_key]["dino_vs_cpcnn"] = _effect_summary(
                representation_pivot["cpcnn"],
                representation_pivot["dino"],
                "dino - cpcnn",
            )

        actual_all = frame[(frame["Metadata_AggType"] == "all") & (frame["Model_type"] == "Actual")]
        actual_all = _classifier_subset(actual_all, category)
        for representation in ("cellprofiler", "cpcnn", "dino"):
            representation_rows = actual_all[actual_all["Feat_type"] == representation]
            distributions[category][representation] = {}
            for metric in ("AUROC", "PRAUC"):
                values = representation_rows[metric].astype(float)
                distributions[category][representation][metric.lower()] = {
                    "count": len(values),
                    "minimum": _native_float(values.min()),
                    "first_quartile": _native_float(values.quantile(0.25)),
                    "median": _native_float(values.median()),
                    "third_quartile": _native_float(values.quantile(0.75)),
                    "maximum": _native_float(values.max()),
                }
    classifier_text = _input_path(root, "1_snakemake/classifier/classify.py").read_text(encoding="utf-8")
    aggregate_text = _input_path(root, "1_snakemake/classifier/aggregate_profiles.py").read_text(encoding="utf-8")
    hitcall_text = _input_path(root, "1_snakemake/classifier/hitcalls.py").read_text(encoding="utf-8")
    rules_text = _input_path(root, "1_snakemake/rules/classifier.smk").read_text(encoding="utf-8")
    method_trace = {
        "folds": 5,
        "stratified": "StratifiedKFold(n_splits=n_splits)" in classifier_text,
        "model": "XGBClassifier" if "XGBClassifier" in classifier_text else "unresolved",
        "compound_level_label_join": 'rename({"OASIS_ID": "Metadata_OASIS_ID"})' in classifier_text,
        "published_baselines": all(
            token in classifier_text for token in ("Random_baseline", "Cellcount_baseline", "shuffle=True", "cc=True")
        ),
        "consensus_strategies": all(
            token in aggregate_text for token in ('method == "all"', 'method == "allpod"', 'method == "allpodcc"')
        ),
        "paired_assay_hitcalls": all(token in hitcall_text for token in ("mtt_hits", "ldh_hits", "cc_hits")),
        "workflow_wiring": all(
            token in rules_text
            for token in ("toxcast_cellbased_binary", "toxcast_cellfree_binary", "toxcast_cytotox_binary")
        ),
    }
    _confirm(
        bool(method_trace["stratified"]) and method_trace["model"] == "XGBClassifier", "classifier method trace differs"
    )

    all_cellprofiler_medians = {
        category: {metric: distributions[category]["cellprofiler"][metric]["median"] for metric in ("auroc", "prauc")}
        for category in category_files
    }
    expected_medians = {
        "axiom": {"auroc": 0.901547, "prauc": 0.805566},
        "toxcast_cytotox": {"auroc": 0.737210, "prauc": 0.477455},
        "toxcast_cellbased": {"auroc": 0.607226, "prauc": 0.144840},
        "toxcast_cellfree": {"auroc": 0.532086, "prauc": 0.454015},
    }
    _confirm(
        all(
            abs(float(all_cellprofiler_medians[category][metric]) - expected) <= 5e-7
            for category, metrics in expected_medians.items()
            for metric, expected in metrics.items()
        ),
        f"all-concentration classifier medians differ: {all_cellprofiler_medians}",
    )

    target_effects = {
        "dino_vs_cpcnn_cellbased_auroc": {
            key: representation_effects["toxcast_cellbased"]["auroc"]["dino_vs_cpcnn"][key]
            for key in ("mean_difference", "median_difference")
        },
        "dino_vs_cellprofiler_cellbased_auroc": {
            key: representation_effects["toxcast_cellbased"]["auroc"]["dino"][key]
            for key in ("mean_difference", "median_difference")
        },
    }
    _confirm(
        abs(float(target_effects["dino_vs_cpcnn_cellbased_auroc"]["mean_difference"]) - 0.01079046) <= 5e-8
        and abs(float(target_effects["dino_vs_cpcnn_cellbased_auroc"]["median_difference"]) - 0.01587302) <= 5e-8
        and abs(float(target_effects["dino_vs_cellprofiler_cellbased_auroc"]["median_difference"]) - 0.02209021)
        <= 5e-8,
        f"classifier representation target effects differ: {target_effects}",
    )

    axiom_above_baselines = all(
        baseline_effects["axiom"][metric][baseline]["mean_difference"] > 0
        for metric in ("auroc", "prauc")
        for baseline in ("random", "cell_count")
    )
    cellbased_not_cellfree = all(
        baseline_effects[category][metric][baseline]["mean_difference"] > 0
        for category in ("axiom", "toxcast_cytotox", "toxcast_cellbased")
        for metric in ("auroc", "prauc")
        for baseline in ("random", "cell_count")
    ) and all(
        abs(baseline_effects["toxcast_cellfree"][metric]["random"]["mean_difference"]) < 0.1
        for metric in ("auroc", "prauc")
    )
    allpod_small_effects = all(
        abs(strategy_effects[category][metric]["allpod"]["mean_difference"]) < 0.1
        for category in category_files
        for metric in ("auroc", "prauc")
    )
    allpodcc_filter_direction = all(
        filter_effects[category][metric]["mean_difference"] < 0
        for category in ("axiom", "toxcast_cytotox")
        for metric in ("auroc", "prauc")
    ) and all(
        abs(filter_effects[category][metric]["mean_difference"]) < 0.02
        for category in ("toxcast_cellbased", "toxcast_cellfree")
        for metric in ("auroc", "prauc")
    )
    representation_small_effects = all(
        abs(representation_effects[category][metric][representation]["mean_difference"]) < 0.1
        for category in category_files
        for metric in ("auroc", "prauc")
        for representation in ("cpcnn", "dino", "dino_vs_cpcnn")
    )
    all_concentration_not_worse = all(
        strategy_effects[category][metric][alternative]["mean_difference"] < 0.1
        for category in category_files
        for metric in ("auroc", "prauc")
        for alternative in ("allpod", "allpodcc")
    )
    prauc_no_material_improvement = all(
        strategy_effects[category]["prauc"][alternative]["mean_difference"] < 0.1
        for category in category_files
        for alternative in ("allpod", "allpodcc")
    ) and all(
        representation_effects[category]["prauc"][representation]["mean_difference"] < 0.1
        for category in category_files
        for representation in ("cpcnn", "dino", "dino_vs_cpcnn")
    )
    conclusion_gates = {
        "table2": len(table2_rows) == 10 and axiom_above_baselines,
        "axiom_above_baselines": axiom_above_baselines,
        "cellbased_not_cellfree": cellbased_not_cellfree,
        "allpod_small_effects": allpod_small_effects,
        "allpodcc_filter_direction": allpodcc_filter_direction,
        "all_concentration_not_worse": all_concentration_not_worse,
        "representation_small_effects": representation_small_effects,
        "prauc_no_material_improvement": prauc_no_material_improvement,
        "conclusion_003": allpod_small_effects
        and allpodcc_filter_direction
        and representation_small_effects
        and all_concentration_not_worse,
    }
    _confirm(all(conclusion_gates.values()), f"classifier conclusion inequality failed: {conclusion_gates}")
    return {
        "file_rows": file_rows,
        "modeled_endpoint_counts": modeled_endpoint_counts,
        "table2": {"rows": table2_rows},
        "classifier_001": classifier_001,
        "baseline_effects": baseline_effects,
        "strategy_effects": strategy_effects,
        "filter_effects": filter_effects,
        "representation_effects": representation_effects,
        "distributions": distributions,
        "all_cellprofiler_medians": all_cellprofiler_medians,
        "target_effects": target_effects,
        "method_trace": method_trace,
        "raw_prediction_recomputation": False,
        "conclusion_gates": conclusion_gates,
    }


def _analyze_external_image(root: Path) -> dict[str, object]:
    image = _input_path(root, "paper/figures/figure-s1.jpg").read_bytes()
    _require(
        image.startswith(b"\xff\xd8") and image.endswith(b"\xff\xd9"),
        "paper/figures/figure-s1.jpg is not a complete JPEG",
    )
    paper_text = _input_path(root, "paper/paper.md").read_text(encoding="utf-8")
    identity_trace = all(token in paper_text for token in ("41002889", "L12", "site = 6", "191,754"))
    _confirm(identity_trace, "Figure S1 identity or inventory trace is incomplete")
    evidence_text = _input_path(root, "paper/evidence/figure-s1.md").read_text(encoding="utf-8")
    producer_text = _input_path(root, "paper/render_sfig1.py").read_text(encoding="utf-8")
    external_reproduction_documented = all(
        token in evidence_text
        for token in (
            "318,828",
            "72,519",
            "undocumented nine-site selection rule",
            "reproduced-with-deviation",
        )
    ) and all(token in producer_text for token in ("TARGET_PLATE", "TARGET_WELL", "TARGET_SITE", "CHANNELS"))
    _confirm(external_reproduction_documented, "Figure S1 external reproduction evidence is incomplete")
    return {
        "navigation_image_sha256": hashlib.sha256(image).hexdigest(),
        "navigation_image_bytes": len(image),
        "identity_trace": identity_trace,
        "external_reproduction_documented": external_reproduction_documented,
        "source_image_available": False,
        "limitation": (
            "The raw source TIFF and image index are absent from the tracked audit, but the external producer and "
            "measured inventory-count deviation are documented."
        ),
    }


CheckGetter = Callable[[Mapping[str, Any]], object]
CheckPredicate = Callable[[object, object], bool]
CheckRule = tuple[str, CheckGetter, object, CheckPredicate | None]


def _path_getter(*path: str) -> CheckGetter:
    def get(analyses: Mapping[str, Any]) -> object:
        value: object = analyses
        for part in path:
            if not isinstance(value, Mapping) or part not in value:
                raise InputValidationError(f"analysis field is absent: {'.'.join(path)}")
            value = value[part]
        return value

    return get


def _rule(name: str, path: tuple[str, ...], expected: object, predicate: CheckPredicate | None = None) -> CheckRule:
    return (name, _path_getter(*path), expected, predicate)


def _computed_rule(
    name: str, getter: CheckGetter, expected: object, predicate: CheckPredicate | None = None
) -> CheckRule:
    return (name, getter, expected, predicate)


def _target_builder(*rules: CheckRule) -> Callable[[Mapping[str, Any]], list[dict[str, object]]]:
    def build(analyses: Mapping[str, Any]) -> list[dict[str, object]]:
        checks: list[dict[str, object]] = []
        for name, getter, expected, predicate in rules:
            observed = getter(analyses)
            checks.append(
                _check(
                    name,
                    observed,
                    expected,
                    passed=None if predicate is None else predicate(observed, expected),
                )
            )
        return checks

    return build


def _all_true(value: object, _expected: object) -> bool:
    return isinstance(value, Mapping) and all(bool(item) for item in value.values())


def _less_than(value: object, expected: object) -> bool:
    return float(value) < float(expected)


def _within(value: object, expected: object) -> bool:
    observed, tolerance = value if isinstance(value, tuple) else (value, 0.0)
    return abs(float(observed) - float(expected)) <= float(tolerance)


S1_RECIPE_INPUTS = (
    "paper/sources/table-s1.xlsx",
    "1_snakemake/inputs/annotations/v5_oasis_03Sept2024_simple.csv",
)
ACTIVITY_RECIPE_INPUTS = (
    "paper/sources/table-s2.xlsx",
    "paper/sources/table-s3.xlsx",
    "paper/sources/table-s4.xlsx",
    "2_downstream_analysis/compiled_results/SI_tables/mt_pods.csv",
    "2_downstream_analysis/compiled_results/SI_tables/cellcount_pods.csv",
    "2_downstream_analysis/compiled_results/SI_tables/ldh_pods.csv",
    "2_downstream_analysis/compiled_results/SI_tables/cellpainting_cellprofiler_pods.csv",
    "2_downstream_analysis/compiled_results/SI_tables/cellpainting_cpcnn_pods.csv",
    "2_downstream_analysis/compiled_results/SI_tables/cellpainting_dino_pods.csv",
    "2_downstream_analysis/compiled_results/SI_tables/hit_summary.csv",
)
ENRICHMENT_RECIPE_INPUTS = tuple(path for path in COMPILED_INPUTS if path.endswith("_targets.csv"))
TOXCAST_RECIPE_INPUTS = tuple(path for path in ANNOTATION_INPUTS if "/toxcast_" in path)
CLASSIFIER_RECIPE_INPUTS = tuple(
    path for path in COMPILED_INPUTS if "/compiled_" in path and path.endswith("_metrics.parquet")
)


# Each ledger ID has one concrete recipe.  The check builders below are
# target-scoped even where several targets consume the same validated analysis.
TARGET_RECIPES: dict[str, TargetRecipe] = {
    "DESIGN-001": TargetRecipe(
        "sources_design",
        "documentary-trace",
        "documentary-only",
        ("paper/paper.md", "paper/evidence/experimental-design-and-figure-1.md"),
        _target_builder(
            _rule(
                "published compound, dose, and replicate design",
                ("sources_design", "documentary_trace", "experimental_design"),
                True,
            )
        ),
    ),
    "DESIGN-002": TargetRecipe(
        "sources_design",
        "documentary-trace",
        "documentary-only",
        ("paper/paper.md", "paper/evidence/experimental-design-and-figure-1.md"),
        _target_builder(
            _rule(
                "published representation feature counts",
                ("sources_design", "documentary_trace", "feature_count_claims"),
                True,
            )
        ),
    ),
    "DESIGN-003": TargetRecipe(
        "sources_design",
        "documentary-trace",
        "documentary-only",
        ("paper/paper.md", "paper/evidence/experimental-design-and-figure-1.md"),
        _target_builder(
            _rule(
                "published assay and exposure constants",
                ("sources_design", "documentary_trace", "assay_and_exposure_design"),
                True,
            )
        ),
    ),
    "FIG-1": TargetRecipe(
        "sources_design",
        "documentary-trace",
        "documentary-only",
        ("paper/figures/figure-1.jpg", "paper/evidence/experimental-design-and-figure-1.md"),
        _target_builder(
            _rule(
                "Figure 1 workflow stages and outcomes",
                ("sources_design", "documentary_trace", "figure_1_workflow"),
                True,
            )
        ),
    ),
    "TABLE-S1": TargetRecipe(
        "sources_design",
        "source-recomputation",
        "available",
        S1_RECIPE_INPUTS,
        _target_builder(
            _rule("Table S1 rows", ("sources_design", "table_s1", "rows"), 1085),
            _rule("Table S1 stable IDs", ("sources_design", "table_s1", "stable_id_count"), 966),
            _rule("Table S1 blank IDs", ("sources_design", "table_s1", "blank_id_count"), 119),
        ),
    ),
    "TABLE-KEY-RESOURCES": TargetRecipe(
        "sources_design",
        "documentary-trace",
        "documentary-only",
        ("paper/paper.md", "paper/sources/main.pdf"),
        _target_builder(
            _rule(
                "Key Resources transcription trace",
                ("sources_design", "documentary_trace", "table_key_resources"),
                True,
            ),
            _rule("Key Resources Markdown data rows", ("sources_design", "key_resources_data_rows"), 34),
        ),
    ),
    "METHOD-STATS": TargetRecipe(
        "sources_design",
        "documentary-trace",
        "documentary-only",
        ("paper/paper.md",),
        _target_builder(
            _rule(
                "statistical thresholds and sample design trace",
                ("sources_design", "documentary_trace", "statistical_thresholds"),
                True,
            )
        ),
    ),
    "RESOURCE-001": TargetRecipe(
        "sources_design",
        "documentary-trace",
        "documentary-only",
        ("README.md", "paper/paper.md", "paper/evidence/remaining-paper-reproduction-targets.md"),
        _target_builder(
            _rule(
                "published data and code locations", ("sources_design", "documentary_trace", "resource_locations"), True
            ),
            _rule(
                "tracked-only resource boundary", ("sources_design", "documentary_trace", "tracked_only_boundary"), True
            ),
        ),
    ),
    "ACTIVITY-001": TargetRecipe(
        "activity_pods",
        "source-recomputation",
        "available",
        ("paper/sources/table-s2.xlsx", *ACTIVITY_RECIPE_INPUTS[3:6]),
        _target_builder(
            _rule(
                "published Table S2 activity counts",
                ("activity_pods", "table_s2_counts"),
                {"MT": 429, "Cell count": 220, "LDH": 147, "unique_compounds": 437},
            )
        ),
    ),
    "ACTIVITY-002": TargetRecipe(
        "activity_pods",
        "documentary-trace",
        "documentary-only",
        (
            "2_downstream_analysis/compiled_results/SI_tables/hit_summary.csv",
            "paper/evidence/activity-and-figure-2a.md",
        ),
        _target_builder(
            _rule(
                "direction-aware cytotoxic compound count",
                ("activity_pods", "direction_aware_cytotoxicity", "count"),
                429,
            ),
            _rule(
                "direction-aware definition trace",
                ("activity_pods", "direction_aware_cytotoxicity", "documented_in_tracked_evidence"),
                True,
            ),
        ),
    ),
    "ACTIVITY-003": TargetRecipe(
        "activity_pods",
        "documentary-trace",
        "documentary-only",
        ("paper/evidence/activity-and-figure-2a.md", "2_downstream_analysis/compiled_results/SI_tables/mt_pods.csv"),
        _target_builder(
            _rule(
                "camera-ready increasing-MT call count",
                ("activity_pods", "direction_aware_cytotoxicity", "mt_increasing_count"),
                10,
            ),
            _rule(
                "increasing-MT count documentary trace",
                ("activity_pods", "direction_aware_cytotoxicity", "mt_increasing_count_documented"),
                True,
            ),
            _rule(
                "four dominant increasing-MT compounds",
                ("activity_pods", "figure_2a", "compound_names"),
                ["Benzarone", "Tiratricol", "Tolcapone", "2-Ethylanthracene-9,10-dione"],
            ),
            _rule("increasing-MT direction", ("activity_pods", "figure_2a", "direction"), "increasing MT"),
        ),
    ),
    "FIG-2A": TargetRecipe(
        "activity_pods",
        "source-recomputation",
        "available",
        (
            "paper/sources/table-s2.xlsx",
            "2_downstream_analysis/compiled_results/SI_tables/mt_pods.csv",
            "paper/evidence/activity-and-figure-2a.md",
        ),
        _target_builder(
            _rule(
                "Figure 2A four published compounds",
                ("activity_pods", "figure_2a", "compound_names"),
                ["Benzarone", "Tiratricol", "Tolcapone", "2-Ethylanthracene-9,10-dione"],
            ),
            _computed_rule(
                "Figure 2A Table S2 POD agreement",
                lambda a: max(
                    abs(row["pod_um"] - row["expected_published_pod_um"])
                    for row in a["activity_pods"]["figure_2a"]["rows"]
                ),
                1e-6,
                lambda observed, expected: float(observed) <= float(expected),
            ),
        ),
    ),
    "BIOACTIVITY-001": TargetRecipe(
        "activity_pods",
        "source-recomputation",
        "available",
        ("paper/sources/table-s3.xlsx", *ACTIVITY_RECIPE_INPUTS[6:9], "paper/evidence/bioactivity-and-figure-2b-d.md"),
        _target_builder(
            _computed_rule(
                "all published-SI morphology count estimands",
                lambda a: {
                    representation: {
                        mode: a["activity_pods"]["morphology_activity_summary"][representation][mode]["count"]
                        for mode in ("global", "categorical", "general")
                    }
                    for representation in ("cellprofiler", "cpcnn", "dino")
                },
                {
                    "cellprofiler": {"global": 169, "categorical": 598, "general": 607},
                    "cpcnn": {"global": 539, "categorical": 0, "general": 539},
                    "dino": {"global": 545, "categorical": 626, "general": 644},
                },
            ),
            _computed_rule(
                "CellProfiler-global published-SI fraction",
                lambda a: (
                    a["activity_pods"]["morphology_activity_summary"]["cellprofiler"]["global"]["fraction_of_1085"],
                    5e-4,
                ),
                0.156,
                _within,
            ),
            _rule(
                "CellProfiler general published-SI count",
                ("activity_pods", "morphology_activity_summary", "cellprofiler", "general", "count"),
                607,
            ),
            _computed_rule(
                "published-SI general morphology ordering over cytotoxic assays",
                lambda a: (
                    min(
                        a["activity_pods"]["morphology_activity_summary"][name]["general"]["count"]
                        for name in ("cellprofiler", "cpcnn", "dino")
                    )
                    > a["activity_pods"]["table_s2_counts"]["MT"]
                ),
                True,
            ),
        ),
    ),
    "FIG-2B": TargetRecipe(
        "activity_pods",
        "source-recomputation",
        "available",
        ("paper/sources/table-s3.xlsx", *ACTIVITY_RECIPE_INPUTS[6:9]),
        _target_builder(
            _rule(
                "CellProfiler general active compounds",
                ("activity_pods", "morphology_counts", "cellprofiler", "general", "count"),
                607,
            ),
            _rule(
                "DINO general active compounds", ("activity_pods", "morphology_counts", "dino", "general", "count"), 644
            ),
        ),
    ),
    "BIOACTIVITY-002": TargetRecipe(
        "activity_pods",
        "source-recomputation",
        "blocked",
        ("paper/sources/table-s3.xlsx", *ACTIVITY_RECIPE_INPUTS[6:9], "paper/evidence/bioactivity-and-figure-2b-d.md"),
        _target_builder(
            _rule("three-general shared compounds", ("activity_pods", "figure_2c_three_general", "count"), 488),
            _computed_rule(
                "CP-CNN over CellProfiler general POD ratio",
                lambda a: (
                    a["activity_pods"]["figure_2c_three_general"]["geometric_fold_ratios"]["cpcnn_over_cellprofiler"],
                    5e-5,
                ),
                1.8181,
                _within,
            ),
            _computed_rule(
                "CellProfiler-DINO null conclusion is substrate-dependent",
                lambda a: a["activity_pods"]["figure_2c_three_general"]["cellprofiler_vs_dino_paired_log10"][
                    "paired_t_p_value"
                ],
                0.05,
                lambda observed, expected: float(observed) > float(expected),
            ),
        ),
    ),
    "FIG-2C": TargetRecipe(
        "activity_pods",
        "source-recomputation",
        "available",
        ("paper/sources/table-s3.xlsx", *ACTIVITY_RECIPE_INPUTS[6:9], "paper/evidence/bioactivity-and-figure-2b-d.md"),
        _target_builder(
            _rule(
                "camera-ready five-series count trace",
                ("activity_pods", "figure_2c_complete_case", "camera_ready_count_trace"),
                342,
            ),
            _rule(
                "published-SI five-series complete cases", ("activity_pods", "figure_2c_complete_case", "count"), 156
            ),
            _rule(
                "published-SI count deviation from camera-ready",
                ("activity_pods", "figure_2c_complete_case", "source_si_count_deviation"),
                186,
            ),
            _rule(
                "five-series median ordering preserved",
                ("activity_pods", "figure_2c_complete_case", "ordering_preserved"),
                True,
            ),
            _computed_rule(
                "tracked-SI five-series finite POD summaries and median order",
                lambda a: {
                    "series_count": len(a["activity_pods"]["figure_2c_complete_case"]["median_pod_um"]),
                    "finite_nonempty": a["activity_pods"]["figure_2c_complete_case"]["finite_nonempty_pod_summaries"],
                    "median_order": a["activity_pods"]["figure_2c_complete_case"]["median_order"],
                },
                {
                    "series_count": 5,
                    "finite_nonempty": True,
                    "median_order": [
                        "cellprofiler_categorical",
                        "dino_categorical",
                        "dino_global",
                        "cpcnn_global",
                        "cellprofiler_global",
                    ],
                },
            ),
        ),
    ),
    "BIOACTIVITY-003": TargetRecipe(
        "activity_pods",
        "source-recomputation",
        "available",
        ACTIVITY_RECIPE_INPUTS,
        _target_builder(
            _computed_rule(
                "assay median sensitivity ordering",
                lambda a: list(a["activity_pods"]["figure_2d"]["median_pod_um"].values()),
                "Morphology < MT < cell count < LDH",
                lambda values, _expected: values[0] < values[1] < values[2] < values[3],
            ),
            _rule("published-SI complete cases", ("activity_pods", "figure_2d", "complete_case_count"), 121),
        ),
    ),
    "FIG-2D": TargetRecipe(
        "activity_pods",
        "source-recomputation",
        "available",
        ACTIVITY_RECIPE_INPUTS,
        _target_builder(
            _rule("published-SI four-assay complete cases", ("activity_pods", "figure_2d", "complete_case_count"), 121),
            _rule(
                "MT fold ratio versus morphology",
                ("activity_pods", "figure_2d", "geometric_fold_ratio_vs_morphology", "mt"),
                1.78550470485347,
            ),
        ),
    ),
    "TABLE-S2": TargetRecipe(
        "activity_pods",
        "source-recomputation",
        "available",
        ("paper/sources/table-s2.xlsx", *ACTIVITY_RECIPE_INPUTS[3:6]),
        _target_builder(
            _rule(
                "Table S2 semantic keys",
                ("activity_pods", "supplemental_tables", "table_s2", "matched_semantic_keys"),
                796,
            ),
            _rule(
                "Table S2 maximum POD difference",
                ("activity_pods", "supplemental_tables", "table_s2", "maximum_absolute_pod_difference"),
                1e-12,
                _less_than,
            ),
        ),
    ),
    "TABLE-S3": TargetRecipe(
        "activity_pods",
        "source-recomputation",
        "available",
        ("paper/sources/table-s3.xlsx", *ACTIVITY_RECIPE_INPUTS[6:9]),
        _target_builder(
            _rule(
                "Table S3 semantic keys",
                ("activity_pods", "supplemental_tables", "table_s3", "matched_semantic_keys"),
                10935,
            ),
            _rule(
                "Table S3 exact bioactivity flags",
                ("activity_pods", "supplemental_tables", "table_s3", "bioactivity_flag_exact_rows"),
                10935,
            ),
        ),
    ),
    "TABLE-S4": TargetRecipe(
        "activity_pods",
        "source-recomputation",
        "available",
        ("paper/sources/table-s4.xlsx", "2_downstream_analysis/compiled_results/SI_tables/hit_summary.csv"),
        _target_builder(
            _rule(
                "Table S4 semantic keys",
                ("activity_pods", "supplemental_tables", "table_s4", "matched_semantic_keys"),
                1086,
            ),
            _rule(
                "Table S4 exact tracked hit rows",
                ("activity_pods", "supplemental_tables", "table_s4", "all_hit_calls_exact_rows"),
                1086,
            ),
        ),
    ),
    "METHOD-POD": TargetRecipe(
        "activity_pods",
        "documentary-trace",
        "documentary-only",
        (
            "1_snakemake/concresponse/fit_curves.R",
            "1_snakemake/concresponse/fit_curves_meta.R",
            "1_snakemake/concresponse/select_pod.R",
            "paper/paper.md",
            "paper/evidence/method-deviations.md",
        ),
        _target_builder(
            _rule("POD implementation and deviation trace", ("activity_pods", "pod_method_trace"), True, _all_true)
        ),
    ),
    "CONCLUSION-001": TargetRecipe(
        "activity_pods",
        "derived-artifact-reanalysis",
        "available",
        ACTIVITY_RECIPE_INPUTS,
        _target_builder(
            _rule("morphology sensitivity inequalities", ("activity_pods", "conclusion_gates"), True, _all_true)
        ),
    ),
    "TABLE-1": TargetRecipe(
        "regression_enrichment",
        "documentary-trace",
        "documentary-only",
        (
            "paper/paper.md",
            "1_snakemake/classifier/regression.py",
            "2_downstream_analysis/manuscript_notebooks/2_1_predict_continuous_assays.ipynb",
            "paper/evidence/regression-and-figure-s2.md",
        ),
        _target_builder(
            _rule(
                "Table 1 documentary schema and value trace",
                ("regression_enrichment", "regression_trace", "table_1_documentary"),
                True,
            ),
            _rule(
                "Table 1 numerical acceptance rerun",
                ("regression_enrichment", "regression_trace", "numerical_acceptance_rerun"),
                False,
            ),
        ),
    ),
    "REGRESSION-001": TargetRecipe(
        "regression_enrichment",
        "documentary-trace",
        "documentary-only",
        (
            "1_snakemake/classifier/regression.py",
            "2_downstream_analysis/manuscript_notebooks/2_1_predict_continuous_assays.ipynb",
            "paper/evidence/regression-and-figure-s2.md",
        ),
        _target_builder(
            _rule(
                "regression comparison documentary trace",
                ("regression_enrichment", "regression_trace", "relative_performance_documentary"),
                True,
            ),
            _rule(
                "regression numerical acceptance rerun",
                ("regression_enrichment", "regression_trace", "numerical_acceptance_rerun"),
                False,
            ),
        ),
    ),
    "REGRESSION-002": TargetRecipe(
        "regression_enrichment",
        "documentary-trace",
        "documentary-only",
        (
            "paper/paper.md",
            "2_downstream_analysis/manuscript_notebooks/2_1_predict_continuous_assays.ipynb",
            "paper/evidence/regression-and-figure-s2.md",
        ),
        _target_builder(
            _rule(
                "LDH replicate comparison documentary trace",
                ("regression_enrichment", "regression_trace", "replicate_effect_documentary"),
                True,
            ),
            _rule(
                "regression numerical acceptance rerun",
                ("regression_enrichment", "regression_trace", "numerical_acceptance_rerun"),
                False,
            ),
        ),
    ),
    "ENRICH-001": TargetRecipe(
        "regression_enrichment",
        "derived-artifact-reanalysis",
        "blocked",
        (
            "2_downstream_analysis/compiled_results/err_higher_targets.csv",
            "paper/evidence/prediction-error-enrichment.md",
        ),
        _target_builder(
            _rule(
                "historical higher hit-list size",
                ("regression_enrichment", "files", "err_higher_targets.csv", "hit_list_size"),
                304,
            ),
            _rule(
                "stored higher significant sets",
                ("regression_enrichment", "files", "err_higher_targets.csv", "significant_count"),
                178,
            ),
            _rule(
                "literal 480-target acceptance available",
                ("regression_enrichment", "regression_trace", "err_480_acceptance_available"),
                False,
            ),
        ),
    ),
    "ENRICH-002": TargetRecipe(
        "regression_enrichment",
        "derived-artifact-reanalysis",
        "blocked",
        (
            "2_downstream_analysis/compiled_results/err_lower_targets.csv",
            "paper/evidence/prediction-error-enrichment.md",
        ),
        _target_builder(
            _rule(
                "stored lower hit-list size",
                ("regression_enrichment", "files", "err_lower_targets.csv", "hit_list_size"),
                138,
            ),
            _rule(
                "stored lower significant sets",
                ("regression_enrichment", "files", "err_lower_targets.csv", "significant_count"),
                0,
            ),
            _rule(
                "literal 304-well acceptance available",
                ("regression_enrichment", "regression_trace", "err_304_acceptance_available"),
                False,
            ),
        ),
    ),
    "ENRICH-003": TargetRecipe(
        "regression_enrichment",
        "derived-artifact-reanalysis",
        "available",
        (
            "2_downstream_analysis/compiled_results/mtt_higher_targets.csv",
            "paper/evidence/mt-discrepancy-enrichment.md",
        ),
        _target_builder(
            _rule(
                "MT higher hit-list size",
                ("regression_enrichment", "files", "mtt_higher_targets.csv", "hit_list_size"),
                261,
            ),
            _rule(
                "MT higher significant sets",
                ("regression_enrichment", "files", "mtt_higher_targets.csv", "significant_count"),
                147,
            ),
            _rule(
                "MT higher named target classes",
                ("regression_enrichment", "significant_classes", "mtt_higher"),
                {
                    "cyp_prefix_count": 8,
                    "htr_prefix_count": 6,
                    "transporters_present": ["ABCB1", "ABCG2", "SLCO1B1", "SLCO1B3"],
                },
            ),
        ),
    ),
    "ENRICH-004": TargetRecipe(
        "regression_enrichment",
        "derived-artifact-reanalysis",
        "available",
        ("2_downstream_analysis/compiled_results/mtt_lower_targets.csv", "paper/evidence/mt-discrepancy-enrichment.md"),
        _target_builder(
            _rule(
                "MT lower hit-list size",
                ("regression_enrichment", "files", "mtt_lower_targets.csv", "hit_list_size"),
                131,
            ),
            _rule(
                "MT lower significant sets",
                ("regression_enrichment", "files", "mtt_lower_targets.csv", "significant_count"),
                107,
            ),
            _rule(
                "MT lower named target classes",
                ("regression_enrichment", "significant_classes", "mtt_lower"),
                {"psm_prefix_count": 18, "cyp_prefix_count": 3},
            ),
        ),
    ),
    "SFIG-2": TargetRecipe(
        "regression_enrichment",
        "documentary-trace",
        "documentary-only",
        (
            "paper/paper.md",
            "2_downstream_analysis/manuscript_notebooks/2_1_predict_continuous_assays.ipynb",
            "2_downstream_analysis/other_notebooks/01_checkwelleffects.ipynb",
            "paper/evidence/regression-and-figure-s2.md",
        ),
        _target_builder(
            _rule(
                "Figure S2 panel documentary trace",
                ("regression_enrichment", "regression_trace", "sfig2_documentary"),
                True,
            ),
            _rule(
                "Figure S2 numerical acceptance rerun",
                ("regression_enrichment", "regression_trace", "numerical_acceptance_rerun"),
                False,
            ),
        ),
    ),
    "METHOD-REGRESSION": TargetRecipe(
        "regression_enrichment",
        "documentary-trace",
        "documentary-only",
        ("1_snakemake/classifier/regression.py", "paper/evidence/method-deviations.md"),
        _target_builder(
            _rule(
                "ten 80/20 compound-group splits",
                ("regression_enrichment", "regression_trace", "compound_group_isolation"),
                True,
            )
        ),
    ),
    "INTERPRETATION-001": TargetRecipe(
        "regression_enrichment",
        "derived-artifact-reanalysis",
        "available",
        (
            "2_downstream_analysis/compiled_results/mtt_higher_targets.csv",
            "2_downstream_analysis/compiled_results/mtt_lower_targets.csv",
            "paper/paper.md",
        ),
        _target_builder(
            _rule(
                "direct enrichment associations separated from mechanism",
                ("regression_enrichment", "regression_trace", "mechanism_claim_is_hypothesis"),
                True,
            )
        ),
    ),
    "TOXCAST-001": TargetRecipe(
        "toxcast",
        "source-recomputation",
        "available",
        (*TOXCAST_RECIPE_INPUTS, "paper/evidence/toxcast-curation-and-figure-s3.md"),
        _target_builder(
            _rule("stored ToxCast annotation-ID union, not tested overlap", ("toxcast", "union_ids"), 963),
            _computed_rule(
                "stored annotation-union/library-denominator arithmetic, not tested overlap",
                lambda a: (a["toxcast"]["union_fraction_of_published_library"], 0.005),
                0.89,
                _within,
            ),
            _rule(
                "documented tested-library intersection IDs",
                ("toxcast", "documented_tested_intersection", "ids"),
                670,
            ),
            _computed_rule(
                "documented tested-library intersection percentage",
                lambda a: (a["toxcast"]["documented_tested_intersection"]["percent_of_published_library"], 5e-7),
                61.751152,
                _within,
            ),
            _rule(
                "963 is an annotation union rather than a tested-library join",
                ("toxcast", "annotation_union_not_tested_library_join"),
                True,
            ),
        ),
    ),
    "TOXCAST-002": TargetRecipe(
        "toxcast",
        "source-recomputation",
        "available",
        TOXCAST_RECIPE_INPUTS,
        _target_builder(
            _rule(
                "ToxCast source endpoint counts",
                ("toxcast", "source_endpoint_counts"),
                {"cellbased": 292, "cellfree": 72, "cytotox": 48},
            ),
            _rule(
                "classification-ready binary endpoint counts",
                ("toxcast", "binary_endpoint_counts"),
                {"cellbased": 292, "cellfree": 72, "cytotox": 38},
            ),
        ),
    ),
    "TOXCAST-003": TargetRecipe(
        "toxcast",
        "source-recomputation",
        "available",
        TOXCAST_RECIPE_INPUTS,
        _target_builder(
            _rule(
                "cell-based tissue composition",
                ("toxcast", "composition", "cellbased_tissues"),
                {"liver": 151, "vascular": 63, "kidney": 35},
            ),
            _rule(
                "cell-free assay composition",
                ("toxcast", "composition", "cellfree_assay_types"),
                {"binding": 37, "enzymatic activity": 35},
            ),
            _rule(
                "cell-free target-family composition",
                ("toxcast", "composition", "cellfree_target_families"),
                {"gpcr": 21, "cyp": 11, "nuclear receptor": 10},
            ),
            _rule(
                "median compounds tested per endpoint",
                ("toxcast", "endpoint_medians", "observed_compounds"),
                {"cytotox": 346, "cellbased": 306, "cellfree": 33},
            ),
            _computed_rule(
                "median endpoint active fractions",
                lambda a: a["toxcast"]["endpoint_medians"]["active_fraction"],
                {"cytotox": 0.2068348801, "cellbased": 0.0711613553, "cellfree": 0.4134295228},
                lambda observed, expected: all(abs(observed[key] - expected[key]) <= 1e-10 for key in expected),
            ),
        ),
    ),
    "SFIG-3": TargetRecipe(
        "toxcast",
        "source-recomputation",
        "available",
        (
            "1_snakemake/inputs/annotations/toxcast_cytotox_binary.parquet",
            "paper/evidence/toxcast-curation-and-figure-s3.md",
        ),
        _target_builder(
            _rule(
                "cytotoxicity heatmap summary",
                ("toxcast", "heatmap_summary"),
                {"cell_categories": 12, "tissue_categories": 6, "complete_compounds": 839},
            )
        ),
    ),
    "TABLE-S5": TargetRecipe(
        "toxcast",
        "source-recomputation",
        "available",
        (
            "paper/sources/table-s5.xlsx",
            "1_snakemake/inputs/annotations/toxcast_cellbased_info.parquet",
            "1_snakemake/inputs/annotations/toxcast_cytotox_info.parquet",
            "1_snakemake/inputs/annotations/toxcast_cytotox_binary.parquet",
        ),
        _target_builder(
            _rule("Table S5 nuclear-receptor assays", ("toxcast", "table_s5", "nuclear_receptor_assays"), 12),
            _computed_rule(
                "Table S5 nuclear-receptor AC50 minimum",
                lambda a: (a["toxcast"]["table_s5"]["nuclear_receptor_ac50_min_um"], 0.001),
                1.648,
                _within,
            ),
            _rule(
                "Table S5 nuclear-receptor AC50 maximum", ("toxcast", "table_s5", "nuclear_receptor_ac50_max_um"), 45.0
            ),
            _rule(
                "Table S5 retained pinned receptor assays",
                ("toxcast", "table_s5", "retained_nuclear_receptor_assays"),
                8,
            ),
            _rule("Table S5 source cytotoxicity hits", ("toxcast", "table_s5", "cytotoxicity_source_hits"), 0),
            _computed_rule(
                "Table S5 MMP activity evidence",
                lambda a: {
                    "hitcall_above_0_9": a["toxcast"]["table_s5"]["mmp_hitcall"] > 0.9,
                    "ac50_um": a["toxcast"]["table_s5"]["mmp_ac50_um"],
                },
                "active finite MMP signal",
                lambda observed, _expected: observed["hitcall_above_0_9"] and 0 < observed["ac50_um"] <= 100,
            ),
        ),
    ),
    "METHOD-TOXCAST": TargetRecipe(
        "toxcast",
        "documentary-trace",
        "documentary-only",
        (
            "paper/paper.md",
            "2_downstream_analysis/manuscript_notebooks/3_1_toxcast_endpoints.ipynb",
            "paper/evidence/toxcast-curation-and-figure-s3.md",
        ),
        _target_builder(
            _rule("ToxCast threshold and decision-rule trace", ("toxcast", "method_trace"), True, _all_true)
        ),
    ),
    "TABLE-2": TargetRecipe(
        "classifier",
        "derived-artifact-reanalysis",
        "available",
        ("2_downstream_analysis/compiled_results/compiled_axiom_metrics.parquet",),
        _target_builder(
            _computed_rule("Table 2 row count", lambda a: len(a["classifier"]["table2"]["rows"]), 10),
            _rule("Table 2 conclusion gates", ("classifier", "conclusion_gates", "table2"), True),
        ),
    ),
    "CLASSIFIER-001": TargetRecipe(
        "classifier",
        "derived-artifact-reanalysis",
        "available",
        ("2_downstream_analysis/compiled_results/compiled_axiom_metrics.parquet",),
        _target_builder(
            _computed_rule(
                "LDH morphology mean AUROC",
                lambda a: (a["classifier"]["classifier_001"]["morphology_mean_auroc"], 5e-7),
                0.932625,
                _within,
            ),
            _computed_rule(
                "LDH morphology mean PRAUC",
                lambda a: (a["classifier"]["classifier_001"]["morphology_mean_prauc"], 5e-7),
                0.753212,
                _within,
            ),
            _rule(
                "LDH representations beat both baselines",
                ("classifier", "classifier_001", "all_representations_above_both_baselines"),
                True,
            ),
        ),
    ),
    "FIG-3AB": TargetRecipe(
        "classifier",
        "derived-artifact-reanalysis",
        "available",
        CLASSIFIER_RECIPE_INPUTS,
        _target_builder(
            _rule(
                "classifier modeled endpoint distributions",
                ("classifier", "modeled_endpoint_counts"),
                {"axiom": 2, "toxcast_cytotox": 34, "toxcast_cellbased": 267, "toxcast_cellfree": 53},
            ),
            _rule(
                "all-concentration CellProfiler distribution summaries",
                ("classifier", "all_cellprofiler_medians"),
                {
                    "axiom": {"auroc": 0.901547, "prauc": 0.805566},
                    "toxcast_cytotox": {"auroc": 0.73721, "prauc": 0.477455},
                    "toxcast_cellbased": {"auroc": 0.607226, "prauc": 0.14484},
                    "toxcast_cellfree": {"auroc": 0.532086, "prauc": 0.454015},
                },
                lambda observed, expected: all(
                    abs(observed[c][m] - expected[c][m]) <= 5e-7 for c in expected for m in expected[c]
                ),
            ),
        ),
    ),
    "FIG-3C": TargetRecipe(
        "classifier",
        "derived-artifact-reanalysis",
        "available",
        CLASSIFIER_RECIPE_INPUTS,
        _target_builder(
            _rule(
                "cell-based versus cell-free baseline conclusion",
                ("classifier", "conclusion_gates", "cellbased_not_cellfree"),
                True,
            )
        ),
    ),
    "FILTER-001": TargetRecipe(
        "classifier",
        "derived-artifact-reanalysis",
        "available",
        CLASSIFIER_RECIPE_INPUTS,
        _target_builder(
            _rule(
                "allpod versus all effects remain small",
                ("classifier", "conclusion_gates", "allpod_small_effects"),
                True,
            )
        ),
    ),
    "FILTER-002": TargetRecipe(
        "classifier",
        "derived-artifact-reanalysis",
        "available",
        CLASSIFIER_RECIPE_INPUTS,
        _target_builder(
            _computed_rule(
                "Axiom allpodcc minus allpod mean AUROC",
                lambda a: a["classifier"]["filter_effects"]["axiom"]["auroc"]["mean_difference"],
                -0.124974386867459,
                lambda observed, expected: abs(float(observed) - float(expected)) <= 1e-12,
            ),
            _computed_rule(
                "Axiom allpodcc minus allpod mean PRAUC",
                lambda a: a["classifier"]["filter_effects"]["axiom"]["prauc"]["mean_difference"],
                -0.372361412793057,
                lambda observed, expected: abs(float(observed) - float(expected)) <= 1e-12,
            ),
            _computed_rule(
                "allpodcc minus allpod mean AUROC",
                lambda a: {
                    category: a["classifier"]["filter_effects"][category]["auroc"]["mean_difference"]
                    for category in ("toxcast_cellbased", "toxcast_cellfree", "toxcast_cytotox")
                },
                {
                    "toxcast_cellbased": -0.0079701890,
                    "toxcast_cellfree": 0.0134291664,
                    "toxcast_cytotox": -0.0885859687,
                },
                lambda observed, expected: all(abs(observed[key] - expected[key]) <= 1e-10 for key in expected),
            ),
            _computed_rule(
                "allpodcc minus allpod mean PRAUC",
                lambda a: {
                    category: a["classifier"]["filter_effects"][category]["prauc"]["mean_difference"]
                    for category in ("toxcast_cellbased", "toxcast_cellfree", "toxcast_cytotox")
                },
                {
                    "toxcast_cellbased": -0.0065967963,
                    "toxcast_cellfree": 0.0051519574,
                    "toxcast_cytotox": -0.1671635603,
                },
                lambda observed, expected: all(abs(observed[key] - expected[key]) <= 1e-10 for key in expected),
            ),
            _rule(
                "Axiom and cytotoxic effects are negative while cell-based and cell-free effects remain below 0.02",
                ("classifier", "conclusion_gates", "allpodcc_filter_direction"),
                True,
            ),
        ),
    ),
    "FIG-4A": TargetRecipe(
        "classifier",
        "derived-artifact-reanalysis",
        "available",
        CLASSIFIER_RECIPE_INPUTS,
        _target_builder(
            _rule(
                "all-concentration strategy conclusion",
                ("classifier", "conclusion_gates", "all_concentration_not_worse"),
                True,
            )
        ),
    ),
    "REPRESENTATION-001": TargetRecipe(
        "classifier",
        "derived-artifact-reanalysis",
        "available",
        CLASSIFIER_RECIPE_INPUTS,
        _target_builder(
            _computed_rule(
                "DINO versus CP-CNN cell-based AUROC effects",
                lambda a: a["classifier"]["target_effects"]["dino_vs_cpcnn_cellbased_auroc"],
                {"mean_difference": 0.01079046, "median_difference": 0.01587302},
                lambda observed, expected: all(abs(observed[key] - expected[key]) <= 5e-8 for key in expected),
            ),
            _computed_rule(
                "DINO versus CellProfiler median cell-based AUROC",
                lambda a: a["classifier"]["target_effects"]["dino_vs_cellprofiler_cellbased_auroc"][
                    "median_difference"
                ],
                0.02209021,
                lambda observed, expected: abs(float(observed) - float(expected)) <= 5e-8,
            ),
        ),
    ),
    "FIG-4B": TargetRecipe(
        "classifier",
        "derived-artifact-reanalysis",
        "available",
        CLASSIFIER_RECIPE_INPUTS,
        _target_builder(
            _rule(
                "representation effects remain practically small",
                ("classifier", "conclusion_gates", "representation_small_effects"),
                True,
            )
        ),
    ),
    "SFIG-4": TargetRecipe(
        "classifier",
        "derived-artifact-reanalysis",
        "available",
        CLASSIFIER_RECIPE_INPUTS,
        _target_builder(
            _rule(
                "PRAUC filtering and representation practical conclusion",
                ("classifier", "conclusion_gates", "prauc_no_material_improvement"),
                True,
            )
        ),
    ),
    "METHOD-CLASSIFIER": TargetRecipe(
        "classifier",
        "documentary-trace",
        "documentary-only",
        (
            "1_snakemake/classifier/classify.py",
            "1_snakemake/classifier/aggregate_profiles.py",
            "1_snakemake/classifier/hitcalls.py",
            "1_snakemake/rules/classifier.smk",
        ),
        _target_builder(_rule("classifier implementation trace", ("classifier", "method_trace"), True, _all_true)),
    ),
    "CONCLUSION-002": TargetRecipe(
        "classifier",
        "derived-artifact-reanalysis",
        "available",
        CLASSIFIER_RECIPE_INPUTS,
        _target_builder(
            _rule(
                "cell-based but not cell-free inequality gate",
                ("classifier", "conclusion_gates", "cellbased_not_cellfree"),
                True,
            )
        ),
    ),
    "CONCLUSION-003": TargetRecipe(
        "classifier",
        "derived-artifact-reanalysis",
        "available",
        CLASSIFIER_RECIPE_INPUTS,
        _target_builder(
            _rule(
                "representation and filtering practical-equivalence gates",
                ("classifier", "conclusion_gates", "conclusion_003"),
                True,
            )
        ),
    ),
    "SFIG-1": TargetRecipe(
        "external_image",
        "unavailable",
        "out-of-scope",
        (
            "paper/figures/figure-s1.jpg",
            "paper/paper.md",
            "paper/evidence/figure-s1.md",
            "paper/render_sfig1.py",
        ),
        _target_builder(
            _rule("tracked navigation image identity trace", ("external_image", "identity_trace"), True),
            _rule(
                "external source-image reproduction documented",
                ("external_image", "external_reproduction_documented"),
                True,
            ),
            _rule("external source image available", ("external_image", "source_image_available"), False),
        ),
    ),
}


def _execution_outcome(recipe: TargetRecipe, checks_passed: bool) -> str:
    if not checks_passed:
        raise ScientificContradictionError("one or more target-specific checks failed")
    outcomes = {
        "available": "checked",
        "documentary-only": "documentary-only",
        "blocked": "blocked",
        "out-of-scope": "out-of-scope",
    }
    if recipe.availability not in outcomes:
        raise InputValidationError(f"invalid recipe availability: {recipe.availability}")
    return outcomes[recipe.availability]


def _artifact_names(group: str) -> list[str]:
    names = ["evidence-coverage.svg"]
    if group == "activity_pods":
        names.append("pod-summary.svg")
    elif group == "regression_enrichment":
        names.append("enrichment-summary.svg")
    elif group == "toxcast":
        names.append("toxcast-summary.svg")
    elif group == "classifier":
        names.append("classifier-summary.svg")
    return names


def _count_field(rows: Sequence[Mapping[str, object]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row[field]) for row in rows).items()))


def build_report(root: Path, selected_ids: set[str] | None = None) -> dict[str, object]:
    """Build a deterministic report from the explicit tracked-input allowlist."""
    root = root.resolve()
    validated_inputs: set[str] = set()
    tracker_token = _VALIDATED_INPUTS.set(validated_inputs)
    try:
        targets = load_targets(root)
        ledger_ids = [row["id"] for row in targets]
        grouped_ids = [target_id for group in TARGET_GROUPS.values() for target_id in group]
        _require(len(grouped_ids) == len(set(grouped_ids)), "TARGET_GROUPS contains duplicate target assignments")
        _require(set(grouped_ids) == set(ledger_ids), "TARGET_GROUPS does not cover the target ledger exactly")
        _require(set(TARGET_RECIPES) == set(ledger_ids), "TARGET_RECIPES does not cover the target ledger exactly")
        _require(len(TARGET_RECIPES) == 53, f"TARGET_RECIPES has {len(TARGET_RECIPES)} entries; expected 53")
        _require(len(ledger_ids) == 53, f"target ledger has {len(ledger_ids)} rows; expected 53")
        for target_id, recipe in TARGET_RECIPES.items():
            _require(target_id in TARGET_GROUPS[recipe.group], f"{target_id}: recipe group assignment differs")
            _require(recipe.evidence_strength in EVIDENCE_STRENGTHS, f"{target_id}: invalid evidence strength")
            _require(bool(recipe.inputs), f"{target_id}: recipe has no concrete inputs")
            _require(set(recipe.inputs) <= ALLOWED_INPUTS, f"{target_id}: recipe contains a non-allowlisted input")

        if selected_ids is not None:
            unknown = sorted(selected_ids - set(ledger_ids))
            _require(not unknown, f"unknown selected target IDs: {', '.join(unknown)}")
            selected = set(selected_ids)
            _require(bool(selected), "no targets selected")
        else:
            selected = set(ledger_ids)

        executed_groups = [
            group for group, group_ids in TARGET_GROUPS.items() if any(target_id in selected for target_id in group_ids)
        ]
        analysis_builders: dict[str, Callable[[Path], dict[str, object]]] = {
            "sources_design": _analyze_sources_design,
            "activity_pods": _analyze_activity_pods,
            "regression_enrichment": _analyze_regression_enrichment,
            "toxcast": _analyze_toxcast,
            "classifier": _analyze_classifier,
            "external_image": _analyze_external_image,
        }
        analyses: dict[str, object] = {group: analysis_builders[group](root) for group in executed_groups}

        result_targets: list[dict[str, object]] = []
        check_ids: set[str] = set()
        for ledger_row in targets:
            target_id = ledger_row["id"]
            if target_id not in selected:
                continue
            recipe = TARGET_RECIPES[target_id]
            raw_checks = recipe.check_builder(analyses)
            _require(bool(raw_checks), f"{target_id}: recipe built no target-specific checks")
            checks: list[dict[str, object]] = []
            for index, raw_check in enumerate(raw_checks, start=1):
                check_id = f"{target_id}:{index:02d}"
                _require(check_id not in check_ids, f"duplicate target check ID {check_id}")
                check_ids.add(check_id)
                checks.append({"id": check_id, "target_id": target_id, **raw_check})
            checks_passed = all(bool(check["passed"]) for check in checks)
            _confirm(checks_passed, f"{target_id}: one or more target-specific checks failed")
            execution_outcome = _execution_outcome(recipe, checks_passed)
            limitations = [] if ledger_row["deviation"] == "-" else [ledger_row["deviation"]]
            if recipe.availability == "documentary-only":
                limitations.append(
                    "The required numerical substrate is not tracked; numerical acceptance was not rerun, and this recipe validates source, notebook, or code trace only."
                )
            elif recipe.evidence_strength == "derived-artifact-reanalysis":
                limitations.append(
                    "Tracked derived artifacts were reanalyzed; classifiers, curves, predictions, and upstream workflows were not regenerated."
                )
            elif recipe.availability == "out-of-scope":
                limitations.append("The raw source image is external and excluded from tracked-only execution.")
            result_targets.append(
                {
                    "id": target_id,
                    "source": ledger_row["source"],
                    "kind": ledger_row["kind"],
                    "description": ledger_row["description"],
                    "expected": ledger_row["expected"],
                    "acceptance": ledger_row["acceptance"],
                    "producer": ledger_row["producer"],
                    "evidence": ledger_row["evidence"],
                    "deviation": ledger_row["deviation"],
                    "group": recipe.group,
                    "ledger_status": ledger_row["status"],
                    "execution_outcome": execution_outcome,
                    "evidence_strength": recipe.evidence_strength,
                    "availability": recipe.availability,
                    "acceptance_class": ledger_row["acceptance"].partition(":")[0],
                    "summary": f"{ledger_row['description']}: target-specific tracked-only checks completed with execution outcome {execution_outcome}.",
                    "checks": checks,
                    "inputs": list(recipe.inputs),
                    "limitations": limitations,
                    "artifacts": _artifact_names(recipe.group),
                }
            )

        ledger_bytes = _input_path(root, "paper/targets.tsv").read_bytes()
        for target in result_targets:
            missing_validations = sorted(set(target["inputs"]) - validated_inputs)
            _require(
                not missing_validations,
                f"{target['id']}: reported inputs were not opened and validated: {', '.join(missing_validations)}",
            )

        group_reports: dict[str, object] = {}
        for group in executed_groups:
            rows = [row for row in result_targets if row["group"] == group]
            group_reports[group] = {
                "target_ids": [row["id"] for row in rows],
                "target_count": len(rows),
                "execution_outcome_counts": _count_field(rows, "execution_outcome"),
                "evidence_strength_counts": _count_field(rows, "evidence_strength"),
                "checks": [check for row in rows for check in row["checks"]],
            }

        summary = {
            "total": len(result_targets),
            "ledger_status_counts": _count_field(result_targets, "ledger_status"),
            "execution_outcome_counts": _count_field(result_targets, "execution_outcome"),
            "evidence_strength_counts": _count_field(result_targets, "evidence_strength"),
            "acceptance_class_counts": _count_field(result_targets, "acceptance_class"),
        }
        report: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "mode": "tracked",
            "ledger_sha256": hashlib.sha256(ledger_bytes).hexdigest(),
            "executed_groups": executed_groups,
            "validated_inputs": sorted(validated_inputs),
            "summary": summary,
            "analyses": analyses,
            "groups": group_reports,
            "targets": result_targets,
        }
    finally:
        _VALIDATED_INPUTS.reset(tracker_token)
    # This is both a finiteness gate and an early guarantee that no unsupported
    # object type entered the public report schema.
    try:
        report = json.loads(json.dumps(report, sort_keys=True, allow_nan=False, ensure_ascii=True))
    except (TypeError, ValueError) as exc:
        raise InputValidationError(f"report is not strict JSON: {exc}") from exc
    return report


def _output_is_protected(output_dir: Path) -> bool:
    resolved_parts = output_dir.resolve().parts
    for relative in (*PROTECTED_INPUT_TREES, *FORBIDDEN_OUTPUT_TREES):
        protected_parts = Path(relative).parts
        width = len(protected_parts)
        if any(
            tuple(resolved_parts[index : index + width]) == protected_parts
            for index in range(len(resolved_parts) - width + 1)
        ):
            return True
    return False


def _atomic_bytes(path: Path, content: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        # A failed temporary file remains recoverable and clearly named.
        raise


def _markdown_cell(value: object) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)
    elif value is None:
        text = "null"
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    analyses = report["analyses"]
    lines = [
        "# Tracked paper audit",
        "",
        "This report is an archive-safe reanalysis of tracked sources, annotations, and compiled artifacts.",
        "It is not a rerun of ignored scientific workflows and its figures are not publisher reproductions.",
        "An execution outcome of `checked` means the declared checks passed against tracked inputs; it does not mean upstream workflows were regenerated.",
        "Historical ledger status is retained for provenance and does not determine the execution outcome.",
        "",
        f"Mode: `{report['mode']}`.",
        f"Targets covered: {summary['total']}.",
        f"Executed groups: {', '.join(report['executed_groups'])}.",
        f"Validated tracked inputs: {len(report['validated_inputs'])}.",
        f"Ledger SHA-256: `{report['ledger_sha256']}`.",
        "",
        "## Execution outcome counts",
        "",
        "| Execution outcome | Count |",
        "| --- | ---: |",
    ]
    lines.extend(f"| {name} | {count} |" for name, count in summary["execution_outcome_counts"].items())
    lines.extend(
        [
            "",
            "## Historical ledger status counts",
            "",
            "| Ledger status | Count |",
            "| --- | ---: |",
        ]
    )
    lines.extend(f"| {name} | {count} |" for name, count in summary["ledger_status_counts"].items())
    lines.extend(
        [
            "",
            "## Evidence coverage",
            "",
            "| Evidence strength | Targets |",
            "| --- | ---: |",
        ]
    )
    lines.extend(f"| {name} | {count} |" for name, count in summary["evidence_strength_counts"].items())
    lines.extend(["", "[Open the evidence-coverage figure](evidence-coverage.svg)."])

    if "sources_design" in analyses:
        sources = analyses["sources_design"]
        table_s1 = sources["table_s1"]
        lines.extend(
            [
                "",
                "## Sources, design, and Table S1",
                "",
                f"All {sources['source_count']} manifest sources passed SHA-256 and byte-count checks.",
                f"All {sources['office_archive_count']} Office archives passed ZIP CRC checks.",
                f"Table S1 has {table_s1['rows']} rows, {table_s1['stable_id_count']} stable IDs, and {table_s1['blank_id_count']} blank IDs.",
            ]
        )

    if "activity_pods" in analyses:
        activity = analyses["activity_pods"]
        figure_2c = activity["figure_2c_three_general"]
        figure_2d = activity["figure_2d"]
        lines.extend(
            [
                "",
                "## Activity and PODs",
                "",
                f"The direction-aware cytotoxicity trace records {activity['direction_aware_cytotoxicity']['count']} compounds and explicitly records that direction is absent from hit_summary.csv.",
                "",
                "| Figure 2A compound | Published Table S2 POD (uM) |",
                "| --- | ---: |",
            ]
        )
        lines.extend(f"| {row['compound']} | {row['pod_um']:.6g} |" for row in activity["figure_2a"]["rows"])
        lines.extend(
            [
                "",
                f"Figure 2C has {activity['figure_2c_complete_case']['count']} published-SI five-series cases and {figure_2c['count']} three-general cases.",
                f"The three-general CP-CNN ratios are {figure_2c['geometric_fold_ratios']['cpcnn_over_cellprofiler']:.6g} over CellProfiler and {figure_2c['geometric_fold_ratios']['cpcnn_over_dino']:.6g} over DINO.",
                f"The three-general CellProfiler-DINO paired-log10 p-value is {figure_2c['cellprofiler_vs_dino_paired_log10']['paired_t_p_value']:.6g}.",
                f"Figure 2D has {figure_2d['complete_case_count']} published-SI complete cases and preserves the morphology, MT, cell-count, LDH median ordering.",
                "",
                "[Open the POD-summary figure](pod-summary.svg).",
            ]
        )

    if "regression_enrichment" in analyses:
        regression = analyses["regression_enrichment"]
        lines.extend(
            [
                "",
                "## Regression and enrichment",
                "",
                "Regression and Figure S2 numerical acceptance was not rerun because the required prediction and metric Parquets are not tracked.",
                "Their recipes validate the paper, producer notebook, implementation, and evidence trace explicitly.",
                "The four tracked enrichment tables were directly recomputed with upper-tail hypergeometric tests and BH FDR.",
                "",
                "| Enrichment artifact | Hit list | Significant sets | Maximum p error | Maximum FDR error |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for name, values in regression["files"].items():
            lines.append(
                f"| {name} | {values['hit_list_size']} | {values['significant_count']} | "
                f"{values['maximum_p_value_recomputation_error']:.3g} | "
                f"{values['maximum_fdr_recomputation_error']:.3g} |"
            )
        lines.extend(
            [
                "",
                f"MT-higher significant classes: {_markdown_cell(regression['significant_classes']['mtt_higher'])}.",
                f"MT-lower significant classes: {_markdown_cell(regression['significant_classes']['mtt_lower'])}.",
                "",
                "[Open the enrichment-summary figure](enrichment-summary.svg).",
            ]
        )

    if "toxcast" in analyses:
        toxcast = analyses["toxcast"]
        lines.extend(
            [
                "",
                "## ToxCast and Table S5",
                "",
                f"The pinned binary annotation union contains {toxcast['union_ids']} OASIS IDs; it is not a tested-library join.",
                f"Tracked evidence documents an actual tested-library intersection of {toxcast['documented_tested_intersection']['ids']} IDs ({toxcast['documented_tested_intersection']['percent_of_published_library']:.6f}%).",
                f"Cell-based tissue composition: {_markdown_cell(toxcast['composition']['cellbased_tissues'])}.",
                f"Cell-free assay composition: {_markdown_cell(toxcast['composition']['cellfree_assay_types'])}.",
                f"Cell-free target-family composition: {_markdown_cell(toxcast['composition']['cellfree_target_families'])}.",
                f"Median compounds observed per endpoint: {_markdown_cell(toxcast['endpoint_medians']['observed_compounds'])}.",
                f"Median endpoint active fractions: {_markdown_cell(toxcast['endpoint_medians']['active_fraction'])}.",
                f"The heatmap substrate has {toxcast['heatmap_summary']['cell_categories']} cell categories, {toxcast['heatmap_summary']['tissue_categories']} tissue categories, and {toxcast['heatmap_summary']['complete_compounds']} complete compounds.",
                f"Table S5 has {toxcast['table_s5']['nuclear_receptor_assays']} nuclear-receptor assays and {toxcast['table_s5']['cytotoxicity_source_hits']} source cytotoxicity hits.",
                "",
                "[Open the ToxCast-summary figure](toxcast-summary.svg).",
            ]
        )

    if "classifier" in analyses:
        classifier = analyses["classifier"]
        lines.extend(
            [
                "",
                "## Classifier metrics",
                "",
                f"Modeled endpoint counts: {_markdown_cell(classifier['modeled_endpoint_counts'])}.",
                f"All-concentration CellProfiler median AUROC and PRAUC: {_markdown_cell(classifier['all_cellprofiler_medians'])}.",
                f"DINO cell-based target effects: {_markdown_cell(classifier['target_effects'])}.",
                "",
                "| Family | Metric | allpodcc minus allpod mean | Median | Matched endpoints |",
                "| --- | --- | ---: | ---: | ---: |",
            ]
        )
        for category, metric_rows in classifier["filter_effects"].items():
            for metric, effect in metric_rows.items():
                lines.append(
                    f"| {category} | {metric} | {effect['mean_difference']:.6g} | "
                    f"{effect['median_difference']:.6g} | {effect['matched_endpoints']} |"
                )
        lines.extend(["", "[Open the classifier-summary figure](classifier-summary.svg)."])

    if "external_image" in analyses:
        lines.extend(
            [
                "",
                "## External image boundary",
                "",
                analyses["external_image"]["limitation"],
            ]
        )

    figure_links = ["- [Evidence coverage](evidence-coverage.svg)"]
    if "activity_pods" in analyses:
        figure_links.append("- [POD summary](pod-summary.svg)")
    if "regression_enrichment" in analyses:
        figure_links.append("- [Enrichment summary](enrichment-summary.svg)")
    if "toxcast" in analyses:
        figure_links.append("- [ToxCast summary](toxcast-summary.svg)")
    if "classifier" in analyses:
        figure_links.append("- [Classifier summary](classifier-summary.svg)")
    lines.extend(
        [
            "",
            "## Generated figures",
            "",
            "Each SVG is generated from this report and labeled as tracked-artifact reanalysis.",
            "",
            *figure_links,
            "",
            "## Targets",
        ]
    )
    for target in report["targets"]:
        lines.extend(
            [
                "",
                f"### {target['id']} - {target['description']}",
                "",
                f"Source: {_markdown_cell(target['source'])}.",
                f"Kind: {_markdown_cell(target['kind'])}.",
                f"Expected: {_markdown_cell(target['expected'])}.",
                f"Full acceptance: {_markdown_cell(target['acceptance'])}.",
                f"Producer: {_markdown_cell(target['producer'])}.",
                f"Ledger evidence: {_markdown_cell(target['evidence'])}.",
                f"Historical ledger status: `{target['ledger_status']}`.",
                f"Execution outcome: `{target['execution_outcome']}`; availability: `{target['availability']}`; evidence strength: `{target['evidence_strength']}`.",
                f"Declared deviation: {_markdown_cell(target['deviation'])}.",
                "",
                "| Target-specific check | Observed | Expected | Passed |",
                "| --- | --- | --- | --- |",
            ]
        )
        for check in target["checks"]:
            lines.append(
                f"| {check['id']} - {_markdown_cell(check['name'])} | {_markdown_cell(check['observed'])} | "
                f"{_markdown_cell(check['expected'])} | {str(check['passed']).lower()} |"
            )
        lines.extend(["", "Validated inputs:"])
        lines.extend(f"- `{path}`" for path in target["inputs"])
        lines.extend(["", "Limitations and deviations:"])
        if target["limitations"]:
            lines.extend(f"- {_markdown_cell(limitation)}" for limitation in target["limitations"])
        else:
            lines.append("- None declared.")
    lines.append("")
    text = "\n".join(lines)
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise InputValidationError("rendered Markdown is not ASCII") from exc
    return text


def _plot_style() -> None:
    matplotlib.rcParams.update(
        {
            "axes.unicode_minus": False,
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "svg.fonttype": "path",
            "svg.hashsalt": "oasis-paper-tracked-v1",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#333333",
            "axes.titleweight": "bold",
        }
    )


def _save_svg(fig: Any, path: Path) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.stem}.", suffix=".svg", dir=path.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    fig.savefig(temporary, format="svg", metadata={"Date": None}, bbox_inches="tight")
    plt.close(fig)
    svg_text = temporary.read_text(encoding="utf-8")
    normalized_svg = "\n".join(line.rstrip(" \t") for line in svg_text.splitlines()) + "\n"
    temporary.write_text(normalized_svg, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _bar_figure(labels: Sequence[str], values: Sequence[float], title: str, ylabel: str, color: str) -> Any:
    fig, axis = plt.subplots(figsize=(7.2, 4.2), dpi=100)
    positions = np.arange(len(labels))
    axis.bar(positions, values, color=color, width=0.68)
    axis.set_xticks(positions, labels, rotation=20, ha="right")
    axis.set_ylabel(ylabel)
    axis.set_title(title)
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#dddddd", linewidth=0.6)
    axis.set_axisbelow(True)
    return fig


def render_outputs(report: dict[str, object], output_dir: Path) -> list[Path]:
    """Render current outputs, then prune stale files from the known inventory."""
    required = {
        "schema_version",
        "mode",
        "ledger_sha256",
        "executed_groups",
        "validated_inputs",
        "summary",
        "analyses",
        "groups",
        "targets",
    }
    _require(set(report) == required, "report has an unexpected top-level schema")
    output_dir = output_dir.resolve()
    _require(not _output_is_protected(output_dir), f"output path is inside a protected input tree: {output_dir}")
    if output_dir.exists():
        _require(output_dir.is_dir(), f"output path is not a directory: {output_dir}")
    else:
        output_dir.mkdir(parents=True, exist_ok=False)

    expected_filenames = {"report.json", "report.md", "evidence-coverage.svg"}
    expected_filenames.update(
        filename for group, filename in ANALYSIS_FIGURE_FILENAMES.items() if group in report["analyses"]
    )
    _require(expected_filenames <= KNOWN_OUTPUT_FILENAMES, "computed an unknown generated output filename")

    json_bytes = (json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n").encode(
        "ascii"
    )
    markdown_bytes = _render_markdown(report).encode("ascii")
    report_json = output_dir / "report.json"
    report_markdown = output_dir / "report.md"
    _atomic_bytes(report_json, json_bytes)
    _atomic_bytes(report_markdown, markdown_bytes)

    _plot_style()
    summary = report["summary"]
    evidence_counts = summary["evidence_strength_counts"]
    evidence_labels = list(evidence_counts)
    evidence_figure = _bar_figure(
        evidence_labels,
        [evidence_counts[label] for label in evidence_labels],
        "Evidence coverage - tracked-artifact audit",
        "Targets",
        "#4c78a8",
    )
    evidence_path = output_dir / "evidence-coverage.svg"
    _save_svg(evidence_figure, evidence_path)
    written = [report_json, report_markdown, evidence_path]

    if "activity_pods" in report["analyses"]:
        medians = report["analyses"]["activity_pods"]["figure_2d"]["median_pod_um"]
        pod_labels = ["Morphology", "MT", "Cell count", "LDH"]
        pod_figure = _bar_figure(
            pod_labels,
            [medians[label] for label in pod_labels],
            "POD summary - tracked-artifact reanalysis",
            "Median POD (uM)",
            "#59a14f",
        )
        pod_path = output_dir / "pod-summary.svg"
        _save_svg(pod_figure, pod_path)
        written.append(pod_path)

    if "classifier" in report["analyses"]:
        modeled = report["analyses"]["classifier"]["modeled_endpoint_counts"]
        classifier_labels = list(modeled)
        classifier_figure = _bar_figure(
            classifier_labels,
            [modeled[label] for label in classifier_labels],
            "Classifier denominators - tracked-artifact reanalysis",
            "Modeled endpoints",
            "#f28e2b",
        )
        classifier_path = output_dir / "classifier-summary.svg"
        _save_svg(classifier_figure, classifier_path)
        written.append(classifier_path)

    if "regression_enrichment" in report["analyses"]:
        enrichment_files = report["analyses"]["regression_enrichment"]["files"]
        enrichment_labels = [name.removesuffix("_targets.csv") for name in enrichment_files]
        enrichment_figure = _bar_figure(
            enrichment_labels,
            [item["significant_count"] for item in enrichment_files.values()],
            "Enrichment summary - tracked-artifact reanalysis",
            "Target sets with FDR < 0.05",
            "#e15759",
        )
        enrichment_path = output_dir / "enrichment-summary.svg"
        _save_svg(enrichment_figure, enrichment_path)
        written.append(enrichment_path)

    if "toxcast" in report["analyses"]:
        toxcast = report["analyses"]["toxcast"]
        categories = ["cellbased", "cellfree", "cytotox"]
        positions = np.arange(len(categories))
        width = 0.36
        toxcast_figure, axis = plt.subplots(figsize=(7.2, 4.2), dpi=100)
        axis.bar(
            positions - width / 2,
            [toxcast["source_endpoint_counts"][name] for name in categories],
            width,
            label="Source",
            color="#4c78a8",
        )
        axis.bar(
            positions + width / 2,
            [toxcast["binary_endpoint_counts"][name] for name in categories],
            width,
            label="Binary",
            color="#b279a2",
        )
        axis.set_xticks(positions, categories)
        axis.set_ylabel("Endpoints")
        axis.set_title("ToxCast endpoints - tracked-artifact reanalysis")
        axis.legend(frameon=False)
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", color="#dddddd", linewidth=0.6)
        axis.set_axisbelow(True)
        toxcast_path = output_dir / "toxcast-summary.svg"
        _save_svg(toxcast_figure, toxcast_path)
        written.append(toxcast_path)

    _require({path.name for path in written} == expected_filenames, "rendered output inventory is incomplete")
    # Prune only obsolete artifacts from the fixed generated-output inventory,
    # and only after every output expected for this report rendered successfully.
    # Unknown files in the destination are deliberately preserved.
    for filename in sorted(KNOWN_OUTPUT_FILENAMES - expected_filenames):
        stale_path = output_dir / filename
        if stale_path.exists() or stale_path.is_symlink():
            stale_path.unlink()

    return written


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="output directory (default: paper/reproduction)")
    parser.add_argument("--target", action="append", default=[], help="target ID to include; repeat as needed")
    parser.add_argument("--list", action="store_true", dest="list_targets", help="list target IDs and exit")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return 0, 1, or 2 according to the paper contract."""
    arguments = _parser().parse_args(argv)
    try:
        targets = load_targets(REPOSITORY_ROOT)
        if arguments.list_targets:
            for row in targets:
                print(row["id"])
            return 0
        selected = set(arguments.target) if arguments.target else None
        if arguments.target and len(arguments.target) != len(selected or ()):
            raise InputValidationError("--target values must not be repeated")
        report = build_report(REPOSITORY_ROOT, selected)
        output = arguments.output or REPOSITORY_ROOT / "paper/reproduction"
        paths = render_outputs(report, output)
        print(f"Wrote tracked paper audit for {report['summary']['total']} targets to {paths[0].parent}")
        return 0
    except ScientificContradictionError as exc:
        print(f"scientific or ledger contradiction: {exc}", file=sys.stderr)
        return 1
    except (InputValidationError, OSError) as exc:
        print(f"malformed input, incomplete coverage, or unsafe output: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
