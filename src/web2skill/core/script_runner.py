from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from pydantic import ConfigDict, Field

from web2skill.core.contracts import JsonValue, RuntimeBaseModel


class ScriptInvocationError(RuntimeError):
    pass


def _empty_json_list() -> list[JsonValue]:
    return []


class ScriptInvocationResponse(RuntimeBaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str | None = None
    capability: str | None = None
    strategy_used: str = Field(min_length=1)
    requires_human: bool
    data: JsonValue | None = None
    errors: list[JsonValue] = Field(default_factory=_empty_json_list)
    warnings: list[JsonValue] = Field(default_factory=_empty_json_list)
    trace: list[JsonValue] = Field(default_factory=_empty_json_list)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ScriptRunner:
    def invoke(
        self,
        *,
        script_path: Path,
        python_executable: Path,
        request: dict[str, Any],
        cwd: Path | None = None,
        extra_env: dict[str, str] | None = None,
        python_path: tuple[Path, ...] = (),
    ) -> ScriptInvocationResponse:
        env = os.environ.copy()
        if python_path:
            path_entries = [str(path) for path in python_path]
            existing = env.get("PYTHONPATH")
            if existing:
                path_entries.append(existing)
            env["PYTHONPATH"] = os.pathsep.join(path_entries)
        if extra_env:
            env.update(extra_env)

        completed = subprocess.run(
            [str(python_executable), str(script_path)],
            input=json.dumps(request),
            text=True,
            capture_output=True,
            cwd=str(cwd or script_path.parent),
            env=env,
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            msg = f"Script invocation failed for '{script_path}': {stderr or 'unknown error'}"
            raise ScriptInvocationError(msg)

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            msg = f"Script '{script_path}' did not emit valid JSON."
            raise ScriptInvocationError(msg) from exc
        return ScriptInvocationResponse.model_validate(payload)
