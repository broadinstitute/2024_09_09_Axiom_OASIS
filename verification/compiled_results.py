# ruff: noqa: EM101, EM102, FBT001, T201, TRY003
"""Verify regenerated compiled results against a reference artifact directory.

The comparison is deliberately semantic. Parquet row order, CSV row order, and
the serialization order of enrichment ``overlap_hits`` sets are ignored. The
input trees are only read; the optional JSON report must live outside them.
The expected artifacts and acceptance thresholds are specific to OASIS paper 1A.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from collections.abc import Sequence

REPORT_SCHEMA_VERSION = 1
EXPECTED_METRIC_ROWS = {
    "compiled_axiom_metrics.parquet": 81,
    "compiled_toxcast_cellbased_metrics.parquet": 7_209,
    "compiled_toxcast_cellfree_metrics.parquet": 1_431,
    "compiled_toxcast_cytotox_metrics.parquet": 918,
}
EXPECTED_TOXCAST_ALL_ROWS = {
    "compiled_toxcast_cellbased_metrics.parquet": 2_403,
    "compiled_toxcast_cytotox_metrics.parquet": 306,
}
EXPECTED_TOXCAST_ALL_TOTAL = 2_709
EXPECTED_ENRICHMENT_ROWS = 8_858
EXPECTED_ENRICHMENT_UNIVERSE = 13_176

METRIC_KEY = ("Metadata_AggType", "Metadata_Label", "Model_type", "Feat_type")
METRIC_PAYLOAD = ("AUROC", "PRAUC", "Metadata_Count_0", "Metadata_Count_1")
METRIC_COLUMNS = frozenset((*METRIC_KEY, *METRIC_PAYLOAD))
EXPECTED_AGG_TYPES = frozenset({"all", "allpod", "allpodcc"})

POD_KEY = ("OASIS_ID", "Compound_name", "Assay_Endpoint")
POD_VALUES = ("POD_um", "POD_um_l", "POD_um_u")
POD_BASE_COLUMNS = frozenset((*POD_KEY, *POD_VALUES))
POD_FILES = {
    "SI_tables/cellcount_pods.csv": POD_BASE_COLUMNS,
    "SI_tables/mt_pods.csv": POD_BASE_COLUMNS,
    "SI_tables/ldh_pods.csv": POD_BASE_COLUMNS,
    "SI_tables/cellpainting_cellprofiler_pods.csv": POD_BASE_COLUMNS | {"Bioactivity_POD"},
    "SI_tables/cellpainting_cpcnn_pods.csv": POD_BASE_COLUMNS | {"Bioactivity_POD"},
    "SI_tables/cellpainting_dino_pods.csv": POD_BASE_COLUMNS | {"Bioactivity_POD"},
}
POD_MIN_BIDIRECTIONAL_COVERAGE = 0.80
POD_MIN_WITHIN_ONE_PERCENT = 0.85
POD_MAX_MEDIAN_RELATIVE_DIFFERENCE = 1e-5
POD_ONE_PERCENT_THRESHOLD = 0.01
POD_RELATIVE_BOUNDARY_ATOL = 1e-12
POD_MATERIAL_TAIL_THRESHOLD = 0.10

HIT_SUMMARY_FILE = "SI_tables/hit_summary.csv"
HIT_SUMMARY_KEY = ("OASIS_ID", "Compound_name")
HIT_COLUMNS = (
    "Cell_count_hit",
    "MT_hit",
    "LDH_hit",
    "Cell_Painting_hit",
    "Hit_in_all_assays",
)
HIT_SUMMARY_COLUMNS = frozenset((*HIT_SUMMARY_KEY, *HIT_COLUMNS))

ENRICHMENT_FILES = ("err_higher_targets.csv", "err_lower_targets.csv")
ENRICHMENT_KEY = ("target_set",)
ENRICHMENT_INTEGER_COLUMNS = (
    "overlap_size",
    "target_set_size",
    "hit_list_size",
    "universe_size",
)
ENRICHMENT_FLOAT_COLUMNS = ("p_value", "fdr")
ENRICHMENT_COLUMNS = frozenset(
    (*ENRICHMENT_KEY, *ENRICHMENT_INTEGER_COLUMNS, *ENRICHMENT_FLOAT_COLUMNS, "overlap_hits"),
)
OVERLAP_MEMBER_PATTERN = re.compile(
    r"(?P<member>.+?_[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?_[A-Za-z]+\d+_plate_\d+)(?:,|$)",
)

Key = tuple[str | None, ...]


class InputValidationError(ValueError):
    """Raised when an input artifact cannot be compared safely."""


@dataclass(frozen=True)
class VerificationResult:
    """Structured result from a complete compiled-results comparison."""

    report: dict[str, object]
    gate_failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """Return whether every reproducibility gate passed."""
        return not self.gate_failures


def _display_columns(columns: set[str] | frozenset[str]) -> str:
    return ", ".join(sorted(columns)) or "<none>"


def _validate_columns(frame: pd.DataFrame, expected: frozenset[str], label: str) -> None:
    actual = set(frame.columns)
    if actual != expected:
        missing = expected - actual
        extra = actual - expected
        raise InputValidationError(
            f"{label}: unexpected columns; missing [{_display_columns(missing)}], extra [{_display_columns(extra)}]",
        )
    if frame.empty:
        raise InputValidationError(f"{label}: table is empty")


def _read_parquet(path: Path, expected: frozenset[str], label: str) -> pd.DataFrame:
    if not path.is_file():
        raise InputValidationError(f"{label}: missing Parquet file {path}")
    try:
        frame = pd.read_parquet(path, engine="pyarrow")
    except Exception as exc:
        raise InputValidationError(f"{label}: cannot read Parquet file {path}: {exc}") from exc
    _validate_columns(frame, expected, label)
    return frame


def _read_csv(path: Path, expected: frozenset[str], label: str) -> pd.DataFrame:
    if not path.is_file():
        raise InputValidationError(f"{label}: missing CSV file {path}")
    try:
        frame = pd.read_csv(path, keep_default_na=False)
    except Exception as exc:
        raise InputValidationError(f"{label}: cannot read CSV file {path}: {exc}") from exc
    _validate_columns(frame, expected, label)
    return frame


def _normalize_nullable_string(value: object) -> str | None:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    if value == "":
        return None
    if not isinstance(value, str):
        raise TypeError(type(value).__name__)
    return value


def _validate_string_column(
    frame: pd.DataFrame,
    column: str,
    label: str,
    *,
    nullable: bool = False,
) -> None:
    for row_number, value in enumerate(frame[column].tolist(), start=2):
        try:
            normalized = _normalize_nullable_string(value)
        except TypeError as exc:
            raise InputValidationError(
                f"{label}: {column} contains a non-string value on CSV/data row {row_number}",
            ) from exc
        if normalized is None and not nullable:
            raise InputValidationError(f"{label}: {column} contains a null or empty value on CSV/data row {row_number}")


def _numeric_column(
    frame: pd.DataFrame,
    column: str,
    label: str,
    *,
    integer: bool,
) -> np.ndarray:
    converted = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=np.float64)
    if not np.isfinite(converted).all():
        raise InputValidationError(f"{label}: {column} must contain only finite numeric values")
    if integer and not np.equal(converted, np.floor(converted)).all():
        raise InputValidationError(f"{label}: {column} must contain only integer values")
    return converted.astype(np.int64) if integer else converted


def _keys(
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    label: str,
    *,
    nullable_columns: frozenset[str] = frozenset(),
) -> list[Key]:
    for column in columns:
        _validate_string_column(frame, column, label, nullable=column in nullable_columns)

    keys = [
        tuple(_normalize_nullable_string(value) for value in values)
        for values in frame.loc[:, list(columns)].itertuples(index=False, name=None)
    ]
    if len(set(keys)) != len(keys):
        seen: set[Key] = set()
        duplicate: Key | None = None
        for key in keys:
            if key in seen:
                duplicate = key
                break
            seen.add(key)
        raise InputValidationError(f"{label}: duplicate semantic key {duplicate!r}")
    return keys


def _key_index(keys: Sequence[Key]) -> dict[Key, int]:
    return {key: index for index, key in enumerate(keys)}


def _key_sort_value(key: Key) -> tuple[tuple[bool, str], ...]:
    return tuple((value is not None, value or "") for value in key)


def _key_sample(keys: set[Key], limit: int = 5) -> list[list[str | None]]:
    return [list(key) for key in sorted(keys, key=_key_sort_value)[:limit]]


def _append_gate(gate_failures: list[str], condition: bool, message: str) -> None:
    if not condition:
        gate_failures.append(message)


def _bit_exact_float_equal(reference: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    reference_bits = np.ascontiguousarray(reference, dtype=np.float64).view(np.uint64)
    candidate_bits = np.ascontiguousarray(candidate, dtype=np.float64).view(np.uint64)
    return np.equal(reference_bits, candidate_bits)


def _difference_stats(
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    bit_exact: bool,
) -> dict[str, object]:
    if reference.size == 0:
        return {
            "exact_rows": 0,
            "maximum_absolute_difference": None,
            "mean_absolute_difference": None,
        }
    differences = np.abs(candidate.astype(np.float64) - reference.astype(np.float64))
    exact = _bit_exact_float_equal(reference, candidate) if bit_exact else np.equal(reference, candidate)
    return {
        "exact_rows": int(exact.sum()),
        "maximum_absolute_difference": float(differences.max()),
        "mean_absolute_difference": float(differences.mean()),
    }


def _load_metric(path: Path, label: str) -> tuple[pd.DataFrame, list[Key]]:
    frame = _read_parquet(path, METRIC_COLUMNS, label)
    keys = _keys(frame, METRIC_KEY, label)
    frame = frame.copy()
    for column in ("AUROC", "PRAUC"):
        frame[column] = _numeric_column(frame, column, label, integer=False)
    for column in ("Metadata_Count_0", "Metadata_Count_1"):
        frame[column] = _numeric_column(frame, column, label, integer=True)
    return frame, keys


def _metric_file_report(
    reference_root: Path,
    candidate_root: Path,
    filename: str,
    gate_failures: list[str],
) -> tuple[dict[str, object], dict[str, int]]:
    expected_rows = EXPECTED_METRIC_ROWS[filename]
    reference, reference_keys = _load_metric(reference_root / filename, f"reference/{filename}")
    candidate, candidate_keys = _load_metric(candidate_root / filename, f"candidate/{filename}")

    reference_key_set = set(reference_keys)
    candidate_key_set = set(candidate_keys)
    matched_keys = sorted(reference_key_set & candidate_key_set, key=_key_sort_value)
    reference_only = reference_key_set - candidate_key_set
    candidate_only = candidate_key_set - reference_key_set

    _append_gate(
        gate_failures,
        len(reference) == expected_rows,
        f"{filename}: reference has {len(reference)} metric rows; expected {expected_rows}",
    )
    _append_gate(
        gate_failures,
        len(candidate) == expected_rows,
        f"{filename}: candidate has {len(candidate)} metric rows; expected {expected_rows}",
    )
    _append_gate(
        gate_failures,
        reference_key_set == candidate_key_set,
        f"{filename}: metric semantic key sets differ",
    )
    for side, frame in (("reference", reference), ("candidate", candidate)):
        agg_types = frozenset(frame["Metadata_AggType"].tolist())
        _append_gate(
            gate_failures,
            agg_types == EXPECTED_AGG_TYPES,
            f"{filename}: {side} AggType domain is {sorted(agg_types)!r}; expected {sorted(EXPECTED_AGG_TYPES)!r}",
        )
        for metric in ("AUROC", "PRAUC"):
            values = frame[metric].to_numpy(dtype=np.float64)
            _append_gate(
                gate_failures,
                bool(((values >= 0.0) & (values <= 1.0)).all()),
                f"{filename}: {side} {metric} has values outside [0, 1]",
            )
        for count_column in ("Metadata_Count_0", "Metadata_Count_1"):
            values = frame[count_column].to_numpy(dtype=np.int64)
            _append_gate(
                gate_failures,
                bool((values > 0).all()),
                f"{filename}: {side} {count_column} must be positive",
            )

    reference_index = _key_index(reference_keys)
    candidate_index = _key_index(candidate_keys)
    reference_positions = [reference_index[key] for key in matched_keys]
    candidate_positions = [candidate_index[key] for key in matched_keys]
    reference_payload = reference.iloc[reference_positions].loc[:, list(METRIC_PAYLOAD)]
    candidate_payload = candidate.iloc[candidate_positions].loc[:, list(METRIC_PAYLOAD)]
    payload_equal = np.ones(len(matched_keys), dtype=bool)
    for column in METRIC_PAYLOAD:
        reference_values = reference_payload[column].to_numpy()
        candidate_values = candidate_payload[column].to_numpy()
        payload_equal &= (
            _bit_exact_float_equal(reference_values, candidate_values)
            if column in {"AUROC", "PRAUC"}
            else np.equal(reference_values, candidate_values)
        )

    by_agg_type: dict[str, object] = {}
    for agg_type in sorted(EXPECTED_AGG_TYPES):
        positions = [index for index, key in enumerate(matched_keys) if key[0] == agg_type]
        agg_reference = reference_payload.iloc[positions]
        agg_candidate = candidate_payload.iloc[positions]
        by_agg_type[agg_type] = {
            "matched_rows": len(positions),
            "payload_exact_rows": int(payload_equal[positions].sum()),
            "auroc": _difference_stats(
                agg_reference["AUROC"].to_numpy(),
                agg_candidate["AUROC"].to_numpy(),
                bit_exact=True,
            ),
            "prauc": _difference_stats(
                agg_reference["PRAUC"].to_numpy(),
                agg_candidate["PRAUC"].to_numpy(),
                bit_exact=True,
            ),
            "class_counts_exact_rows": int(
                (
                    np.equal(
                        agg_reference["Metadata_Count_0"].to_numpy(),
                        agg_candidate["Metadata_Count_0"].to_numpy(),
                    )
                    & np.equal(
                        agg_reference["Metadata_Count_1"].to_numpy(),
                        agg_candidate["Metadata_Count_1"].to_numpy(),
                    )
                ).sum(),
            ),
        }

    core = {"reference_rows": 0, "candidate_rows": 0, "matched_rows": 0, "payload_exact_rows": 0}
    if filename in EXPECTED_TOXCAST_ALL_ROWS:
        reference_core = int((reference["Metadata_AggType"] == "all").sum())
        candidate_core = int((candidate["Metadata_AggType"] == "all").sum())
        matched_core_positions = [index for index, key in enumerate(matched_keys) if key[0] == "all"]
        expected_core = EXPECTED_TOXCAST_ALL_ROWS[filename]
        _append_gate(
            gate_failures,
            reference_core == expected_core,
            f"{filename}: reference has {reference_core} AggType=all rows; expected {expected_core}",
        )
        _append_gate(
            gate_failures,
            candidate_core == expected_core,
            f"{filename}: candidate has {candidate_core} AggType=all rows; expected {expected_core}",
        )
        core = {
            "reference_rows": reference_core,
            "candidate_rows": candidate_core,
            "matched_rows": len(matched_core_positions),
            "payload_exact_rows": int(payload_equal[matched_core_positions].sum()),
        }

    report = {
        "expected_rows": expected_rows,
        "reference_rows": len(reference),
        "candidate_rows": len(candidate),
        "matched_keys": len(matched_keys),
        "reference_only_keys": len(reference_only),
        "candidate_only_keys": len(candidate_only),
        "reference_only_key_sample": _key_sample(reference_only),
        "candidate_only_key_sample": _key_sample(candidate_only),
        "payload_exact_rows": int(payload_equal.sum()),
        "by_agg_type": by_agg_type,
    }
    return report, core


def _compare_metrics(
    reference_root: Path,
    candidate_root: Path,
    gate_failures: list[str],
) -> dict[str, object]:
    files: dict[str, object] = {}
    core_totals = {"reference_rows": 0, "candidate_rows": 0, "matched_rows": 0, "payload_exact_rows": 0}
    for filename in EXPECTED_METRIC_ROWS:
        file_report, core = _metric_file_report(reference_root, candidate_root, filename, gate_failures)
        files[filename] = file_report
        for field in core_totals:
            core_totals[field] += core[field]

    core_passed = all(value == EXPECTED_TOXCAST_ALL_TOTAL for value in core_totals.values())
    _append_gate(
        gate_failures,
        core_passed,
        "ToxCast AggType=all core payload is not bit-exact across exactly 2709 matched rows",
    )
    return {
        "files": files,
        "toxcast_all_core": {
            "expected_rows": EXPECTED_TOXCAST_ALL_TOTAL,
            **core_totals,
            "passed": core_passed,
        },
    }


def _load_pod(path: Path, expected: frozenset[str], label: str) -> tuple[pd.DataFrame, list[Key]]:
    frame = _read_csv(path, expected, label)
    keys = _keys(frame, POD_KEY, label, nullable_columns=frozenset({"OASIS_ID"}))
    frame = frame.copy()
    for column in POD_VALUES:
        frame[column] = _numeric_column(frame, column, label, integer=False)
    if "Bioactivity_POD" in frame:
        normalized = frame["Bioactivity_POD"].astype(str).str.lower()
        if not normalized.isin({"true", "false"}).all():
            raise InputValidationError(f"{label}: Bioactivity_POD must contain only true/false values")
        frame["Bioactivity_POD"] = normalized == "true"
    return frame, keys


def _pod_validity_report(
    frame: pd.DataFrame,
    filename: str,
    side: str,
    gate_failures: list[str],
) -> dict[str, int]:
    pod = frame["POD_um"].to_numpy(dtype=np.float64)
    lower = frame["POD_um_l"].to_numpy(dtype=np.float64)
    upper = frame["POD_um_u"].to_numpy(dtype=np.float64)
    nonpositive = int(((pod <= 0.0) | (lower <= 0.0) | (upper <= 0.0)).sum())
    invalid_bounds = int(((lower > pod) | (pod > upper)).sum())
    _append_gate(
        gate_failures,
        nonpositive == 0,
        f"{filename}: {side} has {nonpositive} rows with non-positive POD values or bounds",
    )
    _append_gate(
        gate_failures,
        invalid_bounds == 0,
        f"{filename}: {side} has {invalid_bounds} rows with invalid POD bounds",
    )
    return {"nonpositive_rows": nonpositive, "invalid_bound_rows": invalid_bounds}


def _pod_file_report(
    reference_root: Path,
    candidate_root: Path,
    filename: str,
    expected_columns: frozenset[str],
    gate_failures: list[str],
) -> dict[str, object]:
    reference, reference_keys = _load_pod(reference_root / filename, expected_columns, f"reference/{filename}")
    candidate, candidate_keys = _load_pod(candidate_root / filename, expected_columns, f"candidate/{filename}")
    reference_validity = _pod_validity_report(reference, filename, "reference", gate_failures)
    candidate_validity = _pod_validity_report(candidate, filename, "candidate", gate_failures)

    reference_key_set = set(reference_keys)
    candidate_key_set = set(candidate_keys)
    # Preserve SQL/Polars join semantics for the required triple: a missing
    # OASIS_ID is valid and participates in duplicate detection, but null does
    # not equal null across the two inputs.
    matched_key_set = {key for key in reference_key_set & candidate_key_set if key[0] is not None}
    matched_keys = sorted(matched_key_set, key=_key_sort_value)
    reference_only = reference_key_set - matched_key_set
    candidate_only = candidate_key_set - matched_key_set
    reference_coverage = len(matched_keys) / len(reference)
    candidate_coverage = len(matched_keys) / len(candidate)

    _append_gate(
        gate_failures,
        reference_coverage >= POD_MIN_BIDIRECTIONAL_COVERAGE,
        f"{filename}: candidate covers {reference_coverage:.3%} of reference POD keys; minimum is 80%",
    )
    _append_gate(
        gate_failures,
        candidate_coverage >= POD_MIN_BIDIRECTIONAL_COVERAGE,
        f"{filename}: reference covers {candidate_coverage:.3%} of candidate POD keys; minimum is 80%",
    )

    reference_index = _key_index(reference_keys)
    candidate_index = _key_index(candidate_keys)
    reference_positions = [reference_index[key] for key in matched_keys]
    candidate_positions = [candidate_index[key] for key in matched_keys]
    reference_pod = reference.iloc[reference_positions]["POD_um"].to_numpy(dtype=np.float64)
    candidate_pod = candidate.iloc[candidate_positions]["POD_um"].to_numpy(dtype=np.float64)
    comparable = (reference_pod > 0.0) & (candidate_pod > 0.0)
    relative_difference = np.abs(candidate_pod[comparable] - reference_pod[comparable]) / np.abs(
        reference_pod[comparable],
    )
    within_one_percent = (relative_difference <= POD_ONE_PERCENT_THRESHOLD) | np.isclose(
        relative_difference,
        POD_ONE_PERCENT_THRESHOLD,
        rtol=0.0,
        atol=POD_RELATIVE_BOUNDARY_ATOL,
    )
    within_one_percent_fraction = float(within_one_percent.mean()) if within_one_percent.size else 0.0
    median_relative_difference = float(np.median(relative_difference)) if relative_difference.size else None
    maximum_relative_difference = float(relative_difference.max()) if relative_difference.size else None
    material_tail = relative_difference > POD_MATERIAL_TAIL_THRESHOLD
    comparable_pod_rows = int(comparable.sum())
    excluded_nonpositive_pod_point_rows = len(matched_keys) - comparable_pod_rows

    _append_gate(
        gate_failures,
        within_one_percent_fraction >= POD_MIN_WITHIN_ONE_PERCENT,
        f"{filename}: {within_one_percent_fraction:.3%} of comparable POD point estimates are within 1%; "
        "minimum is 85%",
    )
    median_passed = (
        median_relative_difference is not None and median_relative_difference <= POD_MAX_MEDIAN_RELATIVE_DIFFERENCE
    )
    _append_gate(
        gate_failures,
        median_passed,
        f"{filename}: median reference-relative POD difference is {median_relative_difference!r}; maximum is 1e-5",
    )

    bioactivity_exact_rows: int | None = None
    if "Bioactivity_POD" in expected_columns:
        reference_bioactivity = reference.iloc[reference_positions]["Bioactivity_POD"].to_numpy(dtype=bool)
        candidate_bioactivity = candidate.iloc[candidate_positions]["Bioactivity_POD"].to_numpy(dtype=bool)
        bioactivity_exact_rows = int(np.equal(reference_bioactivity, candidate_bioactivity).sum())

    row_count_relative_drift = abs(len(candidate) - len(reference)) / max(len(reference), len(candidate))
    return {
        "reference_rows": len(reference),
        "candidate_rows": len(candidate),
        "matched_keys": len(matched_keys),
        "reference_key_coverage": reference_coverage,
        "candidate_key_coverage": candidate_coverage,
        "reference_only_keys": len(reference_only),
        "candidate_only_keys": len(candidate_only),
        "reference_only_key_sample": _key_sample(reference_only),
        "candidate_only_key_sample": _key_sample(candidate_only),
        "comparable_pod_rows": comparable_pod_rows,
        "excluded_nonpositive_pod_point_rows": excluded_nonpositive_pod_point_rows,
        "within_one_percent_rows": int(within_one_percent.sum()),
        "within_one_percent_fraction": within_one_percent_fraction,
        "median_reference_relative_difference": median_relative_difference,
        "maximum_reference_relative_difference": maximum_relative_difference,
        "over_ten_percent_rows": int(material_tail.sum()),
        "over_ten_percent_fraction": float(material_tail.mean()) if material_tail.size else 0.0,
        "row_count_relative_drift": row_count_relative_drift,
        "bioactivity_pod_exact_rows": bioactivity_exact_rows,
        "reference_validity": reference_validity,
        "candidate_validity": candidate_validity,
    }


def _compare_pods(
    reference_root: Path,
    candidate_root: Path,
    gate_failures: list[str],
) -> dict[str, object]:
    return {
        filename: _pod_file_report(reference_root, candidate_root, filename, columns, gate_failures)
        for filename, columns in POD_FILES.items()
    }


def _load_hit_summary(path: Path, label: str) -> tuple[pd.DataFrame, list[Key]]:
    frame = _read_csv(path, HIT_SUMMARY_COLUMNS, label)
    keys = _keys(frame, HIT_SUMMARY_KEY, label, nullable_columns=frozenset({"OASIS_ID"}))
    for column in HIT_COLUMNS:
        values = set(frame[column].tolist())
        if not values <= {"Yes", "No"}:
            raise InputValidationError(f"{label}: {column} must contain only Yes/No values")
    return frame, keys


def _compare_hit_summary(
    reference_root: Path,
    candidate_root: Path,
    gate_failures: list[str],
) -> dict[str, object]:
    reference, reference_keys = _load_hit_summary(
        reference_root / HIT_SUMMARY_FILE,
        f"reference/{HIT_SUMMARY_FILE}",
    )
    candidate, candidate_keys = _load_hit_summary(
        candidate_root / HIT_SUMMARY_FILE,
        f"candidate/{HIT_SUMMARY_FILE}",
    )
    reference_key_set = set(reference_keys)
    candidate_key_set = set(candidate_keys)
    matched_keys = sorted(reference_key_set & candidate_key_set, key=_key_sort_value)
    reference_only = reference_key_set - candidate_key_set
    candidate_only = candidate_key_set - reference_key_set
    _append_gate(
        gate_failures,
        reference_key_set == candidate_key_set,
        f"{HIT_SUMMARY_FILE}: compound key sets differ",
    )

    reference_index = _key_index(reference_keys)
    candidate_index = _key_index(candidate_keys)
    reference_positions = [reference_index[key] for key in matched_keys]
    candidate_positions = [candidate_index[key] for key in matched_keys]
    per_column_exact: dict[str, int] = {}
    all_equal = np.ones(len(matched_keys), dtype=bool)
    for column in HIT_COLUMNS:
        equal = np.equal(
            reference.iloc[reference_positions][column].to_numpy(),
            candidate.iloc[candidate_positions][column].to_numpy(),
        )
        per_column_exact[column] = int(equal.sum())
        all_equal &= equal
    return {
        "reference_rows": len(reference),
        "candidate_rows": len(candidate),
        "matched_keys": len(matched_keys),
        "reference_only_keys": len(reference_only),
        "candidate_only_keys": len(candidate_only),
        "reference_only_key_sample": _key_sample(reference_only),
        "candidate_only_key_sample": _key_sample(candidate_only),
        "all_hit_calls_exact_rows": int(all_equal.sum()),
        "per_column_exact_rows": per_column_exact,
    }


def _load_enrichment(path: Path, label: str) -> tuple[pd.DataFrame, list[Key]]:
    frame = _read_csv(path, ENRICHMENT_COLUMNS, label)
    keys = _keys(frame, ENRICHMENT_KEY, label)
    frame = frame.copy()
    for column in ENRICHMENT_INTEGER_COLUMNS:
        frame[column] = _numeric_column(frame, column, label, integer=True)
    for column in ENRICHMENT_FLOAT_COLUMNS:
        frame[column] = _numeric_column(frame, column, label, integer=False)
    parsed_overlap_sets: list[frozenset[str]] = []
    for row_number, (value, overlap_size) in enumerate(
        zip(frame["overlap_hits"].tolist(), frame["overlap_size"].tolist(), strict=True),
        start=2,
    ):
        if not isinstance(value, str):
            raise InputValidationError(
                f"{label}: overlap_hits contains a non-string value on CSV row {row_number}",
            )
        parsed_overlap_sets.append(_parse_overlap_hits(value, overlap_size, label, row_number))
    frame["__overlap_hit_set"] = parsed_overlap_sets
    return frame, keys


def _parse_overlap_hits(value: str, expected_size: int, label: str, row_number: int) -> frozenset[str]:
    """Parse the notebook's comma-joined IDs without splitting commas in compound names."""
    if not value and expected_size == 0:
        return frozenset()
    position = 0
    members: list[str] = []
    while position < len(value):
        match = OVERLAP_MEMBER_PATTERN.match(value, position)
        if match is None:
            raise InputValidationError(
                f"{label}: overlap_hits cannot be parsed using the observed Unique_ID encoding on CSV row {row_number}",
            )
        members.append(match.group("member"))
        position = match.end()
    member_set = frozenset(members)
    if len(members) != expected_size or len(member_set) != expected_size:
        raise InputValidationError(
            f"{label}: overlap_hits encodes {len(member_set)} unique members but overlap_size is "
            f"{expected_size} on CSV row {row_number}",
        )
    return member_set


