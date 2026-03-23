from __future__ import annotations

import pytest

manifests = pytest.importorskip(
    "web2skill.skills.manifests",
    reason="skill packaging slice is still in flight",
)


def test_manifest_declares_exact_v1_modelscope_capabilities() -> None:
    manifest = manifests.SkillManifest.model_validate(
        {
            "bundle_id": "modelscope",
            "bundle_version": "1.0.0",
            "provider": "modelscope",
            "runtime": {"kind": "python_scripts", "env": "core"},
            "capabilities": [
                {
                    "name": "modelscope.search_models",
                    "entry_script": "scripts/capabilities/search_models.py",
                },
                {
                    "name": "modelscope.get_model_overview",
                    "entry_script": "scripts/capabilities/get_model_overview.py",
                },
                {
                    "name": "modelscope.list_model_files",
                    "entry_script": "scripts/capabilities/list_model_files.py",
                },
                {
                    "name": "modelscope.get_quickstart",
                    "entry_script": "scripts/capabilities/get_quickstart.py",
                },
                {
                    "name": "modelscope.get_account_profile",
                    "entry_script": "scripts/capabilities/get_account_profile.py",
                },
                {
                    "name": "modelscope.list_tokens",
                    "entry_script": "scripts/capabilities/list_tokens.py",
                },
                {
                    "name": "modelscope.get_token",
                    "entry_script": "scripts/capabilities/get_token.py",
                },
                {
                    "name": "modelscope.create_token",
                    "entry_script": "scripts/capabilities/create_token.py",
                },
            ],
        }
    )

    assert [capability.name for capability in manifest.capabilities] == [
        "modelscope.search_models",
        "modelscope.get_model_overview",
        "modelscope.list_model_files",
        "modelscope.get_quickstart",
        "modelscope.get_account_profile",
        "modelscope.list_tokens",
        "modelscope.get_token",
        "modelscope.create_token",
    ]


def test_manifest_schema_supports_skill_artifact_contract() -> None:
    assert hasattr(manifests, "SkillManifest")


def test_manifest_schema_supports_bundle_execution_metadata() -> None:
    manifest = manifests.SkillManifest.model_validate(
        {
            "bundle_id": "modelscope",
            "bundle_version": "1.2.3",
            "provider": "modelscope",
            "runtime": {"kind": "python_scripts", "env": "bundle"},
            "session_hooks": {
                "login_script": "scripts/session/login.py",
                "doctor_script": "scripts/session/doctor.py",
            },
            "capabilities": [
                {
                    "name": "modelscope.get_token",
                    "strategies": ["network", "ui"],
                    "entry_script": "scripts/capabilities/get_token.py",
                    "confirmation_field": "confirm_reveal",
                    "session_required": True,
                }
            ],
        }
    )

    assert manifest.bundle_id == "modelscope"
    assert manifest.bundle_version == "1.2.3"
    assert manifest.runtime.kind == "python_scripts"
    assert manifest.runtime.env == "bundle"
    assert manifest.session_hooks.login_script == "scripts/session/login.py"
    assert manifest.session_hooks.doctor_script == "scripts/session/doctor.py"
    assert manifest.capabilities[0].entry_script == "scripts/capabilities/get_token.py"
    assert manifest.capabilities[0].confirmation_field == "confirm_reveal"
    assert manifest.capabilities[0].session_required is True
    assert manifest.capabilities[0].strategies == ["network", "guided_ui"]
