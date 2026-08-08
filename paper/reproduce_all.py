# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
# ruff: noqa: C901, E501, EM101, EM102, PLR0911, PLR0912, PLR0915, PLR2004, PTH105, S603, S607, T201, TC003, TRY003, TRY300, TRY301
"""Run the repository's end-to-end paper reproduction in an isolated snapshot.

This orchestrator regenerates the supported upstream analyses, executes the
documented runnable notebooks, and applies the numerical acceptance gates.
It deliberately does not claim to rebuild the publisher's composite figures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TextIO

SCHEMA_VERSION = 1
MINIMUM_FREE_BYTES = 20 * 1024**3
EXPECTED_FIGURE_S1_TIFFS = 5
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = REPOSITORY_ROOT / "paper/runs/cache/zenodo-17067683"
MANIFEST_NAME = "manifest.json"
ORCHESTRATOR_RELATIVE_PATH = "paper/reproduce_all.py"
WORKSPACE_MUTABLE_PREFIXES = (
    "1_snakemake/benchmarks/",
    "1_snakemake/outputs/",
    "2_downstream_analysis/compiled_results/",
)
WORKSPACE_RUNTIME_DIRECTORY_NAMES = {
    ".ipynb_checkpoints",
    ".mypy_cache",
    ".pixi",
    ".pytest_cache",
    ".ruff_cache",
    ".snakemake",
    "__pycache__",
}
LOAD_BEARING_SUFFIXES = {
    ".ipynb",
    ".json",
    ".lock",
    ".nix",
    ".py",
    ".r",
    ".sh",
    ".smk",
    ".toml",
    ".tsv",
}


class ReproductionError(RuntimeError):
    """The requested run is unsafe or cannot be initialized."""


class StageError(RuntimeError):
    """A required reproduction stage failed."""


@dataclass(frozen=True)
class InputSpec:
    """One immutable file in the public compiled-input deposit."""

    name: str
    destination: str
    size: int
    md5: str

    @property
    def url(self) -> str:
        """Return the pinned record's content URL."""
        return f"https://zenodo.org/api/records/17067683/files/{self.name}/content"


INPUTS = (
    InputSpec(
        "cellprofiler_raw.parquet",
        "1_snakemake/inputs/profiles/cellprofiler/raw.parquet",
        413_433_180,
        "0cf2b9d11268c363d756e69851a1a568",
    ),
    InputSpec(
        "dino_raw.parquet",
        "1_snakemake/inputs/profiles/dino/raw.parquet",
        399_927_644,
        "421529eb80880721eaa42bdcd26920d5",
    ),
    InputSpec(
        "cpcnn_raw.parquet",
        "1_snakemake/inputs/profiles/cpcnn/raw.parquet",
        48_201_019,
        "d79b1cebc8aa3999fa993ea2500fab8d",
    ),
    InputSpec(
        "metadata.parquet",
        "1_snakemake/inputs/metadata/metadata.parquet",
        734_477,
        "6731b56f8f4fe2db31fcdf1308c305fb",
    ),
    InputSpec(
        "index.parquet",
        "1_snakemake/inputs/images/index.parquet",
        2_524_798,
        "b56e249504f76bc2f6025f90abc8608c",
    ),
)


@dataclass(frozen=True)
class Notebook:
    """An executable notebook and the Pixi environment it requires."""

    path: str
    environment: str


@dataclass(frozen=True)
class SnakemakeConfig:
    """One named configuration and its deterministic output directory."""

    config: str
    features: str
    name: str
    workflow: str = "mad_featselect"

    @property
    def output_root(self) -> str:
        """Return the output directory relative to 1_snakemake/outputs."""
        return f"{self.features}/{self.name}"


PRODUCER_NOTEBOOKS = (
    Notebook("2_downstream_analysis/manuscript_notebooks/3_2_0_assay_metrics.ipynb", "pipeline"),
    Notebook("2_downstream_analysis/manuscript_notebooks/4_1_results_tables_SI.ipynb", "pipeline"),
    Notebook("2_downstream_analysis/manuscript_notebooks/2_1_predict_continuous_assays.ipynb", "pipeline"),
    Notebook("2_downstream_analysis/manuscript_notebooks/2_2_outlier_enrichment_analysis.ipynb", "pipeline"),
)
ANALYSIS_NOTEBOOKS = (
    Notebook("2_downstream_analysis/manuscript_notebooks/3_2_1_compare_endpoint_types.ipynb", "pipeline"),
    Notebook("2_downstream_analysis/manuscript_notebooks/1_2_number_active_readouts.ipynb", "pipeline"),
    Notebook("2_downstream_analysis/manuscript_notebooks/1_2_1_cmpds_increase_mt.ipynb", "pipeline"),
    Notebook("2_downstream_analysis/manuscript_notebooks/3_1_toxcast_endpoints.ipynb", "pipeline"),
    Notebook("2_downstream_analysis/manuscript_notebooks/3_2_2_compare_concs_reps.ipynb", "pipeline"),
    Notebook("2_downstream_analysis/manuscript_notebooks/3_2_3_compare_endpoints_detail.ipynb", "notebooks"),
    Notebook("2_downstream_analysis/other_notebooks/01_checkwelleffects.ipynb", "pipeline"),
    Notebook("2_downstream_analysis/other_notebooks/02_analyze_AR.ipynb", "notebooks"),
    Notebook("2_downstream_analysis/other_notebooks/03_analyze_ER.ipynb", "notebooks"),
    Notebook("2_downstream_analysis/other_notebooks/04_analyze_GR.ipynb", "notebooks"),
)
EXTENDED_NOTEBOOKS = (
    Notebook("2_downstream_analysis/manuscript_notebooks/1_3_compare_pods.ipynb", "notebooks"),
    Notebook("2_downstream_analysis/manuscript_notebooks/SI_compare_processing.ipynb", "notebooks"),
    Notebook("2_downstream_analysis/other_notebooks/05_compare_pods_transforms.ipynb", "notebooks"),
)
ALL_NOTEBOOKS = PRODUCER_NOTEBOOKS + ANALYSIS_NOTEBOOKS + EXTENDED_NOTEBOOKS

CORE_CONFIGS = (
    SnakemakeConfig("cellprofiler", "cellprofiler", "mad_featselect"),
    SnakemakeConfig("cpcnn", "cpcnn", "mad_featselect"),
    SnakemakeConfig("dino", "dino", "mad_featselect"),
)
FILTERED_CONFIG = SnakemakeConfig("cellprofiler_filt", "cellprofiler", "mad_featselect_filt")
SENSITIVITY_CONFIGS = (
    SnakemakeConfig("cellprofiler_log10", "cellprofiler", "mad_featselect_log10"),
    SnakemakeConfig("cpcnn_log10", "cpcnn", "mad_featselect_log10"),
    SnakemakeConfig("dino_log10", "dino", "mad_featselect_log10"),
    SnakemakeConfig(
        "cellprofiler_int",
        "cellprofiler",
        "mad_int_featselect",
        workflow="mad_int_featselect",
    ),
    SnakemakeConfig("cpcnn_int", "cpcnn", "mad_int_featselect", workflow="mad_int_featselect"),
    SnakemakeConfig("dino_int", "dino", "mad_int_featselect", workflow="mad_int_featselect"),
    SnakemakeConfig("cellprofiler_ap", "cellprofiler", "mad_featselect_ap"),
    SnakemakeConfig("cpcnn_ap", "cpcnn", "mad_featselect_ap"),
    SnakemakeConfig("dino_ap", "dino", "mad_featselect_ap"),
)

