# web2skill

`web2skill` turns stable capabilities from closed-source web apps and SaaS products into agent-usable skills.

Version 1 is centered on ModelScope and ships:

- a validated Python runtime for capability execution
- a CLI for invocation, login/bootstrap, and replay
- reusable browser session handling based on Playwright storage state
- replayable traces for every invocation
- unit, integration, e2e, and drift coverage

## Getting Started

```bash
uv sync --dev
uv run playwright install chromium
uv run pytest
```

## Planned CLI

```bash
uv run web2skill skills list
uv run web2skill skills describe
uv run web2skill invoke <capability> --input @input.json --json
uv run web2skill sessions login <provider>
uv run web2skill sessions doctor <provider>
uv run web2skill replay run <trace_id>
```

## Repository Map

- `src/web2skill/`: runtime, browser, skill, and provider implementation
- `skills/`: provider skill artifacts
- `tests/`: unit, integration, e2e, and drift coverage
- `docs/architecture/`: architecture decisions and system design
- `docs/evals/`: evaluation and smoke guidance
- `docs/quality/`: quality gates and release criteria

