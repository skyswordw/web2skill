# web2skill

`web2skill` turns stable capabilities from closed-source web apps and SaaS products into agent-usable skills.

Version 1 is centered on ModelScope and ships:

- a validated Python runtime for capability execution
- a CLI for invocation, login/bootstrap, and replay
- bundled first-party skills shipped inside the `web2skill` wheel
- installable user skill bundles from a local path or git URL
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
uv run web2skill skills install <local-path-or-git-url>
uv run web2skill skills uninstall <bundle_id>
uv run web2skill skills update <bundle_id>
uv run web2skill invoke <capability> --input @input.json --json
uv run web2skill sessions login <provider>
uv run web2skill sessions doctor <provider>
uv run web2skill replay run <trace_id>
```

## Skill Bundle Layout

`web2skill` publishes a single core package. First-party and user-installed skills follow the same
bundle contract:

```text
<skill>/
  SKILL.md
  skill.yaml
  scripts/
    capabilities/
    session/
    lib/
  references/
  assets/
  pyproject.toml
  uv.lock
```

Built-in bundles ship inside the `web2skill` wheel. User-installed bundles live under
`~/.web2skill/skills/`.

## Repository Map

- `src/web2skill/`: core runtime, browser support, bundle registry, CLI, and installer logic
- `skills/`: canonical first-party skill bundles authored in bundle layout
- `tests/`: unit, integration, e2e, and drift coverage
- `docs/architecture/`: architecture decisions and system design
- `docs/evals/`: evaluation and smoke guidance
- `docs/quality/`: quality gates and release criteria
