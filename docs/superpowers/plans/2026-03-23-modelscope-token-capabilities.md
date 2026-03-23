# ModelScope Token Capabilities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ModelScope token management capabilities that list non-secret token metadata, reveal a selected raw token with explicit confirmation, and create a new token with explicit confirmation.

**Architecture:** Reuse the current session-authenticated ModelScope provider surface. Implement `list_tokens` and `get_token` network-first against the stable `users/tokens/list` endpoint, fix imported cookie normalization so Playwright can reuse browser-import sessions, and implement `create_token` network-first if a stable create endpoint can be captured or guided UI otherwise.

**Tech Stack:** Python 3.13, httpx, Playwright, Typer, Pydantic v2, pytest, Ruff, Pyright

---

## File Map

- Modify: `src/web2skill/providers/modelscope/contracts.py`
  Add token-specific input/output models and capability names.
- Modify: `src/web2skill/providers/modelscope/provider.py`
  Add provider handlers for list/reveal/create token flows and secret-safe tracing.
- Modify: `src/web2skill/providers/modelscope/parsers.py`
  Add token-list normalization helpers.
- Modify: `src/web2skill/providers/modelscope/login.py`
  Normalize imported storage-state cookies to Playwright-compatible booleans.
- Modify: `src/web2skill/providers/modelscope/__init__.py`
  Re-export any new token contracts if needed.
- Modify: `skills/modelscope/skill.yaml`
  Add the three token capabilities, schemas, risk, and examples.
- Modify: `skills/modelscope/SKILL.md`
  Document token workflows, confirmation requirements, and human handoff.
- Create: `tests/fixtures/modelscope/token_list.json`
  Fixture for `GET /api/v1/users/tokens/list`.
- Create: `tests/unit/providers/modelscope/test_tokens.py`
  Unit coverage for parsers, confirmation guardrails, and secret redaction.
- Modify: `tests/unit/providers/modelscope/test_login.py`
  Add coverage for browser-import cookie normalization.
- Modify: `tests/integration/test_modelscope_provider.py`
  Add integration coverage for capability registration and provider behavior.
- Modify: `tests/integration/test_cli_json.py`
  Add CLI envelope coverage for list/reveal/create token flows.
- Modify: `tests/e2e/test_modelscope_live.py`
  Add live token read coverage and gated live create coverage.
- Modify: `tests/drift/test_modelscope_drift.py`
  Add drift probes for token-list response shapes and create-dialog anchors.
- Modify: `docs/evals/modelscope.md`
  Add token capability setup and live verification instructions.

### Task 1: Add Token Contracts, Manifest Entries, And Metadata-Only List Parsing

**Files:**
- Modify: `src/web2skill/providers/modelscope/contracts.py`
- Modify: `src/web2skill/providers/modelscope/parsers.py`
- Modify: `skills/modelscope/skill.yaml`
- Modify: `skills/modelscope/SKILL.md`
- Create: `tests/fixtures/modelscope/token_list.json`
- Create: `tests/unit/providers/modelscope/test_tokens.py`
- Modify: `tests/integration/test_modelscope_provider.py`

- [ ] **Step 1: Write the failing unit test for token list normalization**

```python
def test_token_list_normalizer_returns_metadata_only(load_fixture):
    payload = load_fixture("modelscope/token_list.json")

    result = parsers.normalize_token_list(payload)

    assert result.total_count == 1
    assert result.items[0].token_id == 3245671
    assert result.items[0].name == "default"
    assert "token" not in result.items[0].model_dump()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/providers/modelscope/test_tokens.py::test_token_list_normalizer_returns_metadata_only -v`
Expected: FAIL because the token parser and contracts do not exist yet

- [ ] **Step 3: Add the token contracts and parser**

Implement:
- `CapabilityName.LIST_TOKENS`, `CapabilityName.GET_TOKEN`, `CapabilityName.CREATE_TOKEN`
- `TokenSummary`
- `ListTokensInput`
- `ListTokensOutput`
- `GetTokenInput`
- `GetTokenOutput`
- `CreateTokenInput`
- `CreateTokenOutput`
- parser helpers that map `SdkTokens[]` into metadata-only summaries

- [ ] **Step 4: Update packaged skill metadata**

Add the three token capabilities to `skills/modelscope/skill.yaml` and `skills/modelscope/SKILL.md` with:
- `list_tokens` risk `medium`
- `get_token` risk `high`
- `create_token` risk `high`
- examples that use explicit confirmation for reveal/create

