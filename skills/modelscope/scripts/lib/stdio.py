# ruff: noqa: E501

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from .contracts import DoctorResult, SkillResult, StdioRequest, StrategyUsed, TraceEvent
from .login import (
    bootstrap_interactive_login,
    doctor_storage_state,
    import_browser_storage_state,
    resolve_storage_state_path,
)
from .provider import ModelScopeBundle, resolve_storage_state_path_from_request


def run_capability(capability_name: str, handler_name: str) -> None:
    request = _read_request()
    storage_state_path = resolve_storage_state_path_from_request(request.model_dump(mode="python"))
    with ModelScopeBundle(storage_state_path=storage_state_path) as bundle:
        handler = getattr(bundle, handler_name)
        result = handler(request.payload)
    _emit_result(result, request_trace_id=request.trace_id)


def run_login() -> None:
    request = _read_request()
    payload = request.payload
    mode = payload.get("mode", "interactive")
    storage_state_path = payload.get(
        "storage_state_path"
    ) or resolve_storage_state_path_from_request(request.model_dump(mode="python"))
    if mode == "import_browser":
        browser = payload.get("browser", "auto")
        result = import_browser_storage_state(
            browser_name=browser,
            storage_state_path=storage_state_path,
        )
    else:
        result = bootstrap_interactive_login(
            storage_state_path=storage_state_path,
            entry_model_slug=payload.get("entry_model_slug", "Qwen/Qwen2.5-7B-Instruct"),
            timeout_seconds=int(payload.get("timeout_seconds", 300)),
        )
    _emit_result(
        SkillResult(
            trace_id=result.trace_id,
            capability="modelscope.session.login",
            strategy_used=StrategyUsed.GUIDED_UI if mode == "interactive" else StrategyUsed.NETWORK,
            requires_human=not result.authenticated,
            data=result,
            trace=[
                TraceEvent(
                    stage="session_login",
                    detail=result.message,
                    strategy=StrategyUsed.GUIDED_UI
                    if mode == "interactive"
                    else StrategyUsed.NETWORK,
                )
            ],
        ),
        request_trace_id=request.trace_id,
    )


def run_doctor() -> None:
    request = _read_request()
    storage_state_path = request.payload.get(
        "storage_state_path"
    ) or resolve_storage_state_path_from_request(request.model_dump(mode="python"))
    ok, message = doctor_storage_state(storage_state_path)
    resolved_path = str(resolve_storage_state_path(storage_state_path))
    _emit_result(
        SkillResult(
            trace_id=request.trace_id or uuid4().hex,
            capability="modelscope.session.doctor",
            strategy_used=StrategyUsed.NETWORK,
            requires_human=not ok,
            data=DoctorResult(ok=ok, message=message, storage_state_path=resolved_path),
            errors=[] if ok else [message],
            trace=[
                TraceEvent(stage="session_doctor", detail=message, strategy=StrategyUsed.NETWORK)
            ],
        )
    )


def _read_request() -> StdioRequest:
    raw = sys.stdin.read().strip()
    if not raw:
        return StdioRequest()
    payload = json.loads(raw)
    return StdioRequest.model_validate(payload)


def _emit_result(result: SkillResult[Any], *, request_trace_id: str | None = None) -> None:
    if request_trace_id and not result.trace_id or request_trace_id:
        result.trace_id = request_trace_id
    json.dump(result.model_dump(mode="json"), sys.stdout)
    sys.stdout.write("\n")


def emit_fatal_error(capability: str, exc: Exception) -> None:
    trace_id = uuid4().hex
    errors = [exc.json()] if isinstance(exc, ValidationError) else [str(exc)]
    result = SkillResult(
        trace_id=trace_id,
        capability=capability,
        strategy_used=StrategyUsed.NETWORK,
        requires_human=False,
        errors=errors,
        trace=[TraceEvent(stage="fatal_error", detail=errors[0], strategy=StrategyUsed.NETWORK)],
    )
    json.dump(result.model_dump(mode="json"), sys.stdout)
    sys.stdout.write("\n")


def main(capability: str, runner: Callable[[], None]) -> None:
    try:
        runner()
    except Exception as exc:  # pragma: no cover - entrypoint safeguard
        emit_fatal_error(capability, exc)
