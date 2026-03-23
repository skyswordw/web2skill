# ModelScope Skill Pack

ModelScope skills expose normalized capability contracts for model discovery, overview inspection, file listing, quickstart extraction, authenticated profile lookup, and access-token management.

This bundle separates public read-only capabilities from authenticated account capabilities. Public capabilities can run without a login. Authenticated capabilities reuse a saved Playwright storage-state file and session record created by `web2skill sessions login modelscope`.

The commands below assume `web2skill` is installed as a package. If you are developing from a source checkout, prefix CLI commands with `uv run`.

## Install Paths

This skill can be used in three ways:

- Built-in: `pip install web2skill` and then invoke `modelscope.*` directly.
- Standalone from a monorepo subdirectory: `web2skill skills install https://github.com/skyswordw/web2skill.git --subdir skills/modelscope`
- Standalone from a `web2skill` marketplace entry: add a marketplace manifest and run `web2skill skills install modelscope@<marketplace>`

This is not the same as Anthropic Claude Code's native plugin marketplace format. This bundle currently installs through the `web2skill` CLI, not through Claude Code's `/plugin install ...` flow.

## Provider

- Provider id: `modelscope`
- Auth mode: `session`
- Login required: `true` for authenticated capabilities only
- Base URL: `https://www.modelscope.cn/`

## Capability Groups

### Public capabilities

These do not require an authenticated ModelScope session:

- `modelscope.search_models`
- `modelscope.get_model_overview`
- `modelscope.list_model_files`
- `modelscope.get_quickstart`

### Authenticated capabilities

These require a previously captured ModelScope session:

- `modelscope.get_account_profile`
- `modelscope.list_tokens`
- `modelscope.get_token`
- `modelscope.create_token`

## Shared Prerequisites

- Install Chromium with `python -m playwright install chromium` before using interactive login.
- Capture a reusable browser session with `web2skill sessions login modelscope`.
- Re-run login when ModelScope signs you out or when saved cookies expire.

## Session Bootstrap

`web2skill sessions login modelscope` supports two login modes:

- `interactive`: Opens a real browser window and lets a human complete login on ModelScope. This is the most reliable option when you expect QR login, CAPTCHA, MFA, or other interactive prompts. It is slower, requires a browser UI, and waits for the bundle to detect that authentication succeeded before saving storage state.
- `import-browser`: Reads existing ModelScope cookies from a local browser profile and writes them into Playwright storage state. This is faster and works well when you are already signed in with Chrome, Edge, Chromium, or another supported browser. It can fail if the browser has no ModelScope cookies, if local cookie access is blocked, or if the imported cookies are no longer authenticated.

In practice:

- Choose `interactive` when onboarding a machine for the first time or when login involves a human checkpoint.
- Choose `import-browser` when you are already signed in locally and want the quickest non-interactive bootstrap.

## Shared Workflow

1. Prefer network responses for search and metadata endpoints.
1. Fall back to DOM parsing when no stable JSON contract is available.
1. Escalate to guided UI only for login or strongly interactive flows.

## Shared Recovery

- If search responses drift, inspect captured network payloads before adding new selectors.
- If an authenticated capability starts failing, run `web2skill sessions doctor modelscope` first, then re-run `web2skill sessions login modelscope` if needed.

## `sessions doctor`

`web2skill sessions doctor modelscope` is a lightweight local health check for the saved session artifact. It currently checks:

- whether the expected storage-state file exists
- whether the file can be loaded as Playwright storage state
- whether the storage state includes at least one cookie

It does not currently prove that the cookies are still valid on the remote ModelScope service. A passing doctor result means the local session file looks usable; it does not guarantee that ModelScope will still accept the session.

## Storage Locations

By default, this bundle stores ModelScope session artifacts in two places:

- storage state: `./.web2skill/modelscope-storage-state.json` relative to the current working directory when login runs
- interactive browser profile cache: `./.web2skill/modelscope-login-profile` relative to the current working directory when interactive login runs
- session records: `~/.web2skill/sessions/<session-id>.json`

The storage-state JSON contains browser cookies and should be treated like a local secret. The session record JSON stores an absolute path to that storage-state file together with metadata such as the generated `session_id`, provider name, and timestamps.

## Shared Human Handoff