def _enrichment_validity_report(
    frame: pd.DataFrame,
    filename: str,
    side: str,
    gate_failures: list[str],
) -> dict[str, object]:
    target_sizes = frame["target_set_size"].to_numpy(dtype=np.int64)
    hit_sizes = frame["hit_list_size"].to_numpy(dtype=np.int64)
    universe_sizes = frame["universe_size"].to_numpy(dtype=np.int64)
    overlap_sizes = frame["overlap_size"].to_numpy(dtype=np.int64)
    p_values = frame["p_value"].to_numpy(dtype=np.float64)
    fdr_values = frame["fdr"].to_numpy(dtype=np.float64)
    unique_hit_sizes = sorted(set(hit_sizes.tolist()))

    valid_target_sizes = bool(((target_sizes > 0) & (target_sizes <= universe_sizes)).all())
    valid_hit_sizes = (
        len(unique_hit_sizes) == 1 and unique_hit_sizes[0] > 0 and bool((hit_sizes <= universe_sizes).all())
    )
    valid_overlap_sizes = bool(
        ((overlap_sizes >= 0) & (overlap_sizes <= target_sizes) & (overlap_sizes <= hit_sizes)).all(),
    )
    valid_probability_ranges = bool(
        ((p_values >= 0.0) & (p_values <= 1.0) & (fdr_values >= 0.0) & (fdr_values <= 1.0)).all(),
    )
    expected_universe = bool((universe_sizes == EXPECTED_ENRICHMENT_UNIVERSE).all())

    _append_gate(
        gate_failures,
        valid_target_sizes,
        f"{filename}: {side} target_set_size values are not all within [1, universe_size]",
    )
    _append_gate(
        gate_failures,
        valid_hit_sizes,
        f"{filename}: {side} hit_list_size must be one positive constant no larger than universe_size",
    )
    _append_gate(
        gate_failures,
        valid_overlap_sizes,
        f"{filename}: {side} overlap_size values are outside their valid ranges",
    )
    _append_gate(
        gate_failures,
        valid_probability_ranges,
        f"{filename}: {side} p_value or fdr values are outside [0, 1]",
    )
    _append_gate(
        gate_failures,
        expected_universe,
        f"{filename}: {side} universe_size is not {EXPECTED_ENRICHMENT_UNIVERSE} on every row",
    )
    return {
        "hit_list_sizes": unique_hit_sizes,
        "target_sizes_valid": valid_target_sizes,
        "hit_list_size_valid": valid_hit_sizes,
        "overlap_sizes_valid": valid_overlap_sizes,
        "probability_ranges_valid": valid_probability_ranges,
        "universe_size_valid": expected_universe,
    }


