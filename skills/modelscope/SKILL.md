# ModelScope Skill Pack

ModelScope skills expose normalized read-only capability contracts for model discovery, overview inspection, file listing, quickstart extraction, and authenticated profile lookup.

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
