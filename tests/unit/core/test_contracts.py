from __future__ import annotations

import pytest
from pydantic import ValidationError

contracts = pytest.importorskip(
    "web2skill.core.contracts",
    reason="runtime contracts are still in flight",
)


def test_skill_result_requires_trace_strategy_and_human_flag() -> None:
    with pytest.raises(ValidationError):
        contracts.SkillResult.model_validate({})


def test_skill_result_accepts_minimal_spec_contract() -> None:
    result = contracts.SkillResult.model_validate(
        {
            "trace_id": "trace-123",
            "strategy_used": "network",
            "requires_human": False,
        }
    )

    assert result.trace_id == "trace-123"
    assert result.strategy_used == "network"
    assert result.requires_human is False


def test_runtime_payload_models_are_pydantic_validated() -> None:
    assert hasattr(contracts, "SkillRequest")
    assert hasattr(contracts, "SkillResult")
