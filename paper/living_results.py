import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium")

with app.setup:
    import hashlib
    import json
    from collections import Counter
    from pathlib import Path
    from typing import Any

    import marimo as mo
    import tomllib

    NOTEBOOK_PATH = Path(__file__).resolve()
    REPOSITORY_ROOT = NOTEBOOK_PATH.parents[1]
    REPORT_PATH = REPOSITORY_ROOT / "paper/reproduction/report.json"
    SOURCE_MANIFEST_PATH = REPOSITORY_ROOT / "paper/sources/manifest.toml"
    FIGURE_PATHS = {
        "activity": REPOSITORY_ROOT / "paper/reproduction/pod-summary.svg",
        "toxcast": REPOSITORY_ROOT / "paper/reproduction/toxcast-summary.svg",
        "coverage": REPOSITORY_ROOT / "paper/reproduction/evidence-coverage.svg",
    }
    RENDERED_STATE_PATHS = (
        NOTEBOOK_PATH,
        REPORT_PATH,
        SOURCE_MANIFEST_PATH,
        *FIGURE_PATHS.values(),
    )
    REQUIRED_ANALYSES = {
        "activity_pods",
        "classifier",
        "regression_enrichment",
        "sources_design",
        "toxcast",
    }
    REQUIRED_CONCLUSION_GATES = {
        "activity_pods": {
            "complete_case_median_order",
            "general_morphology_count_exceeds_mt",
        },
        "classifier": {
            "all_concentration_not_worse",
            "allpod_small_effects",
            "allpodcc_filter_direction",
            "axiom_above_baselines",
            "cellbased_not_cellfree",
            "conclusion_003",
            "prauc_no_material_improvement",
            "representation_small_effects",
            "table2",
        },
    }
    RESULT_SECTION_TARGETS = {
        "Bioactivity and sensitivity": (
            "ACTIVITY-001",
            "FIG-2A",
            "BIOACTIVITY-001",
            "FIG-2B",
            "FIG-2C",
            "BIOACTIVITY-003",
            "FIG-2D",
            "TABLE-S2",
            "TABLE-S3",
            "TABLE-S4",
            "CONCLUSION-001",
        ),
        "Paired cellular responses": (
            "TABLE-2",
            "CLASSIFIER-001",
            "ENRICH-003",
            "ENRICH-004",
            "INTERPRETATION-001",
        ),
        "ToxCast transfer": (
            "TOXCAST-001",
            "TOXCAST-002",
            "TOXCAST-003",
            "FIG-3AB",
            "FIG-3C",
            "SFIG-3",
            "TABLE-S5",
            "CONCLUSION-002",
        ),
        "Robustness choices": (
            "FILTER-001",
            "FILTER-002",
            "FIG-4A",
            "REPRESENTATION-001",
            "FIG-4B",
            "SFIG-4",
            "CONCLUSION-003",
        ),
    }


@app.function
def counts_by_field(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(item[key]) for item in items).items()))


