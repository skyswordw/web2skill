from __future__ import annotations

from pathlib import Path

import pytest
import yaml

marketplaces = pytest.importorskip(
    "web2skill.skills.marketplaces",
    reason="marketplace installer support is still in flight",
)


def test_source_descriptor_normalizes_subdir_paths() -> None:
    source = marketplaces.SourceDescriptor(
        kind="git_subdir",
        repo="https://github.com/example/skills.git",
        subdir="skills/demo/",
    )

    assert source.kind == "git_subdir"
    assert source.subdir == "skills/demo"


def test_official_marketplace_manifest_contains_modelscope_entry() -> None:
    manifest_path = Path(__file__).resolve().parents[3] / "marketplace.yaml"
    manifest = marketplaces.MarketplaceManifest.model_validate(
        yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    )

    entry = next(plugin for plugin in manifest.plugins if plugin.plugin_id == "modelscope")
    assert entry.bundle_id == "modelscope"
    assert entry.provider == "modelscope"
    assert entry.source.kind == "git_subdir"
    assert entry.source.subdir == "skills/modelscope"
