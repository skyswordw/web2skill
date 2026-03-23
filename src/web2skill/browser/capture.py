from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field

from web2skill.core.contracts import JsonValue, MetadataValue, RuntimeBaseModel, Strategy
from web2skill.core.traces import TraceArtifact, TraceEvent


class NetworkCapture(RuntimeBaseModel):
    url: str = Field(min_length=1)
    method: str = Field(min_length=1, max_length=16)
    status_code: int | None = Field(default=None, ge=100, le=599)
    request_headers: dict[str, str] = Field(default_factory=dict)
    response_headers: dict[str, str] = Field(default_factory=dict)
    request_body: JsonValue | None = None
    response_body: JsonValue | None = None
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_event(self) -> TraceEvent:
        artifact = TraceArtifact(
            kind="network_exchange",
            inline_data={
                "url": self.url,
                "method": self.method,
                "status_code": self.status_code,
                "request_body": self.request_body,
                "response_body": self.response_body,
            },
            content_type="application/json",
        )
        return TraceEvent.create(
            phase="capture.network",
            strategy=Strategy.NETWORK,
            message=f"Captured network exchange for {self.method} {self.url}",
            artifacts=(artifact,),
        )


class DomCapture(RuntimeBaseModel):
    url: str = Field(min_length=1)
    selector: str = Field(min_length=1)
    html: str = Field(min_length=1)
    text: str | None = None
    screenshot_path: Path | None = None
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_event(self) -> TraceEvent:
        artifacts = [
            TraceArtifact(
                kind="dom_snapshot",
                inline_data={"url": self.url, "selector": self.selector, "html": self.html},
                content_type="text/html",
            )
        ]
        if self.text is not None:
            artifacts.append(
                TraceArtifact(
                    kind="dom_text",
                    inline_data=self.text,
                    content_type="text/plain",
                )
            )
        if self.screenshot_path is not None:
            artifacts.append(
                TraceArtifact(
                    kind="screenshot",
                    path=self.screenshot_path,
                    content_type="image/png",
                )
            )
        return TraceEvent.create(
            phase="capture.dom",
            strategy=Strategy.DOM,
            message=f"Captured DOM snapshot for selector {self.selector}",
            artifacts=tuple(artifacts),
        )


class GuidedStep(RuntimeBaseModel):
    action: str = Field(min_length=1, max_length=64)
    target: str = Field(min_length=1)
    value: str | None = None
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_event(self) -> TraceEvent:
        return TraceEvent.create(
            phase="capture.guided_ui",
            strategy=Strategy.GUIDED_UI,
            message=f"Recorded guided step {self.action} on {self.target}",
            metadata={"target": self.target, **self.metadata},
        )


class BrowserCaptureBundle(RuntimeBaseModel):
    network: tuple[NetworkCapture, ...] = ()
    dom: tuple[DomCapture, ...] = ()
    guided_steps: tuple[GuidedStep, ...] = ()

    def to_trace_events(self) -> tuple[TraceEvent, ...]:
        events: list[TraceEvent] = []
        events.extend(item.to_event() for item in self.network)
        events.extend(item.to_event() for item in self.dom)
        events.extend(item.to_event() for item in self.guided_steps)
        return tuple(events)


class BrowserCaptureRecorder:
    def __init__(self) -> None:
        self._network: list[NetworkCapture] = []
        self._dom: list[DomCapture] = []
        self._guided_steps: list[GuidedStep] = []

    def record_network(self, capture: NetworkCapture) -> None:
        self._network.append(capture)

    def record_dom(self, capture: DomCapture) -> None:
        self._dom.append(capture)

    def record_guided_step(self, step: GuidedStep) -> None:
        self._guided_steps.append(step)

    def build(self) -> BrowserCaptureBundle:
        return BrowserCaptureBundle(
            network=tuple(self._network),
            dom=tuple(self._dom),
            guided_steps=tuple(self._guided_steps),
        )