@app.function
def validate_contract(report: dict[str, Any], manifest: dict[str, Any]) -> None:
    required_report_keys = {
        "schema_version",
        "mode",
        "ledger_sha256",
        "summary",
        "analyses",
        "targets",
    }
    missing_report_keys = sorted(required_report_keys - report.keys())
    if missing_report_keys:
        raise ValueError(f"Report is missing keys: {missing_report_keys}")
    if report["schema_version"] != 3:
        raise ValueError(f"Expected report schema 3, found {report['schema_version']!r}")
    if report["mode"] != "tracked":
        raise ValueError("The living paper accepts only the committed tracked-artifact report.")
    if not isinstance(report["ledger_sha256"], str) or len(report["ledger_sha256"]) != 64:
        raise ValueError("Report ledger_sha256 must be a 64-character digest.")

    targets = report["targets"]
    if not isinstance(targets, list) or not targets:
        raise ValueError("Report targets must be a non-empty list.")
    target_ids = [str(target["id"]) for target in targets]
    duplicate_ids = sorted(target_id for target_id, count in Counter(target_ids).items() if count > 1)
    if duplicate_ids:
        raise ValueError(f"Report contains duplicate target IDs: {duplicate_ids}")

    summary = report["summary"]
    if summary["total"] != len(targets):
        raise ValueError("Report summary total does not match its target inventory.")
    count_contract = {
        "acceptance_class_counts": "acceptance_class",
        "evidence_strength_counts": "evidence_strength",
        "execution_outcome_counts": "execution_outcome",
        "ledger_status_counts": "ledger_status",
    }
    for summary_key, target_key in count_contract.items():
        if summary[summary_key] != counts_by_field(targets, target_key):
            raise ValueError(f"Report summary {summary_key} does not match target field {target_key}.")

    failed_checks = [
        check["id"] for target in targets for check in target.get("checks", []) if check.get("passed") is not True
    ]
    if failed_checks:
        raise ValueError(f"Report contains failed acceptance checks: {failed_checks}")

    missing_analyses = sorted(REQUIRED_ANALYSES - report["analyses"].keys())
    if missing_analyses:
        raise ValueError(f"Report is missing analyses: {missing_analyses}")

    target_index = {target["id"]: target for target in targets}
    for section_name, section_ids in RESULT_SECTION_TARGETS.items():
        for target_id in section_ids:
            if target_id not in target_index:
                raise ValueError(f"{section_name} references missing target {target_id}.")
            if target_index[target_id]["execution_outcome"] != "checked":
                raise ValueError(f"{section_name} includes non-checked target {target_id}.")

    required_manifest_keys = {"article_title", "doi", "publication", "source"}
    missing_manifest_keys = sorted(required_manifest_keys - manifest.keys())
    if missing_manifest_keys:
        raise ValueError(f"Source manifest is missing keys: {missing_manifest_keys}")
    canonical_sources = [source for source in manifest["source"] if source["canonical"]]
    if not canonical_sources:
        raise ValueError("Source manifest contains no canonical publication source.")


@app.function
def load_contract(
    report_path: Path = REPORT_PATH,
    manifest_path: Path = SOURCE_MANIFEST_PATH,
) -> tuple[dict[str, Any], dict[str, Any]]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    validate_contract(report, manifest)
    return report, manifest


