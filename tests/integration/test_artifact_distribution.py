from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest


@dataclass(frozen=True, slots=True)
class InstalledArtifact:
    artifact_path: Path
    install_root: Path
    python_executable: Path
    cli_executable: Path


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def built_artifacts(repo_root: Path, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    dist_dir = tmp_path_factory.mktemp("dist-artifacts")
    _run(
        ["uv", "build", "--wheel", "--sdist", "--out-dir", str(dist_dir)],
        cwd=repo_root,
    )
    wheel = next(dist_dir.glob("web2skill-*.whl"))
    sdist = next(dist_dir.glob("web2skill-*.tar.gz"))
    return {"wheel": wheel, "sdist": sdist}


@pytest.fixture(params=("wheel", "sdist"), ids=("wheel", "sdist"))
def installed_artifact(
    request: pytest.FixtureRequest,
    built_artifacts: dict[str, Path],
    tmp_path: Path,
) -> InstalledArtifact:
    artifact_kind = str(request.param)
    artifact_path = built_artifacts[artifact_kind]
    install_root = tmp_path / artifact_kind
    venv_root = install_root / "venv"
    install_root.mkdir(parents=True, exist_ok=True)
    _run(["uv", "venv", "--python", sys.executable, str(venv_root)], cwd=install_root)
    python_executable = _venv_python(venv_root)
    cli_executable = _venv_cli(venv_root)
    _run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python_executable),
            str(artifact_path),
        ],
        cwd=install_root,
    )
    return InstalledArtifact(
        artifact_path=artifact_path,
        install_root=install_root,
        python_executable=python_executable,
        cli_executable=cli_executable,
    )


@pytest.mark.integration
def test_installed_artifact_imports_cli_from_site_packages(
    installed_artifact: InstalledArtifact,
    repo_root: Path,
) -> None:
    completed = _run_json(
        [
            str(installed_artifact.python_executable),
            "-c",
            (
                "import json, web2skill.cli; "
                "print(json.dumps({'module_file': web2skill.cli.__file__}))"
            ),
        ],
        cwd=installed_artifact.install_root,
    )

    module_file = Path(completed["module_file"]).resolve()
    assert "site-packages" in module_file.parts
    assert repo_root not in module_file.parents


@pytest.mark.integration
def test_installed_artifact_lists_bundled_modelscope_capabilities(
    installed_artifact: InstalledArtifact,
) -> None:
    payload = _run_json(
        [str(installed_artifact.cli_executable), "skills", "list", "--json"],
        cwd=installed_artifact.install_root,
    )

    capability_names = {item["name"] for item in payload["capabilities"]}
    assert "modelscope.search_models" in capability_names
    assert "modelscope.get_model_overview" in capability_names
    assert "modelscope.list_model_files" in capability_names
    assert "modelscope.get_quickstart" in capability_names
    assert "modelscope.get_account_profile" in capability_names


@pytest.mark.integration
def test_installed_artifact_describes_modelscope_bundle(
    installed_artifact: InstalledArtifact,
) -> None:
    completed = _run(
        [str(installed_artifact.cli_executable), "skills", "describe", "modelscope"],
        cwd=installed_artifact.install_root,
    )

    assert "ModelScope" in completed.stdout
    assert "modelscope.search_models" in completed.stdout
    assert "modelscope.get_account_profile" in completed.stdout


@pytest.mark.integration
def test_installed_artifact_invokes_modelscope_search_models_json(
    installed_artifact: InstalledArtifact,
) -> None:
    payload = _run_json(
        [
            str(installed_artifact.cli_executable),
            "invoke",
            "modelscope.search_models",
            "--input",
            '{"query":"qwen"}',
            "--json",
        ],
        cwd=installed_artifact.install_root,
    )

    assert isinstance(payload["trace_id"], str)
    assert payload["trace_id"]
    assert payload["strategy_used"] == "network"
    assert isinstance(payload["requires_human"], bool)
    if "output" in payload:
        assert payload["output"] is None or isinstance(payload["output"], dict)
    if "errors" in payload:
        assert isinstance(payload["errors"], list)


@pytest.mark.integration
def test_installed_artifact_marketplace_install_smoke(
    installed_artifact: InstalledArtifact,
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repos" / "market.git"
    bundle_root = repo_root / "skills" / "demo"
    _write_demo_bundle(bundle_root)
    _commit_repo(repo_root)
    manifest_path = tmp_path / "fixtures" / "marketplace.yaml"
    _write_marketplace_manifest(manifest_path, repo_root=repo_root)

    add_completed = _run(
        [
            str(installed_artifact.cli_executable),
            "marketplaces",
            "add",
            "local",
            str(manifest_path),
            "--json",
        ],
        cwd=installed_artifact.install_root,
    )

    add_payload = json.loads(add_completed.stdout)
    assert add_payload["alias"] == "local"

    install_payload = _run_json(
        [
            str(installed_artifact.cli_executable),
            "skills",
            "install",
            "demo-plugin@local",
            "--json",
        ],
        cwd=installed_artifact.install_root,
    )

    assert install_payload["bundle_id"] == "demo"
    listed_payload = _run_json(
        [str(installed_artifact.cli_executable), "skills", "list", "--json"],
        cwd=installed_artifact.install_root,
    )
    capability_names = {item["name"] for item in listed_payload["capabilities"]}
    assert "demo.echo" in capability_names


def _venv_python(venv_root: Path) -> Path:
    if os.name == "nt":
        return venv_root / "Scripts" / "python.exe"
    return venv_root / "bin" / "python"


def _venv_cli(venv_root: Path) -> Path:
    if os.name == "nt":
        return venv_root / "Scripts" / "web2skill.exe"
    return venv_root / "bin" / "web2skill"


def _run_json(command: list[str], *, cwd: Path) -> dict[str, Any]:
    completed = _run(command, cwd=cwd)
    return json.loads(completed.stdout)


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "0"
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _write_marketplace_manifest(manifest_path: Path, *, repo_root: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "\n".join(
            [
                'marketplace_id: "local"',
                'display_name: "Local Test Marketplace"',
                "plugins:",
                '  - plugin_id: "demo-plugin"',
                '    bundle_id: "demo"',
                '    provider: "demo"',
                '    display_name: "Demo"',
                '    summary: "Demo provider for marketplace install"',
                "    source:",
                '      kind: "git_subdir"',
                f'      repo: "{repo_root}"',
                '      subdir: "skills/demo"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_demo_bundle(bundle_root: Path) -> None:
    capability_root = bundle_root / "scripts" / "capabilities"
    capability_root.mkdir(parents=True, exist_ok=True)
    bundle_root.joinpath("SKILL.md").write_text("# Demo\n", encoding="utf-8")
    bundle_root.joinpath("skill.yaml").write_text(
        "\n".join(
            [
                'bundle_id: "demo"',
                'bundle_version: "1.0.0"',
                'provider: "demo"',
                'summary: "demo bundle"',
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
