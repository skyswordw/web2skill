from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Literal, cast
from urllib.request import urlopen

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

MarketplaceSourceKind = Literal["git_repo", "git_subdir"]
SourceKind = Literal[
    "local_path",
    "local_subdir",
    "git_repo",
    "git_subdir",
    "marketplace_ref",
]


class SourceDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: SourceKind
    path: str | None = None
    repo: str | None = None
    subdir: str | None = None
    ref: str | None = None
    plugin_id: str | None = None
    marketplace: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> SourceDescriptor:
        if self.kind == "local_path":
            _require(self.path, "path is required for local_path sources")
        elif self.kind == "local_subdir":
            _require(self.path, "path is required for local_subdir sources")
            self.subdir = _normalize_subdir(self.subdir, kind=self.kind)
        elif self.kind == "git_repo":
            _require(self.repo, "repo is required for git_repo sources")
        elif self.kind == "git_subdir":
            _require(self.repo, "repo is required for git_subdir sources")
            self.subdir = _normalize_subdir(self.subdir, kind=self.kind)
        elif self.kind == "marketplace_ref":
            _require(self.plugin_id, "plugin_id is required for marketplace_ref sources")
            _require(self.marketplace, "marketplace is required for marketplace_ref sources")
        return self

    def as_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude_none=True)

    def to_legacy_source_kind(self) -> str:
        if self.kind.startswith("git"):
            return "git"
        if self.kind == "marketplace_ref":
            return "marketplace"
        return "local"


class MarketplaceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: MarketplaceSourceKind
    repo: str = Field(min_length=1)
    ref: str | None = None
    subdir: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> MarketplaceSource:
        if self.kind == "git_subdir" or self.subdir is not None:
            self.subdir = _normalize_subdir(self.subdir, kind=self.kind)
        return self

    def to_source_descriptor(self) -> SourceDescriptor:
        return SourceDescriptor(
            kind=self.kind,
            repo=self.repo,
            ref=self.ref,
            subdir=self.subdir,
        )


class MarketplacePlugin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plugin_id: str = Field(min_length=1)
    bundle_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    source: MarketplaceSource


class MarketplaceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    plugins: list[MarketplacePlugin] = Field(
        default_factory=lambda: cast(list[MarketplacePlugin], [])
    )


class MarketplaceRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str = Field(min_length=1)
    manifest: str = Field(min_length=1)

    def as_dict(self) -> dict[str, str]:
        return self.model_dump(mode="json")


class InstallMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bundle_id: str = Field(min_length=1)
    bundle_version: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    installed_at: str = Field(min_length=1)
    source_kind: str | None = None
    source: str | None = None
    source_descriptor: SourceDescriptor | None = None
    resolved_source: SourceDescriptor | None = None

    @model_validator(mode="after")
    def validate_sources(self) -> InstallMetadata:
        if self.source_descriptor is None and not self.source:
            msg = "install metadata must include source_descriptor or legacy source"
            raise ValueError(msg)
        return self

    def as_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude_none=True)


