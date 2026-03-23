from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from web2skill import cli as cli_module
from web2skill.skills.registry import SkillRegistry

runner = CliRunner()


def test_cli_uses_bundle_session_hooks_for_login_and_doctor(tmp_path: Path) -> None:
    user_root = tmp_path / "skills"
    _write_session_bundle(user_root)
    app = cli_module.build_app(
        registry=SkillRegistry.discover(user_root=user_root, builtin_roots=()),
    )

    login = runner.invoke(app, ["sessions", "login", "demo", "--json"])

    assert login.exit_code == 0, login.stdout
    login_payload = json.loads(login.stdout)
    assert login_payload["session_id"].startswith("demo-")
    assert login_payload["authenticated"] is True

    doctor = runner.invoke(app, ["sessions", "doctor", "demo", "--json"])

    assert doctor.exit_code == 0, doctor.stdout
    doctor_payload = json.loads(doctor.stdout)
    assert doctor_payload["provider"] == "demo"
    assert doctor_payload["ok"] is True
    assert doctor_payload["session_id"] == login_payload["session_id"]


def _write_session_bundle(root: Path) -> None:
    bundle_root = root / "demo"
    scripts_root = bundle_root / "scripts"
    session_root = scripts_root / "session"
    session_root.mkdir(parents=True, exist_ok=True)
    storage_state_path = bundle_root / "demo-storage.json"
    storage_state_path.write_text('{"cookies": [], "origins": []}\n', encoding="utf-8")
    bundle_root.joinpath("SKILL.md").write_text("# Demo\n", encoding="utf-8")
    bundle_root.joinpath("skill.yaml").write_text(
        "\n".join(
            [
                'bundle_id: "demo"',
                'bundle_version: "1.0.0"',
                'provider: "demo"',
                "runtime:",
                '  kind: "python_scripts"',
                '  env: "core"',
                "session_hooks:",
                '  login_script: "scripts/session/login.py"',
                '  doctor_script: "scripts/session/doctor.py"',
                "capabilities:",
                '  - name: "demo.echo"',
                '    entry_script: "scripts/session/login.py"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    session_root.joinpath("login.py").write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "",
                "request = json.load(sys.stdin)",
                "json.dump(",
                "    {",
                '        "trace_id": request["trace_id"],',
                '        "capability": "demo.session.login",',
                '        "strategy_used": "guided_ui",',
                '        "requires_human": False,',
                '        "data": {"authenticated": True, "message": "ok", "storage_state_path": "'
                + str(storage_state_path)
                + '"},',
                '        "errors": [],',
                '        "trace": [],',
                "    },",
                "    sys.stdout,",
                ")",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    session_root.joinpath("doctor.py").write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "",
                "request = json.load(sys.stdin)",
                "json.dump(",
                "    {",
                '        "trace_id": request["trace_id"],',
                '        "capability": "demo.session.doctor",',
                '        "strategy_used": "network",',
                '        "requires_human": False,',
                '        "data": {"ok": True, "message": "healthy"},',
                '        "errors": [],',
                '        "trace": [],',
                "    },",
                "    sys.stdout,",
                ")",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
