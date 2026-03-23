from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

from typer.testing import CliRunner

from web2skill import cli as cli_module

runner = CliRunner()
EnvOverride = Callable[[str, str | None], None]


def test_cli_marketplaces_add_list_and_remove(
    tmp_path: Path,
    env_override: EnvOverride,
) -> None:
    home = tmp_path / "home"
    env_override("HOME", str(home))
    repo_root = tmp_path / "repos" / "market.git"
    bundle_root = repo_root / "skills" / "demo"
    _write_demo_bundle(bundle_root)
    _commit_repo(repo_root)
    manifest_path = tmp_path / "fixtures" / "marketplace.yaml"
    _write_marketplace_manifest(manifest_path, repo_root=repo_root)
    app = cli_module.build_app()

    added = runner.invoke(
        app,
        ["marketplaces", "add", "local", str(manifest_path), "--json"],
    )

    assert added.exit_code == 0, added.stdout
    add_payload = json.loads(added.stdout)
    assert add_payload["alias"] == "local"

    listed = runner.invoke(app, ["marketplaces", "list", "--json"])

    assert listed.exit_code == 0, listed.stdout
    listed_payload = json.loads(listed.stdout)
    assert listed_payload["marketplaces"] == [
        {
            "alias": "local",
            "manifest": str(manifest_path.resolve()),
        }
    ]

    removed = runner.invoke(app, ["marketplaces", "remove", "local", "--json"])

    assert removed.exit_code == 0, removed.stdout
    removed_payload = json.loads(removed.stdout)
    assert removed_payload["removed"] is True


def test_cli_skills_search_queries_registered_marketplace(
    tmp_path: Path,
    env_override: EnvOverride,
) -> None:
    home = tmp_path / "home"
    env_override("HOME", str(home))
    repo_root = tmp_path / "repos" / "market.git"
    bundle_root = repo_root / "skills" / "demo"
    _write_demo_bundle(bundle_root)
    _commit_repo(repo_root)
    manifest_path = tmp_path / "fixtures" / "marketplace.yaml"
    _write_marketplace_manifest(
        manifest_path,
        repo_root=repo_root,
        plugin_id="demo-plugin",
        summary="Demo provider for marketplace search",
    )
    app = cli_module.build_app()
    add_result = runner.invoke(
        app,
        ["marketplaces", "add", "local", str(manifest_path), "--json"],
    )
    assert add_result.exit_code == 0, add_result.stdout

    search = runner.invoke(
        app,
        ["skills", "search", "demo", "--marketplace", "local", "--json"],
    )

    assert search.exit_code == 0, search.stdout
    payload = json.loads(search.stdout)
    assert payload["matches"][0]["plugin_id"] == "demo-plugin"
    assert payload["matches"][0]["marketplace"] == "local"


def test_cli_installs_bundle_from_marketplace_reference_and_records_metadata(
    tmp_path: Path,
    env_override: EnvOverride,
) -> None:
    home = tmp_path / "home"
    env_override("HOME", str(home))
    repo_root = tmp_path / "repos" / "market.git"
    bundle_root = repo_root / "skills" / "demo"
    _write_demo_bundle(bundle_root)
    _commit_repo(repo_root)
    manifest_path = tmp_path / "fixtures" / "marketplace.yaml"
    _write_marketplace_manifest(
        manifest_path,
        repo_root=repo_root,
        plugin_id="demo-plugin",
    )
    app = cli_module.build_app()
    add_result = runner.invoke(
        app,
        ["marketplaces", "add", "local", str(manifest_path), "--json"],
    )
    assert add_result.exit_code == 0, add_result.stdout

    install = runner.invoke(
        app,
        ["skills", "install", "demo-plugin@local", "--json"],
    )

    assert install.exit_code == 0, install.stdout
    payload = json.loads(install.stdout)
    assert payload["bundle_id"] == "demo"
    assert payload["source_descriptor"] == {
        "kind": "marketplace_ref",
        "plugin_id": "demo-plugin",
        "marketplace": "local",
    }
    metadata_path = home / ".web2skill" / "skills" / "demo" / ".web2skill-install.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["source_descriptor"]["kind"] == "marketplace_ref"
    assert metadata["resolved_source"]["kind"] == "git_subdir"
    assert metadata["resolved_source"]["subdir"] == "skills/demo"


def _write_marketplace_manifest(
    manifest_path: Path,
    *,
    repo_root: Path,
    plugin_id: str = "demo-plugin",
    summary: str = "Demo provider for marketplace install",
) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "\n".join(
            [
                'marketplace_id: "local"',
                'display_name: "Local Test Marketplace"',
                "plugins:",
                f'  - plugin_id: "{plugin_id}"',
                '    bundle_id: "demo"',
                '    provider: "demo"',
                '    display_name: "Demo"',
                f'    summary: "{summary}"',
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
