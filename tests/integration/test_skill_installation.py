from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

from typer.testing import CliRunner

from web2skill import cli as cli_module

runner = CliRunner()
EnvOverride = Callable[[str, str | None], None]


def test_cli_installs_and_uninstalls_local_skill_bundle(
    tmp_path: Path,
    env_override: EnvOverride,
) -> None:
    home = tmp_path / "home"
    env_override("HOME", str(home))
    source_bundle = tmp_path / "source" / "demo"
    _write_demo_bundle(source_bundle)
    app = cli_module.build_app()

    install = runner.invoke(
        app,
        ["skills", "install", str(source_bundle), "--json"],
    )

    assert install.exit_code == 0, install.stdout
    install_payload = json.loads(install.stdout)
    assert install_payload["bundle_id"] == "demo"
    installed_bundle = home / ".web2skill" / "skills" / "demo"
    assert installed_bundle.joinpath("skill.yaml").exists()

    listed = runner.invoke(app, ["skills", "list", "--json"])

    assert listed.exit_code == 0, listed.stdout
    listed_payload = json.loads(listed.stdout)
    capability_names = {item["name"] for item in listed_payload["capabilities"]}
    assert "demo.echo" in capability_names

    uninstall = runner.invoke(app, ["skills", "uninstall", "demo", "--json"])

    assert uninstall.exit_code == 0, uninstall.stdout
    assert not installed_bundle.exists()


def test_cli_installs_skill_bundle_from_git_source(
    tmp_path: Path,
    env_override: EnvOverride,
) -> None:
    home = tmp_path / "home"
    env_override("HOME", str(home))
    repo_root = tmp_path / "source" / "demo.git"
    _write_demo_bundle(repo_root)
    _commit_repo(repo_root)
    app = cli_module.build_app()

    install = runner.invoke(app, ["skills", "install", str(repo_root), "--json"])

    assert install.exit_code == 0, install.stdout
    payload = json.loads(install.stdout)
    assert payload["bundle_id"] == "demo"
    assert payload["source_kind"] == "git"
    installed_bundle = home / ".web2skill" / "skills" / "demo"
    assert installed_bundle.joinpath("skill.yaml").exists()


def test_cli_updates_local_skill_bundle_from_original_source(
    tmp_path: Path,
    env_override: EnvOverride,
) -> None:
    home = tmp_path / "home"
    env_override("HOME", str(home))
    source_bundle = tmp_path / "source" / "demo"
    _write_demo_bundle(source_bundle)
    app = cli_module.build_app()

    install = runner.invoke(app, ["skills", "install", str(source_bundle), "--json"])

    assert install.exit_code == 0, install.stdout
    source_manifest = source_bundle / "skill.yaml"
    source_manifest.write_text(
        source_manifest.read_text(encoding="utf-8").replace(
            'bundle_version: "1.0.0"',
            'bundle_version: "1.1.0"',
        ),
        encoding="utf-8",
    )

    update = runner.invoke(app, ["skills", "update", "demo", "--json"])

    assert update.exit_code == 0, update.stdout
    installed_manifest = home / ".web2skill" / "skills" / "demo" / "skill.yaml"
    assert 'bundle_version: "1.1.0"' in installed_manifest.read_text(encoding="utf-8")


def test_cli_installs_bundle_with_private_env_when_bundle_requires_it(
    tmp_path: Path,
    env_override: EnvOverride,
) -> None:
    home = tmp_path / "home"
    env_override("HOME", str(home))
    source_bundle = tmp_path / "source" / "demo-env"
    _write_demo_bundle(source_bundle, runtime_env="bundle", include_pyproject=True)
    app = cli_module.build_app()

    install = runner.invoke(app, ["skills", "install", str(source_bundle), "--json"])

    assert install.exit_code == 0, install.stdout
    payload = json.loads(install.stdout)
    assert payload["environment_created"] is True
    installed_root = home / ".web2skill" / "skills" / "demo"
    assert installed_root.joinpath(".venv").exists()


def _write_demo_bundle(
    bundle_root: Path,
    *,
    runtime_env: str = "core",
    include_pyproject: bool = False,
) -> None:
    capability_root = bundle_root / "scripts" / "capabilities"
    capability_root.mkdir(parents=True, exist_ok=True)
    bundle_root.joinpath("SKILL.md").write_text("# Demo\n", encoding="utf-8")
    bundle_root.joinpath("skill.yaml").write_text(
        "\n".join(
            [
                'bundle_id: "demo"',
                'bundle_version: "1.0.0"',
                'provider: "demo"',
                "runtime:",
                '  kind: "python_scripts"',
                f'  env: "{runtime_env}"',
                "capabilities:",
                '  - name: "demo.echo"',
                '    entry_script: "scripts/capabilities/echo.py"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    capability_root.joinpath("echo.py").write_text(
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
                '        "trace": [],',
                "    },",
                "    sys.stdout,",
                ")",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if include_pyproject:
        package_root = bundle_root / "src" / "demo_skill_env"
        package_root.mkdir(parents=True, exist_ok=True)
        package_root.joinpath("__init__.py").write_text(
            '__all__ = ["__version__"]\n__version__ = "0.1.0"\n',
            encoding="utf-8",
        )
        bundle_root.joinpath("pyproject.toml").write_text(
            "\n".join(
                [
                    "[project]",
                    'name = "demo-skill-env"',
                    'version = "0.1.0"',
                    'requires-python = ">=3.13,<3.15"',
                    "dependencies = []",
                    "",
                    "[build-system]",
                    'requires = ["hatchling"]',
                    'build-backend = "hatchling.build"',
                    "",
                    "[tool.hatch.build.targets.wheel]",
                    'packages = ["src/demo_skill_env"]',
                ]
            )
            + "\n",
            encoding="utf-8",
        )


def _commit_repo(repo_root: Path) -> None:
    _git(repo_root, "init")
    _git(repo_root, "config", "user.email", "ci@example.com")
    _git(repo_root, "config", "user.name", "CI")
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-m", "init")


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
    )
