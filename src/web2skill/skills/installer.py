from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from .registry import LoadedSkill, default_user_skills_root, load_skill_bundle

INSTALL_METADATA = ".web2skill-install.json"
InstallSourceKind = Literal["local", "git"]


class BundleInstallError(RuntimeError):
    pass


class BundleInstaller:
    def __init__(self, install_root: Path | None = None) -> None:
        self.install_root = install_root or default_user_skills_root()
        self.install_root.mkdir(parents=True, exist_ok=True)

    def install(self, source: str) -> dict[str, object]:
        source_kind = _classify_source(source)
        bundle_root = _materialize_source(source, source_kind=source_kind)
        loaded = load_skill_bundle(bundle_root / "skill.yaml", source="user")
        target_root = self.install_root / loaded.manifest.bundle_id
        if target_root.exists():
            shutil.rmtree(target_root)
        shutil.copytree(
            bundle_root,
            target_root,
            ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache"),
        )
        installed = load_skill_bundle(target_root / "skill.yaml", source="user")
        self._write_install_metadata(
            installed,
            source=source,
            source_kind=source_kind,
        )
        env_created = self._ensure_bundle_env(installed)
        return {
            "bundle_id": installed.manifest.bundle_id,
            "bundle_version": installed.manifest.bundle_version,
            "install_root": str(target_root),
            "source": source,
            "source_kind": source_kind,
            "environment_created": env_created,
        }

    def uninstall(self, bundle_id: str) -> dict[str, object]:
        target_root = self.install_root / bundle_id
        if not target_root.exists():
            msg = f"unknown bundle '{bundle_id}'"
            raise LookupError(msg)
        shutil.rmtree(target_root)
        return {
            "bundle_id": bundle_id,
            "removed": True,
        }

    def update(self, bundle_id: str) -> dict[str, object]:
        installed_root = self.install_root / bundle_id
        metadata_path = installed_root / INSTALL_METADATA
        if not metadata_path.exists():
            msg = (
                f"bundle '{bundle_id}' is missing install metadata. "
                "Reinstall it from the original source."
            )
            raise LookupError(msg)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        source = metadata.get("source")
        if not isinstance(source, str) or not source:
            msg = f"bundle '{bundle_id}' has invalid install metadata"
            raise LookupError(msg)
        return self.install(source)

    def _write_install_metadata(
        self,
        loaded: LoadedSkill,
        *,
        source: str,
        source_kind: InstallSourceKind,
    ) -> None:
        metadata = {
            "bundle_id": loaded.manifest.bundle_id,
            "bundle_version": loaded.manifest.bundle_version,
            "provider": loaded.manifest.provider,
            "source": source,
            "source_kind": source_kind,
            "installed_at": datetime.now(UTC).isoformat(),
        }
        (loaded.bundle_root / INSTALL_METADATA).write_text(
            json.dumps(metadata, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _ensure_bundle_env(self, loaded: LoadedSkill) -> bool:
        bundle_root = loaded.bundle_root
        needs_env = (
            loaded.manifest.runtime.env == "bundle"
            or bundle_root.joinpath("pyproject.toml").exists()
        )
        if not needs_env:
            return False
        if not bundle_root.joinpath("pyproject.toml").exists():
            msg = (
                f"bundle '{loaded.manifest.bundle_id}' requests a bundle environment "
                "but does not define a pyproject.toml"
            )
            raise BundleInstallError(msg)
        uv_bin = shutil.which("uv")
        if uv_bin is None:
            msg = (
                "This bundle requires uv to provision its isolated environment. "
                "Install uv and rerun `web2skill skills install`."
            )
            raise BundleInstallError(msg)
        command = [uv_bin, "sync"]
        if bundle_root.joinpath("uv.lock").exists():
            command.append("--frozen")
        completed = subprocess.run(
            command,
            cwd=str(bundle_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            msg = (
                f"Failed to provision bundle environment for '{loaded.manifest.bundle_id}': "
                f"{stderr or 'unknown error'}"
            )
            raise BundleInstallError(msg)
        return True


def _classify_source(source: str) -> InstallSourceKind:
    if _looks_like_git_url(source):
        return "git"
    return "local"


def _materialize_source(source: str, *, source_kind: InstallSourceKind) -> Path:
    if source_kind == "git":
        return _clone_git_source(source)
    candidate = Path(source).expanduser().resolve()
    if candidate.is_dir() and candidate.joinpath("skill.yaml").exists():
        return candidate
    msg = (
        f"'{source}' is not a valid skill bundle path. Expected a directory containing skill.yaml."
    )
    raise BundleInstallError(msg)


def _clone_git_source(source: str) -> Path:
    target_root = Path(tempfile.mkdtemp(prefix="web2skill-bundle-"))
    clone_root = target_root / "repo"
    completed = subprocess.run(
        ["git", "clone", "--depth", "1", source, str(clone_root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        msg = f"Failed to clone bundle source '{source}': {stderr or 'unknown error'}"
        raise BundleInstallError(msg)
    if not clone_root.joinpath("skill.yaml").exists():
        msg = f"Git source '{source}' does not contain a root-level skill.yaml bundle."
        raise BundleInstallError(msg)
    return clone_root


def _looks_like_git_url(source: str) -> bool:
    prefixes = ("https://", "http://", "ssh://", "git@", "git://", "file://")
    return source.startswith(prefixes) or source.endswith(".git")
