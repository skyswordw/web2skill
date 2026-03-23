from __future__ import annotations

import json
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from web2skill.core.contracts import (
    CapabilityDescriptor,
    ExecutionContext,
    GuardrailWarning,
    RiskLevel,
    SkillError,
    SkillResult,
    Strategy,
)
from web2skill.core.runtime import CapabilityHandler
from web2skill.core.script_runner import (
    ScriptInvocationError,
    ScriptInvocationResponse,
    ScriptRunner,
)
from web2skill.core.sessions import SessionRecord, SessionStore

from .registry import LoadedSkill, SkillRegistry


class BundleEnvironmentError(RuntimeError):
    pass


class BundleCapabilityHandler:
    def __init__(
        self,
        *,
        loaded_skill: LoadedSkill,
        capability_name: str,
        script_path: Path,
        session_store: SessionStore,
        runner: ScriptRunner | None = None,
    ) -> None:
        self._loaded_skill = loaded_skill
        self._capability_name = capability_name
        self._script_path = script_path
        self._session_store = session_store
        self._runner = runner or ScriptRunner()

    def execute(self, context: ExecutionContext) -> SkillResult:
        session = self._resolve_session(context.session_id)
        try:
            response = self._runner.invoke(
                script_path=self._script_path,
                python_executable=_resolve_python_executable(self._loaded_skill),
                request={
                    "action": "invoke",
                    "bundle_id": self._loaded_skill.manifest.bundle_id,
                    "capability_name": self._capability_name,
                    "payload": context.payload,
                    "session_id": context.session_id,
                    "session": _session_payload(session),
                    "trace_id": context.trace_id,
                },
                cwd=self._loaded_skill.bundle_root,
                extra_env={"WEB2SKILL_BUNDLE_ROOT": str(self._loaded_skill.bundle_root)},
                python_path=(self._loaded_skill.bundle_root / "scripts",),
            )
        except (ScriptInvocationError, BundleEnvironmentError) as exc:
            return SkillResult.failure(
                context=context,
                strategy=context.allowed_strategies[0],
                error=SkillError(
                    code="bundle_invocation_failed",
                    message=str(exc),
                    retriable=True,
                ),
            )
        return _skill_result_from_script_response(
            loaded_skill=self._loaded_skill,
            context=context,
            response=response,
        )

    def _resolve_session(self, session_id: str | None) -> SessionRecord | None:
        if session_id is None:
            return None
        return self._session_store.get(session_id)


class BundleCapabilityRegistry:
    def __init__(
        self,
        *,
        skill_registry: SkillRegistry,
        session_store: SessionStore,
        runner: ScriptRunner | None = None,
    ) -> None:
        self._skill_registry = skill_registry
        self._session_store = session_store
        self._runner = runner or ScriptRunner()

    def resolve(self, capability_name: str) -> CapabilityHandler:
        return self.get_handler(capability_name)

    def get_handler(self, capability_name: str) -> CapabilityHandler:
        loaded_skill, capability = self._skill_registry.get_capability(capability_name)
        if capability.entry_script is None:
            msg = f"capability '{capability_name}' is missing entry_script metadata"
            raise LookupError(msg)
        return BundleCapabilityHandler(
            loaded_skill=loaded_skill,
            capability_name=capability_name,
            script_path=loaded_skill.bundle_root / capability.entry_script,
            session_store=self._session_store,
            runner=self._runner,
        )

    def get_descriptor(self, capability_name: str) -> CapabilityDescriptor:
        loaded_skill, capability = self._skill_registry.get_capability(capability_name)
        return CapabilityDescriptor(
            capability_name=capability.name,
            provider_name=loaded_skill.manifest.provider,
            risk_level=RiskLevel(capability.risk),
            supported_strategies=tuple(Strategy(item) for item in capability.strategies),
            requires_session=capability.session_required,
            confirmation_field=capability.confirmation_field,
        )


