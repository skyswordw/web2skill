# web2skill v1 Design

> This document captures the approved product and architecture baseline supplied by the user on 2026-03-23.

## Goal

Build a standalone Python repository that turns stable capabilities from closed-source web apps and SaaS products into agent-usable skills. Version 1 uses ModelScope as the first provider and delivers a reusable runtime, CLI entrypoint, session reuse flow, replay support, and an evaluation stack aligned with harness engineering.

## Product Shape

- The repository is greenfield with no migration or legacy naming constraints.
- The product is skill-first; the CLI exists for execution, debugging, and demos.
- Version 1 only supports non-destructive capabilities.
- Write automation, MCP support, and a marketplace are intentionally out of scope.
- The system should expose stable service capabilities rather than “teach agents to click.”

## Technical Baseline

- Primary language: Python
- Supported versions: Python 3.13 baseline, Python 3.14 in CI
- Tooling: `uv`, Playwright for Python, Typer, Pydantic v2, pytest, Ruff, Pyright
- Core inputs and outputs must be validated with Pydantic.

## Repository Layout

```text
src/web2skill/core/
src/web2skill/browser/
src/web2skill/skills/
src/web2skill/providers/modelscope/
skills/modelscope/
tests/
docs/architecture/
docs/evals/
docs/quality/
.github/workflows/
AGENTS.md
```

## Execution Strategy

1. Prefer real site network responses such as JSON, XHR, or GraphQL.
2. Fall back to DOM parsing only when no stable network source exists.
3. Allow guided UI fallback only for login or strongly interactive flows.
4. Every invocation returns a structured `SkillResult` with `trace_id`, `strategy_used`, and `requires_human`.

## Public Interfaces

### Python API

```python
SkillRuntime.invoke(capability_name, payload, session_id=None) -> SkillResult
```

### CLI

```bash
uv run web2skill skills list
uv run web2skill skills describe
uv run web2skill invoke <capability> --input @input.json --json
uv run web2skill sessions login <provider>
uv run web2skill sessions doctor <provider>
uv run web2skill replay run <trace_id>
```

## Provider Contract

Each provider ships:

- `skills/<provider>/skill.yaml`
- `skills/<provider>/SKILL.md`

These artifacts define schemas, auth mode, risk, strategy guidance, examples, prerequisites, workflows, recovery steps, and human handoff points.

## ModelScope v1 Scope

Exactly five capabilities ship in v1:

1. `modelscope.search_models(query, task=None, sort="relevance", page=1)`
2. `modelscope.get_model_overview(model_slug)`
3. `modelscope.list_model_files(model_slug)`
4. `modelscope.get_quickstart(model_slug)`
5. `modelscope.get_account_profile()`

### Auth Layers

1. Provider token/header hook as a future extension point
2. Playwright storage-state reuse as the primary path
3. Interactive login bootstrap as a required v1 path

## Delivery Model

The implementation is split into five ownership areas:

- Harness Lead Agent: repo bootstrap, docs, CI, `AGENTS.md`
- Runtime Agent: `src/web2skill/core/`, `src/web2skill/browser/`
- Skill Packaging Agent: `src/web2skill/skills/`, `src/web2skill/cli.py`, `skills/`
- ModelScope Provider Agent: `src/web2skill/providers/modelscope/`
- Eval Agent: `tests/`, `docs/evals/`

Overlapping write scopes are not allowed.

## Milestones

1. Bootstrap the Python repository, `uv`, CI, and `AGENTS.md`
2. Implement runtime contracts, browser trace, and replay
3. Implement skill packaging and CLI shell
4. Implement the ModelScope provider and login/session bootstrap
5. Implement evals, drift probes, demo docs, and final quality gates

Every milestone ends with architecture review and provider behavior review.

## Test Strategy

### Unit

- Schema validation
- Session save/load
- Strategy selection
- Parser normalization
- Guardrail escalation
- Manifest and `SKILL.md` generation

### Integration

- Storage-state reuse after interactive login
- Stable CLI `--json` envelope
- Replay trace generation and replay execution
- `network -> DOM` fallback behavior
- Runtime dispatch and provider registry behavior

### E2E

- `search_models("qwen")`
- `get_model_overview(<known_slug>)`
- `list_model_files(<known_slug>)`
- `get_quickstart(<known_slug>)`
- Authenticated `get_account_profile()`

### Drift

- Critical network response shapes
- Critical DOM anchors
- Normalized output snapshots

## Acceptance Criteria

- Fresh clone reaches a working dev environment with one `uv sync` and browser install.
- One human login is enough for agents to use all five capabilities through the skill/CLI surface.
- Every capability returns stable JSON with a `trace_id`.
- CI passes and `AGENTS.md` onboards a new agent.
- There is at least one demo path covering `login -> search -> overview -> files -> quickstart`.

## Guardrails

- Project name is fixed as `web2skill`
- `requires-python` is fixed as `>=3.13,<3.15`
- Provider code may not leak across provider boundaries
- No capability may merge without `unit + integration + e2e + drift` coverage
- Any later high-risk or write-capable capability must include explicit human confirmation

