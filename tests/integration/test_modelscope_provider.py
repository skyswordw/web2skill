from __future__ import annotations

import pytest

registry_module = pytest.importorskip(
    "web2skill.skills.registry",
    reason="skill registry slice is still in flight",
)


@pytest.mark.integration
def test_builtin_modelscope_bundle_exposes_all_v1_capabilities() -> None:
    registry = registry_module.SkillRegistry.discover()
    loaded = registry.get_provider("modelscope")
    capability_names = {capability.name for capability in loaded.manifest.capabilities}

    assert capability_names == {
        "modelscope.search_models",
        "modelscope.get_model_overview",
        "modelscope.list_model_files",
        "modelscope.get_quickstart",
        "modelscope.get_account_profile",
        "modelscope.list_tokens",
        "modelscope.get_token",
        "modelscope.create_token",
    }


@pytest.mark.integration
def test_builtin_modelscope_bundle_exposes_session_hooks() -> None:
    registry = registry_module.SkillRegistry.discover()
    loaded = registry.get_provider("modelscope")

    assert loaded.manifest.runtime.kind == "python_scripts"
    assert loaded.manifest.session_hooks.login_script == "scripts/session/login.py"
    assert loaded.manifest.session_hooks.doctor_script == "scripts/session/doctor.py"
