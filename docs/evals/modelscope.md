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
| Unit | `tests/unit/core/`, `tests/unit/skills/`, `tests/unit/providers/modelscope/` | Validate Pydantic contracts, runtime shape, bundle manifests, installer behavior, and parser normalization |
| Integration | `tests/integration/` | Validate bundle discovery, CLI install/update flows, artifact installability from wheel/sdist, installed-package runtime/script execution, session hooks, replay contracts, and capability exposure |
| E2E | `tests/e2e/test_modelscope_live.py` | Exercise the approved ModelScope read capabilities live and gate token writes behind an explicit opt-in |
| Drift | `tests/drift/test_modelscope_drift.py` | Freeze expected response keys and token-page create-dialog anchors so bundle/parser changes surface early |

## Environment Gating

Live coverage is opt-in and should stay quiet by default during local and CI development while
implementation is still landing.

Required environment toggle:

- `WEB2SKILL_RUN_LIVE=1`

Optional live inputs:

- `WEB2SKILL_MODELSCOPE_SESSION_ID`
- `WEB2SKILL_MODELSCOPE_STORAGE_STATE`
- `WEB2SKILL_MODELSCOPE_KNOWN_SLUG`
- `WEB2SKILL_RUN_TOKEN_WRITES=1`
- `WEB2SKILL_MODELSCOPE_TEST_TOKEN_NAME`

If `WEB2SKILL_RUN_LIVE` is not set, tests marked `live` or `e2e` are skipped during collection.

## Local Commands

Contract and scaffold coverage:

```bash
uv run pytest tests/unit tests/integration tests/drift
```

Bundle management coverage:

```bash
uv run pytest tests/integration/test_skill_installation.py -v
```

Artifact install and installed-package coverage:

```bash
uv run pytest tests/integration/test_artifact_distribution.py -v
```

Live smoke coverage after preparing a reusable storage-state session:

```bash
WEB2SKILL_RUN_LIVE=1 \
WEB2SKILL_MODELSCOPE_STORAGE_STATE=.web2skill/modelscope-storage-state.json \
uv run pytest tests/e2e/test_modelscope_live.py -v
```

Targeted parser contract coverage:

```bash
uv run pytest tests/unit/providers/modelscope/test_parsers.py -v
```

## Live Execution Notes

The live suite is written against the approved v1 surface and runs through the bundled-script
execution path:

1. `modelscope.search_models`
2. `modelscope.get_model_overview`
3. `modelscope.list_model_files`
4. `modelscope.get_quickstart`
5. `modelscope.get_account_profile`
6. `modelscope.list_tokens`
7. `modelscope.get_token`

`modelscope.create_token` is covered separately and only runs when:

- `WEB2SKILL_RUN_LIVE=1`
- `WEB2SKILL_MODELSCOPE_STORAGE_STATE` points at an authenticated storage-state file
- `WEB2SKILL_RUN_TOKEN_WRITES=1`

Expected operator flow:

1. Bootstrap dependencies with `uv sync --dev`
2. Install Chromium with `uv run playwright install chromium`
3. Create or refresh a ModelScope session via `web2skill sessions login modelscope --mode import-browser`
4. Export the storage-state path and optional session identifier
5. Run the live suite with `WEB2SKILL_RUN_LIVE=1`

Every live invocation should return a `SkillResult` envelope with:

- `trace_id`
- `strategy_used`
- `requires_human`

## Drift Strategy

Drift coverage serves two purposes:

1. Keep fixture-based network-shape assertions stable for normalizer tests
2. Reserve a live drift lane for DOM anchors and endpoint payload changes once the bundled skill
   implementation lands

The initial scaffolding stores representative ModelScope payloads under `tests/fixtures/modelscope/`.
As the provider stabilizes, those fixtures should be refreshed from real captures and paired with
assertions on selector anchors, replay traces, and normalized output snapshots.

Current token drift checks cover:

- `GET /api/v1/users/tokens/list` response-shape keys
- `/my/access/token` create-dialog anchors: `Create Your Token`, `#TokenName`, `Token validity`, and `Create Token`

## Current Limits

- The suite is contract-first and will skip live coverage unless reusable ModelScope session inputs
  are configured.
- The live suite assumes `SkillRuntime(registry=BundleCapabilityRegistry(...))` is the default
  execution path for built-in bundles.
- Drift coverage currently freezes response-shape scaffolding; live DOM-anchor assertions should be
  expanded when the provider exposes selector constants and capture hooks.
