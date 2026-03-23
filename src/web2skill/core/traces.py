from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import Field

from web2skill.core.contracts import (
    ExecutionContext,
    JsonValue,
    MetadataValue,
    RuntimeBaseModel,
    SkillResult,
    Strategy,
)


def default_trace_root() -> Path:
    return Path.home() / ".web2skill" / "traces"


class TraceArtifact(RuntimeBaseModel):
    kind: str = Field(min_length=1, max_length=64)
    path: Path | None = None
    inline_data: JsonValue | None = None
    content_type: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)


class TraceEvent(RuntimeBaseModel):
    timestamp: datetime
    phase: str = Field(min_length=1, max_length=64)
    strategy: Strategy
    message: str = Field(min_length=1)
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)
    artifacts: tuple[TraceArtifact, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        phase: str,
        strategy: Strategy,
        message: str,
        metadata: dict[str, MetadataValue] | None = None,
        artifacts: tuple[TraceArtifact, ...] = (),
    ) -> TraceEvent:
        return cls(
            timestamp=datetime.now(UTC),
            phase=phase,
            strategy=strategy,
            message=message,
            metadata=metadata or {},
            artifacts=artifacts,
        )


class InvocationTrace(RuntimeBaseModel):
    trace_id: str
    capability_name: str
    provider_name: str
    session_id: str | None = None
    request_payload: dict[str, JsonValue] = Field(default_factory=dict)
    strategy_used: Strategy
    risk_level: str
    created_at: datetime
    completed_at: datetime
    result: SkillResult
    events: tuple[TraceEvent, ...] = ()
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)

    @classmethod
    def from_result(
        cls,
        *,
        context: ExecutionContext,
        result: SkillResult,
        strategy: Strategy,
        events: tuple[TraceEvent, ...] = (),
        metadata: dict[str, MetadataValue] | None = None,
    ) -> InvocationTrace:
        completed_at = datetime.now(UTC)
        return cls(
            trace_id=context.trace_id,
            capability_name=context.capability_name,
            provider_name=context.provider_name,
            session_id=context.session_id,
            request_payload=context.payload,
            strategy_used=strategy,
            risk_level=context.risk_level.value,
            created_at=context.started_at,
            completed_at=completed_at,
            result=result.model_copy(update={"completed_at": completed_at}),
            events=events,
            metadata=metadata or context.metadata,
        )


class TraceStore(Protocol):
    def get(self, trace_id: str) -> InvocationTrace | None: ...

    def put(self, trace: InvocationTrace) -> InvocationTrace: ...

    def list(self, capability_name: str | None = None) -> list[InvocationTrace]: ...


class InMemoryTraceStore:
    def __init__(self) -> None:
        self._traces: dict[str, InvocationTrace] = {}

    def get(self, trace_id: str) -> InvocationTrace | None:
        return self._traces.get(trace_id)

    def put(self, trace: InvocationTrace) -> InvocationTrace:
        self._traces[trace.trace_id] = trace
        return trace

    def list(self, capability_name: str | None = None) -> list[InvocationTrace]:
        traces = list(self._traces.values())
        if capability_name is None:
            return sorted(traces, key=lambda item: item.completed_at, reverse=True)
        return sorted(
            (item for item in traces if item.capability_name == capability_name),
            key=lambda item: item.completed_at,
            reverse=True,
        )


class FileTraceStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or default_trace_root()
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, trace_id: str) -> InvocationTrace | None:
        path = self.root / f"{trace_id}.json"
        if not path.exists():
            return None
        return InvocationTrace.model_validate_json(path.read_text())

    def put(self, trace: InvocationTrace) -> InvocationTrace:
        path = self.root / f"{trace.trace_id}.json"
        path.write_text(trace.model_dump_json(indent=2))
        return trace

    def list(self, capability_name: str | None = None) -> list[InvocationTrace]:
        traces: list[InvocationTrace] = []
        for path in sorted(self.root.glob("*.json")):
            trace = InvocationTrace.model_validate_json(path.read_text())
            if capability_name is None or trace.capability_name == capability_name:
                traces.append(trace)
        return sorted(traces, key=lambda item: item.completed_at, reverse=True)


class ReplayStore(RuntimeBaseModel):
    trace_store: TraceStore

    def replay(self, trace_id: str) -> SkillResult:
        trace = self.trace_store.get(trace_id)
        if trace is None:
            msg = f"Unknown trace_id: {trace_id}"
            raise KeyError(msg)
        return trace.result.model_copy(update={"strategy_used": Strategy.REPLAY})
