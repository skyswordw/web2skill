from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

cli_module = pytest.importorskip(
    "web2skill.cli",
    reason="CLI slice is still in flight",
)

runner = CliRunner()
SkillResultAsserter = Callable[[dict[str, Any]], None]


@pytest.mark.integration
def test_skills_list_outputs_capabilities_json() -> None:
    result = runner.invoke(cli_module.app, ["skills", "list", "--json"])

    if result.exit_code != 0:
        pytest.xfail("skills list JSON command has not been wired yet")

    parsed = json.loads(result.stdout)
    capability_names = {item["name"] for item in parsed["capabilities"]}
    assert "modelscope.search_models" in capability_names
    assert "modelscope.get_account_profile" in capability_names


@pytest.mark.integration
def test_invoke_json_envelope_contains_core_contract(
    assert_skill_result_contract: SkillResultAsserter,
) -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "invoke",
            "modelscope.search_models",
            "--input",
            '{"query":"qwen"}',
            "--json",
        ],
    )

    if result.exit_code != 0:
        pytest.xfail("invoke JSON envelope is not available yet")

    payload = json.loads(result.stdout)
    assert_skill_result_contract(payload)


@pytest.mark.integration
def test_invoke_list_tokens_returns_metadata_only_json(
    assert_skill_result_contract: SkillResultAsserter,
) -> None:
    app = _build_token_cli_app()

    result = runner.invoke(
        app,
        [
            "invoke",
            "modelscope.list_tokens",
            "--input",
            "{}",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert_skill_result_contract(payload)
    assert payload["requires_human"] is False
    assert payload["output"]["items"][0]["token_id"] == 3245671
    assert "token" not in payload["output"]["items"][0]


@pytest.mark.integration
def test_invoke_get_token_requires_confirmation_json(
    assert_skill_result_contract: SkillResultAsserter,
) -> None:
    app = _build_token_cli_app()

    result = runner.invoke(
        app,
        [
            "invoke",
            "modelscope.get_token",
            "--input",
            '{"token_id":3245671,"confirm_reveal":false}',
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert_skill_result_contract(payload)
    assert payload["requires_human"] is True
    assert payload["output"] is None
    assert "confirmation" in payload["errors"][0]["message"].lower()


@pytest.mark.integration
def test_invoke_get_token_returns_raw_token_after_confirmation_json(
    assert_skill_result_contract: SkillResultAsserter,
) -> None:
    app = _build_token_cli_app()

    result = runner.invoke(
        app,
        [
            "invoke",
            "modelscope.get_token",
            "--input",
            '{"token_id":3245671,"confirm_reveal":true}',
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert_skill_result_contract(payload)
    assert payload["requires_human"] is False
    assert payload["output"]["token_id"] == 3245671
    assert payload["output"]["name"] == "default"
    assert payload["output"]["token"] == "ms-cde0e8be-4f10-42d0-834f-6d93352b91b3"


@pytest.mark.integration
def test_invoke_create_token_requires_confirmation_json(
    assert_skill_result_contract: SkillResultAsserter,
) -> None:
    app = _build_token_cli_app()

    result = runner.invoke(
        app,
        [
            "invoke",
            "modelscope.create_token",
            "--input",
            '{"name":"ci-dev","validity":"permanent","confirm_create":false}',
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert_skill_result_contract(payload)
    assert payload["requires_human"] is True
    assert payload["output"] is None
    assert "confirmation" in payload["errors"][0]["message"].lower()


@pytest.mark.integration
def test_invoke_create_token_returns_raw_token_after_confirmation_json(
    assert_skill_result_contract: SkillResultAsserter,
) -> None:
    app = _build_token_cli_app()

    result = runner.invoke(
        app,
        [
            "invoke",
            "modelscope.create_token",
            "--input",
            '{"name":"ci-dev","validity":"permanent","confirm_create":true}',
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert_skill_result_contract(payload)
    assert payload["requires_human"] is False
    assert payload["output"]["token_id"] == 3245672
    assert payload["output"]["name"] == "ci-dev"
    assert payload["output"]["token"] == "ms-created-ci-dev"


def _build_token_cli_app() -> Any:
    runtime_module = pytest.importorskip(
        "web2skill.core.runtime",
        reason="runtime module is still in flight",
    )
    sessions_module = pytest.importorskip(
        "web2skill.core.sessions",
        reason="sessions module is still in flight",
    )
    provider_module = pytest.importorskip(
        "web2skill.providers.modelscope.provider",
        reason="ModelScope provider slice is still in flight",
    )
    transport = httpx.MockTransport(_token_handler_factory())
    runtime = runtime_module.SkillRuntime(
        registry=provider_module.ModelScopeRegistry(
            session_store=sessions_module.InMemorySessionStore(),
            transport=transport,
        )
    )
    return cli_module.build_app(runtime=runtime)


def _token_handler_factory() -> Any:
    created_name: str | None = None

    def _token_handler(request: httpx.Request) -> httpx.Response:
        nonlocal created_name
        if request.url.path == "/api/v1/users/tokens/list":
            payload = _token_list_payload(created_name=created_name)
            return httpx.Response(200, json=payload)
        if request.url.path == "/api/v1/users/tokens":
            assert request.method == "POST"
            payload = json.loads(request.content.decode("utf-8"))
            if payload == {"TokenName": "ci-dev", "ExpireMonths": 1200}:
                created_name = "ci-dev"
            else:
                msg = f"Unexpected token create payload: {payload!r}"
                raise AssertionError(msg)
            return httpx.Response(
                200,
                json={
                    "Code": 200,
                    "Data": {"Id": 3245672},
                    "Message": "success",
                    "Success": True,
                },
            )
        msg = f"Unexpected request: {request.method} {request.url}"
        raise AssertionError(msg)

    return _token_handler


def _token_list_payload(*, created_name: str | None = None) -> dict[str, Any]:
    tokens: list[dict[str, Any]] = [
        {
            "ExpiresAt": "2026-04-22T03:23:21Z",
            "GmtCreated": "2026-03-23T03:23:22Z",
            "Id": 3245671,
            "SdkToken": "ms-cde0e8be-4f10-42d0-834f-6d93352b91b3",
            "SdkTokenName": "default",
            "Valid": "1",
        }
    ]
    if created_name is not None:
        tokens.append(
            {
                "ExpiresAt": "2027-03-23T03:23:21Z",
                "GmtCreated": "2026-03-23T04:23:22Z",
                "Id": 3245672,
                "SdkToken": f"ms-created-{created_name}",
                "SdkTokenName": created_name,
                "Valid": "1",
            }
        )
    return {
        "Code": 200,
        "Data": {
            "SdkTokens": tokens,
            "TotalCount": len(tokens),
        },
        "Success": True,
    }
