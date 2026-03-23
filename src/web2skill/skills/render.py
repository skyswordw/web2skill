from __future__ import annotations

from .manifests import CapabilityManifest, SkillManifest


def render_capability_markdown(capability: CapabilityManifest) -> str:
    lines = [
        f"## `{capability.name}`",
        "",
        capability.description,
        "",
        f"- Risk: `{capability.risk}`",
        f"- Strategy order: `{', '.join(capability.strategies)}`",
        f"- Human confirmation required: `{str(capability.requires_confirmation).lower()}`",
    ]
    if capability.prerequisites:
        lines.extend(["", "### Prerequisites", ""])
        lines.extend(f"- {item}" for item in capability.prerequisites)
    if capability.workflows:
        lines.extend(["", "### Workflow", ""])
        lines.extend(f"1. {item}" for item in capability.workflows)
    if capability.recovery:
        lines.extend(["", "### Recovery", ""])
        lines.extend(f"- {item}" for item in capability.recovery)
    if capability.human_handoff:
        lines.extend(["", "### Human Handoff", ""])
        lines.extend(f"- {item}" for item in capability.human_handoff)
    if capability.examples:
        lines.extend(["", "### Examples", ""])
        for example in capability.examples:
            lines.append(f"#### {example.name}")
            lines.append("")
            lines.append(example.description)
            if example.input is not None:
                lines.extend(["", "Input:", "```json", _pretty_json(example.input), "```"])
            if example.output is not None:
                lines.extend(["", "Output:", "```json", _pretty_json(example.output), "```"])
            lines.append("")
    return "\n".join(lines).rstrip()


def render_skill_markdown(manifest: SkillManifest) -> str:
    lines = [
        f"# {manifest.provider_display_name} Skill Pack",
        "",
        manifest.description,
        "",
        "## Provider",
        "",
        f"- Provider id: `{manifest.provider}`",
        f"- Auth mode: `{manifest.auth.mode}`",
        f"- Login required: `{str(manifest.auth.login_required).lower()}`",
    ]
    if manifest.base_url is not None:
        lines.append(f"- Base URL: `{manifest.base_url}`")
    if manifest.prerequisites:
        lines.extend(["", "## Shared Prerequisites", ""])
        lines.extend(f"- {item}" for item in manifest.prerequisites)
    if manifest.workflows:
        lines.extend(["", "## Shared Workflow", ""])
        lines.extend(f"1. {item}" for item in manifest.workflows)
    if manifest.recovery:
        lines.extend(["", "## Shared Recovery", ""])
        lines.extend(f"- {item}" for item in manifest.recovery)
    if manifest.human_handoff:
        lines.extend(["", "## Shared Human Handoff", ""])
        lines.extend(f"- {item}" for item in manifest.human_handoff)
    for capability in manifest.capabilities:
        lines.extend(["", render_capability_markdown(capability)])
    return "\n".join(lines).rstrip() + "\n"


def _pretty_json(payload: object) -> str:
    import json

    return json.dumps(payload, indent=2, sort_keys=True)