- [ ] **Step 5: Run focused tests to verify they pass**

Run: `uv run pytest tests/unit/providers/modelscope/test_tokens.py tests/integration/test_modelscope_provider.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/web2skill/providers/modelscope/contracts.py src/web2skill/providers/modelscope/parsers.py skills/modelscope/skill.yaml skills/modelscope/SKILL.md tests/fixtures/modelscope/token_list.json tests/unit/providers/modelscope/test_tokens.py tests/integration/test_modelscope_provider.py
git commit -m "feat: add modelscope token contracts and manifests"
```

### Task 2: Implement `list_tokens` And `get_token` With Confirmation Guardrails

**Files:**
- Modify: `src/web2skill/providers/modelscope/provider.py`
- Create: `tests/unit/providers/modelscope/test_tokens.py`
- Modify: `tests/integration/test_cli_json.py`
- Modify: `tests/integration/test_modelscope_provider.py`

- [ ] **Step 1: Write the failing unit test for confirmation enforcement**

```python
def test_get_token_requires_explicit_confirmation():
    provider = ModelScopeProvider(transport=mock_transport_with_token_list())

    result = provider.get_token({"token_id": 3245671, "confirm_reveal": False})

    assert result.requires_human is True
    assert "confirmation" in result.errors[0].lower()
    assert result.data is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/providers/modelscope/test_tokens.py::test_get_token_requires_explicit_confirmation -v`
Expected: FAIL because `get_token` is not implemented yet

- [ ] **Step 3: Write the failing unit test for raw reveal after confirmation**

