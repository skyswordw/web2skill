from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from pydantic import JsonValue as PydanticJsonValue


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_trace_id() -> str:
    return uuid4().hex


JsonPrimitive = str | int | float | bool | None
JsonValue = PydanticJsonValue
StructuredPayload = dict[str, JsonValue]
MetadataValue = JsonPrimitive | list[JsonPrimitive] | dict[str, JsonPrimitive]

TraceId = Annotated[str, Field(min_length=8, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")]
CapabilityName = Annotated[
    str,
    Field(min_length=3, pattern=r"^[a-z0-9]+(?:[._][a-z0-9]+)+$"),
]
SessionId = Annotated[str, Field(min_length=1, max_length=128)]


class Strategy(StrEnum):
    NETWORK = "network"
    DOM = "dom"
    GUIDED_UI = "guided_ui"
    REPLAY = "replay"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RuntimeBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)


STRUCTURED_PAYLOAD_ADAPTER = TypeAdapter(StructuredPayload)


class SkillError(RuntimeBaseModel):
    code: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1)
    retriable: bool = False
    details: dict[str, MetadataValue] = Field(default_factory=dict)


class GuardrailWarning(RuntimeBaseModel):
    code: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1)


class ExecutionContext(RuntimeBaseModel):
    trace_id: TraceId = Field(default_factory=new_trace_id)
    capability_name: CapabilityName
    provider_name: Annotated[str, Field(min_length=1, max_length=64)]
    payload: StructuredPayload = Field(default_factory=dict)
    session_id: SessionId | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    allowed_strategies: tuple[Strategy, ...] = (Strategy.NETWORK, Strategy.DOM, Strategy.GUIDED_UI)
    preferred_strategy: Strategy | None = None
    requires_human_confirmation: bool = False
    human_confirmation_granted: bool = False
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=utc_now)


class SkillResult(RuntimeBaseModel):
    trace_id: TraceId
    capability_name: CapabilityName | None = None
    strategy_used: Strategy
    requires_human: bool
    output: JsonValue | None = None
    errors: tuple[SkillError, ...] = ()
    warnings: tuple[GuardrailWarning, ...] = ()
    session_id: SessionId | None = None
    completed_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @classmethod
    def human_required(
        cls,
        *,
        context: ExecutionContext,
        strategy: Strategy,
        warning: GuardrailWarning,
    ) -> SkillResult:
        return cls(
            trace_id=context.trace_id,
            capability_name=context.capability_name,
            strategy_used=strategy,
            requires_human=True,
            session_id=context.session_id,
            warnings=(warning,),
            metadata=context.metadata,
        )

    @classmethod
    def failure(
        cls,
        *,
        context: ExecutionContext,
        strategy: Strategy,
        error: SkillError,
        warnings: tuple[GuardrailWarning, ...] = (),
    ) -> SkillResult:
        return cls(
            trace_id=context.trace_id,
            capability_name=context.capability_name,
            strategy_used=strategy,
            requires_human=False,
            session_id=context.session_id,
            errors=(error,),
            warnings=warnings,
            metadata=context.metadata,
        )


class InvocationRequest(RuntimeBaseModel):
    capability_name: CapabilityName
    payload: StructuredPayload = Field(default_factory=dict)
    session_id: SessionId | None = None
    preferred_strategy: Strategy | None = None
    trace_id: TraceId | None = None


class ReplayRequest(RuntimeBaseModel):
    trace_id: TraceId


class CapabilityDescriptor(RuntimeBaseModel):
    capability_name: CapabilityName
    provider_name: Annotated[str, Field(min_length=1, max_length=64)]
    risk_level: RiskLevel = RiskLevel.LOW
    supported_strategies: tuple[Strategy, ...] = (Strategy.NETWORK, Strategy.DOM)
    requires_session: bool = False
    confirmation_field: str | None = None
    input_model: type[BaseModel] | None = None

    def validate_payload(self, payload: StructuredPayload) -> StructuredPayload:
        if self.input_model is None:
            return payload
        validated = self.input_model.model_validate(payload)
        normalized = validated.model_dump(mode="json")
        return STRUCTURED_PAYLOAD_ADAPTER.validate_python(normalized)


def validate_structured_payload(payload: object) -> StructuredPayload:
    return STRUCTURED_PAYLOAD_ADAPTER.validate_python(payload)


SkillRequest = InvocationRequest
