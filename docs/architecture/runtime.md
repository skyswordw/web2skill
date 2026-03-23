# Runtime Architecture

## Intent

The runtime is the stable contract boundary between agent callers, provider implementations, and browser execution support.

## Layers

1. `web2skill.core`
   - contracts and enums
   - runtime dispatch
   - session persistence
   - guardrails and escalation
   - trace and replay models
2. `web2skill.browser`
   - Playwright lifecycle helpers
   - network capture
   - DOM snapshot support
   - guided fallback orchestration
3. `web2skill.skills`
   - manifest schema
   - provider capability registry
   - `SKILL.md` rendering helpers
4. `web2skill.providers.<provider>`
   - capability handlers
   - selectors and parsers
   - provider-specific login and drift probes

## Execution Rules

- Prefer network data to UI scraping.
- Treat DOM parsing as fallback, not the primary contract.
- Reserve guided UI fallback for login and genuinely interactive flows.
- Return a `SkillResult` for every invocation, even when escalation is required.

## Replay Model

Every invocation should write enough structured trace data to replay the decision path, data source, and normalized output without requiring a live re-run.

