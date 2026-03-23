from __future__ import annotations

import pytest

contracts_module = pytest.importorskip(
    "web2skill.core.contracts",
    reason="runtime contracts slice is still in flight",
)
guardrails_module = pytest.importorskip(
    "web2skill.core.guardrails",
    reason="guardrails slice is still in flight",
)


def test_high_risk_automation_requires_confirmation_until_granted() -> None:
    context = contracts_module.ExecutionContext(
        capability_name="modelscope.get_token",
        provider_name="modelscope",
        risk_level=contracts_module.RiskLevel.HIGH,
        allowed_strategies=(contracts_module.Strategy.NETWORK,),
    )
    engine = guardrails_module.GuardrailEngine()

    blocked = engine.select_strategy(context)

    assert blocked.requires_human is True

    confirmed_context = context.model_copy(update={"human_confirmation_granted": True})
    allowed = engine.select_strategy(confirmed_context)

    assert allowed.requires_human is False