class MarketplaceRegistry:
    def __init__(self, storage_root: Path | None = None) -> None:
        self.storage_root = storage_root or default_marketplaces_root()
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def add(self, alias: str, manifest: str) -> dict[str, str]:
        registration = MarketplaceRegistration(
            alias=alias,
            manifest=_normalize_manifest_reference(manifest),
        )
        self._load_manifest_reference(registration.manifest)
        self._registration_path(alias).write_text(
            json.dumps(registration.as_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return registration.as_dict()

    def list_registrations(self) -> list[MarketplaceRegistration]:
        registrations: list[MarketplaceRegistration] = []
        for path in sorted(self.storage_root.glob("*.json")):
            registrations.append(
                MarketplaceRegistration.model_validate_json(path.read_text(encoding="utf-8"))
            )
        return registrations

    def remove(self, alias: str) -> dict[str, object]:
        path = self._registration_path(alias)
        if not path.exists():
            msg = f"unknown marketplace '{alias}'"
            raise LookupError(msg)
        path.unlink()
        return {"alias": alias, "removed": True}

    def search(
        self,
        query: str | None = None,
        *,
        marketplace: str | None = None,
    ) -> list[dict[str, object]]:
        aliases = (
            [marketplace]
            if marketplace
            else [item.alias for item in self.list_registrations()]
        )
        normalized_query = (query or "").strip().lower()
        matches: list[dict[str, object]] = []
        for alias in aliases:
            manifest = self.load_manifest(alias)
            for plugin in manifest.plugins:
                haystack = " ".join(
                    [
                        plugin.plugin_id,
                        plugin.bundle_id,
                        plugin.provider,
                        plugin.display_name,
                        plugin.summary,
                    ]
                ).lower()
                if normalized_query and normalized_query not in haystack:
                    continue
                payload = plugin.model_dump(mode="json", exclude_none=True)
                payload["marketplace"] = alias
                matches.append(payload)
        return sorted(
            matches,
            key=lambda item: (str(item["marketplace"]), str(item["plugin_id"])),
        )

    def load_manifest(self, alias: str) -> MarketplaceManifest:
        path = self._registration_path(alias)
        if not path.exists():
            msg = f"unknown marketplace '{alias}'"
            raise LookupError(msg)
        registration = MarketplaceRegistration.model_validate_json(path.read_text(encoding="utf-8"))
        return self._load_manifest_reference(registration.manifest)

    def resolve(self, source: SourceDescriptor) -> tuple[MarketplacePlugin, SourceDescriptor]:
        if source.kind != "marketplace_ref":
            msg = "marketplace resolution requires a marketplace_ref source descriptor"
            raise ValueError(msg)
        manifest = self.load_manifest(str(source.marketplace))
        for plugin in manifest.plugins:
            if plugin.plugin_id == source.plugin_id:
                return plugin, plugin.source.to_source_descriptor()
        msg = f"unknown plugin '{source.plugin_id}' in marketplace '{source.marketplace}'"
        raise LookupError(msg)

    def _load_manifest_reference(self, manifest_reference: str) -> MarketplaceManifest:
        try:
            if _looks_like_url(manifest_reference):
                with urlopen(manifest_reference, timeout=30) as response:
                    raw = response.read().decode("utf-8")
            else:
                raw = Path(manifest_reference).read_text(encoding="utf-8")
        except OSError as exc:
            msg = f"failed to load marketplace manifest '{manifest_reference}': {exc}"
            raise LookupError(msg) from exc
        loaded = yaml.safe_load(raw)
        return MarketplaceManifest.model_validate(loaded)

    def _registration_path(self, alias: str) -> Path:
        return self.storage_root / f"{alias}.json"


def default_marketplaces_root() -> Path:
    return Path.home() / ".web2skill" / "marketplaces"


def _normalize_manifest_reference(reference: str) -> str:
    if _looks_like_url(reference):
        return reference
    candidate = Path(reference).expanduser()
    if not candidate.exists():
        msg = f"marketplace manifest '{reference}' does not exist"
        raise LookupError(msg)
    return str(candidate.resolve())


def _looks_like_url(reference: str) -> bool:
    return reference.startswith(("https://", "http://"))


def _normalize_subdir(raw_value: str | None, *, kind: str) -> str:
    _require(raw_value, f"subdir is required for {kind} sources")
    assert raw_value is not None
    candidate = PurePosixPath(raw_value)
    if candidate.is_absolute() or ".." in candidate.parts:
        msg = f"subdir '{raw_value}' must stay within the source root"
        raise ValueError(msg)
    normalized = candidate.as_posix().strip("/")
    if not normalized:
        msg = f"subdir is required for {kind} sources"
        raise ValueError(msg)
    return normalized


def _require(value: str | None, message: str) -> None:
    if not value:
        raise ValueError(message)
