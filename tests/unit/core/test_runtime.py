from __future__ import annotations

from typing import Any

import pytest

runtime_module = pytest.importorskip(
    "web2skill.core.runtime",
    reason="runtime module is still in flight",
)


class _FakeHandler:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response

    def __call__(self, payload: dict[str, Any], session_id: str | None = None) -> dict[str, Any]:
        assert payload == {"query": "qwen"}
        assert session_id == "session-1"
        return self.response


class _FakeRegistry:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response

    def resolve(self, capability_name: str) -> _FakeHandler:
        assert capability_name == "modelscope.search_models"
        return _FakeHandler(self.response)


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
