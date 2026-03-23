from __future__ import annotations

import pytest

provider_module = pytest.importorskip(
    "web2skill.providers.modelscope.provider",
    reason="ModelScope provider slice is still in flight",
)


@pytest.mark.integration
def test_provider_exposes_all_v1_capabilities() -> None:
    provider = provider_module.ModelScopeProvider()
    capability_names = set(provider.capabilities())

    assert capability_names == {
        "modelscope.search_models",
        "modelscope.get_model_overview",
        "modelscope.list_model_files",
        "modelscope.get_quickstart",
        "modelscope.get_account_profile",
    }


@pytest.mark.integration
def test_provider_doctor_or_login_surface_exists() -> None:
    assert hasattr(provider_module, "ModelScopeProvider")
