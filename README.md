# web2skill

[English](https://github.com/skyswordw/web2skill/blob/main/README.md) | [简体中文](https://github.com/skyswordw/web2skill/blob/main/README.zh-CN.md)

`web2skill` turns stable capabilities from closed-source web apps and SaaS products into agent-usable skills.
Version 1 ships one Python package, `web2skill`, with a built-in ModelScope skill bundle and support for installing additional skill bundles from a local path, git URL, git subdirectory, or marketplace entry.

## Quickstart

### 1. Install the package

```bash
pip install web2skill
python -m playwright install chromium
```

### 2. See the built-in skills

```bash
web2skill skills list
web2skill skills describe modelscope
```

### 3. Run a public ModelScope capability

```bash
web2skill invoke modelscope.search_models --input '{"query":"qwen"}' --json
```

### 4. Log in for account-scoped capabilities

```bash
web2skill sessions login modelscope --mode interactive
web2skill sessions doctor modelscope --json
web2skill invoke modelscope.get_account_profile --input '{}' --json
```

## What You Get

- One installable package: `web2skill`
- Built-in first-party ModelScope skill bundle
- Stable JSON results with `trace_id`, `strategy_used`, and `requires_human`
- Reusable browser sessions based on Playwright storage state
- Replayable traces for every invocation
- Installable third-party or local skill bundles

## Public And Authenticated ModelScope Capabilities

| Capability | Login required | What it does |
| --- | --- | --- |
| `modelscope.search_models` | No | Search public models by query |
| `modelscope.get_model_overview` | No | Fetch normalized overview metadata |
| `modelscope.list_model_files` | No | List repository files for a model |
| `modelscope.get_quickstart` | No | Extract quickstart or usage guidance |
| `modelscope.get_account_profile` | Yes | Read the authenticated account profile |
| `modelscope.list_tokens` | Yes | List non-secret token metadata |
| `modelscope.get_token` | Yes | Reveal a selected token after explicit confirmation |
| `modelscope.create_token` | Yes | Create a token after explicit confirmation |

## First Login

`web2skill sessions login modelscope` supports two modes:

- `interactive`: Opens a real browser window. Use this when you expect CAPTCHA, QR login, MFA, or any human checkpoint.
- `import-browser`: Imports cookies from a locally signed-in browser. Use this when you already have an authenticated ModelScope browser session and want a faster bootstrap.

`web2skill sessions doctor modelscope` checks the local storage-state artifact only. It confirms that the file exists and contains cookies, but it does not prove that ModelScope will still accept those cookies remotely.

## Payload Examples

Inline JSON:

```bash
web2skill invoke modelscope.get_model_overview --input '{"model_slug":"Qwen/Qwen3.5-27B"}' --json
```

JSON file input:

```bash
cat > input.json <<'JSON'
{
  "model_slug": "Qwen/Qwen3.5-27B"
}
JSON
web2skill invoke modelscope.list_model_files --input @input.json --json
```

## Built-In And Custom Skills

Built-in first-party skills ship inside the `web2skill` wheel. Additional user-created skill bundles can be installed without publishing a separate PyPI package:

```bash
web2skill skills install /path/to/skill-bundle
web2skill skills install https://github.com/your-org/your-skill-repo.git
web2skill skills install https://github.com/your-org/your-monorepo.git --subdir skills/your-skill
web2skill marketplaces add official https://raw.githubusercontent.com/skyswordw/web2skill/main/marketplace.yaml
web2skill skills search modelscope --marketplace official
web2skill skills install modelscope@official
web2skill skills update <bundle_id>
web2skill skills uninstall <bundle_id>
```

The official first-party marketplace manifest lives at [`marketplace.yaml`](./marketplace.yaml). Marketplace entries resolve to a git repository plus an optional bundle subdirectory, which lets one monorepo publish multiple installable skills without making users clone the whole repository.

## Claude Code Marketplace Status

Anthropic's Claude Code plugin marketplace uses a different packaging contract from `web2skill`. Claude Code marketplace installs expect plugin metadata in `.claude-plugin/plugin.json`, a marketplace catalog in `.claude-plugin/marketplace.json`, and install flows such as `/plugin marketplace add ...` followed by `/plugin install plugin-name@marketplace-name`.

This repository does not ship that Claude Code plugin structure yet. The marketplace support implemented here is currently for the `web2skill` runtime and CLI only:

```bash
web2skill marketplaces add official https://raw.githubusercontent.com/skyswordw/web2skill/main/marketplace.yaml
web2skill skills install modelscope@official
```

So today:

- If you want to use `web2skill`, follow the `web2skill` CLI install flow in this README.
- If you want direct Claude Code marketplace installation, that is not implemented yet in this repository and should be treated as future work.

## Contributor Setup

If you are working from a source checkout instead of an installed package:

```bash
uv sync --dev
uv run playwright install chromium
uv run pytest
uv run web2skill skills list
```

## Skill Bundle Layout

Every first-party or user-installed skill bundle follows the same contract:

```text
<skill>/
  SKILL.md
  skill.yaml
  scripts/
    capabilities/
    session/
    lib/
  references/
  assets/
  pyproject.toml
  uv.lock
```

User-installed bundles live under `~/.web2skill/skills/`.

## Repository Map

- `src/web2skill/`: core runtime, browser support, bundle registry, CLI, and installer logic
- `skills/`: canonical first-party skill bundles authored in bundle layout
- `marketplace.yaml`: official first-party marketplace manifest for git/subdir installs
- `tests/`: unit, integration, e2e, and drift coverage
- `docs/architecture/`: architecture decisions and system design
- `docs/evals/`: evaluation and smoke guidance
- `docs/quality/`: quality gates and release criteria
