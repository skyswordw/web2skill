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
- drift coverage for stable network shapes and DOM anchors

## Review Gates

Each milestone must complete:

- architecture review
- provider behavior review

## Release Readiness

A release candidate is ready when:

- a fresh clone can bootstrap with one `uv sync --dev`
- the built wheel contains bundled first-party skills and works without a repo checkout
- user-installed bundles can be installed from a local path or git URL
- a single login can be reused across all supported capabilities
- all capability responses are stable JSON with `trace_id`
- the login -> search -> overview -> files -> quickstart demo path works
