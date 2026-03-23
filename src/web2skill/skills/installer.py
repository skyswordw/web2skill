from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from .marketplaces import InstallMetadata, MarketplaceRegistry, SourceDescriptor
from .registry import LoadedSkill, default_user_skills_root, load_skill_bundle

INSTALL_METADATA = ".web2skill-install.json"
InstallSourceKind = Literal["local", "git", "marketplace"]


class BundleInstallError(RuntimeError):
    pass


class BundleInstaller:
    def __init__(
        self,
        install_root: Path | None = None,
        *,
        marketplaces: MarketplaceRegistry | None = None,
    ) -> None:
        self.install_root = install_root or default_user_skills_root()
        self.install_root.mkdir(parents=True, exist_ok=True)
        self.marketplaces = marketplaces or MarketplaceRegistry()

    def install(self, source: str, *, subdir: str | None = None) -> dict[str, object]:
        source_descriptor = _parse_source_descriptor(source, subdir=subdir)
        return self.install_descriptor(source_descriptor)

    def install_descriptor(self, source_descriptor: SourceDescriptor) -> dict[str, object]:
        resolved_source = self._resolve_source_descriptor(source_descriptor)
        bundle_root = _materialize_source_descriptor(resolved_source)
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
            source_descriptor=source_descriptor,
            resolved_source=resolved_source,
        )
        env_created = self._ensure_bundle_env(installed)
        return {
            "bundle_id": installed.manifest.bundle_id,
            "bundle_version": installed.manifest.bundle_version,
            "install_root": str(target_root),
            "source": _legacy_source_value(source_descriptor),
            "source_kind": source_descriptor.to_legacy_source_kind(),
            "source_descriptor": source_descriptor.as_dict(),
            "resolved_source": resolved_source.as_dict(),
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
        metadata = InstallMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))
        if metadata.source_descriptor is not None:
            return self.install_descriptor(metadata.source_descriptor)
        if not metadata.source:
            msg = f"bundle '{bundle_id}' has invalid install metadata"
            raise LookupError(msg)
        return self.install(metadata.source)

    def _resolve_source_descriptor(self, source_descriptor: SourceDescriptor) -> SourceDescriptor:
        if source_descriptor.kind != "marketplace_ref":
            return source_descriptor
        _, resolved_source = self.marketplaces.resolve(source_descriptor)
        return resolved_source

    def _write_install_metadata(
        self,
        loaded: LoadedSkill,
        *,
        source_descriptor: SourceDescriptor,
        resolved_source: SourceDescriptor,
    ) -> None:
        metadata = InstallMetadata(
            bundle_id=loaded.manifest.bundle_id,
            bundle_version=loaded.manifest.bundle_version,
            provider=loaded.manifest.provider,
            source=_legacy_source_value(source_descriptor),
            source_kind=source_descriptor.to_legacy_source_kind(),
            source_descriptor=source_descriptor,
            resolved_source=resolved_source,
            installed_at=datetime.now(UTC).isoformat(),
        )
        (loaded.bundle_root / INSTALL_METADATA).write_text(
            json.dumps(metadata.as_dict(), indent=2, sort_keys=True),
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


def _parse_source_descriptor(source: str, *, subdir: str | None) -> SourceDescriptor:
    if subdir and _looks_like_marketplace_ref(source):
        msg = "marketplace references do not support --subdir"
        raise BundleInstallError(msg)
    if _looks_like_marketplace_ref(source):
        plugin_id, marketplace = source.split("@", 1)
        return SourceDescriptor(
            kind="marketplace_ref",
            plugin_id=plugin_id,
            marketplace=marketplace,
        )
    if _looks_like_git_url(source):
        if subdir:
            return SourceDescriptor(kind="git_subdir", repo=source, subdir=subdir)
        return SourceDescriptor(kind="git_repo", repo=source)
    candidate = Path(source).expanduser().resolve()
    if subdir:
        return SourceDescriptor(kind="local_subdir", path=str(candidate), subdir=subdir)
    return SourceDescriptor(kind="local_path", path=str(candidate))


def _materialize_source_descriptor(source_descriptor: SourceDescriptor) -> Path:
    if source_descriptor.kind == "local_path":
        return _validate_local_bundle(Path(str(source_descriptor.path)))
    if source_descriptor.kind == "local_subdir":
        assert source_descriptor.path is not None
        assert source_descriptor.subdir is not None
        return _validate_local_bundle(Path(source_descriptor.path) / source_descriptor.subdir)
    if source_descriptor.kind == "git_repo":
        assert source_descriptor.repo is not None
        return _clone_git_source(source_descriptor.repo, ref=source_descriptor.ref)
    if source_descriptor.kind == "git_subdir":
        assert source_descriptor.repo is not None
        assert source_descriptor.subdir is not None
        return _clone_git_subdir_source(
            source_descriptor.repo,
            subdir=source_descriptor.subdir,
            ref=source_descriptor.ref,
        )
    msg = f"unsupported source kind '{source_descriptor.kind}'"
    raise BundleInstallError(msg)


def _validate_local_bundle(bundle_root: Path) -> Path:
    candidate = bundle_root.expanduser().resolve()
    if candidate.is_dir() and candidate.joinpath("skill.yaml").exists():
        return candidate
    msg = (
        f"'{bundle_root}' is not a valid skill bundle path. "
        "Expected a directory containing skill.yaml."
    )
    raise BundleInstallError(msg)


def _clone_git_source(source: str, *, ref: str | None = None) -> Path:
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
    _checkout_git_ref(clone_root, ref)
    if not clone_root.joinpath("skill.yaml").exists():
        msg = f"Git source '{source}' does not contain a root-level skill.yaml bundle."
        raise BundleInstallError(msg)
    return clone_root


def _clone_git_subdir_source(source: str, *, subdir: str, ref: str | None = None) -> Path:
    target_root = Path(tempfile.mkdtemp(prefix="web2skill-subdir-"))
    clone_root = target_root / "repo"
    clone = subprocess.run(
        ["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", source, str(clone_root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if clone.returncode != 0:
        stderr = clone.stderr.strip()
        msg = (
            f"Failed to start sparse git install for '{source}': {stderr or 'unknown error'}. "
            "This install path requires git sparse-checkout support."
        )
        raise BundleInstallError(msg)
    _checkout_git_ref(clone_root, ref)
    sparse = subprocess.run(
        ["git", "-C", str(clone_root), "sparse-checkout", "set", "--no-cone", subdir],
        capture_output=True,
        text=True,
        check=False,
    )
    if sparse.returncode != 0:
        stderr = sparse.stderr.strip()
        msg = (
            f"Failed to materialize git subdir '{subdir}' from '{source}': "
            f"{stderr or 'unknown error'}. "
            "Upgrade git or install from a local checkout with `--subdir`."
        )
        raise BundleInstallError(msg)
    bundle_root = clone_root / subdir
    if not bundle_root.joinpath("skill.yaml").exists():
        msg = f"Git source '{source}' does not contain a skill bundle at '{subdir}'."
        raise BundleInstallError(msg)
    return bundle_root


def _checkout_git_ref(clone_root: Path, ref: str | None) -> None:
    if not ref:
        return
    completed = subprocess.run(
        ["git", "-C", str(clone_root), "checkout", ref],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        msg = f"Failed to checkout git ref '{ref}': {stderr or 'unknown error'}"
        raise BundleInstallError(msg)


def _legacy_source_value(source_descriptor: SourceDescriptor) -> str:
    if source_descriptor.kind == "marketplace_ref":
        assert source_descriptor.plugin_id is not None
        assert source_descriptor.marketplace is not None
        return f"{source_descriptor.plugin_id}@{source_descriptor.marketplace}"
    if source_descriptor.kind.startswith("git"):
        assert source_descriptor.repo is not None
        return source_descriptor.repo
    assert source_descriptor.path is not None
    return source_descriptor.path


def _looks_like_marketplace_ref(source: str) -> bool:
    if _looks_like_git_url(source):
        return False
    if "@" not in source or "/" in source or "\\" in source:
        return False
    candidate = Path(source).expanduser()
    return not candidate.exists()


def _looks_like_git_url(source: str) -> bool:
    prefixes = ("https://", "http://", "ssh://", "git@", "git://", "file://")
    return source.startswith(prefixes) or source.endswith(".git")
