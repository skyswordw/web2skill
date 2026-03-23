from __future__ import annotations

from pathlib import Path

import pytest

registry_module = pytest.importorskip(
    "web2skill.skills.registry",
    reason="skill packaging slice is still in flight",
)


def test_discover_prefers_user_installed_bundle_over_builtin_bundle(tmp_path: Path) -> None:
    user_root = tmp_path / "user"
    builtin_root = tmp_path / "builtin"
    _write_bundle(user_root, provider="modelscope", summary="user bundle")
    _write_bundle(builtin_root, provider="modelscope", summary="builtin bundle")

    registry = registry_module.SkillRegistry.discover(
        user_root=user_root,
        builtin_roots=(builtin_root,),
    )

    loaded = registry.get_provider("modelscope")
    assert loaded.manifest.summary == "user bundle"
    assert loaded.source == "user"
    assert loaded.bundle_root == user_root / "modelscope"


def test_discover_loads_builtin_bundle_when_no_user_install_exists(tmp_path: Path) -> None:
    builtin_root = tmp_path / "builtin"
    _write_bundle(builtin_root, provider="modelscope", summary="builtin bundle")

    registry = registry_module.SkillRegistry.discover(
        user_root=tmp_path / "user",
        builtin_roots=(builtin_root,),
    )

    loaded = registry.get_provider("modelscope")
    assert loaded.manifest.summary == "builtin bundle"
    assert loaded.source == "builtin"
    assert loaded.bundle_root == builtin_root / "modelscope"


def _write_bundle(root: Path, *, provider: str, summary: str) -> None:
    bundle_root = root / provider
    bundle_root.mkdir(parents=True, exist_ok=True)
    (bundle_root / "SKILL.md").write_text(f"# {provider}\n", encoding="utf-8")
    (bundle_root / "skill.yaml").write_text(
        "\n".join(
            [
                'bundle_id: "modelscope"',
                'bundle_version: "1.0.0"',
                f'provider: "{provider}"',
                f'summary: "{summary}"',
                "runtime:",
                '  kind: "python_scripts"',
                '  env: "core"',
                "capabilities:",
                f'  - name: "{provider}.search_models"',
                '    entry_script: "scripts/capabilities/search_models.py"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
