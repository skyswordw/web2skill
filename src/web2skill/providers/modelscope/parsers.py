from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any, cast

from .contracts import (
    AccountProfile,
    ListModelFilesOutput,
    ModelFileEntry,
    ModelOverview,
    ModelSearchItem,
    OrganizationSummary,
    QuickstartSnippet,
    SearchModelsOutput,
)
from .selectors import BASE_URL, EMBEDDED_DETAIL_MARKER


def parse_unix_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, int) or value <= 0:
        return None
    return datetime.fromtimestamp(value, tz=UTC)


def model_slug_to_url(model_slug: str) -> str:
    return f"{BASE_URL}/models/{model_slug}"


def extract_embedded_detail_data(html: str) -> dict[str, Any]:
    marker_index = html.find(EMBEDDED_DETAIL_MARKER)
    if marker_index == -1:
        raise ValueError("ModelScope embedded detail payload not found in HTML.")

    start = marker_index + len(EMBEDDED_DETAIL_MARKER)
    end = html.find(";\n", start)
    if end == -1:
        end = html.find(";</script>", start)
    if end == -1:
        raise ValueError("Unable to determine end of embedded detail payload.")

    raw_value = html[start:end].strip()
    if not raw_value or raw_value == '""':
        raise ValueError("Embedded detail payload was empty.")
    return json.loads(json.loads(raw_value))


def _organization_from_payload(payload: dict[str, Any] | None) -> OrganizationSummary | None:
    if not payload:
        return None
    avatar = payload.get("Avatar")
    return OrganizationSummary(
        name=_as_str(payload.get("Name")),
        full_name=_as_str(payload.get("FullName")),
        avatar_url=avatar if isinstance(avatar, str) and avatar.startswith("http") else None,
    )


def _task_names(tasks: Any) -> list[str]:
    output: list[str] = []
    for task in _list_from(tasks):
        task_payload = _as_dict(task)
        if task_payload is not None:
            task_name = _as_str(task_payload.get("Name")) or _as_str(
                task_payload.get("ChineseName")
            )
            if task_name:
                output.append(task_name)
    return output


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def normalize_search_results(payload: dict[str, Any], query: str, page: int) -> SearchModelsOutput:
    data_block = _dict_from(payload.get("Data"))
    model_block = _dict_from(data_block.get("Model"))
    items: list[ModelSearchItem] = []
    raw_models = _list_from(model_block.get("Models"))
    for entry in raw_models:
        if not isinstance(entry, dict):
            continue
        model_payload = cast(dict[str, Any], entry)
        model_slug = _build_model_slug(model_payload)
        if not model_slug:
            continue
        items.append(
            ModelSearchItem(
                model_slug=model_slug,
                name=_as_str(model_payload.get("Name")) or model_slug.rsplit("/", 1)[-1],
                chinese_name=_as_str(model_payload.get("ChineseName")),
                description=_as_str(model_payload.get("Description")),
                task_names=_task_names(model_payload.get("Tasks")),
                license=_as_str(model_payload.get("License")),
                libraries=_string_list(model_payload.get("Libraries")),
                downloads=_as_int(model_payload.get("Downloads")),
                stars=_as_int(model_payload.get("Stars")),
                updated_at=parse_unix_timestamp(model_payload.get("LastUpdatedTime")),
                organization=_organization_from_payload(_as_dict(model_payload.get("Organization"))),
                model_url=model_slug_to_url(model_slug),
            )
        )
    return SearchModelsOutput(
        query=query,
        total_count=_as_int(model_block.get("TotalCount")),
        page=page,
        items=items,
    )


def normalize_model_overview(payload: dict[str, Any]) -> ModelOverview:
    model_slug = _build_model_slug(payload)
    if not model_slug:
        raise ValueError("Model payload did not include a usable model slug.")

    return ModelOverview(
        model_slug=model_slug,
        name=_as_str(payload.get("Name")) or model_slug.rsplit("/", 1)[-1],
        chinese_name=_as_str(payload.get("ChineseName")),
        headline=_as_str(payload.get("Description")),
        description=_as_str(payload.get("Description")),
        downloads=_as_int(payload.get("Downloads")),
        stars=_as_int(payload.get("Stars")),
        revision=_as_str(payload.get("Revision")),
        license=_as_str(payload.get("License")),
        tasks=_task_names(payload.get("Tasks")),
        frameworks=_string_list(payload.get("Frameworks")),
        libraries=_string_list(payload.get("Libraries")),
        languages=_string_list(payload.get("Language")),
        tags=_string_list(payload.get("Tags")),
        base_models=_string_list(payload.get("BaseModel")),
        storage_size=_as_int(payload.get("StorageSize")),
        updated_at=parse_unix_timestamp(payload.get("LastUpdatedTime")),
        organization=_organization_from_payload(payload.get("Organization")),
        readme_markdown=_as_str(payload.get("ReadMeContent")),
        model_url=model_slug_to_url(model_slug),
    )


