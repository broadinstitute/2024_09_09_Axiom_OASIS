# Repository Guidelines

## Project Structure and Module Organization

`0_prepare_data/` downloads and formats analysis inputs.
`1_snakemake/` owns the primary workflow, rules, configurations, and pipeline tests.
`2_downstream_analysis/` contains manuscript and exploratory notebooks plus compiled results.
`paper/` contains source publications, the target ledger, evidence, verification code, executable-paper tools, and paper tests.
`image_archive/` is the small manifest-driven TIFF-to-JPEG-XL converter and includes a validated 1,000-row manifest sample from the `cpg0037-oasis/axiom` dataset.
Tests live beside their subsystem under `1_snakemake/tests/`, `paper/tests/`, and `image_archive/tests/`.

## Build, Test, and Development Commands

Use `direnv` and the locked Pixi environments; `pipeline`, `notebooks`, and `images` intentionally carry different dependencies.

```bash
direnv exec . pixi install --locked -e pipeline
direnv exec . pixi run -e pipeline dry
direnv exec . pixi run -e pipeline python -m unittest discover -s 1_snakemake/tests
uv run paper/reproduce.py
direnv exec . pixi run -e images pytest -q image_archive/tests
direnv exec . pixi run -e images ruff check image_archive
direnv exec . pixi run -e images pyright image_archive
```

Run `uv run paper/reproduce_all.py --dry-run` before attempting the multi-hour end-to-end reproduction.
See `paper/README.md` for the split pipeline/notebook paper-test commands.

## Coding Style and Naming Conventions

Use four-space Python indentation, `snake_case` for functions and modules, `PascalCase` for classes, and uppercase names for constants.
Preserve numbered workflow names such as `1A_download_metadata.py` when order is meaningful.
Ruff uses `ALL` rules with a 120-character line limit; Pyright targets Python 3.11.
Keep changes local to the owning subsystem and avoid new frameworks for one-dataset workflows.

## Testing Guidelines

Name tests `test_*.py` and add regression coverage for every corrected failure mode.
Pipeline and paper suites use `unittest`; image-archive tests use Pytest.
There is no global coverage threshold, so validate the affected subsystem and run `git diff --check`.
Never modify or recompress the external `cpg0037-oasis/axiom` JPEG XL archive during tests.

## Commit and Pull Request Guidelines

Use short imperative commit subjects without scope prefixes, for example `Harden archive validation`.
Keep commits signed and pull with rebase.
PRs should state the problem, bounded solution, scientific or reproduction impact, and exact validation commands.
Link the relevant issue when one exists and include screenshots only for changed rendered figures or notebook output.
