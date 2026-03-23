# ModelScope Token Capabilities Design

> This document captures the approved design for adding ModelScope access-token capabilities to `web2skill` on 2026-03-23.

## Goal

Add first-class ModelScope token capabilities so agents can list token metadata, reveal a selected raw token for downstream development pipelines, and create a new token with explicit confirmation.

## Scope Change

This is a deliberate extension beyond the original `web2skill` v1 boundary.

- The original repository spec limited v1 to non-destructive capabilities.
- `modelscope.create_token` is a write-capable action.
- This design keeps the expansion narrow by requiring explicit confirmation and by separating read-style token listing from reveal and creation flows.

## User Intent

- Reuse the already-authenticated ModelScope browser/session.
- Support development pipelines in other projects by retrieving a raw access token on demand.
- Return token metadata without secrets by default.
- Allow token creation only when the caller explicitly asks for it.

## In Scope

- `modelscope.list_tokens()`
- `modelscope.get_token(token_id, confirm_reveal=true)`
- `modelscope.create_token(name, validity="permanent", confirm_create=true)`
- CLI invocation through the existing `uv run web2skill invoke ... --json` surface
- Session-authenticated access via existing browser-session reuse
- Unit, integration, live, and drift coverage for the new token flows

## Out Of Scope

- Token-based inference calls
- Provider-wide migration from session auth to bearer-token auth
- Token deletion or rotation
- Automatic token provisioning for CI
- CAPTCHA bypass or automated login challenge handling

## Live Feasibility Findings

The current authenticated session already proved the token area is reachable without another interactive login.

### Confirmed stable read endpoint

The authenticated token settings page at `https://modelscope.cn/my/access/token` loads token data from:

`GET https://modelscope.cn/api/v1/users/tokens/list`

The live response shape includes:

- `Data.SdkTokens[].Id`
- `Data.SdkTokens[].SdkTokenName`
- `Data.SdkTokens[].SdkToken`
- `Data.SdkTokens[].ExpiresAt`
- `Data.SdkTokens[].GmtCreated`
- `Data.SdkTokens[].Valid`

This means:

- `list_tokens` can be implemented as a network-first read capability.
- `get_token` can also be implemented as a network-first read capability by selecting a token from the same response.
- Existing raw token values are available from the authenticated API, not only from the UI.

### Confirmed UI create dialog

The token page exposes a create dialog with:

- token name entry
- validity selection (`Long-term (Permanent)` and `Short-term`)
- `Create Token` action

The create network endpoint was not yet captured during design exploration, so implementation should probe for a stable API first and fall back to guided UI only if the network path is not stable enough.

### Current storage-state limitation

The browser-imported storage state currently works for `httpx`, but Playwright rejects some imported cookies because `secure` is persisted as `0/1` instead of a boolean. This must be fixed before a reliable guided-UI token creation fallback can ship.

## Capability Design

### `modelscope.list_tokens`

Purpose:
- Return token metadata for selection without revealing secrets.

Inputs:
- empty object

Outputs:
- `items[]` containing only non-secret metadata:
  - `token_id`
  - `name`
  - `expires_at`
  - `created_at`
  - `valid`
- `total_count`

Behavior:
- Read from `GET /api/v1/users/tokens/list`
- Never return `SdkToken`
- Prefer network strategy
- Return `requires_human=false` when session auth succeeds

Risk:
- `medium`

### `modelscope.get_token`

Purpose:
- Reveal the raw token string for one selected token.

Inputs:
- `token_id: int`
- `confirm_reveal: bool`

Outputs:
- `token_id`
- `name`
- `token`
- `expires_at`
- `created_at`
- `valid`

Behavior:
- Read from `GET /api/v1/users/tokens/list`
- Select the matching token by `Id`
- Require `confirm_reveal=true`
- Return a confirmation error instead of the secret when confirmation is absent

Risk:
- `high`

### `modelscope.create_token`

Purpose:
- Create a new ModelScope access token only when explicitly requested.

