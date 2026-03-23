from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

EnvOverride = Callable[[str, str | None], None]
SkillResultAsserter = Callable[[dict[str, Any]], None]


def _build_runtime(*, storage_state_path: Path | None = None) -> tuple[Any, str | None]:
    runtime_module: Any = pytest.importorskip(
        "web2skill.core.runtime",
        reason="runtime module is still in flight",
    )
    sessions_module: Any = pytest.importorskip(
        "web2skill.core.sessions",
        reason="sessions module is still in flight",
    )
    registry_module: Any = pytest.importorskip(
        "web2skill.skills.registry",
        reason="skill registry slice is still in flight",
    )
    execution_module: Any = pytest.importorskip(
        "web2skill.skills.execution",
        reason="bundle execution slice is still in flight",
    )
    session_store = sessions_module.InMemorySessionStore()
    session_id = None
    if storage_state_path is not None:
        session_id = "modelscope-live-session"
        session_store.put(
            sessions_module.SessionRecord.create(
                session_id=session_id,
                provider_name="modelscope",
                storage_state_path=storage_state_path,
                base_url="https://www.modelscope.cn",
            )
        )
    runtime_type = runtime_module.SkillRuntime
    runtime = runtime_type(
        registry=execution_module.BundleCapabilityRegistry(
            skill_registry=registry_module.SkillRegistry.discover(),
            session_store=session_store,
        ),
        session_store=session_store,
    )
    return runtime, session_id


def _require_storage_state(path: Path | None) -> Path:
    if path is None:
        pytest.skip("live token coverage requires WEB2SKILL_MODELSCOPE_STORAGE_STATE")
    return path


def _is_truthy(raw_value: object) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    if raw_value is None:
        return False
    return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}


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
    runtime, runtime_session_id = _build_runtime()
    result = runtime.invoke(
        "modelscope.search_models",
        {"query": "qwen"},
        session_id=modelscope_session_id or runtime_session_id,
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
    runtime, runtime_session_id = _build_runtime()
    result = runtime.invoke(
        "modelscope.get_model_overview",
        {"model_slug": modelscope_known_slug},
        session_id=modelscope_session_id or runtime_session_id,
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
    runtime, runtime_session_id = _build_runtime()
    result = runtime.invoke(
        "modelscope.list_model_files",
        {"model_slug": modelscope_known_slug},
        session_id=modelscope_session_id or runtime_session_id,
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
    runtime, runtime_session_id = _build_runtime()
    result = runtime.invoke(
        "modelscope.get_quickstart",
        {"model_slug": modelscope_known_slug},
        session_id=modelscope_session_id or runtime_session_id,
    )

    assert_skill_result_contract(result.model_dump())


@pytest.mark.e2e
@pytest.mark.live
def test_get_account_profile_live(
    require_live: None,
    assert_skill_result_contract: SkillResultAsserter,
    modelscope_session_id: str | None,
    modelscope_storage_state_path: Path | None,
) -> None:
    runtime, runtime_session_id = _build_runtime(storage_state_path=modelscope_storage_state_path)
    result = runtime.invoke(
        "modelscope.get_account_profile",
        {},
        session_id=modelscope_session_id or runtime_session_id,
    )

    assert_skill_result_contract(result.model_dump())


@pytest.mark.e2e
@pytest.mark.live
def test_list_tokens_live(
    require_live: None,
    assert_skill_result_contract: SkillResultAsserter,
    modelscope_storage_state_path: Path | None,
) -> None:
    runtime, runtime_session_id = _build_runtime(
        storage_state_path=_require_storage_state(modelscope_storage_state_path)
    )
    result = runtime.invoke("modelscope.list_tokens", {}, session_id=runtime_session_id)

    payload = result.model_dump()
    assert_skill_result_contract(payload)
    assert payload["requires_human"] is False
    assert isinstance(payload["output"], dict)
    assert isinstance(payload["output"]["items"], list)
    if payload["output"]["items"]:
        assert "token" not in payload["output"]["items"][0]


@pytest.mark.e2e
@pytest.mark.live
def test_get_token_live(
    require_live: None,
    assert_skill_result_contract: SkillResultAsserter,
    modelscope_storage_state_path: Path | None,
) -> None:
    runtime, runtime_session_id = _build_runtime(
        storage_state_path=_require_storage_state(modelscope_storage_state_path)
    )
    listed = runtime.invoke("modelscope.list_tokens", {}, session_id=runtime_session_id)
    output = listed.output
    assert isinstance(output, dict)
    typed_output = cast(dict[str, Any], output)
    items = typed_output.get("items")
    assert isinstance(items, list)
    if not items:
        pytest.skip("authenticated ModelScope account does not have any access tokens to reveal")

    typed_items = cast(list[dict[str, Any]], items)
    token_id_value = typed_items[0]["token_id"]
    assert isinstance(token_id_value, int)
    token_id = token_id_value
    result = runtime.invoke(
        "modelscope.get_token",
        {"token_id": token_id, "confirm_reveal": True},
        session_id=runtime_session_id,
    )

    payload = result.model_dump()
    assert_skill_result_contract(payload)
    assert payload["requires_human"] is False
    assert isinstance(payload["output"], dict)
    assert payload["output"]["token_id"] == token_id
    assert isinstance(payload["output"]["token"], str)
    assert payload["output"]["token"]


@pytest.mark.e2e
@pytest.mark.live
def test_create_token_live(
    require_live: None,
    assert_skill_result_contract: SkillResultAsserter,
    modelscope_storage_state_path: Path | None,
) -> None:
    if not _is_truthy(os.getenv("WEB2SKILL_RUN_TOKEN_WRITES")):
        pytest.skip("token write coverage disabled; set WEB2SKILL_RUN_TOKEN_WRITES=1 to enable")

    runtime, runtime_session_id = _build_runtime(
        storage_state_path=_require_storage_state(modelscope_storage_state_path)
    )
    token_name = os.getenv(
        "WEB2SKILL_MODELSCOPE_TEST_TOKEN_NAME",
        f"web2skill-live-{uuid.uuid4().hex[:8]}",
    )
    result = runtime.invoke(
        "modelscope.create_token",
        {"name": token_name, "validity": "short_term", "confirm_create": True},
        session_id=runtime_session_id,
    )

    payload = result.model_dump()
    assert_skill_result_contract(payload)
    assert payload["requires_human"] is False
    assert isinstance(payload["output"], dict)
    assert payload["output"]["name"] == token_name
    assert isinstance(payload["output"]["token"], str)
    assert payload["output"]["token"]
