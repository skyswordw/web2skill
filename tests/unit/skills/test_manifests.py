from __future__ import annotations

import pytest

manifests = pytest.importorskip(
    "web2skill.skills.manifests",
    reason="skill packaging slice is still in flight",
)


def test_manifest_declares_exact_v1_modelscope_capabilities() -> None:
    manifest = manifests.SkillManifest.model_validate(
        {
            "provider": "modelscope",
            "capabilities": [
                {"name": "modelscope.search_models"},
                {"name": "modelscope.get_model_overview"},
                {"name": "modelscope.list_model_files"},
                {"name": "modelscope.get_quickstart"},
                {"name": "modelscope.get_account_profile"},
            ],
        }
    )

    assert [capability.name for capability in manifest.capabilities] == [
        "modelscope.search_models",
        "modelscope.get_model_overview",
        "modelscope.list_model_files",
        "modelscope.get_quickstart",
        "modelscope.get_account_profile",
    ]


def test_manifest_schema_supports_skill_artifact_contract() -> None:
    assert hasattr(manifests, "SkillManifest")
