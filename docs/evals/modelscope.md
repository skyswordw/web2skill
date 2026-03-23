# ModelScope Eval Plan

## Scope

This document defines the v1 evaluation slice for the `modelscope` provider in `web2skill`.
It covers the approved runtime, skill packaging, CLI, provider, live, and drift interfaces from the
2026-03-23 design and implementation plan.

## Coverage Matrix

The eval stack is intentionally split into four layers because `web2skill` cannot merge a capability
without `unit + integration + e2e + drift` coverage.

| Layer | Files | Goal |
| --- | --- | --- |
| Unit | `tests/unit/core/`, `tests/unit/skills/`, `tests/unit/providers/modelscope/` | Validate Pydantic contracts, runtime shape, manifest coverage, and parser normalization |
| Integration | `tests/integration/` | Validate runtime/CLI/provider boundaries, replay contracts, and capability exposure |
| E2E | `tests/e2e/test_modelscope_live.py` | Exercise the five approved capabilities against live ModelScope flows |
| Drift | `tests/drift/test_modelscope_drift.py` | Freeze expected response keys and live anchor inputs so provider changes surface early |

## Environment Gating

Live coverage is opt-in and should stay quiet by default during local and CI development while
implementation is still landing.

Required environment toggle:

- `WEB2SKILL_RUN_LIVE=1`

Optional live inputs:

- `WEB2SKILL_MODELSCOPE_SESSION_ID`
- `WEB2SKILL_MODELSCOPE_STORAGE_STATE`
- `WEB2SKILL_MODELSCOPE_KNOWN_SLUG`

If `WEB2SKILL_RUN_LIVE` is not set, tests marked `live` or `e2e` are skipped during collection.

## Local Commands

Contract and scaffold coverage:

```bash
uv run pytest tests/unit tests/integration tests/drift
```

Live smoke coverage after preparing a session:

```bash
WEB2SKILL_RUN_LIVE=1 uv run pytest tests/e2e/test_modelscope_live.py -v
```

Targeted parser contract coverage:

```bash
uv run pytest tests/unit/providers/modelscope/test_parsers.py -v
```

## Live Execution Notes

The live suite is written against the approved v1 surface:

1. `modelscope.search_models`
2. `modelscope.get_model_overview`
3. `modelscope.list_model_files`
4. `modelscope.get_quickstart`
5. `modelscope.get_account_profile`

Expected operator flow:

1. Bootstrap dependencies with `uv sync --dev`
2. Install Chromium with `uv run playwright install chromium`
3. Create or refresh a ModelScope session via the future `sessions login modelscope` flow
4. Export the session identifier or storage-state path
5. Run the live suite with `WEB2SKILL_RUN_LIVE=1`

Every live invocation should return a `SkillResult` envelope with:

- `trace_id`
- `strategy_used`
- `requires_human`

## Drift Strategy

Drift coverage serves two purposes:

1. Keep fixture-based network-shape assertions stable for normalizer tests
2. Reserve a live drift lane for DOM anchors and endpoint payload changes once the provider
   implementation lands

The initial scaffolding stores representative ModelScope payloads under `tests/fixtures/modelscope/`.
As the provider stabilizes, those fixtures should be refreshed from real captures and paired with
assertions on selector anchors, replay traces, and normalized output snapshots.

## Current Limits

- The suite is contract-first and will skip when runtime, CLI, skills, or provider modules are not
  yet present in the worktree.
- The live suite assumes `SkillRuntime(registry=provider)` remains a supported construction path.
- Drift coverage currently freezes response-shape scaffolding; live DOM-anchor assertions should be
  expanded when the provider exposes selector constants and capture hooks.
