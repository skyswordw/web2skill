# Standalone Skill Marketplace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add standalone marketplace and git-subdir skill installation without changing the `web2skill` runtime contract or removing bundled first-party skills.

**Architecture:** The installer layer grows a structured source model, marketplace registry, and sparse git-subdir materialization path. The runtime remains bundle-driven and unchanged at the invoke/session boundary. First-party skills continue shipping in the wheel and also become standalone-install targets through marketplace metadata.

**Tech Stack:** Python 3.13/3.14, uv, Typer, Pydantic v2, pytest, Git sparse checkout

---

### Task 1: Spec, Docs, And Collaboration Baseline

**Files:**
- Create: `docs/superpowers/specs/2026-03-23-standalone-skill-marketplace-design.md`
- Create: `docs/superpowers/plans/2026-03-23-standalone-skill-marketplace.md`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/quality/release-process.md`

- [ ] **Step 1: Write the failing test**

```python
def test_readme_mentions_marketplace_install() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    assert "web2skill marketplaces add" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_docs_marketplace.py::test_readme_mentions_marketplace_install -v`
Expected: FAIL because marketplace docs do not exist yet

- [ ] **Step 3: Write minimal implementation**

Author the design and implementation docs, update onboarding and agent rules, and document the first-party marketplace publication path.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_docs_marketplace.py::test_readme_mentions_marketplace_install -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs AGENTS.md README.md README.zh-CN.md
git commit -m "docs: add marketplace install design"
```

### Task 2: Red Tests For Marketplace And Git-Subdir Install

**Files:**
- Modify: `tests/integration/test_skill_installation.py`
- Create: `tests/integration/test_marketplaces.py`
- Modify: `docs/evals/modelscope.md`

- [ ] **Step 1: Write the failing test**

```python
def test_cli_installs_skill_bundle_from_git_subdir(...) -> None:
    result = runner.invoke(app, ["skills", "install", str(repo_root), "--subdir", "skills/demo", "--json"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_skill_installation.py::test_cli_installs_skill_bundle_from_git_subdir -v`
Expected: FAIL because `--subdir` and sparse materialization do not exist

- [ ] **Step 3: Write minimal implementation**

Add failing coverage for:
- local path with `--subdir`
- git repo with `--subdir`
- marketplace add/list/remove
- marketplace search
- marketplace install
- update/uninstall using structured install metadata
- bundled precedence fallback

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_skill_installation.py tests/integration/test_marketplaces.py -v`
Expected: PASS after implementation lands

- [ ] **Step 5: Commit**

```bash
git add tests docs/evals/modelscope.md
git commit -m "test: add marketplace and subdir install coverage"
```

### Task 3: Structured Installer And Marketplace Registry

**Files:**
- Modify: `src/web2skill/skills/installer.py`
- Modify: `src/web2skill/skills/manifests.py`
- Modify: `src/web2skill/skills/registry.py`
- Create: `src/web2skill/skills/marketplaces.py`

- [ ] **Step 1: Write the failing test**

```python
def test_install_metadata_stores_structured_source_descriptor(...) -> None:
    ...
    assert payload["source_descriptor"]["kind"] == "git_subdir"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_marketplaces.py::test_install_metadata_stores_structured_source_descriptor -v`
Expected: FAIL because install metadata is still a loose string

- [ ] **Step 3: Write minimal implementation**

Implement:
- `SourceDescriptor`
- `InstallMetadata`
- `MarketplaceManifest`
- local/gitrepo/gitsubdir/marketplace source resolution
- sparse clone and sparse checkout for git subdir installs
- marketplace registry storage under `~/.web2skill`
- update/uninstall based on structured metadata

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_skill_installation.py tests/integration/test_marketplaces.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/web2skill/skills
git commit -m "feat: add marketplace and git-subdir installer support"
```

### Task 4: CLI And Runtime Integration

**Files:**
- Modify: `src/web2skill/cli.py`
- Modify: `src/web2skill/skills/execution.py`

- [ ] **Step 1: Write the failing test**

```python
def test_cli_marketplaces_add_and_search(...) -> None:
    result = runner.invoke(app, ["marketplaces", "list", "--json"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_marketplaces.py::test_cli_marketplaces_add_and_search -v`
Expected: FAIL because marketplace CLI commands do not exist

- [ ] **Step 3: Write minimal implementation**

Add CLI groups for marketplace registry and `skills search`, wire marketplace install resolution into the existing installer path, and fix any runtime path assumptions exposed by installed standalone bundles.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_marketplaces.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/web2skill/cli.py src/web2skill/skills/execution.py
git commit -m "feat: add marketplace cli and runtime integration"
```

### Task 5: First-Party Marketplace Metadata, Release Smoke, And Final Gates

**Files:**
- Create: `marketplaces/official.yaml`
- Modify: `skills/modelscope/skill.yaml`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/publish.yml`
- Modify: `README.md`
- Modify: `README.zh-CN.md`

- [ ] **Step 1: Write the failing test**

```python
def test_official_marketplace_contains_modelscope_entry() -> None:
    manifest = yaml.safe_load(Path("marketplaces/official.yaml").read_text())
    assert any(item["plugin_id"] == "modelscope" for item in manifest["plugins"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_marketplaces.py::test_official_marketplace_contains_modelscope_entry -v`
Expected: FAIL because the official marketplace manifest does not exist

- [ ] **Step 3: Write minimal implementation**

Publish the first-party marketplace manifest, wire release smoke tests for marketplace install, update ModelScope metadata/docs for standalone install, and refresh release/onboarding docs.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_marketplaces.py tests/integration/test_artifact_distribution.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add marketplaces skills/modelscope .github README.md README.zh-CN.md
git commit -m "feat: publish official skill marketplace metadata"
```