def _enrichment_file_report(
    reference_root: Path,
    candidate_root: Path,
    filename: str,
    gate_failures: list[str],
) -> dict[str, object]:
    reference, reference_keys = _load_enrichment(reference_root / filename, f"reference/{filename}")
    candidate, candidate_keys = _load_enrichment(candidate_root / filename, f"candidate/{filename}")
    reference_validity = _enrichment_validity_report(reference, filename, "reference", gate_failures)
    candidate_validity = _enrichment_validity_report(candidate, filename, "candidate", gate_failures)

    reference_key_set = set(reference_keys)
    candidate_key_set = set(candidate_keys)
    matched_keys = sorted(reference_key_set & candidate_key_set, key=_key_sort_value)
    reference_only = reference_key_set - candidate_key_set
    candidate_only = candidate_key_set - reference_key_set
    _append_gate(
        gate_failures,
        len(reference) == EXPECTED_ENRICHMENT_ROWS,
        f"{filename}: reference has {len(reference)} target sets; expected {EXPECTED_ENRICHMENT_ROWS}",
    )
    _append_gate(
        gate_failures,
        len(candidate) == EXPECTED_ENRICHMENT_ROWS,
        f"{filename}: candidate has {len(candidate)} target sets; expected {EXPECTED_ENRICHMENT_ROWS}",
    )
    _append_gate(
        gate_failures,
        reference_key_set == candidate_key_set,
        f"{filename}: target_set key sets differ",
    )

    reference_index = _key_index(reference_keys)
    candidate_index = _key_index(candidate_keys)
    reference_positions = [reference_index[key] for key in matched_keys]
    candidate_positions = [candidate_index[key] for key in matched_keys]
    reference_matched = reference.iloc[reference_positions]
    candidate_matched = candidate.iloc[candidate_positions]
    target_sizes_equal = np.equal(
        reference_matched["target_set_size"].to_numpy(),
        candidate_matched["target_set_size"].to_numpy(),
    )
    _append_gate(
        gate_failures,
        bool(target_sizes_equal.all()) and len(matched_keys) == EXPECTED_ENRICHMENT_ROWS,
        f"{filename}: target_set_size values do not match exactly for all {EXPECTED_ENRICHMENT_ROWS} target sets",
    )

    fdr_equal = np.equal(
        reference_matched["fdr"].to_numpy(dtype=np.float64),
        candidate_matched["fdr"].to_numpy(dtype=np.float64),
    )
    p_value_equal = np.equal(
        reference_matched["p_value"].to_numpy(dtype=np.float64),
        candidate_matched["p_value"].to_numpy(dtype=np.float64),
    )
    overlap_size_equal = np.equal(
        reference_matched["overlap_size"].to_numpy(dtype=np.int64),
        candidate_matched["overlap_size"].to_numpy(dtype=np.int64),
    )
    overlap_sets_equal = [
        reference_value == candidate_value
        for reference_value, candidate_value in zip(
            reference_matched["__overlap_hit_set"].tolist(),
            candidate_matched["__overlap_hit_set"].tolist(),
            strict=True,
        )
    ]
    return {
        "expected_target_sets": EXPECTED_ENRICHMENT_ROWS,
        "reference_rows": len(reference),
        "candidate_rows": len(candidate),
        "matched_target_sets": len(matched_keys),
        "reference_only_target_sets": len(reference_only),
        "candidate_only_target_sets": len(candidate_only),
        "reference_only_target_set_sample": _key_sample(reference_only),
        "candidate_only_target_set_sample": _key_sample(candidate_only),
        "target_set_size_exact_rows": int(target_sizes_equal.sum()),
        "overlap_size_exact_rows": int(overlap_size_equal.sum()),
        "overlap_hit_sets_exact_rows": int(sum(overlap_sets_equal)),
        "p_value_exact_rows": int(p_value_equal.sum()),
        "fdr_exact_rows": int(fdr_equal.sum()),
        "reference_validity": reference_validity,
        "candidate_validity": candidate_validity,
    }


