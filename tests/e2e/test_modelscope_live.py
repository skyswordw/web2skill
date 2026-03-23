from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

EnvOverride = Callable[[str, str | None], None]
SkillResultAsserter = Callable[[dict[str, Any]], None]


def _build_runtime() -> Any:
    runtime_module: Any = pytest.importorskip(
        "web2skill.core.runtime",
        reason="runtime module is still in flight",
    )
    provider_module: Any = pytest.importorskip(
        "web2skill.providers.modelscope.provider",
        reason="ModelScope provider slice is still in flight",
    )
    provider = provider_module.ModelScopeProvider()
    runtime_type = runtime_module.SkillRuntime
    return runtime_type(registry=provider)


def test_live_suite_requires_opt_in(env_override: EnvOverride) -> None:
    env_override("WEB2SKILL_RUN_LIVE", None)
    assert True


@pytest.mark.e2e
@pytest.mark.live
def test_search_models_live(
    require_live: None,
    assert_skill_result_contract: SkillResultAsserter,
    modelscope_session_id: str | None,
) -> None:
    runtime = _build_runtime()
    result = runtime.invoke(
        "modelscope.search_models",
        {"query": "qwen"},
        session_id=modelscope_session_id,
    )

    assert_skill_result_contract(result.model_dump())


@pytest.mark.e2e
@pytest.mark.live
def test_get_model_overview_live(
    require_live: None,
    assert_skill_result_contract: SkillResultAsserter,
    modelscope_known_slug: str,
    modelscope_session_id: str | None,
) -> None:
    runtime = _build_runtime()
    result = runtime.invoke(
        "modelscope.get_model_overview",
        {"model_slug": modelscope_known_slug},
        session_id=modelscope_session_id,
    )

    assert_skill_result_contract(result.model_dump())


@pytest.mark.e2e
@pytest.mark.live
def test_list_model_files_live(
    require_live: None,
    assert_skill_result_contract: SkillResultAsserter,
    modelscope_known_slug: str,
    modelscope_session_id: str | None,
) -> None:
    runtime = _build_runtime()
    result = runtime.invoke(
        "modelscope.list_model_files",
        {"model_slug": modelscope_known_slug},
        session_id=modelscope_session_id,
    )

    assert_skill_result_contract(result.model_dump())


@pytest.mark.e2e
@pytest.mark.live
def test_get_quickstart_live(
    require_live: None,
    assert_skill_result_contract: SkillResultAsserter,
    modelscope_known_slug: str,
    modelscope_session_id: str | None,
) -> None:
    runtime = _build_runtime()
    result = runtime.invoke(
        "modelscope.get_quickstart",
        {"model_slug": modelscope_known_slug},
        session_id=modelscope_session_id,
    )

    assert_skill_result_contract(result.model_dump())


@pytest.mark.e2e
@pytest.mark.live
def test_get_account_profile_live(
    require_live: None,
    assert_skill_result_contract: SkillResultAsserter,
    modelscope_session_id: str | None,
) -> None:
    runtime = _build_runtime()
    result = runtime.invoke(
        "modelscope.get_account_profile",
        {},
        session_id=modelscope_session_id,
    )

    assert_skill_result_contract(result.model_dump())
