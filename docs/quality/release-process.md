# Release Process

`web2skill` publishes one Python package with bundled first-party skills. Release automation is defined in `.github/workflows/publish.yml` and uses PyPI Trusted Publishing.

## Before Publishing

Run the local release checks from a clean branch:

```bash
uv sync --dev
uv run ruff check
uv run pyright
uv run pytest
uv build
uv run twine check dist/*
uv run pytest tests/integration/test_artifact_distribution.py -q
```

Confirm that:

- both `dist/web2skill-*.whl` and `dist/web2skill-*.tar.gz` exist
- the artifact smoke tests pass for wheel and sdist
- README and README.zh-CN still match the installed CLI flow
- `marketplace.yaml` still resolves first-party entries to the correct repo URL and bundle subdirectory

## TestPyPI Dry Run

Use the `Publish` workflow with `workflow_dispatch`.

This path should be the default rehearsal before a production release because it validates:

- GitHub Actions build and artifact upload
- Trusted Publishing setup
- package metadata as rendered by the package index

## Production Release

1. Bump `version` in `pyproject.toml`.
2. Merge the release commit to `main`.
3. Push a version tag in the form `vX.Y.Z`.
4. Let `.github/workflows/publish.yml` build, validate, and publish to PyPI.

The publish workflow runs:

- `uv sync --dev`
- `uv run ruff check`
- `uv run pyright`
- `uv run pytest`
- `uv build`
- `uv run twine check dist/*`
- `uv run pytest tests/integration/test_artifact_distribution.py -q`

Publishing only happens after those checks pass.

## Trusted Publishing Setup

Configure Trusted Publishers in both PyPI and TestPyPI for this repository and workflow:

- repository: `skyswordw/web2skill`
- workflow file: `.github/workflows/publish.yml`

No API tokens should be required once Trusted Publishing is configured correctly.