@app.function
def rendered_state_sha256(paths: tuple[Path, ...] = RENDERED_STATE_PATHS) -> str:
    digest = hashlib.sha256()
    for path in paths:
        relative_path = path.relative_to(REPOSITORY_ROOT).as_posix()
        digest.update(relative_path.encode("ascii"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


@app.function
def conclusion_gate_failures(report: dict[str, Any]) -> list[str]:
    failures = []
    for analysis_name, required_gates in REQUIRED_CONCLUSION_GATES.items():
        available_gates = report["analyses"][analysis_name]["conclusion_gates"]
        failures.extend(
            f"{analysis_name}.{gate_name}"
            for gate_name in sorted(required_gates)
            if available_gates.get(gate_name) is not True
        )
    return failures


@app.function
def result_target_ids() -> tuple[str, ...]:
    return tuple(target_id for section_ids in RESULT_SECTION_TARGETS.values() for target_id in section_ids)


@app.function
def target_rows(
    report: dict[str, Any],
    *,
    outcomes: set[str] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for target in report["targets"]:
        if outcomes is not None and target["execution_outcome"] not in outcomes:
            continue
        rows.append(
            {
                "Target": target["id"],
                "Result": target["description"],
                "Execution": target["execution_outcome"],
                "Ledger": target["ledger_status"],
                "Evidence": f"paper/{target['evidence']}",
                "Deviation": target["deviation"],
            }
        )
    return rows


@app.function
def mt_enrichment_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    allowed_files = {"mtt_higher_targets.csv", "mtt_lower_targets.csv"}
    return [
        {
            "Selected set": file_name.removesuffix("_targets.csv").replace("_", " "),
            "Selected wells": file_data["hit_list_size"],
            "Significant target sets (FDR < 0.05)": file_data["significant_count"],
        }
        for file_name, file_data in report["analyses"]["regression_enrichment"]["files"].items()
        if file_name in allowed_files
    ]


@app.function
def format_metric(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


@app.cell
def _():
    report, source_manifest = load_contract()
    gate_failures = conclusion_gate_failures(report)
    rendered_digest = rendered_state_sha256()
    return gate_failures, rendered_digest, report, source_manifest


@app.cell
def _(rendered_digest, report, source_manifest):
    paper_title = source_manifest["article_title"]
    publication = source_manifest["publication"]
    doi = source_manifest["doi"]
    ledger_digest = report["ledger_sha256"]
    mo.md(
        f"""
        # Reproducible Results: {paper_title}

        This is a short, repository-backed Results paper for [{publication}](https://doi.org/{doi}).
        Every number below is read from the committed report contract at `paper/reproduction/report.json`.
        The report was generated from ledger `{ledger_digest}`.
        The rendered notebook state has digest `{rendered_digest}`.
        """
    )
    return


@app.cell
def _(gate_failures, report):
    if gate_failures:
        gate_message = (
            "One or more conclusion gates no longer pass: "
            + ", ".join(f"`{gate}`" for gate in gate_failures)
            + ". The numerical tables remain visible, but the corresponding prose conclusion requires review."
        )
        evidence_callout = mo.callout(mo.md(gate_message), kind="danger", title="Conclusion review required")
    else:
        evidence_callout = mo.callout(
            mo.md("All conclusion gates used by this short paper pass in the committed report."),
            kind="success",
            title="Current interpretation gates",
        )
    boundary_callout = mo.callout(
        mo.md(
            f"""
            This is a **tracked-artifact audit**, not proof that every upstream workflow has been rerun from raw data.
            Of {report["summary"]["total"]} paper targets, {report["summary"]["execution_outcome_counts"].get("checked", 0)} are checked against tracked inputs, {report["summary"]["execution_outcome_counts"].get("documentary-only", 0)} are documentary-only, {report["summary"]["execution_outcome_counts"].get("blocked", 0)} are blocked, and {report["summary"]["execution_outcome_counts"].get("out-of-scope", 0)} is out of scope.
            Deviations are expected and remain part of the result.
            """
        ),
        kind="warn",
        title="Evidence boundary",
    )
    mo.vstack([boundary_callout, evidence_callout])
    return


@app.cell
def _(report):
    execution_counts = report["summary"]["execution_outcome_counts"]
    ledger_counts = report["summary"]["ledger_status_counts"]
    overview_rows = [
        {"Measure": "All paper targets", "Count": report["summary"]["total"]},
        {
            "Measure": "Checked against tracked inputs",
            "Count": execution_counts.get("checked", 0),
        },
        {
            "Measure": "Documentary-only execution",
            "Count": execution_counts.get("documentary-only", 0),
        },
        {
            "Measure": "Blocked execution",
            "Count": execution_counts.get("blocked", 0),
        },
        {
            "Measure": "Historical ledger: reproduced",
            "Count": ledger_counts.get("reproduced", 0),
        },
        {
            "Measure": "Historical ledger: reproduced with deviation",
            "Count": ledger_counts.get("reproduced-with-deviation", 0),
        },
    ]
    mo.vstack(
        [
            mo.md("## Results at a glance"),
            mo.ui.table(
                overview_rows,
                selection=None,
                pagination=False,
                show_search=False,
                show_download=False,
            ),
        ]
    )
    return


@app.cell
def _(gate_failures, report):
    activity = report["analyses"]["activity_pods"]
    hit_counts = activity["hit_summary_counts"]
    median_pods = activity["figure_2d"]["median_pod_um"]
    activity_gate_names = REQUIRED_CONCLUSION_GATES["activity_pods"]
    activity_passes = not any(f"activity_pods.{gate_name}" in gate_failures for gate_name in activity_gate_names)
    activity_conclusion = (
        "The tracked results support the paper's practical conclusion: Cell Painting detects more bioactivity and reaches lower PODs than the paired cytotoxicity assays."
        if activity_passes
        else "The current tracked results do not pass every gate required for the paper's bioactivity and POD conclusion."
    )
    activity_hit_rows = [
        {"Assay": "Cell Painting", "Active compounds": hit_counts["Cell_Painting_hit"]},
        {"Assay": "MT", "Active compounds": hit_counts["MT_hit"]},
        {"Assay": "Cell count", "Active compounds": hit_counts["Cell_count_hit"]},
        {"Assay": "LDH", "Active compounds": hit_counts["LDH_hit"]},
    ]
    activity_pod_rows = [
        {"Assay": assay_name, "Median POD (uM)": format_metric(pod_value)}
        for assay_name, pod_value in median_pods.items()
    ]
    mo.vstack(
        [
            mo.md(
                f"""
                ## 1. Cell Painting detects sensitive bioactivity

                {activity_conclusion}
                The four-assay comparison contains {activity["figure_2d"]["complete_case_count"]} complete cases in the published supplemental substrate.
                """
            ),
            mo.hstack(
                [
                    mo.ui.table(
                        activity_hit_rows,
                        selection=None,
                        pagination=False,
                        show_search=False,
                        show_download=False,
                    ),
                    mo.ui.table(
                        activity_pod_rows,
                        selection=None,
                        pagination=False,
                        show_search=False,
                        show_download=False,
                    ),
                ],
                widths="equal",
                align="start",
            ),
            mo.image(
                FIGURE_PATHS["activity"],
                alt="Tracked Cell Painting activity and point-of-departure summary",
                width="100%",
            ),
            mo.md("These are tracked-artifact summaries rather than reconstructed publisher panels."),
        ]
    )
    return


@app.cell
def _(gate_failures, report):
    classifier = report["analyses"]["classifier"]
    classifier_passes = (
        "classifier.axiom_above_baselines" not in gate_failures and "classifier.table2" not in gate_failures
    )
    classifier_conclusion = (
        "Across the paired LDH and MTT labels, all three morphology representations outperform the cell-count and random baselines in the committed classifier metrics."
        if classifier_passes
        else "The current report does not pass every gate required for the paired-assay classifier conclusion."
    )
    classifier_rows = [
        {
            "Endpoint": row["endpoint"],
            "Input": row["row"],
            "AUROC": format_metric(row["auroc"]),
            "PR-AUC": format_metric(row["prauc"]),
        }
        for row in classifier["table2"]["rows"]
    ]
    enrichment_rows = mt_enrichment_rows(report)
    mo.vstack(
        [
            mo.md(
                f"""
                ## 2. Morphology predicts paired cellular responses

                {classifier_conclusion}
                The strongest LDH morphology model in this table reaches AUROC {format_metric(max(row["auroc"] for row in classifier["table2"]["rows"] if row["endpoint"] == "LDH" and row["row"] in {"CellProfiler", "CP-CNN", "DINO"}))}.
                """
            ),
            mo.ui.table(
                classifier_rows,
                selection=None,
                pagination=False,
                show_search=False,
                show_download=False,
            ),
            mo.md(
                "### MT-discrepancy associations"
                "\n\nThe two committed MT-discrepancy enrichment tables can be reanalyzed directly."
                "\nThese target-set enrichments are associations conditional on selected exposure wells, so they are hypothesis-generating and do not establish mechanism."
            ),
            mo.ui.table(
                enrichment_rows,
                selection=None,
                pagination=False,
                show_search=False,
                show_download=False,
            ),
        ]
    )
    return


@app.cell
def _(gate_failures, report):
    classifier_for_toxcast = report["analyses"]["classifier"]
    toxcast = report["analyses"]["toxcast"]
    toxcast_passes = "classifier.cellbased_not_cellfree" not in gate_failures
    toxcast_conclusion = (
        "Cell Painting carries predictive signal for cell-based ToxCast endpoints, while the cell-free endpoint result remains near its random baseline."
        if toxcast_passes
        else "The current report does not pass the gate distinguishing cell-based from cell-free ToxCast prediction."
    )
    toxcast_names = {
        "toxcast_cellbased": "Cell-based",
        "toxcast_cellfree": "Cell-free",
        "toxcast_cytotox": "Cytotoxicity",
    }
    toxcast_rows = []
    for analysis_key, display_name in toxcast_names.items():
        medians = classifier_for_toxcast["all_cellprofiler_medians"][analysis_key]
        random_effect = classifier_for_toxcast["baseline_effects"][analysis_key]["auroc"]["random"]
        toxcast_rows.append(
            {
                "Endpoint family": display_name,
                "Modeled endpoints": classifier_for_toxcast["modeled_endpoint_counts"][analysis_key],
                "Median AUROC": format_metric(medians["auroc"]),
                "Median PR-AUC": format_metric(medians["prauc"]),
                "AUROC gain vs random": format_metric(random_effect["mean_difference"]),
                "Paired p-value": f"{random_effect['paired_t_p_value']:.2g}",
            }
        )
    mo.vstack(
        [
            mo.md(
                f"""
                ## 3. Predictive transfer is strongest for cellular assays

                {toxcast_conclusion}
                The pinned binary annotations contain {toxcast["binary_endpoint_counts"]["cellbased"]} cell-based, {toxcast["binary_endpoint_counts"]["cellfree"]} cell-free, and {toxcast["binary_endpoint_counts"]["cytotox"]} cytotoxicity endpoints before classifier eligibility filters.
                """
            ),
            mo.ui.table(
                toxcast_rows,
                selection=None,
                pagination=False,
                show_search=False,
                show_download=False,
            ),
            mo.image(
                FIGURE_PATHS["toxcast"],
                alt="Tracked ToxCast source and binary endpoint counts",
                width="100%",
            ),
        ]
    )
    return


@app.cell
def _(gate_failures, report):
    robustness = report["analyses"]["classifier"]
    robustness_passes = not any(
        f"classifier.{gate_name}" in gate_failures
        for gate_name in {
            "all_concentration_not_worse",
            "allpod_small_effects",
            "allpodcc_filter_direction",
            "conclusion_003",
            "prauc_no_material_improvement",
            "representation_small_effects",
        }
    )
    robustness_conclusion = (
        "Representation choice has small average effects, and concentration filtering provides no consistent practical improvement."
        if robustness_passes
        else "The current report does not pass every gate required for the representation and filtering conclusion."
    )
    robustness_rows = []
    for dataset_key, dataset_name in (
        ("axiom", "Paired cellular assays"),
        ("toxcast_cellbased", "ToxCast cell-based"),
    ):
        for representation_key in ("cpcnn", "dino"):
            effect = robustness["representation_effects"][dataset_key]["auroc"][representation_key]
            robustness_rows.append(
                {
                    "Dataset": dataset_name,
                    "Choice": effect["contrast"],
                    "Metric": "AUROC",
                    "Mean difference": format_metric(effect["mean_difference"]),
                    "Matched endpoints": effect["matched_endpoints"],
                }
            )
        for metric_name in ("auroc", "prauc"):
            allpod_effect = robustness["strategy_effects"][dataset_key][metric_name]["allpod"]
            robustness_rows.append(
                {
                    "Dataset": dataset_name,
                    "Choice": allpod_effect["contrast"],
                    "Metric": metric_name.upper(),
                    "Mean difference": format_metric(allpod_effect["mean_difference"]),
                    "Matched endpoints": allpod_effect["matched_endpoints"],
                }
            )
            filtered_effect = robustness["filter_effects"][dataset_key][metric_name]
            robustness_rows.append(
                {
                    "Dataset": dataset_name,
                    "Choice": filtered_effect["contrast"],
                    "Metric": metric_name.upper(),
                    "Mean difference": format_metric(filtered_effect["mean_difference"]),
                    "Matched endpoints": filtered_effect["matched_endpoints"],
                }
            )
    mo.vstack(
        [
            mo.md(
                f"""
                ## 4. Representation and filtering choices do not improve performance consistently

                {robustness_conclusion}
                Local statistical differences remain visible in the evidence and should not be collapsed into a claim of exact equivalence.
                """
            ),
            mo.ui.table(
                robustness_rows,
                selection=None,
                page_size=12,
                show_search=False,
                show_download=False,
            ),
        ]
    )
    return


@app.cell
def _(report):
    blocked_rows = target_rows(report, outcomes={"blocked", "out-of-scope"})
    documentary_rows = target_rows(report, outcomes={"documentary-only"})
    mo.vstack(
        [
            mo.md(
                """
                ## What this short paper does not claim

                Blocked, out-of-scope, and documentary-only targets stay outside the main Results narrative.
                They remain visible here so that a shorter paper cannot hide its evidence boundary.
                """
            ),
            mo.md("### Blocked or out of scope"),
            mo.ui.table(
                blocked_rows,
                selection=None,
                pagination=False,
                show_search=False,
                show_download=False,
                wrapped_columns=["Result", "Deviation"],
            ),
            mo.md("### Documentary-only"),
            mo.ui.table(
                documentary_rows,
                selection=None,
                page_size=10,
                show_search=True,
                show_download=False,
                wrapped_columns=["Result", "Deviation"],
            ),
        ]
    )
    return


@app.cell
def _(report):
    all_target_rows = target_rows(report)
    target_index = {target["id"]: target for target in report["targets"]}
    target_options = {f"{target['id']}: {target['description']}": target["id"] for target in report["targets"]}
    target_selector = mo.ui.dropdown(
        target_options,
        value=next(iter(target_options)),
        searchable=True,
        label="Inspect one paper target",
        full_width=True,
    )
    mo.vstack(
        [
            mo.md(
                """
                ## Complete evidence index

                Search the full inventory or select one target to inspect its acceptance criterion, checks, producer, evidence note, and deviation.
                """
            ),
            mo.ui.table(
                all_target_rows,
                selection=None,
                page_size=12,
                show_search=True,
                show_download=False,
                wrapped_columns=["Result", "Deviation"],
            ),
            target_selector,
        ]
    )
    return target_index, target_selector


@app.cell
def _(target_index, target_selector):
    selected_target = target_index[target_selector.value]
    selected_checks = [
        {
            "Check": check["name"],
            "Expected": check["expected"],
            "Observed": check["observed"],
            "Passed": check["passed"],
        }
        for check in selected_target["checks"]
    ]
    selected_limitations = (
        "\n".join(f"- {limitation}" for limitation in selected_target["limitations"]) or "- None recorded."
    )
    mo.vstack(
        [
            mo.md(
                f"""
                ### {selected_target["id"]}: {selected_target["description"]}

                **Published expectation:** {selected_target["expected"]}

                **Acceptance criterion:** {selected_target["acceptance"]}

                **Execution:** `{selected_target["execution_outcome"]}`; **ledger:** `{selected_target["ledger_status"]}`; **evidence strength:** `{selected_target["evidence_strength"]}`.

                **Producer:** `{selected_target["producer"]}`

                **Evidence note:** `paper/{selected_target["evidence"]}`

                **Limitations**

                {selected_limitations}
                """
            ),
            mo.ui.table(
                selected_checks,
                selection=None,
                pagination=False,
                show_search=False,
                show_download=False,
                wrapped_columns=["Check", "Expected", "Observed"],
            ),
        ]
    )
    return


@app.cell
def _(report):
    mapped_target_count = len(result_target_ids())
    checked_target_count = report["summary"]["execution_outcome_counts"]["checked"]
    mo.vstack(
        [
            mo.md(
                f"""
                ## Reproduction note

                This narrative is backed by {mapped_target_count} explicitly mapped checked targets.
                The remaining {checked_target_count - mapped_target_count} checked target is contextual source-table validation and remains in the complete evidence index.
                Regenerate the tracked report with `uv run paper/reproduce.py`, then rerun this notebook to update its numbers, statuses, and evidence tables.
                A successful export proves that the committed report satisfies this document's schema and interpretation gates; it does not prove that the full GPU workflow completed.
                """
            ),
            mo.image(
                FIGURE_PATHS["coverage"],
                alt="Evidence coverage across all paper targets",
                width="100%",
            ),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
