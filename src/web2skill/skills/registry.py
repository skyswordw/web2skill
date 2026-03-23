from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from .manifests import CapabilityManifest, CapabilitySummary, ProviderSummary, SkillManifest
from .render import render_skill_markdown

LoadedSkillSource = Literal["builtin", "user"]


@dataclass(frozen=True, slots=True)
class LoadedSkill:
    manifest: SkillManifest
    manifest_path: Path
    bundle_root: Path
    skill_doc_path: Path
    skill_markdown: str
    source: LoadedSkillSource


class SkillRegistry:
    def __init__(self, skills: dict[str, LoadedSkill]) -> None:
        self._skills = skills

    @classmethod
    def from_directory(
        cls,
        root: Path,
        *,
        source: LoadedSkillSource = "builtin",
    ) -> SkillRegistry:
        skills: dict[str, LoadedSkill] = {}
        if not root.exists():
            return cls(skills)
        for manifest_path in sorted(root.glob("*/skill.yaml")):
            loaded = load_skill_bundle(manifest_path, source=source)
            skills[loaded.manifest.provider] = loaded
        return cls(skills)

    @classmethod
    def discover(
        cls,
        *,
        user_root: Path | None = None,
        builtin_roots: tuple[Path, ...] | None = None,
    ) -> SkillRegistry:
        resolved_user_root = user_root if user_root is not None else default_user_skills_root()
        roots = builtin_roots if builtin_roots is not None else default_builtin_skills_roots()
        skills: dict[str, LoadedSkill] = {}
        for root in roots:
            if not root.exists():
                continue
            for manifest_path in sorted(root.glob("*/skill.yaml")):
                loaded = load_skill_bundle(manifest_path, source="builtin")
                skills[loaded.manifest.provider] = loaded
        if resolved_user_root.exists():
            for manifest_path in sorted(resolved_user_root.glob("*/skill.yaml")):
                loaded = load_skill_bundle(manifest_path, source="user")
                skills[loaded.manifest.provider] = loaded
        return cls(skills)

    def list_providers(self) -> list[ProviderSummary]:
        return [
            ProviderSummary(
                provider=skill.manifest.provider,
                provider_display_name=skill.manifest.provider_display_name,
                summary=skill.manifest.summary,
                auth_mode=skill.manifest.auth.mode,
                capability_count=len(skill.manifest.capabilities),
            )
            for skill in self._skills.values()
        ]

    def list_capabilities(self, provider: str | None = None) -> list[CapabilitySummary]:
        providers = [self.get_provider(provider)] if provider else self._skills.values()
        capabilities: list[CapabilitySummary] = []
        for loaded in providers:
            capabilities.extend(
                CapabilitySummary(
                    provider=loaded.manifest.provider,
                    name=capability.name,
                    summary=capability.summary,
                    risk=capability.risk,
                    strategies=capability.strategies,
                    auth_mode=loaded.manifest.auth.mode,
                    requires_confirmation=capability.requires_confirmation,
                )
                for capability in loaded.manifest.capabilities
            )
        return sorted(capabilities, key=lambda capability: capability.name)

    def get_provider(self, provider: str) -> LoadedSkill:
        try:
            return self._skills[provider]
        except KeyError as exc:
            msg = f"unknown provider '{provider}'"
            raise LookupError(msg) from exc

    def get_capability(self, capability_name: str) -> tuple[LoadedSkill, CapabilityManifest]:
        provider_name, _, _ = capability_name.partition(".")
        loaded = self.get_provider(provider_name)
        for capability in loaded.manifest.capabilities:
            if capability.name == capability_name:
                return loaded, capability
        msg = f"unknown capability '{capability_name}'"
        raise LookupError(msg)

    def render_skill_doc(self, provider: str) -> str:
        return self.get_provider(provider).skill_markdown


def default_skills_root() -> Path:
    return Path(__file__).resolve().parents[3] / "skills"


def default_user_skills_root() -> Path:
    return Path.home() / ".web2skill" / "skills"


def default_builtin_skills_roots() -> tuple[Path, ...]:
    repo_root = default_skills_root()
    packaged_root = Path(__file__).resolve().parents[1] / "bundled_skills"
    roots: list[Path] = []
    for root in (repo_root, packaged_root):
        if root not in roots:
            roots.append(root)
    return tuple(roots)


def load_skill_bundle(
    manifest_path: Path,
    *,
    source: LoadedSkillSource = "builtin",
) -> LoadedSkill:
    manifest = SkillManifest.model_validate(_load_yaml(manifest_path))
    bundle_root = manifest_path.parent
    skill_doc_path = manifest_path.with_name("SKILL.md")
    if skill_doc_path.exists():
        skill_markdown = skill_doc_path.read_text(encoding="utf-8")
    else:
        skill_markdown = render_skill_markdown(manifest)
    return LoadedSkill(
        manifest=manifest,
        manifest_path=manifest_path,
        bundle_root=bundle_root,
        skill_doc_path=skill_doc_path,
        skill_markdown=skill_markdown,
        source=source,
    )


def _load_yaml(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)
