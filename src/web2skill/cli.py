from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

import typer
from pydantic import BaseModel, TypeAdapter, ValidationError

from web2skill.core.runtime import SkillRuntime
from web2skill.core.sessions import FileSessionStore
from web2skill.core.traces import FileTraceStore
from web2skill.skills import BundleInstaller, SkillRegistry
from web2skill.skills.execution import BundleCapabilityRegistry, BundleSessionService

# pyright: reportUnusedFunction=false


class InvocationRuntime(Protocol):
    def invoke(
        self,
        capability_name: str,
        payload: dict[str, object] | BaseModel,
        session_id: str | None = None,
    ) -> Any: ...


class SessionService(Protocol):
    def login(self, provider: str, *, mode: str = "interactive", browser: str = "auto") -> Any: ...

    def doctor(self, provider: str) -> Any: ...


class ReplayService(Protocol):
    def run(self, trace_id: str) -> Any: ...


@dataclass(slots=True)
class CliServices:
    registry: SkillRegistry
    runtime: InvocationRuntime | None = None
    sessions: SessionService | None = None
    replay: ReplayService | None = None
    session_store: FileSessionStore | None = None
    installer: BundleInstaller | None = None


class DefaultReplayService:
    def __init__(self, runtime: SkillRuntime) -> None:
        self._runtime = runtime

    def run(self, trace_id: str) -> Any:
        return self._runtime.replay(trace_id)


JsonMapping = TypeAdapter(dict[str, Any])


def build_app(
    *,
    registry: SkillRegistry | None = None,
    runtime: InvocationRuntime | None = None,
    sessions: SessionService | None = None,
    replay: ReplayService | None = None,
) -> typer.Typer:
    resolved_registry = registry or SkillRegistry.discover()
    session_store = FileSessionStore()
    trace_store = FileTraceStore()
    default_runtime = SkillRuntime(
        registry=BundleCapabilityRegistry(
            skill_registry=resolved_registry,
            session_store=session_store,
        ),
        session_store=session_store,
        trace_store=trace_store,
    )
    resolved_runtime: InvocationRuntime = runtime or default_runtime
    resolved_replay = replay
    if resolved_replay is None and isinstance(resolved_runtime, SkillRuntime):
        resolved_replay = DefaultReplayService(resolved_runtime)
    services = CliServices(
        registry=resolved_registry,
        runtime=resolved_runtime,
        sessions=sessions
        or BundleSessionService(
            skill_registry=resolved_registry,
            session_store=session_store,
        ),
        replay=resolved_replay,
        session_store=session_store,
        installer=BundleInstaller(),
    )

    application = typer.Typer(
        help="CLI for discovering and invoking packaged web2skill capabilities.",
        no_args_is_help=True,
    )
    skills_app = typer.Typer(help="Inspect packaged provider skills.")
    sessions_app = typer.Typer(help="Manage provider login sessions.")
    replay_app = typer.Typer(help="Replay a recorded trace.")
    application.add_typer(skills_app, name="skills")
    application.add_typer(sessions_app, name="sessions")
    application.add_typer(replay_app, name="replay")

    @skills_app.command("list")
    def skills_list(
        provider: str | None = typer.Option(default=None, help="Limit results to one provider."),
        as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    ) -> None:
        capabilities = services.registry.list_capabilities(provider=provider)
        if as_json:
            _echo_json(
                {
                    "capabilities": [
                        capability.model_dump(mode="json") for capability in capabilities
                    ]
                }
            )
            return
        for capability in capabilities:
            typer.echo(f"{capability.name}\t{capability.summary}")

    @skills_app.command("describe")
    def skills_describe(
        target: str = typer.Argument(help="Provider id or fully-qualified capability name."),
        as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    ) -> None:
        try:
            if "." in target:
                loaded, capability = services.registry.get_capability(target)
                payload = {
                    "provider": loaded.manifest.provider,
                    "provider_display_name": loaded.manifest.provider_display_name,
                    "auth": loaded.manifest.auth.model_dump(mode="json"),
                    "capability": capability.model_dump(mode="json"),
                }
                if as_json:
                    _echo_json(payload)
                else:
                    typer.echo(json.dumps(payload, indent=2, sort_keys=True))
                return
            rendered = services.registry.render_skill_doc(target)
            if as_json:
                loaded = services.registry.get_provider(target)
                _echo_json(
                    {
                        "provider": loaded.manifest.model_dump(mode="json"),
                        "skill_markdown": rendered,
                    }
                )
            else:
                typer.echo(rendered.rstrip())
        except LookupError as exc:
            raise typer.Exit(code=_usage_error(str(exc))) from exc

    @skills_app.command("install")
    def skills_install(
        source: str = typer.Argument(help="Local path or git URL for a skill bundle."),
        as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    ) -> None:
        if services.installer is None:
            raise typer.Exit(code=_missing_integration("skills.install"))
        try:
            result = services.installer.install(source)
        except (LookupError, RuntimeError) as exc:
            raise typer.Exit(code=_usage_error(str(exc))) from exc
        services.registry = SkillRegistry.discover()
        _emit_command_result(result, as_json=as_json)

    @skills_app.command("uninstall")
    def skills_uninstall(
        bundle_id: str = typer.Argument(help="Bundle id to remove."),
        as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    ) -> None:
        if services.installer is None:
            raise typer.Exit(code=_missing_integration("skills.uninstall"))
        try:
            result = services.installer.uninstall(bundle_id)
        except LookupError as exc:
            raise typer.Exit(code=_usage_error(str(exc))) from exc
        services.registry = SkillRegistry.discover()
        _emit_command_result(result, as_json=as_json)

    @skills_app.command("update")
    def skills_update(
        bundle_id: str = typer.Argument(help="Bundle id to update from its install source."),
        as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    ) -> None:
        if services.installer is None:
            raise typer.Exit(code=_missing_integration("skills.update"))
        try:
            result = services.installer.update(bundle_id)
        except LookupError as exc:
            raise typer.Exit(code=_usage_error(str(exc))) from exc
        services.registry = SkillRegistry.discover()
        _emit_command_result(result, as_json=as_json)

    @application.command("invoke")
    def invoke(
        capability: str = typer.Argument(help="Fully-qualified capability name."),
        input_value: str = typer.Option(
            ...,
            "--input",
            help="JSON payload or @path/to/payload.json",
        ),
        session_id: str | None = typer.Option(default=None, help="Existing session id."),
        as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    ) -> None:
        try:
            services.registry.get_capability(capability)
        except LookupError as exc:
            raise typer.Exit(code=_usage_error(str(exc))) from exc
        payload = _load_input_payload(input_value)
        if services.runtime is None:
            raise typer.Exit(code=_missing_integration("runtime.invoke"))
        resolved_session_id = session_id or _latest_session_id(services, capability)
        try:
            result = services.runtime.invoke(capability, payload, session_id=resolved_session_id)
        except Exception as exc:
            if as_json:
                _echo_json(_json_failure_envelope(exc))
                return
            raise typer.Exit(code=_usage_error(str(exc))) from exc
        _emit_command_result(result, as_json=as_json)

    @sessions_app.command("login")
    def sessions_login(
        provider: str = typer.Argument(help="Provider id."),
        mode: str = typer.Option(
            "interactive",
            "--mode",
            help="Login mode: interactive or import-browser.",
        ),
        browser: str = typer.Option(
            "auto",
            "--browser",
            help="Browser source when --mode import-browser is used.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    ) -> None:
        _validate_provider(services.registry, provider)
        if services.sessions is None:
            raise typer.Exit(code=_missing_integration("sessions.login"))
        try:
            result = services.sessions.login(provider, mode=mode, browser=browser)
        except LookupError as exc:
            raise typer.Exit(code=_usage_error(str(exc))) from exc
        _emit_command_result(result, as_json=as_json)

    @sessions_app.command("doctor")
    def sessions_doctor(
        provider: str = typer.Argument(help="Provider id."),
        as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    ) -> None:
        _validate_provider(services.registry, provider)
        if services.sessions is None:
            raise typer.Exit(code=_missing_integration("sessions.doctor"))
        _emit_command_result(services.sessions.doctor(provider), as_json=as_json)

    @replay_app.command("run")
    def replay_run(
        trace_id: str = typer.Argument(help="Trace id to replay."),
        as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    ) -> None:
        if services.replay is None:
            raise typer.Exit(code=_missing_integration("replay.run"))
        _emit_command_result(services.replay.run(trace_id), as_json=as_json)

    return application


def _load_input_payload(raw_value: str) -> dict[str, Any]:
    if raw_value.startswith("@"):
        text = Path(raw_value[1:]).read_text(encoding="utf-8")
    else:
        text = raw_value
    try:
        loaded = json.loads(text)
        return JsonMapping.validate_python(loaded)
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"input file not found: {exc.filename}") from exc
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"input is not valid JSON: {exc.msg}") from exc
    except ValidationError as exc:
        raise typer.BadParameter(f"input payload must be a JSON object: {exc}") from exc


