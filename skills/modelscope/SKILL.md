# ModelScope Skill Pack

ModelScope skills expose normalized capability contracts for model discovery, overview inspection, file listing, quickstart extraction, authenticated profile lookup, and access-token management.

## Provider

- Provider id: `modelscope`
- Auth mode: `session`
- Login required: `true`
- Base URL: `https://www.modelscope.cn/`

## Shared Prerequisites

- Install Chromium with `uv run playwright install chromium` before interactive login flows.
- Persist browser storage state after login so agents can reuse the same session.

## Shared Workflow

1. Prefer network responses for search and metadata endpoints.
1. Fall back to DOM parsing when no stable JSON contract is available.
1. Escalate to guided UI only for login or strongly interactive flows.

## Shared Recovery

- If search responses drift, inspect captured network payloads before adding new selectors.
- If the session expires, run `web2skill sessions login modelscope` again.

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

### Workflow

1. Query the files endpoint for the repository tree.
1. Normalize file names, paths, sizes, and directory markers.

## `modelscope.get_quickstart`

Returns stable quickstart guidance to help an agent explain how to use the model.

- Risk: `low`
- Strategy order: `network, dom`
- Human confirmation required: `false`

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
  "token": "ms-...",
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
