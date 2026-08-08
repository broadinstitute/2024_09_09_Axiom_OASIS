from __future__ import annotations

import ast
import copy
import importlib.util
import json
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_PATH = REPOSITORY_ROOT / "paper/living_results.py"
SESSION_PATH = REPOSITORY_ROOT / "paper/__marimo__/session/living_results.py.json"
MARIMO_AVAILABLE = importlib.util.find_spec("marimo") is not None

if MARIMO_AVAILABLE:
    import marimo as mo

    from paper import living_results
else:
    mo = None
    living_results = None


class LivingResultsSourceTest(unittest.TestCase):
    def test_notebook_is_ascii_and_read_only(self) -> None:
        source = NOTEBOOK_PATH.read_text(encoding="utf-8")
        source.encode("ascii")
        tree = ast.parse(source)

        imported_roots = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue(imported_roots.isdisjoint({"git", "os", "requests", "sh", "subprocess", "urllib"}))

        called_attributes = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertTrue(
            called_attributes.isdisjoint(
                {
                    "mkdir",
                    "rename",
                    "rmdir",
                    "touch",
                    "unlink",
                    "write_bytes",
                    "write_text",
                }
            )
        )


@unittest.skipUnless(MARIMO_AVAILABLE, "marimo is installed in the notebooks environment")
class LivingResultsContractTest(unittest.TestCase):
    def setUp(self) -> None:
        assert living_results is not None
        self.report, self.manifest = living_results.load_contract()

    def test_contract_is_tracked_and_internally_consistent(self) -> None:
        assert living_results is not None
        living_results.validate_contract(self.report, self.manifest)
        self.assertEqual(self.report["schema_version"], 3)
        self.assertEqual(self.report["mode"], "tracked")
        self.assertEqual(self.report["summary"]["total"], len(self.report["targets"]))

    def test_current_interpretation_gates_pass(self) -> None:
        assert living_results is not None
        self.assertEqual(living_results.conclusion_gate_failures(self.report), [])

    def test_committed_molab_session_matches_rendered_state(self) -> None:
        assert living_results is not None
        session_text = SESSION_PATH.read_text(encoding="utf-8")
        session = json.loads(session_text)
        self.assertEqual(session["version"], "1")
        self.assertIn(living_results.rendered_state_sha256(), session_text)

    def test_results_use_only_checked_targets(self) -> None:
        assert living_results is not None
        target_index = {target["id"]: target for target in self.report["targets"]}
        result_ids = living_results.result_target_ids()
        self.assertEqual(len(result_ids), len(set(result_ids)))
        self.assertEqual(len(result_ids), 31)
        self.assertTrue(all(target_index[target_id]["execution_outcome"] == "checked" for target_id in result_ids))

    def test_blocked_and_out_of_scope_targets_remain_outside_results(self) -> None:
        assert living_results is not None
        excluded_ids = {
            target["id"]
            for target in self.report["targets"]
            if target["execution_outcome"] in {"blocked", "out-of-scope"}
        }
        self.assertEqual(
            excluded_ids,
            {"BIOACTIVITY-002", "ENRICH-001", "ENRICH-002", "SFIG-1"},
        )
        self.assertTrue(excluded_ids.isdisjoint(living_results.result_target_ids()))

    def test_main_enrichment_table_excludes_blocked_error_sets(self) -> None:
        assert living_results is not None
        enrichment_rows = living_results.mt_enrichment_rows(self.report)
        self.assertEqual(
            {row["Selected set"] for row in enrichment_rows},
            {"mtt higher", "mtt lower"},
        )
        self.assertEqual(set(living_results.FIGURE_PATHS), {"activity", "coverage", "toxcast"})

    def test_every_target_detail_is_top_level_markdown(self) -> None:
        assert living_results is not None
        assert mo is not None
        for target in self.report["targets"]:
            with self.subTest(target=target["id"]):
                markdown = living_results.target_detail_markdown(target)
                rendered = mo.md(markdown)._repr_html_()
                self.assertTrue(markdown.startswith(f"### {target['id']}:"))
                self.assertFalse(any(line.startswith("    ") for line in markdown.splitlines()))
                self.assertEqual(markdown.count("\n- "), max(1, len(target["limitations"])))
                self.assertIn("<h3", rendered)
                self.assertNotIn("<pre", rendered)

    def test_summary_drift_fails_closed(self) -> None:
        assert living_results is not None
        changed_report = copy.deepcopy(self.report)
        changed_report["summary"]["total"] += 1
        with self.assertRaisesRegex(ValueError, "summary total"):
            living_results.validate_contract(changed_report, self.manifest)

    def test_non_checked_result_mapping_fails_closed(self) -> None:
        assert living_results is not None
        changed_report = copy.deepcopy(self.report)
        mapped_id = living_results.result_target_ids()[0]
        mapped_target = next(target for target in changed_report["targets"] if target["id"] == mapped_id)
        mapped_target["execution_outcome"] = "documentary-only"
        changed_report["summary"]["execution_outcome_counts"] = living_results.counts_by_field(
            changed_report["targets"], "execution_outcome"
        )
        with self.assertRaisesRegex(ValueError, "includes non-checked target"):
            living_results.validate_contract(changed_report, self.manifest)


if __name__ == "__main__":
    unittest.main()
