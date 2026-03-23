from __future__ import annotations

from pydantic import Field

from web2skill.core.contracts import (
    ExecutionContext,
    GuardrailWarning,
    RiskLevel,
    RuntimeBaseModel,
    SkillError,
    Strategy,
)


class GuardrailDecision(RuntimeBaseModel):
    strategy: Strategy
    requires_human: bool = False
    warnings: tuple[GuardrailWarning, ...] = ()


class GuardrailEngine(RuntimeBaseModel):
    interactive_risk_threshold: RiskLevel = RiskLevel.MEDIUM
    allow_guided_ui_without_session: bool = False
    allow_high_risk_automation: bool = False
    guided_ui_warning_code: str = Field(default="guided_ui_requires_human")

    def select_strategy(self, context: ExecutionContext) -> GuardrailDecision:
        allowed = context.allowed_strategies
        if not allowed:
            msg = "ExecutionContext.allowed_strategies must not be empty."
            raise ValueError(msg)
        requested = context.preferred_strategy
        strategy: Strategy = allowed[0]
        if requested is not None and requested in allowed:
            strategy = requested
        warnings: list[GuardrailWarning] = []
        requires_human = context.requires_human_confirmation

        if strategy is Strategy.GUIDED_UI:
            if not self.allow_guided_ui_without_session and context.session_id is None:
                requires_human = True
                warnings.append(
                    GuardrailWarning(
                        code=self.guided_ui_warning_code,
                        message=(
                            "Guided UI fallback requires a reusable session "
                            "or a human login step."
                        ),
                    )
                )
            if self._risk_meets_threshold(context.risk_level, self.interactive_risk_threshold):
                requires_human = True
                warnings.append(
                    GuardrailWarning(
                        code="guided_ui_high_risk",
                        message="Guided UI fallback is gated for medium/high-risk capabilities.",
                    )
                )

        if context.risk_level is RiskLevel.HIGH and not self.allow_high_risk_automation:
            requires_human = True
            warnings.append(
                GuardrailWarning(
                    code="high_risk_requires_human",
                    message="High-risk capabilities require human confirmation.",
                )
            )

        return GuardrailDecision(
            strategy=strategy,
            requires_human=requires_human,
            warnings=tuple(warnings),
        )

    def require_session(self, context: ExecutionContext) -> SkillError | None:
        if context.session_id is not None:
            return None
        return SkillError(
            code="session_required",
            message="This capability requires a previously established session.",
            retriable=True,
        )

    @staticmethod
    def _risk_meets_threshold(risk: RiskLevel, threshold: RiskLevel) -> bool:
        order = {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
        }
        return order[risk] >= order[threshold]