- Ask a human to complete interactive login or MFA challenges.

## `modelscope.search_models`

Returns normalized model search results without mutating remote state.

- Risk: `low`
- Strategy order: `network, dom`
- Human confirmation required: `false`

### Prerequisites

- No authenticated session required for public search.

### Workflow

1. Send the query through the primary search endpoint.
1. Normalize model slugs, owners, tags, and ranking metadata.

### Recovery

- Retry with DOM extraction if the search API shape changes.

### Examples

#### Search Qwen models

Look up Qwen models on the first page.

Input:
```json
{
  "page": 1,
  "query": "qwen"
}
```

Output:
```json
{
  "items": [
    {
      "model_slug": "Qwen/Qwen2.5-7B-Instruct"
    }
  ],
  "total": 1
}
```

## `modelscope.get_model_overview`

Returns owner, summary, tags, stats, and metadata for a known model.

- Risk: `low`
- Strategy order: `network, dom`
- Human confirmation required: `false`

### Prerequisites

- No authenticated session required for public model metadata.

### Workflow

1. Load the model detail resource using the slug.
1. Normalize cards, metadata, and usage signals.

### Recovery

- Fallback to stable DOM anchors on the model overview page.

## `modelscope.list_model_files`

Returns normalized file entries, sizes, and paths exposed by ModelScope.

- Risk: `low`
- Strategy order: `network, dom`
- Human confirmation required: `false`

### Prerequisites

- No authenticated session required for public repository file listings.

### Workflow

1. Query the files endpoint for the repository tree.
1. Normalize file names, paths, sizes, and directory markers.

## `modelscope.get_quickstart`

Returns stable quickstart guidance to help an agent explain how to use the model.

- Risk: `low`
- Strategy order: `network, dom`
- Human confirmation required: `false`

### Prerequisites

- No authenticated session required for public quickstart extraction.

### Workflow

1. Prefer structured model card content when available.
1. Fallback to DOM extraction for the usage block.

### Recovery

- If no quickstart exists, return an empty normalized section with source metadata.

## `modelscope.get_account_profile`

Returns normalized profile details from an already-authenticated ModelScope session.

- Risk: `medium`
- Strategy order: `network, dom, ui`
- Human confirmation required: `false`

### Prerequisites

- An existing authenticated browser session is required.

### Workflow

1. Reuse stored Playwright session state.
1. Read account information from authenticated APIs before DOM fallbacks.

### Recovery

- If session reuse fails, trigger the login bootstrap flow.

### Human Handoff

- Escalate if the account requires CAPTCHA, MFA, or other interactive approval.

## `modelscope.list_tokens`

Returns non-secret token metadata such as id, name, creation time, and expiry.

- Risk: `medium`
- Strategy order: `network, dom`
- Human confirmation required: `false`

### Prerequisites

- An existing authenticated browser session is required.

### Workflow

1. Read token metadata from the authenticated token-management API.
1. Return only non-secret metadata in the list response.

### Recovery

- If the token API drifts, inspect the authenticated account token page network calls.

## `modelscope.get_token`

Returns a raw token string for one selected token only after explicit confirmation.

- Risk: `high`
- Strategy order: `network, dom`
- Human confirmation required: `true`

### Prerequisites

- An existing authenticated browser session is required.

### Workflow

1. Read the authenticated token list.
1. Select the requested token by id and reveal the raw token only when explicitly confirmed.

### Human Handoff

- Escalate if the session is expired or additional account approval is required.

### Examples

#### Reveal the default token

Return the raw token value for one selected token.

Input:
```json
{
  "confirm_reveal": true,
  "token_id": 3245671
}
```

Output:
```json
{
  "name": "default",
  "token": "ms-REDACTED-EXAMPLE",
  "token_id": 3245671
}
```

## `modelscope.create_token`

Creates a new token only after explicit confirmation and returns the created raw token.

- Risk: `high`
- Strategy order: `network, ui`
- Human confirmation required: `true`

### Prerequisites

- An existing authenticated browser session is required.

### Workflow

1. Prefer a stable authenticated create-token API if one is available.
1. Use guided UI fallback only for the bounded create-token flow when needed.

### Human Handoff

- Escalate if the session is expired, the token quota is exhausted, or a human must confirm account actions.