def _compare_enrichment(
    reference_root: Path,
    candidate_root: Path,
    gate_failures: list[str],
) -> dict[str, object]:
    return {
        filename: _enrichment_file_report(reference_root, candidate_root, filename, gate_failures)
        for filename in ENRICHMENT_FILES
    }


def _resolve_input_directory(path: str | Path, label: str) -> Path:
    candidate = Path(path).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise InputValidationError(f"{label} directory does not exist or cannot be resolved: {candidate}") from exc
    if not resolved.is_dir():
        raise InputValidationError(f"{label} path is not a directory: {resolved}")
    return resolved


def verify_compiled_results(reference: str | Path, candidate: str | Path) -> VerificationResult:
    """Compare two compiled-results directories without modifying either one."""
    reference_root = _resolve_input_directory(reference, "reference")
    candidate_root = _resolve_input_directory(candidate, "candidate")
    if reference_root == candidate_root:
        raise InputValidationError("reference and candidate directories resolve to the same location")

    gate_failures: list[str] = []
    metrics = _compare_metrics(reference_root, candidate_root, gate_failures)
    pods = _compare_pods(reference_root, candidate_root, gate_failures)
    hit_summary = _compare_hit_summary(reference_root, candidate_root, gate_failures)
    enrichment = _compare_enrichment(reference_root, candidate_root, gate_failures)
    report: dict[str, object] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass" if not gate_failures else "fail",
        "reference": str(reference_root),
        "candidate": str(candidate_root),
        "gate_failures": gate_failures.copy(),
        "metrics": metrics,
        "pods": pods,
        "hit_summary": hit_summary,
        "enrichment": enrichment,
        "excluded_artifacts": [
            "motive_highexp_PHH.parquet",
            "mtt_higher_targets.csv",
            "mtt_lower_targets.csv",
            "SI_tables/readme.txt",
        ],
    }
    return VerificationResult(report=report, gate_failures=tuple(gate_failures))


