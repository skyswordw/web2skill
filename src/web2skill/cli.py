from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

import typer
from pydantic import TypeAdapter, ValidationError

from web2skill.skills import SkillRegistry

# pyright: reportUnusedFunction=false


class InvocationRuntime(Protocol):
    def invoke(
        self,
        capability_name: str,
        payload: Mapping[str, Any],
        session_id: str | None = None,
    ) -> Any: ...


class SessionService(Protocol):
    def login(self, provider: str) -> Any: ...

    def doctor(self, provider: str) -> Any: ...


class ReplayService(Protocol):
    def run(self, trace_id: str) -> Any: ...


@dataclass(slots=True)
class CliServices:
    registry: SkillRegistry
    runtime: InvocationRuntime | None = None
    sessions: SessionService | None = None
    replay: ReplayService | None = None


JsonMapping = TypeAdapter(dict[str, Any])


def build_app(
    *,
    registry: SkillRegistry | None = None,
    runtime: InvocationRuntime | None = None,
    sessions: SessionService | None = None,
    replay: ReplayService | None = None,
) -> typer.Typer:
    services = CliServices(
        registry=registry or SkillRegistry.discover(),
        runtime=runtime,
        sessions=sessions,
        replay=replay,
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
            _echo_json({"capabilities": [capability.model_dump(mode="json") for capability in capabilities]})
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
        result = services.runtime.invoke(capability, payload, session_id=session_id)
        _emit_command_result(result, as_json=as_json)

    @sessions_app.command("login")
    def sessions_login(
        provider: str = typer.Argument(help="Provider id."),
        as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    ) -> None:
        _validate_provider(services.registry, provider)
        if services.sessions is None:
            raise typer.Exit(code=_missing_integration("sessions.login"))
        _emit_command_result(services.sessions.login(provider), as_json=as_json)

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


app: typer.Typer = build_app()


if __name__ == "__main__":
    app()