def normalize_repo_files(
    payload: dict[str, Any], *, model_slug: str, revision: str | None
) -> ListModelFilesOutput:
    files: list[ModelFileEntry] = []
    data_block = _dict_from(payload.get("Data"))
    raw_files = _list_from(data_block.get("Files"))
    for entry in raw_files:
        if not isinstance(entry, dict):
            continue
        file_payload = cast(dict[str, Any], entry)
        files.append(
            ModelFileEntry(
                path=_as_str(file_payload.get("Path")) or _as_str(file_payload.get("Name")) or "",
                name=_as_str(file_payload.get("Name")) or "",
                file_type=_as_str(file_payload.get("Type")) or "unknown",
                size=_as_int(file_payload.get("Size")),
                revision=_as_str(file_payload.get("Revision")),
                sha256=_as_str(file_payload.get("Sha256")),
                committed_at=parse_unix_timestamp(file_payload.get("CommittedDate")),
                committer_name=_as_str(file_payload.get("CommitterName")),
                is_lfs=bool(file_payload.get("IsLFS", False)),
            )
        )
    return ListModelFilesOutput(model_slug=model_slug, revision=revision, files=files)


def extract_quickstart_from_markdown(model_slug: str, markdown: str | None) -> QuickstartSnippet:
    if not markdown:
        raise ValueError(f"Model {model_slug} did not include README markdown.")

    heading_pattern = re.compile(r"^##\s+Quickstart\s*$", re.MULTILINE)
    match = heading_pattern.search(markdown)
    if not match:
        raise ValueError(f"Quickstart section not found for model {model_slug}.")

    start = match.end()
    next_heading = re.search(r"^##\s+", markdown[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(markdown)
    section = markdown[start:end].strip()
    code_blocks = re.findall(r"```(?:[\w+-]+)?\n(.*?)```", section, re.DOTALL)
    return QuickstartSnippet(heading="Quickstart", body_markdown=section, code_blocks=code_blocks)


def normalize_account_profile(payload: dict[str, Any]) -> AccountProfile:
    data = payload.get("Data")
    source: dict[str, Any] = _as_dict(data) or payload

    organization_names: list[str] = []
    orgs = source.get("Organizations") or source.get("OrganizationList")
    for org in _list_from(orgs):
        org_payload = _as_dict(org)
        if org_payload is not None:
            name = _as_str(org_payload.get("Name")) or _as_str(org_payload.get("FullName"))
            if name:
                organization_names.append(name)

    avatar = source.get("Avatar") or source.get("AvatarUrl")
    return AccountProfile(
        user_id=_stringify(source.get("Id") or source.get("UserId")),
        username=_as_str(source.get("Name")) or _as_str(source.get("UserName")),
        nickname=_as_str(source.get("NickName")),
        display_name=_as_str(source.get("DisplayName")) or _as_str(source.get("FullName")),
        email=_as_str(source.get("Email")),
        avatar_url=avatar if isinstance(avatar, str) and avatar.startswith("http") else None,
        organization_names=organization_names,
        raw_profile=source,
    )


def _string_list(value: Any) -> list[str]:
    output: list[str] = []
    for item in _list_from(value):
        if isinstance(item, str) and item:
            output.append(item)
    return output


def _build_model_slug(payload: dict[str, Any]) -> str | None:
    path = _as_str(payload.get("Path"))
    name = _as_str(payload.get("Name"))
    if path and name:
        return f"{path}/{name}"
    return _as_str(payload.get("ModelId")) or _as_str(payload.get("model_id"))


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    return None


def _as_dict(value: Any) -> dict[str, Any] | None:
    return cast(dict[str, Any], value) if isinstance(value, dict) else None


def _dict_from(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _list_from(value: Any) -> list[Any]:
    return cast(list[Any], value) if isinstance(value, list) else []