def _validated_report_path(path: str | Path, reference_root: Path, candidate_root: Path) -> Path:
    report_path = Path(path).expanduser().resolve(strict=False)
    if report_path.is_relative_to(reference_root) or report_path.is_relative_to(candidate_root):
        raise InputValidationError("JSON report path must not be inside either input directory")
    if report_path.exists() and report_path.is_dir():
        raise InputValidationError(f"JSON report path is a directory: {report_path}")
    if not report_path.parent.is_dir():
        raise InputValidationError(f"JSON report parent directory does not exist: {report_path.parent}")
    return report_path


def _write_json_report(report: dict[str, object], path: Path) -> None:
    try:
        serialized = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
        path.write_text(serialized, encoding="utf-8")
    except (OSError, ValueError, TypeError) as exc:
        raise InputValidationError(f"cannot write JSON report {path}: {exc}") from exc


def _mapping(value: object) -> dict[str, object]:
    return cast("dict[str, object]", value)


def _format_float(value: object, format_specification: str) -> str:
    if value is None:
        return "n/a"
    return format(cast("float", value), format_specification)


def _print_human_summary(result: VerificationResult) -> None:
    """Print the auditable comparison statistics that underlie the exit status."""
    metrics = _mapping(result.report["metrics"])
    metric_files = _mapping(metrics["files"])
    print("Metric Parquets:")
    for filename in EXPECTED_METRIC_ROWS:
        file_report = _mapping(metric_files[filename])
        by_agg_type = _mapping(file_report["by_agg_type"])
        agg_summaries = []
        for agg_type in sorted(EXPECTED_AGG_TYPES):
            agg_report = _mapping(by_agg_type[agg_type])
            agg_summaries.append(
                f"{agg_type} exact {agg_report['payload_exact_rows']}/{agg_report['matched_rows']}",
            )
        print(
            f"  {filename}: rows {file_report['reference_rows']}/{file_report['candidate_rows']} "
            f"(expected {file_report['expected_rows']}), matched keys {file_report['matched_keys']}; "
            + ", ".join(agg_summaries),
        )
    core = _mapping(metrics["toxcast_all_core"])
    print(
        f"  ToxCast all core: exact {core['payload_exact_rows']}/{core['expected_rows']}, "
        f"matched {core['matched_rows']} ({'pass' if core['passed'] else 'fail'})",
    )

    pods = _mapping(result.report["pods"])
    print("POD CSVs:")
    for filename in POD_FILES:
        file_report = _mapping(pods[filename])
        print(
            f"  {filename}: rows {file_report['reference_rows']}/{file_report['candidate_rows']}, "
            f"matched {file_report['matched_keys']}, coverage "
            f"{_format_float(file_report['reference_key_coverage'], '.1%')}/"
            f"{_format_float(file_report['candidate_key_coverage'], '.1%')}, comparable "
            f"{file_report['comparable_pod_rows']}/{file_report['matched_keys']} "
            f"(excluded non-positive POD points {file_report['excluded_nonpositive_pod_point_rows']}), "
            f"within 1% "
            f"{file_report['within_one_percent_rows']}/{file_report['comparable_pod_rows']} "
            f"({_format_float(file_report['within_one_percent_fraction'], '.1%')}), median rel "
            f"{_format_float(file_report['median_reference_relative_difference'], '.3g')}, "
            f">10% tail {_format_float(file_report['over_ten_percent_fraction'], '.1%')} "
            f"({file_report['over_ten_percent_rows']}/{file_report['comparable_pod_rows']} rows), max rel "
            f"{_format_float(file_report['maximum_reference_relative_difference'], '.3g')}, row drift "
            f"{_format_float(file_report['row_count_relative_drift'], '.3%')}",
        )

    hit_summary = _mapping(result.report["hit_summary"])
    print(
        f"Hit summary: rows {hit_summary['reference_rows']}/{hit_summary['candidate_rows']}, "
        f"matched keys {hit_summary['matched_keys']}, all hit calls exact "
        f"{hit_summary['all_hit_calls_exact_rows']}/{hit_summary['matched_keys']}",
    )

    enrichment = _mapping(result.report["enrichment"])
    print("Enrichment CSVs:")
    for filename in ENRICHMENT_FILES:
        file_report = _mapping(enrichment[filename])
        reference_validity = _mapping(file_report["reference_validity"])
        candidate_validity = _mapping(file_report["candidate_validity"])
        print(
            f"  {filename}: rows {file_report['reference_rows']}/{file_report['candidate_rows']}, "
            f"matched target sets {file_report['matched_target_sets']}, universe valid "
            f"{reference_validity['universe_size_valid']}/{candidate_validity['universe_size_valid']}, "
            f"hit-list sizes {reference_validity['hit_list_sizes']}/{candidate_validity['hit_list_sizes']}, "
            f"target sizes exact {file_report['target_set_size_exact_rows']}/{file_report['matched_target_sets']}, "
            f"overlap sets exact {file_report['overlap_hit_sets_exact_rows']}/{file_report['matched_target_sets']}, "
            f"FDR exact {file_report['fdr_exact_rows']}/{file_report['matched_target_sets']}",
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare regenerated Axiom compiled results with a reference directory.",
    )
    parser.add_argument("--reference", required=True, help="Reference compiled_results directory")
    parser.add_argument("--candidate", required=True, help="Regenerated compiled_results directory")
    parser.add_argument("--json-report", help="Optional report path outside both input directories")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line verifier and return its process exit code."""
    arguments = _parser().parse_args(argv)
    try:
        reference_root = _resolve_input_directory(arguments.reference, "reference")
        candidate_root = _resolve_input_directory(arguments.candidate, "candidate")
        report_path = (
            _validated_report_path(arguments.json_report, reference_root, candidate_root)
            if arguments.json_report
            else None
        )
        result = verify_compiled_results(reference_root, candidate_root)
        if report_path is not None:
            _write_json_report(result.report, report_path)
    except InputValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2

    _print_human_summary(result)
    if result.passed:
        print(
            "PASS: all configured reproducibility gates passed; "
            "non-core metric payloads, hit calls, and enrichment hit-list, overlap, p-value, and FDR "
            "differences are diagnostic",
        )
        return 0
    print(f"FAIL: {len(result.gate_failures)} reproducibility gate(s) failed", file=sys.stderr)
    for failure in result.gate_failures:
        print(f"- {failure}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
