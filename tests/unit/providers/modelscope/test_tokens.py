from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from typing import Any

import httpx
import pytest

parsers = pytest.importorskip(
    "web2skill.providers.modelscope.parsers",
    reason="ModelScope provider slice is still in flight",
)
provider_module = pytest.importorskip(
    "web2skill.providers.modelscope.provider",
    reason="ModelScope provider slice is still in flight",
)

FixtureLoader = Callable[[str], dict[str, Any]]


def test_token_list_normalizer_returns_metadata_only(load_fixture: FixtureLoader) -> None:
    payload = load_fixture("modelscope/token_list.json")

    result = parsers.normalize_token_list(payload)

    assert result.total_count == 1
    assert result.items[0].token_id == 3245671
    assert result.items[0].name == "default"
    assert "token" not in result.items[0].model_dump()


def test_get_token_requires_explicit_confirmation(load_fixture: FixtureLoader) -> None:
    provider = provider_module.ModelScopeProvider(
        transport=_mock_transport(load_fixture("modelscope/token_list.json"))
    )

    result = provider.get_token({"token_id": 3245671, "confirm_reveal": False})

    assert result.requires_human is True
    assert "confirmation" in result.errors[0].lower()
    assert result.data is None


def test_get_token_returns_raw_token_after_confirmation(load_fixture: FixtureLoader) -> None:
    provider = provider_module.ModelScopeProvider(
        transport=_mock_transport(load_fixture("modelscope/token_list.json"))
    )

    result = provider.get_token({"token_id": 3245671, "confirm_reveal": True})

    assert result.requires_human is False
    assert result.data is not None
    assert result.data.token == "ms-cde0e8be-4f10-42d0-834f-6d93352b91b3"


def test_create_token_requires_explicit_confirmation(load_fixture: FixtureLoader) -> None:
    provider = provider_module.ModelScopeProvider(
        transport=_mock_transport(load_fixture("modelscope/token_list.json"))
    )

    result = provider.create_token(
        {"name": "ci-dev", "validity": "permanent", "confirm_create": False}
    )

    assert result.requires_human is True
    assert "confirmation" in result.errors[0].lower()
    assert result.data is None


def test_create_token_returns_raw_token_after_confirmation(load_fixture: FixtureLoader) -> None:
    before_payload = load_fixture("modelscope/token_list.json")
    after_payload = _created_token_payload(before_payload, name="ci-dev")
    provider = provider_module.ModelScopeProvider(
        transport=_mock_create_transport(
            before_payload=before_payload,
            after_payload=after_payload,
            expected_post_data={"TokenName": "ci-dev", "ExpireMonths": 1200},
        )
    )

    result = provider.create_token(
        {"name": "ci-dev", "validity": "permanent", "confirm_create": True}
    )

    assert result.requires_human is False
    assert result.data is not None
    assert result.data.token_id == 3245672
    assert result.data.name == "ci-dev"
    assert result.data.token == "ms-created-ci-dev"


def test_create_token_short_term_omits_expire_months(load_fixture: FixtureLoader) -> None:
    before_payload = load_fixture("modelscope/token_list.json")
    after_payload = _created_token_payload(before_payload, name="ci-short")
    provider = provider_module.ModelScopeProvider(
        transport=_mock_create_transport(
            before_payload=before_payload,
            after_payload=after_payload,
            expected_post_data={"TokenName": "ci-short"},
        )
    )

    result = provider.create_token(
        {"name": "ci-short", "validity": "short_term", "confirm_create": True}
    )

    assert result.requires_human is False
    assert result.data is not None
    assert result.data.name == "ci-short"
    assert result.data.token == "ms-created-ci-short"


def _mock_transport(payload: dict[str, Any]) -> httpx.MockTransport:
    def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/users/tokens/list":
            return httpx.Response(200, json=payload)
        msg = f"Unexpected request: {request.method} {request.url}"
        raise AssertionError(msg)

    return httpx.MockTransport(_handler)


def _mock_create_transport(
    *,
    before_payload: dict[str, Any],
    after_payload: dict[str, Any],
    expected_post_data: dict[str, Any],
) -> httpx.MockTransport:
    created = False

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal created
        if request.url.path == "/api/v1/users/tokens/list":
            payload = after_payload if created else before_payload
            return httpx.Response(200, json=payload)
        if request.url.path == "/api/v1/users/tokens":
            assert request.method == "POST"
            assert json.loads(request.content.decode("utf-8")) == expected_post_data
            created = True
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

    return httpx.MockTransport(_handler)


def _created_token_payload(payload: dict[str, Any], *, name: str) -> dict[str, Any]:
    updated = deepcopy(payload)
    tokens = updated["Data"]["SdkTokens"]
    tokens.append(
        {
            "ExpiresAt": "2027-03-23T03:23:21Z",
            "GmtCreated": "2026-03-23T04:23:22Z",
            "GmtModified": "2026-03-23T04:23:22Z",
            "Id": 3245672,
            "Scope": "Scope",
            "SdkToken": f"ms-created-{name}",
            "SdkTokenName": name,
            "Username": "skuwok",
            "Valid": "1",
        }
    )
    updated["Data"]["TotalCount"] = len(tokens)
    return updated