def _emit_command_result(result: Any, *, as_json: bool) -> None:
    payload = _normalize_payload(result)
    if as_json:
        _echo_json(payload)
        return
    if isinstance(payload, str):
        typer.echo(payload)
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


def _normalize_payload(result: Any) -> Any:
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    if isinstance(result, Mapping):
        mapping = cast(Mapping[str, Any], result)
        return {key: value for key, value in mapping.items()}
    return result


def _echo_json(payload: Any) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


def _json_failure_envelope(exc: Exception) -> dict[str, Any]:
    return {
        "trace_id": uuid.uuid4().hex,
        "strategy_used": "network",
        "requires_human": True,
        "errors": [
            {
                "code": "invoke_error",
                "message": str(exc),
                "retriable": False,
            }
        ],
    }


def _validate_provider(registry: SkillRegistry, provider: str) -> None:
    try:
        registry.get_provider(provider)
    except LookupError as exc:
        raise typer.Exit(code=_usage_error(str(exc))) from exc


def _usage_error(message: str) -> int:
    typer.echo(f"Error: {message}", err=True)
    return 2


def _missing_integration(name: str) -> int:
    typer.echo(
        f"Error: CLI integration '{name}' is not wired yet in this worktree.",
        err=True,
    )
    return 2


def _latest_session_id(services: CliServices, capability_name: str) -> str | None:
    provider_name, _, _ = capability_name.partition(".")
    if services.session_store is None or not provider_name:
        return None
    sessions = services.session_store.list(provider_name=provider_name)
    if not sessions:
        return None
    return sessions[0].session_id


app: typer.Typer = build_app()


if __name__ == "__main__":
    app()
