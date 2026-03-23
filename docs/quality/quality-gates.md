# Quality Gates

## Merge Requirements

- `uv sync --dev`
- `uv run ruff check`
- `uv run pyright`
- `uv run pytest`
- `uv run playwright install chromium`

## Coverage Expectations

Every capability change must update:

- unit coverage for schema and normalization behavior
- integration coverage for runtime, replay, and session interactions
- e2e coverage for capability flows
- drift coverage for stable network shapes, DOM anchors, and marketplace manifest expectations when applicable

## Review Gates

Each milestone must complete:

- architecture review
- provider behavior review

## Release Readiness

A release candidate is ready when:

- a fresh clone can bootstrap with one `uv sync --dev`
- `uv build` produces both wheel and sdist artifacts
- `uv run twine check dist/*` passes
- wheel and sdist artifacts both install into clean environments and can run `web2skill` commands without a repo checkout
- the built wheel contains bundled first-party skills and works without a repo checkout
- user-installed bundles can be installed from a local path, git URL, or marketplace entry
- first-party marketplace entries resolve to the correct monorepo git URL and bundle subdirectory
- a single login can be reused across all supported capabilities
- all capability responses are stable JSON with `trace_id`
- the login -> search -> overview -> files -> quickstart demo path works
- the publish workflow can complete a TestPyPI dry run before production release
