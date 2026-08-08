# ruff: noqa: D102, PLR2004, PT009, PT027, S108, SLF001
"""Fast contract tests for the isolated end-to-end reproduction orchestrator."""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

reproduce_all = importlib.import_module("paper.reproduce_all")

PAPER_TEST_MODULES_BY_ENVIRONMENT = {
    "pipeline": frozenset(
        {
            "test_compiled_results",
            "test_paper_reproduce",
            "test_reproduce_all",
        }
    ),
    "notebooks": frozenset(
        {
            "test_living_results",
            "test_render_sfig1",
        }
    ),
}


def _add_tar_file(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    member = tarfile.TarInfo(name)
    member.size = len(payload)
    archive.addfile(member, io.BytesIO(payload))


class InputVerificationTest(unittest.TestCase):
    """Exercise exact cache verification and atomic acquisition."""

    def test_verify_file_requires_exact_size_and_full_md5(self) -> None:
        payload = b"full checksum, not a prefix"
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "input.parquet"
            path.write_bytes(payload)
            digest = hashlib.md5(payload).hexdigest()  # noqa: S324 - deposit contract

            self.assertEqual(
                reproduce_all.verify_file(path, size=len(payload), md5=digest),
                (True, "verified"),
            )
            self.assertFalse(reproduce_all.verify_file(path, size=len(payload) + 1, md5=digest)[0])
            self.assertFalse(reproduce_all.verify_file(path, size=len(payload), md5="0" * 32)[0])

    def test_acquire_input_reuses_only_a_fully_verified_cache_file(self) -> None:
        payload = b"cached"
        spec = reproduce_all.InputSpec(
            "cached.bin",
            "inputs/cached.bin",
            len(payload),
            hashlib.md5(payload).hexdigest(),  # noqa: S324 - deposit contract
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache = Path(temporary_directory)
            (cache / spec.name).write_bytes(payload)
            downloader = mock.Mock(side_effect=AssertionError("verified cache should avoid network"))

            path, disposition = reproduce_all.acquire_input(spec, cache, downloader=downloader)

            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(disposition, "reused")
            downloader.assert_not_called()

    def test_acquire_input_downloads_to_part_then_atomically_renames(self) -> None:
        payload = b"new input"
        spec = reproduce_all.InputSpec(
            "new.bin",
            "inputs/new.bin",
            len(payload),
            hashlib.md5(payload).hexdigest(),  # noqa: S324 - deposit contract
        )
        observed_destinations: list[Path] = []

        def downloader(_url: str, destination: Path) -> None:
            observed_destinations.append(destination)
            self.assertTrue(destination.name.endswith(".part"))
            destination.write_bytes(payload)

        with tempfile.TemporaryDirectory() as temporary_directory:
            cache = Path(temporary_directory)
            path, disposition = reproduce_all.acquire_input(spec, cache, downloader=downloader)

            self.assertEqual(disposition, "downloaded")
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(len(observed_destinations), 1)
            self.assertFalse(observed_destinations[0].exists())

    def test_acquire_input_can_prime_cache_from_verified_checkout_input(self) -> None:
        payload = b"existing exact deposit input"
        spec = reproduce_all.InputSpec(
            "existing.bin",
            "inputs/existing.bin",
            len(payload),
            hashlib.md5(payload).hexdigest(),  # noqa: S324 - deposit contract
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / spec.destination
            source.parent.mkdir(parents=True)
            source.write_bytes(payload)
            downloader = mock.Mock(side_effect=AssertionError("verified checkout input should avoid network"))

            path, disposition = reproduce_all.acquire_input(
                spec,
                root / "cache",
                verified_local_source=source,
                downloader=downloader,
            )

            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(disposition, "copied-from-verified-checkout")
            self.assertNotEqual(path, source)
            downloader.assert_not_called()

    def test_acquire_input_does_not_trust_invalid_checkout_input(self) -> None:
        payload = b"correct"
        spec = reproduce_all.InputSpec(
            "download.bin",
            "inputs/download.bin",
            len(payload),
            hashlib.md5(payload).hexdigest(),  # noqa: S324 - deposit contract
        )

        def downloader(_url: str, destination: Path) -> None:
            destination.write_bytes(payload)

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / spec.destination
            source.parent.mkdir(parents=True)
            source.write_bytes(b"wrong!!")

            path, disposition = reproduce_all.acquire_input(
                spec,
                root / "cache",
                verified_local_source=source,
                downloader=downloader,
            )

            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(disposition, "downloaded")
            self.assertEqual(source.read_bytes(), b"wrong!!")

    def test_acquire_input_does_not_reuse_same_size_wrong_checksum(self) -> None:
        payload = b"correct"
        spec = reproduce_all.InputSpec(
            "replace.bin",
            "inputs/replace.bin",
            len(payload),
            hashlib.md5(payload).hexdigest(),  # noqa: S324 - deposit contract
        )

        def downloader(_url: str, destination: Path) -> None:
            destination.write_bytes(payload)

        with tempfile.TemporaryDirectory() as temporary_directory:
            cache = Path(temporary_directory)
            (cache / spec.name).write_bytes(b"wrong!!")

            path, disposition = reproduce_all.acquire_input(spec, cache, downloader=downloader)

            self.assertEqual(disposition, "downloaded")
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(len(list(cache.glob("replace.bin.invalid-*"))), 1)

    def test_official_input_contract_uses_full_md5_values(self) -> None:
        self.assertEqual(len(reproduce_all.INPUTS), 5)
        for spec in reproduce_all.INPUTS:
            self.assertEqual(len(spec.md5), 32)
            self.assertGreater(spec.size, 0)
            int(spec.md5, 16)


class ArchiveSafetyTest(unittest.TestCase):
    """Reject archive members that could escape or alias the snapshot."""

    def test_extracts_regular_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "source.tar"
            with tarfile.open(archive_path, "w") as archive:
                _add_tar_file(archive, "nested/file.txt", b"safe")

            reproduce_all._safe_extract_tar(archive_path, root / "workspace")

            self.assertEqual((root / "workspace/nested/file.txt").read_bytes(), b"safe")

    def test_rejects_path_traversal_without_writing_outside(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "source.tar"
            with tarfile.open(archive_path, "w") as archive:
                _add_tar_file(archive, "would-have-been-written.txt", b"safe member")
                _add_tar_file(archive, "../escaped.txt", b"unsafe")

            with self.assertRaises(reproduce_all.ReproductionError):
                reproduce_all._safe_extract_tar(archive_path, root / "workspace")

            self.assertFalse((root / "escaped.txt").exists())
            self.assertFalse((root / "workspace/would-have-been-written.txt").exists())

    def test_rejects_symbolic_links(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive_path = root / "source.tar"
            with tarfile.open(archive_path, "w") as archive:
                member = tarfile.TarInfo("link")
                member.type = tarfile.SYMTYPE
                member.linkname = "../../outside"
                archive.addfile(member)

            with self.assertRaises(reproduce_all.ReproductionError):
                reproduce_all._safe_extract_tar(archive_path, root / "workspace")


class WorkspaceSourceIdentityTest(unittest.TestCase):
    """Bind resumed execution to archived code while allowing notebook outputs."""

    def test_source_identity_allows_snakemake_benchmarks_only_in_runtime_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "workspace"
            root.mkdir()
            snakefile = root / "1_snakemake/Snakefile"
            snakefile.parent.mkdir(parents=True)
            snakefile.write_text("rule all:\n    input: []\n", encoding="ascii")
            identities = reproduce_all._workspace_source_identity(root)

            benchmark = root / "1_snakemake/benchmarks/example/fit_curves.tsv"
            benchmark.parent.mkdir(parents=True)
            benchmark.write_text("seconds\n1.0\n", encoding="ascii")
            reproduce_all._validate_workspace_source_identity(root, identities)

            injected = root / "unexpected.tsv"
            injected.write_text("value\nchanged\n", encoding="ascii")
            with self.assertRaisesRegex(reproduce_all.ReproductionError, "unexpected.tsv"):
                reproduce_all._validate_workspace_source_identity(root, identities)

    def test_source_identity_allows_execution_outputs_but_rejects_source_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "workspace"
            root.mkdir()
            snakefile = root / "1_snakemake/Snakefile"
            snakefile.parent.mkdir(parents=True)
            snakefile.write_text("rule all:\n    input: []\n", encoding="ascii")
            notebook = root / "analysis.ipynb"
            notebook_payload = {
                "cells": [
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "outputs": [],
                        "source": ["value = 1\n"],
                    },
                ],
            }
            notebook.write_text(json.dumps(notebook_payload), encoding="utf-8")
            identities = reproduce_all._workspace_source_identity(root)

            notebook_payload["cells"][0]["execution_count"] = 1
            notebook_payload["cells"][0]["outputs"] = [{"output_type": "stream", "text": ["done\n"]}]
            notebook.write_text(json.dumps(notebook_payload), encoding="utf-8")
            reproduce_all._validate_workspace_source_identity(root, identities)

            snakefile.write_text('rule all:\n    input: ["changed"]\n', encoding="ascii")
            with self.assertRaisesRegex(reproduce_all.ReproductionError, "Snakefile"):
                reproduce_all._validate_workspace_source_identity(root, identities)

    def test_source_identity_rejects_changed_notebook_code_and_added_python(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "workspace"
            root.mkdir()
            notebook = root / "analysis.ipynb"
            notebook.write_text(
                json.dumps({"cells": [{"cell_type": "code", "source": ["value = 1\n"]}]}),
                encoding="utf-8",
            )
            identities = reproduce_all._workspace_source_identity(root)

            notebook.write_text(
                json.dumps({"cells": [{"cell_type": "code", "source": ["value = 2\n"]}]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(reproduce_all.ReproductionError, "analysis.ipynb"):
                reproduce_all._validate_workspace_source_identity(root, identities)

            notebook.write_text(
                json.dumps({"cells": [{"cell_type": "code", "source": ["value = 1\n"]}]}),
                encoding="utf-8",
            )
            (root / "injected.py").write_text("value = 3\n", encoding="ascii")
            with self.assertRaisesRegex(reproduce_all.ReproductionError, "injected.py"):
                reproduce_all._validate_workspace_source_identity(root, identities)


class OutputContractTest(unittest.TestCase):
    """Exercise the added sensitivity and preserved-reference contracts."""

    def test_preserved_reference_tree_has_no_write_bits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "reference"
            nested = root / "nested"
            nested.mkdir(parents=True)
            artifact = nested / "result.parquet"
            artifact.write_bytes(b"reference")
            root.chmod(0o777)
            nested.chmod(0o777)
            artifact.chmod(0o666)

            reproduce_all._make_tree_read_only(root)

            self.assertFalse(reproduce_all._tree_has_write_bits(root))
            self.assertEqual(artifact.read_bytes(), b"reference")
            root.chmod(0o755)
            nested.chmod(0o755)
            artifact.chmod(0o644)

    def test_sensitivity_stage_requires_every_consumed_output_and_inventories_configs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = reproduce_all.RunPaths.from_root(Path(temporary_directory) / "run")
            manifest = reproduce_all._initial_manifest(Path("/repository"), paths, "a" * 40, 4)
            context = reproduce_all.RunContext(
                repository=Path("/repository"),
                paths=paths,
                cache=Path(temporary_directory) / "cache",
                head="a" * 40,
                cores=4,
                manifest=manifest,
            )
            output_root = paths.workspace / "1_snakemake/outputs"

            filtered_root = output_root / reproduce_all.FILTERED_CONFIG.output_root
            for relative in reproduce_all.CORE_CONFIG_OUTPUTS:
                path = filtered_root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"output")
            for config in reproduce_all.SENSITIVITY_CONFIGS:
                required = list(reproduce_all.SENSITIVITY_CONFIG_OUTPUTS)
                if config.config == "dino_log10":
                    required.extend(reproduce_all.DINO_LOG10_NOTEBOOK_OUTPUTS)
                for relative in required:
                    path = output_root / config.output_root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"output")

            reproduce_all._validate_stage_outputs(context, "sensitivity-configs")
            reproduce_all._update_generated_inventory(context, "sensitivity-configs")

            inventory = manifest["scope"]["generated_upstream_artifacts"]["by_config"]
            self.assertEqual(len(inventory), 10)
            self.assertIsNone(inventory["cellprofiler_filt"]["candidate_acceptance_gate"])
            self.assertIsNone(inventory["dino_ap"]["candidate_acceptance_gate"])

            missing_contract = output_root / "dino/mad_featselect_log10/curves/ldhpods.parquet"
            missing_contract.write_bytes(b"")
            with self.assertRaisesRegex(reproduce_all.StageError, "dino_log10"):
                reproduce_all._validate_stage_outputs(context, "sensitivity-configs")

    def test_extended_notebook_contract_rejects_unexecuted_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = [root / Path(notebook.path).name for notebook in reproduce_all.EXTENDED_NOTEBOOKS]
            executed = {
                "cells": [
                    {
                        "cell_type": "code",
                        "execution_count": 1,
                        "outputs": [],
                        "source": ["value = 1\n"],
                    },
                ],
            }
            for path in paths:
                path.write_text(json.dumps(executed), encoding="utf-8")

            reproduce_all._require_executed_notebooks(paths, "extended-notebooks")

            unexecuted = json.loads(json.dumps(executed))
            unexecuted["cells"][0]["execution_count"] = None
            paths[1].write_text(json.dumps(unexecuted), encoding="utf-8")
            with self.assertRaisesRegex(reproduce_all.StageError, "did not execute"):
                reproduce_all._require_executed_notebooks(paths, "extended-notebooks")

    def test_producer_contract_includes_outputs_and_all_four_executed_notebooks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = reproduce_all.RunPaths.from_root(Path(temporary_directory) / "run")
            manifest = reproduce_all._initial_manifest(Path("/repository"), paths, "a" * 40, 4)
            context = reproduce_all.RunContext(
                repository=Path("/repository"),
                paths=paths,
                cache=Path(temporary_directory) / "cache",
                head="a" * 40,
                cores=4,
                manifest=manifest,
            )
            compiled = paths.workspace / "2_downstream_analysis/compiled_results"
            for relative in reproduce_all.GENERATED_COMPILED_RESULTS:
                output = compiled / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"output")
            executed = {
                "cells": [
                    {
                        "cell_type": "code",
                        "execution_count": 1,
                        "outputs": [],
                        "source": ["value = 1\n"],
                    },
                ],
            }
            for notebook in reproduce_all.PRODUCER_NOTEBOOKS:
                notebook_path = paths.workspace / notebook.path
                notebook_path.parent.mkdir(parents=True, exist_ok=True)
                notebook_path.write_text(json.dumps(executed), encoding="utf-8")

            reproduce_all._validate_stage_outputs(context, "producer-notebooks")
            identity_paths = reproduce_all._stage_identity_paths(context, "producer-notebooks")
            self.assertEqual(
                identity_paths[-len(reproduce_all.PRODUCER_NOTEBOOKS) :],
                [paths.workspace / notebook.path for notebook in reproduce_all.PRODUCER_NOTEBOOKS],
            )

            failed_notebook = paths.workspace / reproduce_all.PRODUCER_NOTEBOOKS[-1].path
            failed = json.loads(json.dumps(executed))
            failed["cells"][0]["execution_count"] = None
            failed_notebook.write_text(json.dumps(failed), encoding="utf-8")
            with self.assertRaisesRegex(reproduce_all.StageError, "did not execute"):
                reproduce_all._validate_stage_outputs(context, "producer-notebooks")

    def test_figure_identity_includes_exactly_five_cached_tiffs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = reproduce_all.RunPaths.from_root(Path(temporary_directory) / "run")
            manifest = reproduce_all._initial_manifest(Path("/repository"), paths, "a" * 40, 4)
            context = reproduce_all.RunContext(
                repository=Path("/repository"),
                paths=paths,
                cache=Path(temporary_directory) / "cache",
                head="a" * 40,
                cores=4,
                manifest=manifest,
            )
            figure_root = paths.artifacts / "sfig1"
            for name in ("figure-s1-reproduced.png", "figure-s1-report.json"):
                path = figure_root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"artifact")
            for index in range(reproduce_all.EXPECTED_FIGURE_S1_TIFFS):
                path = figure_root / "tiffs" / f"channel-{index}.tiff"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"tiff")

            reproduce_all._validate_stage_outputs(context, "figure-s1")
            identities = reproduce_all._stage_identity_paths(context, "figure-s1")
            self.assertEqual(len(identities), reproduce_all.EXPECTED_FIGURE_S1_TIFFS + 2)

            identities[-1].write_bytes(b"")
            with self.assertRaises(reproduce_all.StageError):
                reproduce_all._validate_stage_outputs(context, "figure-s1")


class PlanAndManifestTest(unittest.TestCase):
    """Bind commands, scope labels, and durable state to the public recipe."""

    def test_command_plan_has_all_configs_and_documented_notebook_order(self) -> None:
        paths = reproduce_all.RunPaths.from_root(Path("/tmp/axiom-plan"))
        head = "a" * 40
        plan = reproduce_all.build_command_plan(paths, 4, head)

        self.assertEqual(tuple(plan), reproduce_all.STAGE_IDS)
        self.assertEqual(plan["snapshot"][0][-1], head)
        for config in ("cellprofiler", "cpcnn", "dino"):
            command = plan[f"snakemake-{config}"][0]
            self.assertIn(f"inputs/conf/{config}.json", command)
            self.assertEqual(command[-3:], ["--cores", "4", "--rerun-incomplete"])
            self.assertEqual(command[:3], ["nix", "develop", f"path:{paths.env_source}"])
        sensitivity_commands = plan["sensitivity-configs"]
        expected_configs = (
            "cellprofiler_filt",
            "cellprofiler_log10",
            "cpcnn_log10",
            "dino_log10",
            "cellprofiler_int",
            "cpcnn_int",
            "dino_int",
            "cellprofiler_ap",
            "cpcnn_ap",
            "dino_ap",
        )
        observed_configs = tuple(
            Path(command[command.index("--configfile") + 1]).stem for command in sensitivity_commands
        )
        self.assertEqual(observed_configs, expected_configs)
        self.assertEqual(sensitivity_commands[0][-1], "--rerun-incomplete")
        for config, command in zip(reproduce_all.SENSITIVITY_CONFIGS, sensitivity_commands[1:], strict=True):
            root = f"outputs/{config.output_root}"
            self.assertIn("--rerun-incomplete", command)
            self.assertIn(f"{root}/curves/pods.parquet", command)
            if config.config == "dino_log10":
                self.assertEqual(
                    command[-3:],
                    [
                        f"{root}/curves/pods.parquet",
                        f"{root}/curves/mttpods.parquet",
                        f"{root}/curves/ldhpods.parquet",
                    ],
                )
            else:
                self.assertEqual(command[-1], f"{root}/curves/pods.parquet")
        producer_names = [command[-1] for command in plan["producer-notebooks"]]
        self.assertEqual(
            producer_names,
            [Path(notebook.path).name for notebook in reproduce_all.PRODUCER_NOTEBOOKS],
        )
        extended_names = [command[-1] for command in plan["extended-notebooks"]]
        self.assertEqual(
            extended_names,
            [Path(notebook.path).name for notebook in reproduce_all.EXTENDED_NOTEBOOKS],
        )
        for command in plan["extended-notebooks"]:
            environment_index = command.index("-e") + 1
            self.assertEqual(command[environment_index], "notebooks")
        export_names = [Path(command[-1]).name for command in plan["notebook-export"]]
        for notebook in reproduce_all.EXTENDED_NOTEBOOKS:
            self.assertIn(Path(notebook.path).name, export_names)
        self.assertEqual(Path(reproduce_all.PRODUCER_NOTEBOOKS[-1].path).name, "2_2_outlier_enrichment_analysis.ipynb")
        self.assertEqual(Path(reproduce_all.ANALYSIS_NOTEBOOKS[0].path).name, "3_2_1_compare_endpoint_types.ipynb")
        self.assertIn("mtt_higher_targets.csv", reproduce_all.GENERATED_COMPILED_RESULTS)
        self.assertIn("mtt_lower_targets.csv", reproduce_all.GENERATED_COMPILED_RESULTS)
        self.assertEqual(
            reproduce_all.SEEDED_COMPILED_RESULTS,
            ("motive_highexp_PHH.parquet", "SI_tables/readme.txt"),
        )
        verifier = plan["semantic-verifier"][0]
        self.assertIn("paper.verification.compiled_results", verifier)
        module_name = verifier[verifier.index("-m") + 1]
        self.assertIsNotNone(importlib.util.find_spec(module_name))
        self.assertIn(str(paths.reference), verifier)
        self.assertNotIn("paper.reproduce", verifier)
        figure_s1 = plan["figure-s1"][0]
        self.assertIn(str(paths.workspace / "paper/render_sfig1.py"), figure_s1)
        self.assertIn(str(paths.artifacts / "sfig1"), figure_s1)

    def test_every_paper_test_is_assigned_to_one_locked_environment(self) -> None:
        test_directory = Path(__file__).resolve().parent
        observed_modules = {path.stem for path in test_directory.glob("test_*.py")}
        assigned_modules = set().union(*PAPER_TEST_MODULES_BY_ENVIRONMENT.values())
        self.assertEqual(observed_modules, assigned_modules)
        self.assertFalse(PAPER_TEST_MODULES_BY_ENVIRONMENT["pipeline"] & PAPER_TEST_MODULES_BY_ENVIRONMENT["notebooks"])

    def test_extended_stage_order_is_coarse_and_dependency_safe(self) -> None:
        self.assertLess(
            reproduce_all.STAGE_IDS.index("analysis-notebooks"),
            reproduce_all.STAGE_IDS.index("sensitivity-configs"),
        )
        self.assertLess(
            reproduce_all.STAGE_IDS.index("sensitivity-configs"),
            reproduce_all.STAGE_IDS.index("extended-notebooks"),
        )
        self.assertLess(
            reproduce_all.STAGE_IDS.index("extended-notebooks"),
            reproduce_all.STAGE_IDS.index("notebook-export"),
        )

    def test_manifest_is_ascii_and_distinguishes_evidence_roles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = reproduce_all.RunPaths.from_root(Path(temporary_directory) / "run")
            manifest = reproduce_all._initial_manifest(
                Path("/tmp/repository"),
                paths,
                "a" * 40,
                4,
            )
            reproduce_all._atomic_json(paths.manifest, manifest)
            payload = paths.manifest.read_bytes()
            decoded = json.loads(payload)

            self.assertTrue(all(byte < 128 for byte in payload))
            self.assertEqual([stage["id"] for stage in decoded["stages"]], list(reproduce_all.STAGE_IDS))
            self.assertEqual(len(decoded["repository"]["orchestrator_sha256"]), 64)
            self.assertIn("not rebuilt", decoded["scope"]["does_not_claim"])
            self.assertIn("seeded_inputs", decoded["scope"])
            self.assertIn("acceptance_reports", decoded["scope"])
            self.assertEqual(decoded["scope"]["generated_upstream_artifacts"]["count"], 0)
            self.assertIn("explicit candidate root", decoded["candidate"]["future_seam"])
            self.assertEqual(
                decoded["scope"]["external_image_artifacts"]["report"],
                "artifacts/sfig1/figure-s1-report.json",
            )
            sensitivity = decoded["scope"]["sensitivity_layer"]
            self.assertIsNone(sensitivity["acceptance_gate"])
            self.assertEqual(len(sensitivity["partial_configs"]), 9)
            self.assertIn("not treated as recovered historical", sensitivity["interpretation"])
            self.assertEqual(
                decoded["scope"]["executed_notebooks"]["extended"],
                [notebook.path for notebook in reproduce_all.EXTENDED_NOTEBOOKS],
            )

    def test_stage_range_requires_resume_and_completed_prerequisites(self) -> None:
        with self.assertRaises(reproduce_all.ReproductionError):
            reproduce_all._selected_stages(
                None,
                from_stage="environment",
                through_stage=None,
                resume=False,
            )

    def test_resume_manifest_is_bound_to_head_and_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = reproduce_all.RunPaths.from_root(Path(temporary_directory) / "run")
            paths.root.mkdir()
            manifest = reproduce_all._initial_manifest(Path("/repository"), paths, "a" * 40, 4)
            reproduce_all._atomic_json(paths.manifest, manifest)

            with self.assertRaises(reproduce_all.ReproductionError):
                reproduce_all._load_manifest(paths, "b" * 40, manifest["repository"]["orchestrator_sha256"])

    def test_resume_manifest_is_bound_to_committed_orchestrator(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = reproduce_all.RunPaths.from_root(Path(temporary_directory) / "run")
            paths.root.mkdir()
            manifest = reproduce_all._initial_manifest(Path("/repository"), paths, "a" * 40, 4)
            reproduce_all._atomic_json(paths.manifest, manifest)

            with self.assertRaisesRegex(reproduce_all.ReproductionError, "orchestrator"):
                reproduce_all._load_manifest(paths, "a" * 40, "0" * 64)

    def test_resume_rechecks_completed_stage_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = reproduce_all.RunPaths.from_root(Path(temporary_directory) / "run")
            paths.root.mkdir()
            manifest = reproduce_all._initial_manifest(Path("/repository"), paths, "a" * 40, 4)
            semantic = next(stage for stage in manifest["stages"] if stage["id"] == "semantic-verifier")
            semantic["status"] = "succeeded"
            reproduce_all._atomic_json(paths.manifest, manifest)

            with self.assertRaisesRegex(reproduce_all.ReproductionError, "semantic-verifier"):
                reproduce_all._load_manifest(
                    paths,
                    "a" * 40,
                    manifest["repository"]["orchestrator_sha256"],
                )

    def test_resume_rejects_same_size_output_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = reproduce_all.RunPaths.from_root(Path(temporary_directory) / "run")
            paths.artifacts.mkdir(parents=True)
            report = paths.artifacts / "semantic-verification.json"
            report.write_bytes(b"AAAA")
            manifest = reproduce_all._initial_manifest(Path("/repository"), paths, "a" * 40, 4)
            semantic = next(stage for stage in manifest["stages"] if stage["id"] == "semantic-verifier")
            semantic["status"] = "succeeded"
            context = reproduce_all.RunContext(
                repository=Path("/repository"),
                paths=paths,
                cache=Path(temporary_directory) / "cache",
                head="a" * 40,
                cores=4,
                manifest=manifest,
            )
            reproduce_all._record_stage_output_identity(context, "semantic-verifier")
            reproduce_all._atomic_json(paths.manifest, manifest)
            report.write_bytes(b"BBBB")

            with self.assertRaisesRegex(reproduce_all.ReproductionError, "semantic-verifier"):
                reproduce_all._load_manifest(
                    paths,
                    "a" * 40,
                    manifest["repository"]["orchestrator_sha256"],
                )


class CliSafetyTest(unittest.TestCase):
    """Check run-directory and no-write preview guarantees."""

    def test_existing_run_directory_requires_explicit_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "existing"
            run_dir.mkdir()
            with self.assertRaises(reproduce_all.ReproductionError):
                reproduce_all._validate_run_dir(Path(temporary_directory), run_dir, resume=False)

    def test_dry_run_creates_no_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "new-run"
            stdout = io.StringIO()
            with (
                mock.patch.object(reproduce_all, "_git_head", return_value="b" * 40),
                mock.patch.object(reproduce_all, "_require_committed_orchestrator", return_value="c" * 64),
                mock.patch.object(reproduce_all, "_preflight") as preflight,
                contextlib.redirect_stdout(stdout),
            ):
                exit_code = reproduce_all.main(["--dry-run", "--run-dir", str(run_dir)])

            self.assertEqual(exit_code, 0)
            self.assertFalse(run_dir.exists())
            preflight.assert_not_called()
            self.assertIn("No files will be written", stdout.getvalue())

    def test_resume_repairs_terminal_manifest_status_after_final_interruption(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "completed"
            run_dir.mkdir()
            paths = reproduce_all.RunPaths.from_root(run_dir)
            manifest = reproduce_all._initial_manifest(Path("/repository"), paths, "b" * 40, 4)
            for stage in manifest["stages"]:
                stage["status"] = "succeeded"
            manifest["status"] = "running"
            reproduce_all._atomic_json(paths.manifest, manifest)
            stdout = io.StringIO()
            with (
                mock.patch.object(reproduce_all, "_git_head", return_value="b" * 40),
                mock.patch.object(reproduce_all, "_require_committed_orchestrator", return_value="c" * 64),
                mock.patch.object(reproduce_all, "_load_manifest", return_value=manifest),
                contextlib.redirect_stdout(stdout),
            ):
                exit_code = reproduce_all.main(["--resume", "--run-dir", str(run_dir)])

            self.assertEqual(exit_code, 0)
            repaired = json.loads(paths.manifest.read_text(encoding="ascii"))
            self.assertEqual(repaired["status"], "succeeded")
            self.assertIn("Run already complete", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