SEEDED_COMPILED_RESULTS = (
    "motive_highexp_PHH.parquet",
    "SI_tables/readme.txt",
)
GENERATED_COMPILED_RESULTS = (
    "compiled_axiom_metrics.parquet",
    "compiled_toxcast_cellbased_metrics.parquet",
    "compiled_toxcast_cellfree_metrics.parquet",
    "compiled_toxcast_cytotox_metrics.parquet",
    "err_higher_targets.csv",
    "err_lower_targets.csv",
    "mtt_higher_targets.csv",
    "mtt_lower_targets.csv",
    "SI_tables/cellcount_pods.csv",
    "SI_tables/mt_pods.csv",
    "SI_tables/ldh_pods.csv",
    "SI_tables/cellpainting_cellprofiler_pods.csv",
    "SI_tables/cellpainting_cpcnn_pods.csv",
    "SI_tables/cellpainting_dino_pods.csv",
    "SI_tables/hit_summary.csv",
)
CORE_CONFIG_OUTPUTS = (
    "profiles/mad_featselect.parquet",
    "curves/bmds.parquet",
    "curves/ccpods.parquet",
    "curves/mttpods.parquet",
    "curves/ldhpods.parquet",
    "curves/pods.parquet",
    "aggregated_profiles/agg.parquet",
    "classifier_results/axiom_binary_predictions.parquet",
    "classifier_results/axiom_continuous_predictions.parquet",
    "classifier_results/toxcast_cellbased_binary_predictions.parquet",
    "classifier_results/toxcast_cellfree_binary_predictions.parquet",
    "classifier_results/toxcast_cytotox_binary_predictions.parquet",
    "curves/plots/cc_plots.pdf",
    "curves/plots/mtt_plots.pdf",
    "curves/plots/ldh_plots.pdf",
    "curves/plots/cp_plots.pdf",
    "figures/umaps.pdf",
)
SENSITIVITY_CONFIG_OUTPUTS = (
    "curves/bmds.parquet",
    "curves/pods.parquet",
)
DINO_LOG10_NOTEBOOK_OUTPUTS = (
    "profiles/mad_featselect.parquet",
    "curves/ccpods.parquet",
    "curves/mttpods.parquet",
    "curves/ldhpods.parquet",
)


@dataclass(frozen=True)
class Stage:
    """One ordered unit in the reproduction run."""

    id: str
    title: str
    needs_gpu: bool = False


STAGES = (
    Stage("snapshot", "Archive HEAD and create an isolated working tree"),
    Stage("inputs", "Acquire and fully verify the five public compiled inputs"),
    Stage("environment", "Install both locked Pixi environments"),
    Stage("figure-s1", "Acquire the external TIFFs and render supplemental Figure S1"),
    Stage("snakemake-cellprofiler", "Run the core CellProfiler Snakemake configuration", needs_gpu=True),
    Stage("snakemake-cpcnn", "Run the core CP-CNN Snakemake configuration", needs_gpu=True),
    Stage("snakemake-dino", "Run the core DINO Snakemake configuration", needs_gpu=True),
    Stage("producer-notebooks", "Execute the four artifact-producing notebooks in order"),
    Stage("semantic-verifier", "Compare regenerated compiled results with the preserved reference"),
    Stage("analysis-notebooks", "Execute the remaining documented runnable notebooks"),
    Stage(
        "sensitivity-configs",
        "Run the filtered CellProfiler and nine current sensitivity configurations",
        needs_gpu=True,
    ),
    Stage("extended-notebooks", "Execute the three sensitivity comparison notebooks"),
    Stage("tracked-audit", "Run the tracked source and accounting audit on pristine HEAD"),
    Stage("notebook-export", "Export executed notebooks to greppable Markdown and build an index"),
)
STAGE_IDS = tuple(stage.id for stage in STAGES)


@dataclass(frozen=True)
class RunPaths:
    """Stable paths within one run directory."""

    root: Path
    workspace: Path
    archive: Path
    env_source: Path
    reference: Path
    artifacts: Path
    logs: Path
    manifest: Path

    @classmethod
    def from_root(cls, root: Path) -> RunPaths:
        """Construct the fixed run layout."""
        root = root.resolve()
        return cls(
            root=root,
            workspace=root / "workspace",
            archive=root / "source.tar",
            env_source=root / "env-source",
            reference=root / "reference/compiled_results",
            artifacts=root / "artifacts",
            logs=root / "logs",
            manifest=root / MANIFEST_NAME,
        )


