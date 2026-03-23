from __future__ import annotations

from typing import Any

import pytest

contracts_module = pytest.importorskip(
    "web2skill.core.contracts",
    reason="runtime contracts slice is still in flight",
)
runtime_module = pytest.importorskip(
    "web2skill.core.runtime",
    reason="runtime module is still in flight",
)


class _FakeHandler:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response

    def __call__(self, payload: dict[str, Any], session_id: str | None = None) -> dict[str, Any]:
        assert payload["query"] == "qwen"
        assert session_id in {"session-1", None}
        return self.response


class _FakeRegistry:
    def __init__(
        self,
        response: dict[str, Any],
        *,
        risk_level: object | None = None,
        confirmation_field: str | None = None,
    ) -> None:
        self.response = response
        self.risk_level = risk_level or contracts_module.RiskLevel.LOW
        self.confirmation_field = confirmation_field

    def resolve(self, capability_name: str) -> _FakeHandler:
        assert capability_name == "modelscope.search_models"
        return _FakeHandler(self.response)

    def get_descriptor(self, capability_name: str) -> object:
        return contracts_module.CapabilityDescriptor(
            capability_name=capability_name,
            provider_name="modelscope",
            risk_level=self.risk_level,
            supported_strategies=(contracts_module.Strategy.NETWORK,),
            confirmation_field=self.confirmation_field,
        )


class _InMemorySessionStore:
    def get(self, session_id: str) -> dict[str, str]:
        assert session_id == "session-1"
        return {"session_id": session_id}


def test_runtime_returns_structured_skill_result() -> None:
    runtime = runtime_module.SkillRuntime(
        registry=_FakeRegistry(
            {
                "trace_id": "trace-123",
                "strategy_used": "network",
                "requires_human": False,
            }
        ),
        session_store=_InMemorySessionStore(),
    )

    result = runtime.invoke(
        "modelscope.search_models",
        {"query": "qwen"},
        session_id="session-1",
    )

    assert result.trace_id == "trace-123"
    assert result.strategy_used == "network"
    assert result.requires_human is False


def test_runtime_exposes_spec_invoke_signature() -> None:
    invoke = runtime_module.SkillRuntime.invoke
    assert "capability_name" in invoke.__code__.co_varnames
    assert "payload" in invoke.__code__.co_varnames
    assert "session_id" in invoke.__code__.co_varnames


def test_runtime_requires_explicit_confirmation_for_high_risk_capability() -> None:
    runtime = runtime_module.SkillRuntime(
        registry=_FakeRegistry(
            {
                "trace_id": "trace-456",
                "strategy_used": "network",
                "requires_human": False,
            },
            risk_level=contracts_module.RiskLevel.HIGH,
            confirmation_field="confirm_reveal",
        ),
    )

    result = runtime.invoke(
        "modelscope.search_models",
        {"query": "qwen", "confirm_reveal": False},
    )

    assert result.requires_human is True
    assert result.errors[0].code == "confirmation_required"


def test_runtime_allows_high_risk_capability_after_confirmation() -> None:
    runtime = runtime_module.SkillRuntime(
        registry=_FakeRegistry(
            {
                "trace_id": "trace-789",
                "strategy_used": "network",
                "requires_human": False,
                "output": {"token": "ms-123"},
            },
            risk_level=contracts_module.RiskLevel.HIGH,
            confirmation_field="confirm_reveal",
        ),
    )

    result = runtime.invoke(
        "modelscope.search_models",
        {"query": "qwen", "confirm_reveal": True},
    )

    assert result.requires_human is False
    assert result.output == {"token": "ms-123"}
