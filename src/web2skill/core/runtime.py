from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from web2skill.core.contracts import (
    CapabilityDescriptor,
    ExecutionContext,
    GuardrailWarning,
    InvocationRequest,
    SkillError,
    SkillResult,
    Strategy,
    validate_structured_payload,
)
from web2skill.core.guardrails import GuardrailEngine
from web2skill.core.sessions import InMemorySessionStore, SessionStore
from web2skill.core.traces import (
    InMemoryTraceStore,
    InvocationTrace,
    ReplayStore,
    TraceEvent,
    TraceStore,
)


class CapabilityHandler(Protocol):
    def execute(self, context: ExecutionContext) -> SkillResult: ...


class CapabilityRegistry(Protocol):
    def get_descriptor(self, capability_name: str) -> CapabilityDescriptor: ...

    def get_handler(self, capability_name: str) -> CapabilityHandler: ...


class RuntimeDispatchError(RuntimeError):
    pass


class SkillRuntime:
    def __init__(
        self,
        *,
        registry: CapabilityRegistry,
        session_store: SessionStore | None = None,
        trace_store: TraceStore | None = None,
        guardrails: GuardrailEngine | None = None,
    ) -> None:
        self.registry = registry
        self.session_store = session_store or InMemorySessionStore()
        self.trace_store = trace_store or InMemoryTraceStore()
        self.guardrails = guardrails or GuardrailEngine()
        self.replay_store = ReplayStore(trace_store=self.trace_store)

    def invoke(
        self,
        capability_name: str,
        payload: dict[str, object] | BaseModel,
        session_id: str | None = None,
        *,
        preferred_strategy: Strategy | None = None,
        trace_id: str | None = None,
    ) -> SkillResult:
        raw_payload = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
        normalized_payload = validate_structured_payload(raw_payload)

        request = InvocationRequest(
            capability_name=capability_name,
            payload=normalized_payload,
            session_id=session_id,
            preferred_strategy=preferred_strategy,
            trace_id=trace_id,
        )

        descriptor = self.registry.get_descriptor(request.capability_name)
        handler = self.registry.get_handler(request.capability_name)
        validated_payload = descriptor.validate_payload(request.payload)
        if request.trace_id is None:
            context = ExecutionContext(
                capability_name=descriptor.capability_name,
                provider_name=descriptor.provider_name,
                payload=validated_payload,
                session_id=request.session_id,
                risk_level=descriptor.risk_level,
                allowed_strategies=descriptor.supported_strategies,
                preferred_strategy=request.preferred_strategy,
            )
        else:
            context = ExecutionContext(
                trace_id=request.trace_id,
                capability_name=descriptor.capability_name,
                provider_name=descriptor.provider_name,
                payload=validated_payload,
                session_id=request.session_id,
                risk_level=descriptor.risk_level,
                allowed_strategies=descriptor.supported_strategies,
                preferred_strategy=request.preferred_strategy,
            )

        decision = self.guardrails.select_strategy(context)
        if descriptor.requires_session and self.session_store.get(context.session_id or "") is None:
            error = self.guardrails.require_session(context)
            assert error is not None
            return self._finalize_failure(context, decision.strategy, error, decision.warnings)

        if decision.requires_human:
            result = SkillResult.human_required(
                context=context,
                strategy=decision.strategy,
                warning=decision.warnings[0],
            ).model_copy(update={"warnings": decision.warnings})
            self._record_trace(context, result, decision.strategy, phase="guardrails.blocked")
            return result

        result = handler.execute(context)
        if result.trace_id != context.trace_id:
            result = result.model_copy(update={"trace_id": context.trace_id})
        if result.strategy_used not in context.allowed_strategies:
            msg = f"Handler returned unsupported strategy {result.strategy_used!s}."
            raise RuntimeDispatchError(msg)

        warnings = tuple((*decision.warnings, *result.warnings))
        if warnings != result.warnings:
            result = result.model_copy(update={"warnings": warnings})

        self._record_trace(context, result, result.strategy_used, phase="invoke.completed")
        return result

    def replay(self, trace_id: str) -> SkillResult:
        return self.replay_store.replay(trace_id)

    def _finalize_failure(
        self,
        context: ExecutionContext,
        strategy: Strategy,
        error: SkillError,
        warnings: tuple[GuardrailWarning, ...],
    ) -> SkillResult:
        result = SkillResult.failure(
            context=context,
            strategy=strategy,
            error=error,
            warnings=warnings,
        )
        self._record_trace(context, result, strategy, phase="guardrails.failed")
        return result

    def _record_trace(
        self,
        context: ExecutionContext,
        result: SkillResult,
        strategy: Strategy,
        *,
        phase: str,
    ) -> InvocationTrace:
        event = TraceEvent.create(
            phase=phase,
            strategy=strategy,
            message="Skill runtime invocation finalized.",
            metadata={"requires_human": result.requires_human},
        )
        trace = InvocationTrace.from_result(
            context=context,
            result=result,
            strategy=strategy,
            events=(event,),
        )
        return self.trace_store.put(trace)