```python
def test_get_token_returns_raw_token_after_confirmation():
    provider = ModelScopeProvider(transport=mock_transport_with_token_list())

    result = provider.get_token({"token_id": 3245671, "confirm_reveal": True})

    assert result.requires_human is False
    assert result.data.token == "ms-cde0e8be-4f10-42d0-834f-6d93352b91b3"
```

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest tests/unit/providers/modelscope/test_tokens.py::test_get_token_returns_raw_token_after_confirmation -v`
Expected: FAIL because reveal flow is still missing

- [ ] **Step 5: Implement `list_tokens` and `get_token`**

Add provider methods that:
- call `GET /api/v1/users/tokens/list`
- return metadata-only summaries for `list_tokens`
- select by `Id` for `get_token`
- require `confirm_reveal=true`
- redact raw secrets from trace details and non-reveal outputs

- [ ] **Step 6: Add CLI and integration assertions**

Write integration coverage that verifies:
- `uv run web2skill invoke modelscope.list_tokens --input '{}' --json`
- `uv run web2skill invoke modelscope.get_token --input '{"token_id":3245671,"confirm_reveal":true}' --json`
- missing confirmation returns a guarded response instead of a secret

- [ ] **Step 7: Run targeted tests**

Run: `uv run pytest tests/unit/providers/modelscope/test_tokens.py tests/integration/test_cli_json.py tests/integration/test_modelscope_provider.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/web2skill/providers/modelscope/provider.py tests/unit/providers/modelscope/test_tokens.py tests/integration/test_cli_json.py tests/integration/test_modelscope_provider.py
git commit -m "feat: add modelscope token listing and reveal flows"
```

### Task 3: Fix Imported Storage-State Normalization For Playwright Reuse

**Files:**
- Modify: `src/web2skill/providers/modelscope/login.py`
- Modify: `tests/unit/providers/modelscope/test_login.py`

- [ ] **Step 1: Write the failing unit test for Playwright-compatible cookie normalization**

```python
def test_import_browser_storage_state_writes_boolean_secure_flags(tmp_path, monkeypatch):
    monkeypatch.setattr(login, "_load_browser_cookies", fake_cookie_loader)
    monkeypatch.setattr(login, "_cookies_are_authenticated", lambda cookies: True)

    login.import_browser_storage_state(browser_name="chrome", storage_state_path=tmp_path / "state.json")

    payload = json.loads((tmp_path / "state.json").read_text())
    assert isinstance(payload["cookies"][0]["secure"], bool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/providers/modelscope/test_login.py::test_import_browser_storage_state_writes_boolean_secure_flags -v`
Expected: FAIL because imported cookie serialization currently writes `0/1`

- [ ] **Step 3: Implement normalization**

Update the browser-cookie import path so the persisted storage state matches Playwright expectations:
- `secure` is a real boolean
- `httpOnly` is a real boolean
- `sameSite` is always a valid Playwright string

- [ ] **Step 4: Run focused tests**

Run: `uv run pytest tests/unit/providers/modelscope/test_login.py tests/unit/providers/modelscope/test_tokens.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/web2skill/providers/modelscope/login.py tests/unit/providers/modelscope/test_login.py tests/unit/providers/modelscope/test_tokens.py
git commit -m "fix: normalize imported modelscope storage state for playwright"
```

### Task 4: Implement `create_token` With Network Discovery First And Guided UI Fallback Second

**Files:**
- Modify: `src/web2skill/providers/modelscope/provider.py`
- Modify: `src/web2skill/providers/modelscope/selectors.py`
- Modify: `tests/unit/providers/modelscope/test_tokens.py`
- Modify: `tests/e2e/test_modelscope_live.py`
- Modify: `tests/drift/test_modelscope_drift.py`

- [ ] **Step 1: Write the failing unit test for confirmation enforcement**

```python
def test_create_token_requires_explicit_confirmation():
    provider = ModelScopeProvider(transport=mock_transport_with_token_list())

    result = provider.create_token({"name": "ci-dev", "validity": "permanent", "confirm_create": False})

    assert result.requires_human is True
    assert result.data is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/providers/modelscope/test_tokens.py::test_create_token_requires_explicit_confirmation -v`
Expected: FAIL because `create_token` is not implemented yet

- [ ] **Step 3: Capture the live create request shape**

Using the authenticated token page:
- instrument Playwright network events on `/my/access/token`
- submit the dialog in a controlled session
- record the create endpoint, method, request body, and response shape
- stop if the page requires an unstable or heavily obfuscated interaction

- [ ] **Step 4: Implement network-first create if the endpoint is stable**

If capture produces a stable API:
- implement `create_token` through the provider client
- parse the created token response into `CreateTokenOutput`
- keep raw token values out of traces

- [ ] **Step 5: Implement guided UI fallback only if the network path is not stable**

If no stable create API is available:
- drive the bounded create dialog with Playwright using the imported authenticated session
- fill the token name
- choose the requested validity option
- click `Create Token`
- capture the newly created raw token if the UI exposes it

- [ ] **Step 6: Add drift and live gating**

Add:
- drift assertions for the create dialog anchors
- a separate live opt-in gate such as `WEB2SKILL_RUN_TOKEN_WRITES=1`
- a live create test that is skipped by default because it mutates remote state

- [ ] **Step 7: Run targeted tests**

Run: `uv run pytest tests/unit/providers/modelscope/test_tokens.py tests/drift/test_modelscope_drift.py -v`
Expected: PASS or SKIP for live-gated cases

- [ ] **Step 8: Commit**

```bash
git add src/web2skill/providers/modelscope/provider.py src/web2skill/providers/modelscope/selectors.py tests/unit/providers/modelscope/test_tokens.py tests/e2e/test_modelscope_live.py tests/drift/test_modelscope_drift.py
git commit -m "feat: add modelscope token creation flow"
```

### Task 5: Finish CLI, Docs, And Full Verification

**Files:**
- Modify: `tests/integration/test_cli_json.py`
- Modify: `docs/evals/modelscope.md`

- [ ] **Step 1: Add CLI coverage for all three capabilities**

Write integration tests for:
- metadata-only list output
- guarded reveal without confirmation
- successful reveal with confirmation
- guarded create without confirmation

- [ ] **Step 2: Update eval docs**

Document:
- how to refresh the browser-import session
- how to list tokens safely
- how to reveal a token for local development
- how to opt into write-capable live token creation tests

- [ ] **Step 3: Run full verification**

Run:

```bash
uv run ruff check
uv run pyright
uv run pytest -q
```

Expected:
- Ruff: `All checks passed!`
- Pyright: `0 errors, 0 warnings, 0 informations`
- Pytest: all non-live tests pass; live write tests skip unless explicitly enabled

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_cli_json.py docs/evals/modelscope.md
git commit -m "test: cover modelscope token capabilities"
```

## Test Matrix

- Unit
  - token list normalization excludes secrets
  - get-token confirmation enforcement
  - get-token raw reveal after confirmation
  - create-token confirmation enforcement
  - imported cookie normalization writes Playwright-compatible booleans
- Integration
  - provider registry exposes three new capabilities
  - CLI JSON envelopes stay stable for list/reveal/create
  - authenticated session reuse reaches token endpoints
- Live
  - list tokens with a prepared session
  - reveal one token with explicit confirmation
  - create token only with a separate destructive opt-in
- Drift
  - `users/tokens/list` response shape
  - `/my/access/token` create-dialog anchors

