from __future__ import annotations

from pathlib import Path

import pytest

from web2skill.core.runtime import SkillRuntime
from web2skill.core.sessions import FileSessionStore
from web2skill.skills.execution import BundleCapabilityRegistry
from web2skill.skills.registry import SkillRegistry


@pytest.mark.integration
def test_runtime_invokes_discovered_bundle_script(tmp_path: Path) -> None:
    user_root = tmp_path / "skills"
    _write_echo_bundle(user_root)
    registry = SkillRegistry.discover(
        user_root=user_root,
        builtin_roots=(),
    )
    runtime = SkillRuntime(
        registry=BundleCapabilityRegistry(
            skill_registry=registry,
            session_store=FileSessionStore(root=tmp_path / "sessions"),
        )
    )

    result = runtime.invoke("demo.echo", {"message": "hello"})

    assert result.trace_id
    assert result.strategy_used == "network"
    assert result.requires_human is False
    assert result.output == {"message": "hello"}


def _write_echo_bundle(root: Path) -> None:
    bundle_root = root / "demo"
    capability_root = bundle_root / "scripts" / "capabilities"
    capability_root.mkdir(parents=True, exist_ok=True)
    (bundle_root / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
    (bundle_root / "skill.yaml").write_text(
        "\n".join(
            [
                'bundle_id: "demo"',
                'bundle_version: "1.0.0"',
                'provider: "demo"',
                "runtime:",
                '  kind: "python_scripts"',
                '  env: "core"',
                "capabilities:",
                '  - name: "demo.echo"',
                '    entry_script: "scripts/capabilities/echo.py"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (capability_root / "echo.py").write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "",
                "request = json.load(sys.stdin)",
                "json.dump(",
                "    {",
                '        "strategy_used": "network",',
                '        "requires_human": False,',
                '        "data": request["payload"],',
                '        "errors": [],',
                '        "trace": [{"stage": "invoke", "detail": "echo", "strategy": "network"}],',
                "    },",
                "    sys.stdout,",
                ")",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