class BundleSessionService:
    def __init__(
        self,
        *,
        skill_registry: SkillRegistry,
        session_store: SessionStore,
        runner: ScriptRunner | None = None,
    ) -> None:
        self._skill_registry = skill_registry
        self._session_store = session_store
        self._runner = runner or ScriptRunner()

    def login(
        self,
        provider: str,
        *,
        mode: str = "interactive",
        browser: str = "auto",
    ) -> dict[str, Any]:
        loaded_skill = self._skill_registry.get_provider(provider)
        login_script = loaded_skill.manifest.session_hooks.login_script
        if login_script is None:
            msg = f"provider '{provider}' does not define a login session hook"
            raise LookupError(msg)
        response = self._invoke_hook(
            loaded_skill=loaded_skill,
            script_path=loaded_skill.bundle_root / login_script,
            action="login",
            payload={
                "mode": mode.replace("-", "_"),
                "browser": browser,
            },
        )
        data = _response_payload(response)
        if bool(data.get("authenticated")):
            session = SessionRecord.create(
                session_id=f"{provider}-{uuid.uuid4().hex[:12]}",
                provider_name=provider,
                storage_state_path=_maybe_path(data.get("storage_state_path")),
                base_url=(
                    str(loaded_skill.manifest.base_url)
                    if loaded_skill.manifest.base_url
                    else None
                ),
                metadata={"bundle_id": loaded_skill.manifest.bundle_id},
            )
            stored = self._session_store.put(session)
            data["session_id"] = stored.session_id
        data.setdefault("trace_id", response.trace_id or uuid.uuid4().hex)
        data.setdefault("provider", provider)
        return data

    def doctor(self, provider: str) -> dict[str, Any]:
        loaded_skill = self._skill_registry.get_provider(provider)
        doctor_script = loaded_skill.manifest.session_hooks.doctor_script
        if doctor_script is None:
            msg = f"provider '{provider}' does not define a doctor session hook"
            raise LookupError(msg)
        latest = self._latest_session(provider)
        response = self._invoke_hook(
            loaded_skill=loaded_skill,
            script_path=loaded_skill.bundle_root / doctor_script,
            action="doctor",
            payload={},
            session=latest,
        )
        data = _response_payload(response)
        data.setdefault("provider", provider)
        data.setdefault("session_id", latest.session_id if latest else None)
        return data

    def _invoke_hook(
        self,
        *,
        loaded_skill: LoadedSkill,
        script_path: Path,
        action: str,
        payload: dict[str, Any],
        session: SessionRecord | None = None,
    ) -> ScriptInvocationResponse:
        try:
            return self._runner.invoke(
                script_path=script_path,
                python_executable=_resolve_python_executable(loaded_skill),
                request={
                    "action": action,
                    "bundle_id": loaded_skill.manifest.bundle_id,
                    "provider": loaded_skill.manifest.provider,
                    "payload": payload,
                    "session_id": session.session_id if session is not None else None,
                    "session": _session_payload(session),
                    "trace_id": uuid.uuid4().hex,
                },
                cwd=loaded_skill.bundle_root,
                extra_env={"WEB2SKILL_BUNDLE_ROOT": str(loaded_skill.bundle_root)},
                python_path=(loaded_skill.bundle_root / "scripts",),
            )
        except (ScriptInvocationError, BundleEnvironmentError) as exc:
            msg = f"session hook '{script_path.name}' failed: {exc}"
            raise RuntimeError(msg) from exc

    def _latest_session(self, provider: str) -> SessionRecord | None:
        sessions = self._session_store.list(provider_name=provider)
        if not sessions:
            return None
        return sessions[0]


def _resolve_python_executable(loaded_skill: LoadedSkill) -> Path:
    if loaded_skill.manifest.runtime.env == "core":
        return Path(sys.executable)
    bundle_root = loaded_skill.bundle_root
    candidates = (
        bundle_root / ".venv" / "bin" / "python",
        bundle_root / ".venv" / "Scripts" / "python.exe",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    msg = (
        f"Bundle '{loaded_skill.manifest.bundle_id}' requires a bundle environment, "
        "but no Python executable was found in '.venv'. "
        f"Run `web2skill skills install {loaded_skill.manifest.bundle_id}` or update the bundle."
    )
    raise BundleEnvironmentError(msg)


def _skill_result_from_script_response(
    *,
    loaded_skill: LoadedSkill,
    context: ExecutionContext,
    response: ScriptInvocationResponse,
) -> SkillResult:
    metadata = dict(context.metadata)
    metadata["bundle_id"] = loaded_skill.manifest.bundle_id
    metadata["bundle_version"] = loaded_skill.manifest.bundle_version
    metadata["bundle_source"] = loaded_skill.source
    if response.trace:
        metadata["bundle_trace"] = json.dumps(response.trace)
    metadata.update(
        {
            key: value
            for key, value in response.metadata.items()
            if isinstance(value, str | int | float | bool) or value is None
        }
    )
    return SkillResult(
        trace_id=context.trace_id,
        capability_name=context.capability_name,
        strategy_used=Strategy(response.strategy_used),
        requires_human=response.requires_human,
        output=response.data,
        errors=tuple(_normalize_errors(response.errors)),
        warnings=tuple(_normalize_warnings(response.warnings)),
        session_id=context.session_id,
        metadata=metadata,
    )


def _response_payload(response: ScriptInvocationResponse) -> dict[str, Any]:
    if isinstance(response.data, dict):
        return dict(response.data)
    return {}


def _maybe_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    return Path(value)


def _session_payload(session: SessionRecord | None) -> dict[str, Any] | None:
    if session is None:
        return None
    payload = session.model_dump(mode="json")
    storage_state_path = session.storage_state_path
    if storage_state_path is not None:
        payload["storage_state_path"] = str(storage_state_path.expanduser().resolve())
    return payload


def _normalize_errors(raw_errors: Sequence[object]) -> list[SkillError]:
    errors: list[SkillError] = []
    for raw_error in raw_errors:
        if isinstance(raw_error, dict):
            errors.append(SkillError.model_validate(raw_error))
            continue
        errors.append(
            SkillError(
                code="bundle_error",
                message=str(raw_error),
            )
        )
    return errors


def _normalize_warnings(raw_warnings: Sequence[object]) -> list[GuardrailWarning]:
    warnings: list[GuardrailWarning] = []
    for raw_warning in raw_warnings:
        if isinstance(raw_warning, dict):
            warnings.append(GuardrailWarning.model_validate(raw_warning))
            continue
        warnings.append(
            GuardrailWarning(
                code="bundle_warning",
                message=str(raw_warning),
            )
        )
    return warnings