Inputs:
- `name: str`
- `validity: "permanent" | "short_term"` with default `permanent`
- `confirm_create: bool`

Outputs:
- `token_id`
- `name`
- `token`
- `expires_at`
- `created_at`
- `valid`

Behavior:
- Require `confirm_create=true`
- First attempt a stable network implementation if the create endpoint can be captured reliably
- If no stable network endpoint is available, use guided UI as a bounded fallback on the token settings page
- Return the raw token only in the capability payload, never in traces or logs

Risk:
- `high`

## Auth Model

These capabilities remain provider-session authenticated.

- Provider-level auth mode stays `session`
- Existing browser-session import/login flows remain the source of truth
- These capabilities do not require a separate manually configured bearer token

This keeps token-management flows aligned with the current authenticated web-app surface.

## Guardrails

### Confirmation

- `list_tokens` requires no confirmation
- `get_token` requires `confirm_reveal=true`
- `create_token` requires `confirm_create=true`

### Secret handling

Raw token values must not appear in:

- traces
- warnings
- error messages
- drift snapshots
- debug logs
- `list_tokens` output

### Human handoff

Escalate to human when:

- the session is missing or expired
- the token page introduces CAPTCHA, MFA, or additional approval
- token quota is exhausted
- the create flow drifts and can no longer be driven safely

## Architecture

### Provider contracts

Add new provider contracts for:

- `TokenSummary`
- `ListTokensOutput`
- `ListTokensInput`
- `GetTokenInput`
- `GetTokenOutput`
- `CreateTokenInput`
- `CreateTokenOutput`

Extend `CapabilityName` with:

- `modelscope.list_tokens`
- `modelscope.get_token`
- `modelscope.create_token`

### Provider execution

- `list_tokens` and `get_token` should be implemented directly in `ModelScopeProvider`
- Parsing and normalization should live alongside the existing ModelScope parser utilities
- `create_token` should isolate discovery, request shaping, and fallback behavior so the write path does not leak into unrelated read capabilities

### Skill packaging

Update provider artifacts so the new capabilities appear in:

- `skills/modelscope/skill.yaml`
- `skills/modelscope/SKILL.md`

The docs must clearly state that:

- token listing returns metadata only
- token reveal returns a raw secret and is high risk
- token creation is explicit and high risk

## CLI Surface

No new top-level command group is required. The existing invoke surface is sufficient.

Examples:

```bash
uv run web2skill invoke modelscope.list_tokens --input '{}' --json
uv run web2skill invoke modelscope.get_token --input '{"token_id":3245671,"confirm_reveal":true}' --json
uv run web2skill invoke modelscope.create_token --input '{"name":"ci-dev","validity":"permanent","confirm_create":true}' --json
```

## Testing Strategy

### Unit

- validate input schemas and confirmation flags
- normalize `tokens/list` payload into metadata-only summaries
- ensure `get_token` returns the selected raw token only after confirmation
- verify secret redaction behavior in traces and list outputs
- verify storage-state normalization produces Playwright-compatible boolean cookie fields

### Integration

- runtime dispatch for new token capabilities
- CLI `--json` envelopes for list/reveal/create
- session reuse against authenticated token endpoints
- provider behavior when confirmation is missing

### Live

- `list_tokens` with an authenticated session
- `get_token` for an existing token with explicit confirmation
- `create_token` only behind an additional explicit live opt-in because it mutates remote state

### Drift

- response shape for `GET /api/v1/users/tokens/list`
- create-dialog anchors on `/my/access/token`
- normalized token summary snapshots that exclude raw token strings

## Acceptance Criteria

- `modelscope.list_tokens` returns only non-secret metadata and a `trace_id`
- `modelscope.get_token` returns the full raw token only when `confirm_reveal=true`
- `modelscope.create_token` refuses to run without `confirm_create=true`
- raw token values never leak into traces, snapshots, or non-reveal outputs
- the working browser-import session can access the token capabilities without another interactive login
- Playwright compatibility is restored for imported storage-state cookies so guided UI fallback remains viable

