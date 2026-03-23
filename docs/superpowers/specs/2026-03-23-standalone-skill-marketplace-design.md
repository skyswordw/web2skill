# Standalone Skill Marketplace Design

> This document captures the approved design for standalone skill installation, marketplace discovery, and git-subdir delivery while keeping `web2skill` as the runtime.

## Goal

Allow users to install one selected skill from a monorepo or marketplace without cloning the entire repository, while preserving the existing `web2skill` runtime contract and bundled first-party skills.

## Product Decisions

- `web2skill` remains the only PyPI package.
- First-party skills stay bundled in the wheel.
- First-party skills are also installable as standalone marketplace entries.
- The canonical executable bundle format remains:
  - `SKILL.md`
  - `skill.yaml`
  - `scripts/`
  - optional `references/`, `assets/`, `pyproject.toml`, `uv.lock`
- Anthropic marketplace UX is the compatibility target for install semantics, not the primary runtime format.
- Full `.claude-plugin/plugin.json` runtime compatibility is out of scope for this milestone.

## Supported Install Sources

`web2skill` must support installation from:

1. a local bundle directory
2. a local monorepo path plus subdirectory
3. a git repository whose bundle is at repo root
4. a git repository plus subdirectory
5. a marketplace reference in the form `<plugin_id>@<marketplace>`

## Public CLI

Existing commands stay valid:

```bash
web2skill skills install <local-path>
web2skill skills install <git-url>
```

New additive commands:

```bash
web2skill skills install <repo-or-path> --subdir <bundle-path>
web2skill skills install <plugin_id>@<marketplace>
web2skill skills search [query] [--marketplace <alias>]
web2skill marketplaces add <alias> <manifest-url-or-path>
web2skill marketplaces list
web2skill marketplaces remove <alias>
```

`skills describe` remains focused on installed or bundled bundles in this milestone.

## Data Model

### Source Descriptor

Installer sources must be normalized into a structured descriptor:

- `local_path`
- `git_repo`
- `git_subdir`
- `marketplace_ref`

The descriptor must retain enough information for `update` to repeat the install without string parsing heuristics.

### Install Metadata

`.web2skill-install.json` must move from loose `source` strings to structured metadata that includes:

- `bundle_id`
- `bundle_version`
- `provider`
- `installed_at`
- normalized `source_descriptor`
- `source_kind`

### Marketplace Manifest

Add a web2skill marketplace manifest schema with:

- marketplace metadata
- installable plugin entries

Each entry must include:

- `plugin_id`
- `bundle_id`
- `provider`
- `display_name`
- `summary`
- `source.kind`
- `source.repo`
- optional `source.ref`
- optional `source.subdir`

Only `git_repo` and `git_subdir` marketplace source kinds are supported in this milestone.

## Install Resolution

### Local

- `<path>` without `--subdir` must continue to require `skill.yaml` at the target path.
- `<path> --subdir <bundle-path>` resolves to `<path>/<bundle-path>`.

### Git

- `<git-url>` without `--subdir` must continue to support root-level bundle installs.
- `<git-url> --subdir <bundle-path>` must use sparse clone and sparse checkout.
- If sparse checkout is unavailable or fails, installation must stop with clear remediation text. It must not silently fall back to a full clone.

### Marketplace

- `<plugin_id>@<marketplace>` resolves marketplace alias -> marketplace manifest -> plugin entry -> normalized source descriptor -> bundle materialization -> existing validation/install flow.
- Marketplace add/remove only manages local marketplace registry data; it does not install bundles.

## Discovery And Precedence

- Built-in first-party bundles remain discoverable exactly as today.
- User-installed bundles still override bundled first-party bundles when `provider` or `bundle_id` matches.
- Uninstalling the user-installed bundle must reveal the bundled one again without extra recovery steps.

## Harmless Engineering Constraints

- Additive only:
  - do not remove existing install commands
  - do not rename existing install commands
  - do not change runtime invoke/session/replay APIs
  - do not move first-party skills out of the wheel
- Test-first:
  - new install-path behavior must land behind failing tests first
  - all current install tests must remain green
- No repo split:
  - first-party standalone install must be sourced from this monorepo via subdirectory install
- No live network mutation in tests:
  - use local git fixtures and local marketplace manifests

## Documentation And Publication

- Publish an official first-party marketplace manifest from this repo at a stable raw GitHub URL.
- Update README and release docs so users can choose:
  - built-in skill flow through `pip install web2skill`
  - standalone skill install through marketplace or `--subdir`
- Update `AGENTS.md` so agents understand that skill installation is no longer only root-path or root-git based.

## Acceptance Criteria

- Users can install a selected skill from a monorepo subdirectory without cloning the whole repo.
- Users can install a selected skill via marketplace alias and plugin id.
- Existing local-path and root-git install flows still work.
- Marketplace-installed skills can be updated and uninstalled using stored structured metadata.
- Built-in ModelScope remains bundled and callable.
- A user-installed ModelScope bundle can override the bundled one and uninstall cleanly back to the bundled copy.
