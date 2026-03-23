# AGENTS

This repository is built by cooperating agents with strict write ownership. Keep changes inside your assigned scope unless a human explicitly approves a boundary change.

## Ground Rules

- Project name is fixed as `web2skill`.
- Python is the only primary implementation language.
- Publish one Python package: `web2skill`.
- First-party skills ship as bundled skill directories inside that package.
- User-created skills are installed from a local path or git URL, not from PyPI.
- Runtime inputs and outputs must be validated with Pydantic.
- Prefer real network responses, then DOM parsing, then guided UI fallback.
- Every invocation must emit a structured `SkillResult` with `trace_id`, `strategy_used`, and `requires_human`.
- No capability merges without `unit + integration + e2e + drift` coverage.
- High-risk or write-capable capabilities must add an explicit human confirmation step in a later version.

## Worktree Layout

- Root coordination branch: `main`
- Agent branches use the `codex/` prefix.
- Create worktrees under `.worktrees/`.
- Recommended branch names:
  - `codex/harness-lead`
  - `codex/runtime`
  - `codex/skill-packaging`
  - `codex/modelscope-provider`
  - `codex/eval`

## Ownership

### Harness Lead Agent

- Model: `gpt-5.4`
- Reasoning effort: `xhigh`
- Write scope: repository root, `docs/`, `.github/`
- Responsibilities: bootstrap, `pyproject.toml`, `uv` workflow, `AGENTS.md`, architecture docs, quality docs, CI

### Runtime Agent

- Model: `gpt-5.4`
- Reasoning effort: `medium`
- Write scope: `src/web2skill/core/`, `src/web2skill/browser/`
- Responsibilities: runtime contracts, session store, guardrails, trace model, browser capture, replay support

### Skill Packaging Agent

- Model: `gpt-5.4`
- Reasoning effort: `medium`
- Write scope: `src/web2skill/skills/`, `src/web2skill/cli.py`, `skills/`
- Responsibilities: manifest schema, bundle registry, installer, `SKILL.md` rendering, Typer CLI shell

### ModelScope Provider Agent

- Model: `gpt-5.4`
- Reasoning effort: `medium`
- Write scope: `skills/modelscope/`
- Responsibilities: bundle-local capability handlers, parsing, session reuse, login bootstrap, and drift probes

### Eval Agent

- Model: `gpt-5.4`
- Reasoning effort: `medium`
- Write scope: `tests/`, `docs/evals/`
- Responsibilities: pytest coverage, fixtures, smoke checks, eval docs

## Milestone Order

1. Bootstrap the repository, `uv`, CI, and onboarding docs
2. Implement runtime contracts, browser trace, and replay
3. Implement skill packaging and the CLI shell
4. Implement the ModelScope provider and login/session bootstrap
5. Implement evals, drift probes, demos, and final quality gates

Each milestone ends with:

- architecture review
- provider behavior review

## Local Commands

```bash
uv sync --dev
uv run ruff check
uv run pyright
uv run pytest
uv run playwright install chromium
```