@dataclass
class RunContext:
    """Mutable execution context shared by stage handlers."""

    repository: Path
    paths: RunPaths
    cache: Path
    head: str
    cores: int
    manifest: dict[str, object]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _slug_time() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _hash_file(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_tree(root: Path) -> str:
    """Hash a directory by relative path, byte count, and full file hash."""
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(str(path.stat().st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(_hash_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _notebook_source_hash(path: Path) -> str:
    """Hash notebook cell types and source text while ignoring executed outputs."""
    try:
        notebook = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReproductionError(f"cannot read notebook source identity for {path}: {exc}") from exc
    cells = notebook.get("cells")
    if not isinstance(cells, list):
        raise ReproductionError(f"notebook source identity has no cells: {path}")
    normalized = []
    for cell in cells:
        if not isinstance(cell, dict):
            raise ReproductionError(f"notebook source identity has a malformed cell: {path}")
        source = cell.get("source", [])
        if isinstance(source, list) and all(isinstance(line, str) for line in source):
            source_text = "".join(source)
        elif isinstance(source, str):
            source_text = source
        else:
            raise ReproductionError(f"notebook source identity has malformed source text: {path}")
        normalized.append({"cell_type": cell.get("cell_type"), "source": source_text})
    payload = json.dumps(normalized, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _workspace_path_is_runtime(relative: PurePosixPath) -> bool:
    rendered = relative.as_posix()
    return any(rendered.startswith(prefix) for prefix in WORKSPACE_MUTABLE_PREFIXES) or any(
        part in WORKSPACE_RUNTIME_DIRECTORY_NAMES for part in relative.parts
    )


def _workspace_source_identity(root: Path) -> list[dict[str, object]]:
    """Record immutable archived files, normalizing notebooks across execution."""
    records: list[dict[str, object]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = PurePosixPath(path.relative_to(root).as_posix())
        if relative.as_posix() == ".reproduce-all-snapshot.json" or _workspace_path_is_runtime(relative):
            continue
        if path.suffix.lower() == ".ipynb":
            records.append(
                {
                    "path": relative.as_posix(),
                    "kind": "notebook-source",
                    "sha256": _notebook_source_hash(path),
                },
            )
        else:
            records.append(
                {
                    "path": relative.as_posix(),
                    "kind": "file",
                    "size": path.stat().st_size,
                    "sha256": _hash_file(path),
                },
            )
    return records


def _validate_workspace_source_identity(root: Path, identities: object) -> None:
    """Reject archived source changes before a resumed stage executes."""
    if not isinstance(identities, list) or not identities:
        raise ReproductionError("resume manifest has no archived workspace source identity")
    baseline_paths: set[str] = set()
    for identity in identities:
        if not isinstance(identity, dict) or not isinstance(identity.get("path"), str):
            raise ReproductionError("resume manifest has a malformed workspace source identity")
        relative_text = identity["path"]
        relative = PurePosixPath(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            raise ReproductionError("resume manifest has an unsafe workspace source path")
        path = root.joinpath(*relative.parts)
        baseline_paths.add(relative_text)
        if path.is_symlink() or not path.is_file():
            raise ReproductionError(f"archived workspace source is missing: {relative_text}")
        if identity.get("kind") == "notebook-source":
            observed_sha256 = _notebook_source_hash(path)
        elif identity.get("kind") == "file":
            if identity.get("size") != path.stat().st_size:
                raise ReproductionError(f"archived workspace source size changed: {relative_text}")
            observed_sha256 = _hash_file(path)
        else:
            raise ReproductionError("resume manifest has an unknown workspace source identity kind")
        if identity.get("sha256") != observed_sha256:
            raise ReproductionError(f"archived workspace source changed: {relative_text}")

    added_load_bearing: list[str] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = PurePosixPath(path.relative_to(root).as_posix())
        rendered = relative.as_posix()
        if rendered in baseline_paths or rendered == ".reproduce-all-snapshot.json":
            continue
        if _workspace_path_is_runtime(relative):
            continue
        if path.name == "Snakefile" or path.suffix.lower() in LOAD_BEARING_SUFFIXES:
            added_load_bearing.append(rendered)
    if added_load_bearing:
        raise ReproductionError(
            "unarchived load-bearing source appeared in the workspace: " + ", ".join(added_load_bearing[:10]),
        )


def verify_file(path: Path, *, size: int, md5: str) -> tuple[bool, str]:
    """Verify exact byte count and complete MD5, returning a diagnostic."""
    if not path.is_file():
        return False, "missing"
    observed_size = path.stat().st_size
    if observed_size != size:
        return False, f"size {observed_size}, expected {size}"
    observed_md5 = _hash_file(path, "md5")
    if observed_md5 != md5:
        return False, f"md5 {observed_md5}, expected {md5}"
    return True, "verified"


def _quarantine(path: Path, label: str) -> Path:
    """Move an unexpected partial artifact aside without deleting it."""
    suffix = f".{label}-{_slug_time()}"
    destination = path.with_name(path.name + suffix)
    counter = 1
    while destination.exists() or destination.is_symlink():
        destination = path.with_name(path.name + suffix + f"-{counter}")
        counter += 1
    os.replace(path, destination)
    return destination


def _download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "axiom-oasis-reproduce-all/1"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("xb") as output:  # noqa: S310
        shutil.copyfileobj(response, output, length=1024 * 1024)
        output.flush()
        os.fsync(output.fileno())


def acquire_input(
    spec: InputSpec,
    cache: Path,
    *,
    verified_local_source: Path | None = None,
    downloader: Callable[[str, Path], None] = _download,
) -> tuple[Path, str]:
    """Return an exact cached deposit file, copying or downloading atomically."""
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / spec.name
    valid, diagnostic = verify_file(destination, size=spec.size, md5=spec.md5)
    if valid:
        return destination, "reused"
    if destination.exists() or destination.is_symlink():
        _quarantine(destination, "invalid")

    if verified_local_source is not None:
        valid, _ = verify_file(verified_local_source, size=spec.size, md5=spec.md5)
        if valid:
            _copy_atomic(verified_local_source, destination)
            valid, diagnostic = verify_file(destination, size=spec.size, md5=spec.md5)
            if not valid:
                raise StageError(f"cached copy of {spec.name} failed verification: {diagnostic}")
            return destination, "copied-from-verified-checkout"

    partial = destination.with_name(destination.name + ".part")
    if partial.exists() or partial.is_symlink():
        _quarantine(partial, "stale")
    downloader(spec.url, partial)
    valid, diagnostic = verify_file(partial, size=spec.size, md5=spec.md5)
    if not valid:
        quarantined = _quarantine(partial, "invalid")
        raise StageError(f"downloaded {spec.name} failed verification ({diagnostic}); kept at {quarantined}")
    os.replace(partial, destination)
    return destination, "downloaded"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _safe_extract_tar(archive_path: Path, destination: Path) -> None:
    """Extract regular Git archive files without links or path traversal."""
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    directory_modes: list[tuple[Path, int]] = []
    with tarfile.open(archive_path, mode="r:") as archive:
        members = archive.getmembers()
        validated: list[tuple[tarfile.TarInfo, Path]] = []
        seen: set[Path] = set()
        for member in members:
            member_path = PurePosixPath(member.name)
            if member_path.is_absolute() or ".." in member_path.parts or not member_path.parts:
                raise ReproductionError(f"unsafe archive member: {member.name!r}")
            target = destination.joinpath(*member_path.parts)
            resolved_target = target.resolve(strict=False)
            if not _is_relative_to(resolved_target, destination):
                raise ReproductionError(f"archive member escapes destination: {member.name!r}")
            if resolved_target in seen:
                raise ReproductionError(f"archive contains a duplicate member: {member.name!r}")
            seen.add(resolved_target)
            if not member.isdir() and not member.isfile():
                raise ReproductionError(f"archive contains unsupported member type: {member.name!r}")
            validated.append((member, target))

        for member, target in validated:
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                directory_modes.append((target, member.mode & 0o777))
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ReproductionError(f"archive member has no file payload: {member.name!r}")
            with source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
            target.chmod(member.mode & 0o777)
    for directory, mode in reversed(directory_modes):
        directory.chmod(mode)


def _atomic_json(path: Path, value: object) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    if temporary.exists() or temporary.is_symlink():
        _quarantine(temporary, "stale")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _git_head(repository: Path) -> str:
    process = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise ReproductionError(f"cannot resolve Git HEAD: {process.stderr.strip()}")
    head = process.stdout.strip()
    if len(head) != 40 or any(character not in "0123456789abcdef" for character in head):
        raise ReproductionError(f"Git returned an invalid HEAD: {head!r}")
    return head


def _require_committed_orchestrator(repository: Path, head: str) -> str:
    """Require this live runner to be the exact version stored at the captured commit."""
    live_path = repository / ORCHESTRATOR_RELATIVE_PATH
    live_sha256 = _hash_file(live_path)
    process = subprocess.run(
        ["git", "show", f"{head}:{ORCHESTRATOR_RELATIVE_PATH}"],
        cwd=repository,
        check=False,
        capture_output=True,
    )
    if process.returncode != 0:
        diagnostic = process.stderr.decode("utf-8", errors="backslashreplace").strip()
        raise ReproductionError(f"cannot read the orchestrator from captured Git commit: {diagnostic}")
    head_sha256 = hashlib.sha256(process.stdout).hexdigest()
    if live_sha256 != head_sha256:
        raise ReproductionError(
            "paper/reproduce_all.py differs from the captured Git commit; commit it before starting or resuming a run",
        )
    return live_sha256


def _git_ignored(repository: Path, path: Path) -> bool:
    process = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", os.fspath(path)],
        cwd=repository,
        check=False,
    )
    return process.returncode == 0


def _validate_run_dir(repository: Path, run_dir: Path, *, resume: bool) -> Path:
    repository = repository.resolve()
    run_dir = run_dir.resolve()
    if run_dir == repository or _is_relative_to(repository, run_dir):
        raise ReproductionError("the run directory cannot be the repository or one of its parents")
    if _is_relative_to(run_dir, repository / ".git"):
        raise ReproductionError("the run directory cannot be inside .git")
    if resume:
        if not run_dir.is_dir():
            raise ReproductionError("--resume requires an existing run directory")
    elif run_dir.exists() or run_dir.is_symlink():
        raise ReproductionError("run directory already exists; use --resume only for a manifest-backed run")
    if _is_relative_to(run_dir, repository) and not _git_ignored(repository, run_dir):
        raise ReproductionError("a run directory inside the repository must be ignored by Git")
    return run_dir


def _nearest_existing_parent(path: Path) -> Path:
    candidate = path
    while not candidate.exists():
        if candidate.parent == candidate:
            raise ReproductionError(f"no existing parent for {path}")
        candidate = candidate.parent
    return candidate


def _preflight(run_dir: Path, selected: Sequence[Stage]) -> None:
    required_tools = {"git"}
    if any(stage.id not in {"snapshot", "inputs", "tracked-audit"} for stage in selected):
        required_tools.add("nix")
    if any(stage.id == "tracked-audit" for stage in selected):
        required_tools.add("uv")
    missing = sorted(tool for tool in required_tools if shutil.which(tool) is None)
    if missing:
        raise ReproductionError(f"required tools are not on PATH: {', '.join(missing)}")
    free = shutil.disk_usage(_nearest_existing_parent(run_dir)).free
    if free < MINIMUM_FREE_BYTES:
        required_gib = MINIMUM_FREE_BYTES / 1024**3
        raise ReproductionError(f"at least {required_gib:.0f} GiB free is required; found {free / 1024**3:.1f} GiB")
    if any(stage.needs_gpu for stage in selected):
        executable = shutil.which("nvidia-smi")
        if executable is None:
            raise ReproductionError("GPU compute was requested but nvidia-smi is not on PATH")
        process = subprocess.run([executable, "-L"], check=False, capture_output=True, text=True)
        if process.returncode != 0 or "GPU " not in process.stdout:
            diagnostic = process.stderr.strip() or process.stdout.strip() or "no GPU reported"
            raise ReproductionError(f"CUDA GPU preflight failed: {diagnostic}")


def _nix_pixi(paths: RunPaths, *arguments: str) -> list[str]:
    return [
        "nix",
        "develop",
        f"path:{paths.env_source}",
        "--command",
        "pixi",
        "--manifest-path",
        os.fspath(paths.workspace / "pixi.toml"),
        *arguments,
    ]


def _notebook_execute_command(paths: RunPaths, notebook: Notebook) -> list[str]:
    notebook_path = paths.workspace / notebook.path
    return _nix_pixi(
        paths,
        "run",
        "-e",
        notebook.environment,
        "jupyter",
        "nbconvert",
        "--to",
        "notebook",
        "--execute",
        "--inplace",
        "--ExecutePreprocessor.kernel_name=python3",
        notebook_path.name,
    )


def _snakemake_command(
    paths: RunPaths,
    config: SnakemakeConfig,
    cores: int,
    *targets: str,
) -> list[str]:
    """Build one resumable Snakemake invocation from a pinned configuration."""
    return _nix_pixi(
        paths,
        "run",
        "-e",
        "pipeline",
        "snakemake",
        "--configfile",
        f"inputs/conf/{config.config}.json",
        "--cores",
        str(cores),
        "--rerun-incomplete",
        *targets,
    )


def build_command_plan(paths: RunPaths, cores: int, head: str) -> dict[str, list[list[str]]]:
    """Build the exact external command sequence for every stage."""
    workspace = paths.workspace
    plan: dict[str, list[list[str]]] = {stage.id: [] for stage in STAGES}
    plan["snapshot"] = [
        ["git", "archive", "--format=tar", "--output", os.fspath(paths.archive) + ".part", head],
    ]
    plan["environment"] = [_nix_pixi(paths, "install", "--all", "--frozen")]
    plan["figure-s1"] = [
        _nix_pixi(
            paths,
            "run",
            "-e",
            "notebooks",
            "python",
            os.fspath(workspace / "paper/render_sfig1.py"),
            "--index",
            os.fspath(workspace / "1_snakemake/inputs/images/index.parquet"),
            "--metadata",
            os.fspath(workspace / "1_snakemake/inputs/metadata/metadata.parquet"),
            "--output-dir",
            os.fspath(paths.artifacts / "sfig1"),
        ),
    ]
    for config in CORE_CONFIGS:
        plan[f"snakemake-{config.config}"] = [_snakemake_command(paths, config, cores)]
    plan["producer-notebooks"] = [_notebook_execute_command(paths, notebook) for notebook in PRODUCER_NOTEBOOKS]
    plan["semantic-verifier"] = [
        _nix_pixi(
            paths,
            "run",
            "-e",
            "pipeline",
            "python",
            "-m",
            "paper.verification.compiled_results",
            "--reference",
            os.fspath(paths.reference),
            "--candidate",
            os.fspath(workspace / "2_downstream_analysis/compiled_results"),
            "--json-report",
            os.fspath(paths.artifacts / "semantic-verification.json"),
        ),
    ]
    plan["analysis-notebooks"] = [_notebook_execute_command(paths, notebook) for notebook in ANALYSIS_NOTEBOOKS]
    sensitivity_commands = [_snakemake_command(paths, FILTERED_CONFIG, cores)]
    for config in SENSITIVITY_CONFIGS:
        output_root = f"outputs/{config.output_root}"
        targets = [f"{output_root}/curves/pods.parquet"]
        if config.config == "dino_log10":
            targets.extend(
                [
                    f"{output_root}/curves/mttpods.parquet",
                    f"{output_root}/curves/ldhpods.parquet",
                ],
            )
        sensitivity_commands.append(_snakemake_command(paths, config, cores, *targets))
    plan["sensitivity-configs"] = sensitivity_commands
    plan["extended-notebooks"] = [_notebook_execute_command(paths, notebook) for notebook in EXTENDED_NOTEBOOKS]
    tracked_source = paths.root / "tracked-audit-source"
    plan["tracked-audit"] = [
        [
            "uv",
            "run",
            "--cache-dir",
            os.fspath(paths.root / "uv-cache"),
            "--frozen",
            os.fspath(tracked_source / "paper/reproduce.py"),
            "--output",
            os.fspath(paths.artifacts / "tracked-audit"),
        ],
    ]
    export_root = paths.artifacts / "notebooks"
    plan["notebook-export"] = [
        _nix_pixi(
            paths,
            "run",
            "-e",
            notebook.environment,
            "jupyter",
            "nbconvert",
            "--to",
            "markdown",
            "--output-dir",
            os.fspath(export_root),
            os.fspath(workspace / notebook.path),
        )
        for notebook in ALL_NOTEBOOKS
    ]
    return plan


def _initial_manifest(
    repository: Path,
    paths: RunPaths,
    head: str,
    cores: int,
    orchestrator_sha256: str | None = None,
) -> dict[str, object]:
    created = _utc_now()
    orchestrator_sha256 = orchestrator_sha256 or _hash_file(Path(__file__).resolve())
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "running",
        "created_at": created,
        "updated_at": created,
        "repository": {
            "source": os.fspath(repository),
            "head": head,
            "orchestrator_sha256": orchestrator_sha256,
        },
        "run": {
            "root": os.fspath(paths.root),
            "workspace": "workspace",
            "cores": cores,
        },
        "candidate": {
            "root": "workspace",
            "compiled_results": "workspace/2_downstream_analysis/compiled_results",
            "acceptance": "paper.verification.compiled_results against reference/compiled_results",
            "tracked_audit": "Runs separately against a pristine extraction of the Git archive.",
            "future_seam": (
                "paper/reproduce.py is tracked-only today; a future regenerated mode must accept an explicit "
                "candidate root instead of silently reading this workspace."
            ),
        },
        "scope": {
            "claim": (
                "Regenerates the supported upstream analyses and current sensitivity layers, executes the "
                "documented runnable notebooks, and evaluates the repository's numerical acceptance gates."
            ),
            "does_not_claim": "The publisher's composite paper figures are not rebuilt pixel-for-pixel.",
            "generated_upstream_artifacts": {
                "root": "workspace/1_snakemake/outputs",
                "count": 0,
                "by_config": {},
            },
            "generated_notebook_artifacts": {
                "root": "workspace/2_downstream_analysis/compiled_results",
                "files": [],
            },
            "executed_notebook_figures": {
                "root": "artifacts/notebooks",
                "count": 0,
                "note": "Figures are notebook outputs exported with greppable Markdown, not publisher composites.",
            },
            "external_image_artifacts": {
                "root": "artifacts/sfig1",
                "figure": "artifacts/sfig1/figure-s1-reproduced.png",
                "report": "artifacts/sfig1/figure-s1-report.json",
                "note": "A standalone reconstruction from resolved source TIFFs, not a publisher composite page.",
                "source_policy": "The repository index resolves the URLs; the report records observed full TIFF hashes because no published checksums exist.",
            },
            "executed_notebooks": {
                "producer": [notebook.path for notebook in PRODUCER_NOTEBOOKS],
                "analysis": [notebook.path for notebook in ANALYSIS_NOTEBOOKS],
                "extended": [notebook.path for notebook in EXTENDED_NOTEBOOKS],
            },
            "sensitivity_layer": {
                "filtered_config": FILTERED_CONFIG.config,
                "partial_configs": [config.config for config in SENSITIVITY_CONFIGS],
                "acceptance_gate": None,
                "interpretation": (
                    "These are current-code sensitivity reruns for comparison notebooks. They are inventoried "
                    "separately and are not treated as recovered historical acceptance substrates."
                ),
            },
            "acceptance_reports": [],
            "seeded_inputs": [
                {
                    "path": f"workspace/2_downstream_analysis/compiled_results/{relative}",
                    "reason": "No runnable producer is in the supported recipe; copied from tracked HEAD and excluded from core gates.",
                }
                for relative in SEEDED_COMPILED_RESULTS
            ]
            + [
                {
                    "path": "workspace/1_snakemake/inputs/metadata/cc.parquet",
                    "reason": "Tracked, load-bearing input with no producer in the repository.",
                },
                {
                    "path": "workspace/1_snakemake/inputs/annotations",
                    "reason": "Tracked annotation substrate; the published invitrodb acquisition script is non-functional.",
                },
            ],
            "known_gaps": [
                "The _int configurations use the repository's current corrected workflow; historical pre-correction outputs are unavailable.",
                "The current _ap configurations use stable per-compound seeds, but no historical AP dependency, RNG state, or acceptance substrate is available.",
                "The historical Figure 2C significance substrate remains unavailable.",
                "MT discrepancy enrichment is gated for target-library identity and internal statistical validity; its current-versus-historical numerical drift remains diagnostic.",
                "Supplementary Figure 1 source TIFFs are external and acquired at run time.",
                "Both cellprofiler and cellprofiler_filt are run, but the manuscript ambiguity about the authoritative historical substrate remains.",
                "Tracked source auditing is accounting and source-integrity evidence, not regenerated-candidate acceptance.",
            ],
        },
        "inputs": [],
        "stages": [
            {
                "id": stage.id,
                "title": stage.title,
                "required": True,
                "status": "pending",
                "attempts": [],
            }
            for stage in STAGES
        ],
        "invocations": [],
    }


def _load_manifest(paths: RunPaths, head: str, orchestrator_sha256: str) -> dict[str, object]:
    try:
        manifest = json.loads(paths.manifest.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReproductionError(f"cannot load resume manifest: {exc}") from exc
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ReproductionError("resume manifest schema does not match this orchestrator")
    repository = manifest.get("repository")
    if not isinstance(repository, dict) or repository.get("head") != head:
        raise ReproductionError("resume manifest HEAD does not match the current repository HEAD")
    if repository.get("orchestrator_sha256") != orchestrator_sha256:
        raise ReproductionError("resume manifest orchestrator does not match the committed runner")
    run = manifest.get("run")
    if not isinstance(run, dict) or Path(str(run.get("root"))).resolve() != paths.root:
        raise ReproductionError("resume manifest belongs to a different run directory")
    stages = manifest.get("stages")
    if not isinstance(stages, list) or [item.get("id") for item in stages if isinstance(item, dict)] != list(STAGE_IDS):
        raise ReproductionError("resume manifest stage inventory is invalid")
    _validate_resume_state(paths, manifest, head)
    return manifest


def _validate_resume_state(paths: RunPaths, manifest: dict[str, object], head: str) -> None:
    """Reject a resume whose completed-stage substrates no longer match."""
    if _stage_record(manifest, "snapshot").get("status") == "succeeded":
        repository = manifest["repository"]
        if not isinstance(repository, dict):
            raise ReproductionError("resume manifest repository record is malformed")
        archive_sha256 = repository.get("archive_sha256")
        reference_sha256 = repository.get("reference_compiled_results_sha256")
        environment_source_sha256 = repository.get("environment_source_sha256")
        if not isinstance(archive_sha256, str) or not paths.archive.is_file():
            raise ReproductionError("completed snapshot is missing its preserved Git archive")
        if _hash_file(paths.archive) != archive_sha256:
            raise ReproductionError("preserved Git archive changed after the completed snapshot")
        if not isinstance(reference_sha256, str) or not paths.reference.is_dir():
            raise ReproductionError("completed snapshot is missing its compiled-results reference")
        if _hash_tree(paths.reference) != reference_sha256:
            raise ReproductionError("compiled-results reference changed after the completed snapshot")
        if _tree_has_write_bits(paths.reference):
            raise ReproductionError("compiled-results reference is no longer read-only")
        marker_path = paths.workspace / ".reproduce-all-snapshot.json"
        try:
            marker = json.loads(marker_path.read_text(encoding="ascii"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ReproductionError(f"cannot validate isolated workspace marker: {exc}") from exc
        if marker.get("head") != head or marker.get("archive_sha256") != archive_sha256:
            raise ReproductionError("isolated workspace marker does not match the resume manifest")
        if not paths.env_source.is_dir() or not all(
            (paths.env_source / name).is_file() for name in ("flake.nix", "flake.lock")
        ):
            raise ReproductionError("completed snapshot is missing the immutable Nix environment source")
        if not isinstance(environment_source_sha256, str) or _hash_tree(paths.env_source) != environment_source_sha256:
            raise ReproductionError("immutable Nix environment source changed after the completed snapshot")
        if _tree_has_write_bits(paths.env_source):
            raise ReproductionError("immutable Nix environment source is no longer read-only")
        _validate_workspace_source_identity(paths.workspace, repository.get("workspace_source_identity"))
    if _stage_record(manifest, "inputs").get("status") == "succeeded":
        for spec in INPUTS:
            valid, diagnostic = verify_file(paths.workspace / spec.destination, size=spec.size, md5=spec.md5)
            if not valid:
                raise ReproductionError(f"completed input stage is no longer valid for {spec.name}: {diagnostic}")
    run = manifest["run"]
    if not isinstance(run, dict) or not isinstance(run.get("cores"), int):
        raise ReproductionError("resume manifest core count is malformed")
    context = RunContext(
        repository=REPOSITORY_ROOT,
        paths=paths,
        cache=DEFAULT_CACHE,
        head=head,
        cores=run["cores"],
        manifest=manifest,
    )
    for stage in STAGES:
        if _stage_record(manifest, stage.id).get("status") != "succeeded":
            continue
        try:
            _validate_stage_outputs(context, stage.id)
            _validate_stage_output_identity(context, stage.id)
        except StageError as exc:
            raise ReproductionError(
                f"completed stage {stage.id} no longer satisfies its output contract: {exc}",
            ) from exc


def _stage_record(manifest: dict[str, object], stage_id: str) -> dict[str, object]:
    stages = manifest["stages"]
    if not isinstance(stages, list):
        raise ReproductionError("manifest stages are malformed")
    for record in stages:
        if isinstance(record, dict) and record.get("id") == stage_id:
            return record
    raise ReproductionError(f"manifest does not contain stage {stage_id}")


def _save_manifest(context: RunContext) -> None:
    context.manifest["updated_at"] = _utc_now()
    _atomic_json(context.paths.manifest, context.manifest)


def _command_text(command: Sequence[str]) -> str:
    return " ".join(
        json.dumps(argument) if any(character.isspace() for character in argument) else argument for argument in command
    )


def _run_command(command: Sequence[str], *, cwd: Path, log: TextIO) -> None:
    rendered = _command_text(command)
    log.write(f"$ {rendered}\n")
    log.flush()
    print(f"$ {rendered}", flush=True)
    try:
        process = subprocess.Popen(
            list(command),
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="backslashreplace",
            bufsize=1,
        )
    except OSError as exc:
        raise StageError(f"could not start {command[0]}: {exc}") from exc
    if process.stdout is None:
        raise StageError(f"could not capture output from {command[0]}")
    for line in process.stdout:
        print(line, end="", flush=True)
        log.write(line)
        log.flush()
    return_code = process.wait()
    if return_code != 0:
        raise StageError(f"command exited {return_code}: {rendered}")


def _copy_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    if partial.exists() or partial.is_symlink():
        _quarantine(partial, "stale")
    with source.open("rb") as input_handle, partial.open("xb") as output_handle:
        shutil.copyfileobj(input_handle, output_handle, length=1024 * 1024)
        output_handle.flush()
        os.fsync(output_handle.fileno())
    os.replace(partial, destination)


def _make_tree_read_only(root: Path) -> None:
    """Remove every write bit from a preserved reference tree."""
    paths = sorted(root.rglob("*"), key=lambda path: len(path.parts), reverse=True)
    for path in [*paths, root]:
        path.chmod(path.stat().st_mode & ~0o222)


def _tree_has_write_bits(root: Path) -> bool:
    """Return whether any preserved-reference path is mode-writable."""
    return any(path.stat().st_mode & 0o222 for path in [root, *root.rglob("*")])


def _stage_snapshot(context: RunContext, commands: Sequence[Sequence[str]], log: TextIO) -> None:
    paths = context.paths
    archive_partial = paths.archive.with_name(paths.archive.name + ".part")
    env_partial = paths.env_source.with_name(paths.env_source.name + ".part")
    for path in (
        archive_partial,
        paths.archive,
        paths.workspace,
        paths.env_source,
        env_partial,
        paths.reference.parent,
    ):
        if path.exists() or path.is_symlink():
            _quarantine(path, "incomplete-snapshot")
    _run_command(commands[0], cwd=context.repository, log=log)
    archive_sha256 = _hash_file(archive_partial)
    os.replace(archive_partial, paths.archive)

    workspace_partial = paths.workspace.with_name(paths.workspace.name + ".part")
    if workspace_partial.exists() or workspace_partial.is_symlink():
        _quarantine(workspace_partial, "stale")
    _safe_extract_tar(paths.archive, workspace_partial)

    tracked_results = workspace_partial / "2_downstream_analysis/compiled_results"
    if not tracked_results.is_dir():
        raise StageError("Git archive is missing tracked compiled_results")
    paths.reference.parent.mkdir(parents=True, exist_ok=False)
    os.replace(tracked_results, paths.reference)
    candidate_results = workspace_partial / "2_downstream_analysis/compiled_results"
    candidate_results.mkdir(parents=True)
    for relative in SEEDED_COMPILED_RESULTS:
        source = paths.reference / relative
        if not source.is_file():
            raise StageError(f"tracked reference is missing seeded artifact: {relative}")
        _copy_atomic(source, candidate_results / relative)
    _make_tree_read_only(paths.reference)

    env_partial.mkdir(parents=True, exist_ok=False)
    for name in ("flake.nix", "flake.lock"):
        source = workspace_partial / name
        if not source.is_file():
            raise StageError(f"Git archive is missing {name}")
        shutil.copy2(source, env_partial / name)
        (env_partial / name).chmod(0o444)
    env_partial.chmod(0o555)
    os.replace(env_partial, paths.env_source)

    context.manifest["repository"]["workspace_source_identity"] = _workspace_source_identity(  # type: ignore[index]
        workspace_partial,
    )
    context.manifest["repository"]["environment_source_sha256"] = _hash_tree(paths.env_source)  # type: ignore[index]

    marker = {
        "schema_version": SCHEMA_VERSION,
        "head": context.head,
        "archive_sha256": archive_sha256,
        "note": "This workspace came from git archive HEAD; the canonical checkout is not a compute target.",
    }
    _atomic_json(workspace_partial / ".reproduce-all-snapshot.json", marker)
    os.replace(workspace_partial, paths.workspace)
    context.manifest["repository"]["archive_sha256"] = archive_sha256  # type: ignore[index]
    context.manifest["repository"]["reference_compiled_results_sha256"] = _hash_tree(  # type: ignore[index]
        paths.reference,
    )
    log.write(f"Archived and extracted HEAD {context.head}; sha256={archive_sha256}\n")


def _stage_inputs(context: RunContext, log: TextIO) -> None:
    records: list[dict[str, object]] = []
    for spec in INPUTS:
        cached, disposition = acquire_input(
            spec,
            context.cache,
            verified_local_source=context.repository / spec.destination,
        )
        destination = context.paths.workspace / spec.destination
        if destination.exists() or destination.is_symlink():
            valid, diagnostic = verify_file(destination, size=spec.size, md5=spec.md5)
            if not valid:
                quarantined = _quarantine(destination, "invalid")
                log.write(f"Moved invalid workspace input to {quarantined}: {diagnostic}\n")
            else:
                records.append(
                    {
                        "path": f"workspace/{spec.destination}",
                        "source": spec.url,
                        "size": spec.size,
                        "md5": spec.md5,
                        "cache": disposition,
                    },
                )
                continue
        _copy_atomic(cached, destination)
        valid, diagnostic = verify_file(destination, size=spec.size, md5=spec.md5)
        if not valid:
            raise StageError(f"workspace copy of {spec.name} failed verification: {diagnostic}")
        records.append(
            {
                "path": f"workspace/{spec.destination}",
                "source": spec.url,
                "size": spec.size,
                "md5": spec.md5,
                "cache": disposition,
            },
        )
        log.write(f"{spec.name}: {disposition}, exact size and full MD5 verified\n")
        log.flush()
    context.manifest["inputs"] = records


def _run_commands(
    context: RunContext,
    stage_id: str,
    commands: Sequence[Sequence[str]],
    log: TextIO,
) -> None:
    if stage_id.startswith("snakemake-") or stage_id == "sensitivity-configs":
        cwd = context.paths.workspace / "1_snakemake"
    elif stage_id in {"producer-notebooks", "analysis-notebooks", "extended-notebooks"}:
        notebooks_by_stage = {
            "producer-notebooks": PRODUCER_NOTEBOOKS,
            "analysis-notebooks": ANALYSIS_NOTEBOOKS,
            "extended-notebooks": EXTENDED_NOTEBOOKS,
        }
        notebooks = notebooks_by_stage[stage_id]
        for command, notebook in zip(commands, notebooks, strict=True):
            _run_command(command, cwd=(context.paths.workspace / notebook.path).parent, log=log)
        return
    else:
        cwd = context.paths.workspace
    for command in commands:
        _run_command(command, cwd=cwd, log=log)


def _stage_tracked_audit(context: RunContext, commands: Sequence[Sequence[str]], log: TextIO) -> None:
    archive_sha256 = context.manifest["repository"].get("archive_sha256")  # type: ignore[union-attr]
    if not isinstance(archive_sha256, str) or _hash_file(context.paths.archive) != archive_sha256:
        raise StageError("preserved Git archive checksum changed before the tracked audit")
    tracked_source = context.paths.root / "tracked-audit-source"
    if tracked_source.exists() or tracked_source.is_symlink():
        _quarantine(tracked_source, "previous-attempt")
    _safe_extract_tar(context.paths.archive, tracked_source)
    _run_command(commands[0], cwd=tracked_source, log=log)


def _write_notebook_index(context: RunContext) -> None:
    export_root = context.paths.artifacts / "notebooks"
    markdown_files = sorted(export_root.glob("*.md"))
    lines = [
        "# Executed notebook index",
        "",
        "These Markdown files were exported from notebooks executed inside this isolated run.",
        "",
        "They expose notebook code, text, tables, and extracted figures for search and review.",
        "",
        "They are not publisher composite figures and should not be described as pixel-identical paper figures.",
        "",
        "## Notebooks",
        "",
    ]
    lines.extend(f"- [{path.stem}]({path.name})" for path in markdown_files)
    lines.append("")
    (export_root / "index.md").write_text("\n".join(lines), encoding="ascii")
    image_suffixes = {".png", ".jpg", ".jpeg", ".svg"}
    figure_count = sum(1 for path in export_root.rglob("*") if path.is_file() and path.suffix.lower() in image_suffixes)
    figures = context.manifest["scope"]["executed_notebook_figures"]  # type: ignore[index]
    figures["count"] = figure_count  # type: ignore[index]
    figures["notebook_count"] = len(markdown_files)  # type: ignore[index]


def _stage_notebook_export(context: RunContext, commands: Sequence[Sequence[str]], log: TextIO) -> None:
    export_root = context.paths.artifacts / "notebooks"
    export_root.mkdir(parents=True, exist_ok=True)
    for command in commands:
        _run_command(command, cwd=context.paths.workspace, log=log)
    _write_notebook_index(context)


def _require_nonempty_files(paths: Sequence[Path], label: str) -> None:
    missing = [path for path in paths if not path.is_file() or path.stat().st_size == 0]
    if missing:
        rendered = ", ".join(os.fspath(path) for path in missing)
        raise StageError(f"{label} did not produce required nonempty files: {rendered}")


def _require_executed_notebooks(paths: Sequence[Path], label: str) -> None:
    """Require valid notebooks whose nonempty code cells completed without errors."""
    _require_nonempty_files(paths, label)
    for path in paths:
        try:
            notebook = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise StageError(f"{label} produced an unreadable notebook {path}: {exc}") from exc
        cells = notebook.get("cells")
        if not isinstance(cells, list):
            raise StageError(f"{label} produced a malformed notebook without cells: {path}")
        code_cells = [
            cell
            for cell in cells
            if isinstance(cell, dict) and cell.get("cell_type") == "code" and "".join(cell.get("source", [])).strip()
        ]
        if not code_cells or any(cell.get("execution_count") is None for cell in code_cells):
            raise StageError(f"{label} did not execute every nonempty code cell in {path}")
        if any(
            isinstance(output, dict) and output.get("output_type") == "error"
            for cell in code_cells
            for output in cell.get("outputs", [])
        ):
            raise StageError(f"{label} left an error output in {path}")


def _validate_stage_outputs(context: RunContext, stage_id: str) -> None:
    """Make a successful process exit prove its stage's minimum artifact contract."""
    if stage_id == "environment":
        environment_root = context.paths.workspace / ".pixi/envs"
        _require_nonempty_files(
            [
                environment_root / "pipeline/conda-meta/history",
                environment_root / "pipeline/bin/python",
                environment_root / "notebooks/conda-meta/history",
                environment_root / "notebooks/bin/python",
            ],
            stage_id,
        )
    elif stage_id.startswith("snakemake-"):
        config = stage_id.removeprefix("snakemake-")
        root = context.paths.workspace / f"1_snakemake/outputs/{config}/mad_featselect"
        _require_nonempty_files([root / relative for relative in CORE_CONFIG_OUTPUTS], stage_id)
    elif stage_id == "sensitivity-configs":
        output_root = context.paths.workspace / "1_snakemake/outputs"
        filtered_root = output_root / FILTERED_CONFIG.output_root
        _require_nonempty_files([filtered_root / relative for relative in CORE_CONFIG_OUTPUTS], FILTERED_CONFIG.config)
        for config in SENSITIVITY_CONFIGS:
            config_root = output_root / config.output_root
            required = list(SENSITIVITY_CONFIG_OUTPUTS)
            if config.config == "dino_log10":
                required.extend(DINO_LOG10_NOTEBOOK_OUTPUTS)
            _require_nonempty_files([config_root / relative for relative in required], config.config)
    elif stage_id == "producer-notebooks":
        root = context.paths.workspace / "2_downstream_analysis/compiled_results"
        _require_nonempty_files([root / relative for relative in GENERATED_COMPILED_RESULTS], stage_id)
        _require_executed_notebooks(
            [context.paths.workspace / notebook.path for notebook in PRODUCER_NOTEBOOKS],
            stage_id,
        )
    elif stage_id == "analysis-notebooks":
        _require_executed_notebooks(
            [context.paths.workspace / notebook.path for notebook in ANALYSIS_NOTEBOOKS],
            stage_id,
        )
    elif stage_id == "extended-notebooks":
        _require_executed_notebooks(
            [context.paths.workspace / notebook.path for notebook in EXTENDED_NOTEBOOKS],
            stage_id,
        )
    elif stage_id == "semantic-verifier":
        _require_nonempty_files([context.paths.artifacts / "semantic-verification.json"], stage_id)
    elif stage_id == "figure-s1":
        tiffs = sorted(
            path
            for path in (context.paths.artifacts / "sfig1/tiffs").glob("*")
            if path.is_file() and path.suffix.lower() in {".tif", ".tiff"}
        )
        if len(tiffs) != EXPECTED_FIGURE_S1_TIFFS:
            raise StageError(
                f"figure-s1 produced {len(tiffs)} cached TIFFs; expected {EXPECTED_FIGURE_S1_TIFFS}",
            )
        _require_nonempty_files(
            [
                context.paths.artifacts / "sfig1/figure-s1-reproduced.png",
                context.paths.artifacts / "sfig1/figure-s1-report.json",
                *tiffs,
            ],
            stage_id,
        )
    elif stage_id == "tracked-audit":
        _require_nonempty_files([context.paths.artifacts / "tracked-audit/report.json"], stage_id)
    elif stage_id == "notebook-export":
        export_root = context.paths.artifacts / "notebooks"
        _require_nonempty_files(
            [export_root / f"{Path(notebook.path).stem}.md" for notebook in ALL_NOTEBOOKS] + [export_root / "index.md"],
            stage_id,
        )


def _stage_identity_paths(context: RunContext, stage_id: str) -> list[Path]:
    """Return the complete durable identity contract for one completed stage."""
    workspace = context.paths.workspace
    if stage_id == "environment":
        root = workspace / ".pixi/envs"
        return [
            root / "pipeline/conda-meta/history",
            root / "pipeline/bin/python",
            root / "notebooks/conda-meta/history",
            root / "notebooks/bin/python",
        ]
    if stage_id.startswith("snakemake-"):
        config = stage_id.removeprefix("snakemake-")
        root = workspace / f"1_snakemake/outputs/{config}/mad_featselect"
        return [root / relative for relative in CORE_CONFIG_OUTPUTS]
    if stage_id == "sensitivity-configs":
        output_root = workspace / "1_snakemake/outputs"
        paths = [(output_root / FILTERED_CONFIG.output_root / relative) for relative in CORE_CONFIG_OUTPUTS]
        for config in SENSITIVITY_CONFIGS:
            required = list(SENSITIVITY_CONFIG_OUTPUTS)
            if config.config == "dino_log10":
                required.extend(DINO_LOG10_NOTEBOOK_OUTPUTS)
            paths.extend(output_root / config.output_root / relative for relative in required)
        return paths
    if stage_id == "producer-notebooks":
        root = workspace / "2_downstream_analysis/compiled_results"
        return [root / relative for relative in GENERATED_COMPILED_RESULTS] + [
            workspace / notebook.path for notebook in PRODUCER_NOTEBOOKS
        ]
    if stage_id == "analysis-notebooks":
        return [workspace / notebook.path for notebook in ANALYSIS_NOTEBOOKS]
    if stage_id == "extended-notebooks":
        return [workspace / notebook.path for notebook in EXTENDED_NOTEBOOKS]
    if stage_id == "semantic-verifier":
        return [context.paths.artifacts / "semantic-verification.json"]
    if stage_id == "figure-s1":
        return [
            context.paths.artifacts / "sfig1/figure-s1-reproduced.png",
            context.paths.artifacts / "sfig1/figure-s1-report.json",
            *sorted(
                path
                for path in (context.paths.artifacts / "sfig1/tiffs").glob("*")
                if path.is_file() and path.suffix.lower() in {".tif", ".tiff"}
            ),
        ]
    if stage_id == "tracked-audit":
        return sorted(path for path in (context.paths.artifacts / "tracked-audit").rglob("*") if path.is_file())
    if stage_id == "notebook-export":
        export_root = context.paths.artifacts / "notebooks"
        return sorted(path for path in export_root.rglob("*") if path.is_file())
    return []


def _record_stage_output_identity(context: RunContext, stage_id: str) -> None:
    """Record full hashes for every durable required output of a stage."""
    paths = _stage_identity_paths(context, stage_id)
    if not paths:
        return
    record = _stage_record(context.manifest, stage_id)
    record["output_identity"] = [
        {
            "path": path.relative_to(context.paths.root).as_posix(),
            "size": path.stat().st_size,
            "sha256": _hash_file(path),
        }
        for path in paths
    ]


def _validate_stage_output_identity(context: RunContext, stage_id: str) -> None:
    """Reject missing, added, or byte-changed outputs for a completed stage."""
    expected_paths = _stage_identity_paths(context, stage_id)
    if not expected_paths:
        return
    record = _stage_record(context.manifest, stage_id)
    identities = record.get("output_identity")
    if not isinstance(identities, list) or not identities:
        raise StageError(f"{stage_id} has no recorded output identity")
    expected_relative = [path.relative_to(context.paths.root).as_posix() for path in expected_paths]
    recorded_relative = [item.get("path") for item in identities if isinstance(item, dict)]
    if recorded_relative != expected_relative:
        raise StageError(f"{stage_id} output inventory changed after completion")
    for path, identity in zip(expected_paths, identities, strict=True):
        if not isinstance(identity, dict):
            raise StageError(f"{stage_id} has a malformed output identity")
        observed_size = path.stat().st_size
        if identity.get("size") != observed_size or identity.get("sha256") != _hash_file(path):
            raise StageError(f"{stage_id} output changed after completion: {path}")


def _update_generated_inventory(context: RunContext, stage_id: str) -> None:
    output_root = context.paths.workspace / "1_snakemake/outputs"
    count = sum(1 for path in output_root.rglob("*") if path.is_file()) if output_root.is_dir() else 0
    generated = context.manifest["scope"]["generated_upstream_artifacts"]  # type: ignore[index]
    generated["count"] = count  # type: ignore[index]
    config_inventory: list[tuple[SnakemakeConfig, str, str | None]] = []
    if stage_id.startswith("snakemake-"):
        config_id = stage_id.removeprefix("snakemake-")
        config = next(item for item in CORE_CONFIGS if item.config == config_id)
        config_inventory.append((config, "core candidate", "paper.verification.compiled_results"))
    elif stage_id == "sensitivity-configs":
        config_inventory.append((FILTERED_CONFIG, "current filtered comparison", None))
        config_inventory.extend((config, "current sensitivity", None) for config in SENSITIVITY_CONFIGS)
    for config, layer, candidate_acceptance_gate in config_inventory:
        config_root = output_root / config.output_root
        config_count = sum(1 for path in config_root.rglob("*") if path.is_file()) if config_root.is_dir() else 0
        by_config = generated.setdefault("by_config", {})  # type: ignore[union-attr]
        by_config[config.config] = {  # type: ignore[index]
            "root": f"workspace/1_snakemake/outputs/{config.output_root}",
            "file_count": config_count,
            "layer": layer,
            "candidate_acceptance_gate": candidate_acceptance_gate,
        }
    if stage_id in {"producer-notebooks", "analysis-notebooks", "extended-notebooks"}:
        candidate_root = context.paths.workspace / "2_downstream_analysis/compiled_results"
        seeded = {Path(relative) for relative in SEEDED_COMPILED_RESULTS}
        files = []
        for path in sorted(item for item in candidate_root.rglob("*") if item.is_file()):
            relative = path.relative_to(candidate_root)
            if relative in seeded:
                continue
            files.append(
                {
                    "path": f"workspace/2_downstream_analysis/compiled_results/{relative.as_posix()}",
                    "size": path.stat().st_size,
                    "sha256": _hash_file(path),
                },
            )
        notebook_artifacts = context.manifest["scope"]["generated_notebook_artifacts"]  # type: ignore[index]
        notebook_artifacts["files"] = files  # type: ignore[index]
    if stage_id == "extended-notebooks":
        executed_notebooks = context.manifest["scope"]["executed_notebooks"]  # type: ignore[index]
        executed_notebooks["extended_execution_artifacts"] = [  # type: ignore[index]
            {
                "path": f"workspace/{notebook.path}",
                "size": (context.paths.workspace / notebook.path).stat().st_size,
                "sha256": _hash_file(context.paths.workspace / notebook.path),
            }
            for notebook in EXTENDED_NOTEBOOKS
        ]


def _record_acceptance_report(context: RunContext, stage_id: str) -> None:
    reports_by_stage = {
        "figure-s1": {
            "path": "artifacts/sfig1/figure-s1-report.json",
            "role": "Resolved source-image identity, rendered standalone figure, and inventory deviation.",
        },
        "semantic-verifier": {
            "path": "artifacts/semantic-verification.json",
            "role": "Regenerated candidate versus preserved tracked reference numerical gates.",
        },
        "tracked-audit": {
            "path": "artifacts/tracked-audit/report.json",
            "role": "Tracked source and accounting audit only; it is not regenerated-candidate acceptance.",
        },
    }
    report = reports_by_stage.get(stage_id)
    if report is None:
        return
    reports = context.manifest["scope"]["acceptance_reports"]  # type: ignore[index]
    if report not in reports:  # type: ignore[operator]
        reports.append(report)  # type: ignore[union-attr]


def _execute_stage(context: RunContext, stage: Stage, commands: Sequence[Sequence[str]]) -> None:
    record = _stage_record(context.manifest, stage.id)
    attempts = record["attempts"]
    if not isinstance(attempts, list):
        raise ReproductionError(f"manifest attempts are malformed for {stage.id}")
    attempt_number = len(attempts) + 1
    log_path = context.paths.logs / f"{STAGE_IDS.index(stage.id) + 1:02d}-{stage.id}-attempt-{attempt_number}.log"
    attempt: dict[str, object] = {
        "number": attempt_number,
        "started_at": _utc_now(),
        "status": "running",
        "log": log_path.relative_to(context.paths.root).as_posix(),
        "commands": [list(command) for command in commands],
    }
    attempts.append(attempt)
    record["status"] = "running"
    _save_manifest(context)
    print(f"\n[{STAGE_IDS.index(stage.id) + 1}/{len(STAGES)}] {stage.id}: {stage.title}", flush=True)
    try:
        with log_path.open("a", encoding="ascii", errors="backslashreplace") as log:
            log.write(f"stage={stage.id} attempt={attempt_number} started={attempt['started_at']}\n")
            if stage.id == "snapshot":
                _stage_snapshot(context, commands, log)
            elif stage.id == "inputs":
                _stage_inputs(context, log)
            elif stage.id == "tracked-audit":
                _stage_tracked_audit(context, commands, log)
            elif stage.id == "notebook-export":
                _stage_notebook_export(context, commands, log)
            else:
                _run_commands(context, stage.id, commands, log)
            _validate_stage_outputs(context, stage.id)
            _update_generated_inventory(context, stage.id)
            _record_acceptance_report(context, stage.id)
            _record_stage_output_identity(context, stage.id)
            log.write(f"stage={stage.id} status=succeeded finished={_utc_now()}\n")
            log.flush()
    except Exception as exc:
        with log_path.open("a", encoding="ascii", errors="backslashreplace") as failure_log:
            failure_log.write(f"stage={stage.id} status=failed error={type(exc).__name__}: {exc}\n")
        attempt["status"] = "failed"
        attempt["finished_at"] = _utc_now()
        attempt["error"] = f"{type(exc).__name__}: {exc}"
        record["status"] = "failed"
        context.manifest["status"] = "failed"
        _save_manifest(context)
        if isinstance(exc, StageError):
            raise
        raise StageError(f"{stage.id} failed: {exc}") from exc
    attempt["status"] = "succeeded"
    attempt["finished_at"] = _utc_now()
    record["status"] = "succeeded"
    _save_manifest(context)


def _selected_stages(
    manifest: dict[str, object] | None,
    *,
    from_stage: str | None,
    through_stage: str | None,
    resume: bool,
) -> list[Stage]:
    if from_stage is not None and not resume:
        raise ReproductionError("--from-stage requires --resume")
    end = STAGE_IDS.index(through_stage) if through_stage is not None else len(STAGES) - 1
    if resume:
        if manifest is None:
            raise ReproductionError("resume selection requires a manifest")
        if from_stage is None:
            start = next(
                (
                    index
                    for index, stage in enumerate(STAGES)
                    if _stage_record(manifest, stage.id).get("status") != "succeeded"
                ),
                len(STAGES),
            )
        else:
            start = STAGE_IDS.index(from_stage)
    else:
        start = 0
    if start == len(STAGES):
        return []
    if end < start:
        raise ReproductionError("--through-stage precedes the selected starting stage")
    if manifest is not None:
        incomplete = [
            stage.id for stage in STAGES[:start] if _stage_record(manifest, stage.id).get("status") != "succeeded"
        ]
        if incomplete:
            raise ReproductionError(f"cannot skip incomplete prerequisite stages: {', '.join(incomplete)}")
    return list(STAGES[start : end + 1])


def _print_plan(paths: RunPaths, cores: int, head: str, selected: Sequence[Stage]) -> None:
    plan = build_command_plan(paths, cores, head)
    print(f"Run directory: {paths.root}")
    print("No files will be written in dry-run mode.")
    for stage in selected:
        print(f"\n{stage.id}: {stage.title}")
        commands = plan[stage.id]
        if commands:
            for command in commands:
                print(f"  {_command_text(command)}")
        else:
            print("  internal verified file operation")


def _default_run_dir(head: str) -> Path:
    return REPOSITORY_ROOT / "paper/runs" / f"{_slug_time()}-{head[:12]}"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, help="new isolated run directory (default: ignored paper/runs)")
    parser.add_argument("--input-cache", type=Path, default=DEFAULT_CACHE, help="verified immutable input cache")
    parser.add_argument("--cores", type=int, default=4, help="Snakemake cores (default: 4)")
    parser.add_argument("--dry-run", action="store_true", help="print the exact stage and command plan without writing")
    parser.add_argument("--list-stages", action="store_true", help="list ordered stage IDs and exit")
    parser.add_argument("--resume", action="store_true", help="resume a manifest-backed existing run")
    parser.add_argument("--from-stage", choices=STAGE_IDS, help="resume at this stage after completed prerequisites")
    parser.add_argument("--through-stage", choices=STAGE_IDS, help="stop successfully after this stage")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI, returning 0 on success, 1 on stage failure, and 2 on unsafe setup."""
    arguments = _parser().parse_args(argv)
    if arguments.list_stages:
        for stage in STAGES:
            print(f"{stage.id}\t{stage.title}")
        return 0
    if arguments.cores < 1:
        print("setup error: --cores must be at least 1", file=sys.stderr)
        return 2
    try:
        head = _git_head(REPOSITORY_ROOT)
        orchestrator_sha256 = _require_committed_orchestrator(REPOSITORY_ROOT, head)
        proposed_run_dir = arguments.run_dir or _default_run_dir(head)
        run_dir = _validate_run_dir(REPOSITORY_ROOT, proposed_run_dir, resume=arguments.resume)
        paths = RunPaths.from_root(run_dir)
        manifest = _load_manifest(paths, head, orchestrator_sha256) if arguments.resume else None
        if manifest is not None and manifest["run"].get("cores") != arguments.cores:  # type: ignore[union-attr]
            raise ReproductionError("--cores must match the value recorded by the original run")
        selected = _selected_stages(
            manifest,
            from_stage=arguments.from_stage,
            through_stage=arguments.through_stage,
            resume=arguments.resume,
        )
        if arguments.dry_run:
            _print_plan(paths, arguments.cores, head, selected)
            return 0
        if not selected:
            if manifest is not None and manifest.get("status") != "succeeded":
                manifest["status"] = "succeeded"
                manifest["updated_at"] = _utc_now()
                _atomic_json(paths.manifest, manifest)
            print(f"Run already complete: {paths.manifest}")
            return 0
        _preflight(run_dir, selected)
        if manifest is None:
            run_dir.mkdir(parents=True, exist_ok=False)
            paths.logs.mkdir()
            paths.artifacts.mkdir()
            manifest = _initial_manifest(
                REPOSITORY_ROOT,
                paths,
                head,
                arguments.cores,
                orchestrator_sha256,
            )
            _atomic_json(paths.manifest, manifest)
        invocations = manifest["invocations"]
        if not isinstance(invocations, list):
            raise ReproductionError("manifest invocation history is malformed")
        invocations.append(
            {
                "started_at": _utc_now(),
                "resume": arguments.resume,
                "from_stage": selected[0].id,
                "through_stage": selected[-1].id,
            },
        )
        context = RunContext(
            repository=REPOSITORY_ROOT,
            paths=paths,
            cache=arguments.input_cache.resolve(),
            head=head,
            cores=arguments.cores,
            manifest=manifest,
        )
        manifest["status"] = "running"
        _save_manifest(context)
        plan = build_command_plan(paths, arguments.cores, head)
        for stage in selected:
            record = _stage_record(manifest, stage.id)
            if record.get("status") == "succeeded":
                continue
            _execute_stage(context, stage, plan[stage.id])
        all_succeeded = all(_stage_record(manifest, stage.id).get("status") == "succeeded" for stage in STAGES)
        manifest["status"] = "succeeded" if all_succeeded else "partial"
        _save_manifest(context)
        label = "Complete" if all_succeeded else "Stopped at requested stage"
        print(f"\n{label}. Durable manifest: {paths.manifest}")
        return 0
    except StageError as exc:
        print(f"required stage failed: {exc}", file=sys.stderr)
        return 1
    except (OSError, ReproductionError, ValueError) as exc:
        print(f"setup error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
