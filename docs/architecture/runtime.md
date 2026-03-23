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
   - JSON-stdio script runner
2. `web2skill.browser`
   - Playwright lifecycle helpers
   - network capture
   - DOM snapshot support
   - guided fallback orchestration
3. `web2skill.skills`
   - manifest schema
   - built-in, marketplace-resolved, and user-installed bundle discovery
   - bundle installer and per-skill environment management
   - marketplace catalog lookup and subdir-aware source resolution
   - capability and session-hook execution adapters
   - `SKILL.md` rendering helpers
4. `skills/<provider>/`
   - `SKILL.md` and `skill.yaml`
   - `scripts/capabilities/` entry scripts
   - `scripts/session/` login and doctor hooks
   - `scripts/lib/` provider-specific selectors, parsers, and helpers

## Bundle Discovery

- User-installed bundles are discovered first from `~/.web2skill/skills/`
- Built-in first-party bundles are discovered second from the packaged `web2skill/bundled_skills`
  directory inside the wheel
- Configured marketplaces provide searchable install metadata that resolves a plugin id to a git
  source plus an optional bundle subdirectory
- Capability execution always flows through bundle metadata and JSON-stdio scripts rather than
  hard-coded provider imports in the CLI/runtime path

## Execution Rules

- Prefer network data to UI scraping.
- Treat DOM parsing as fallback, not the primary contract.
- Reserve guided UI fallback for login and genuinely interactive flows.
- Return a `SkillResult` for every invocation, even when escalation is required.
- Use explicit confirmation fields for high-risk capabilities before automation proceeds.

## Replay Model

Every invocation should write enough structured trace data to replay the decision path, data source, and normalized output without requiring a live re-run.
