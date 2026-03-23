from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any, cast

from .contracts import (
    AccountProfile,
    CreateTokenOutput,
    ListModelFilesOutput,
    ListTokensOutput,
    ModelFileEntry,
    ModelOverview,
    ModelSearchItem,
    OrganizationSummary,
    QuickstartSnippet,
    SearchModelsOutput,
    TokenDetail,
    TokenSummary,
)
from .selectors import BASE_URL, EMBEDDED_DETAIL_MARKER


def parse_unix_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, int) or value <= 0:
        return None
    return datetime.fromtimestamp(value, tz=UTC)


def parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


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


def normalize_search_results(
    payload: dict[str, Any], query: str | None = None, page: int = 1
) -> list[ModelSearchItem]:
    data_block = _data_block(payload)
    model_block = _dict_from(data_block.get("Model"))
    if not model_block and isinstance(data_block.get("Models"), list):
        model_block = data_block
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
                organization=_organization_from_payload(
                    _as_dict(model_payload.get("Organization"))
                ),
                model_url=model_slug_to_url(model_slug),
            )
        )
    return items


def build_search_models_output(
    payload: dict[str, Any], *, query: str, page: int
) -> SearchModelsOutput:
    data_block = _data_block(payload)
    model_block = _dict_from(data_block.get("Model"))
    if not model_block and isinstance(data_block.get("Models"), list):
        model_block = data_block
    return SearchModelsOutput(
        query=query,
        total_count=_as_int(model_block.get("TotalCount")) or _as_int(data_block.get("Total")),
        page=page,
        items=normalize_search_results(payload, query=query, page=page),
    )


def normalize_model_overview(payload: dict[str, Any]) -> ModelOverview:
    source = _data_block(payload)
    model_slug = _build_model_slug(source)
    if not model_slug:
        raise ValueError("Model payload did not include a usable model slug.")

    return ModelOverview(
        model_slug=model_slug,
        name=_as_str(source.get("Name")) or model_slug.rsplit("/", 1)[-1],
        chinese_name=_as_str(source.get("ChineseName")),
        headline=_as_str(source.get("Summary")) or _as_str(source.get("Description")),
        description=_as_str(source.get("Description")) or _as_str(source.get("Summary")),
        downloads=_as_int(source.get("Downloads")),
        stars=_as_int(source.get("Stars")),
        revision=_as_str(source.get("Revision")),
        license=_as_str(source.get("License")),
        tasks=_task_names(source.get("Tasks")),
        frameworks=_string_list(source.get("Frameworks")),
        libraries=_string_list(source.get("Libraries")),
        languages=_string_list(source.get("Language")),
        tags=_string_list(source.get("Tags")),
        base_models=_string_list(source.get("BaseModel")),
        storage_size=_as_int(source.get("StorageSize")),
        updated_at=parse_unix_timestamp(source.get("LastUpdatedTime")),
        organization=_organization_from_payload(source.get("Organization")),
        readme_markdown=_as_str(source.get("ReadMeContent")) or _as_str(source.get("Quickstart")),
        model_url=model_slug_to_url(model_slug),
    )


def normalize_repo_files(
    payload: dict[str, Any], *, model_slug: str, revision: str | None
) -> ListModelFilesOutput:
    files: list[ModelFileEntry] = []
    data_block = _data_block(payload)
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


def normalize_model_files(payload: dict[str, Any]) -> list[ModelFileEntry]:
    normalized = normalize_repo_files(payload, model_slug=_infer_model_slug(payload), revision=None)
    return normalized.files


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


def normalize_token_list(payload: dict[str, Any]) -> ListTokensOutput:
    data = _data_block(payload)
    items: list[TokenSummary] = []
    for raw_token in _list_from(data.get("SdkTokens")):
        token_payload = _as_dict(raw_token)
        if token_payload is None:
            continue
        token_id = _as_int(token_payload.get("Id"))
        name = _as_str(token_payload.get("SdkTokenName"))
        if token_id is None or name is None:
            continue
        items.append(
            TokenSummary(
                token_id=token_id,
                name=name,
                expires_at=parse_iso_datetime(token_payload.get("ExpiresAt")),
                created_at=parse_iso_datetime(token_payload.get("GmtCreated")),
                valid=_as_boolish(token_payload.get("Valid")),
            )
        )
    return ListTokensOutput(items=items, total_count=_as_int(data.get("TotalCount")) or len(items))


def normalize_token_detail(payload: dict[str, Any], *, token_id: int) -> TokenDetail:
    data = _data_block(payload)
    for raw_token in _list_from(data.get("SdkTokens")):
        token_payload = _as_dict(raw_token)
        if token_payload is None:
            continue
        if _as_int(token_payload.get("Id")) != token_id:
            continue
        name = _as_str(token_payload.get("SdkTokenName"))
        token = _as_str(token_payload.get("SdkToken"))
        if name is None or token is None:
            break
        return TokenDetail(
            token_id=token_id,
            name=name,
            token=token,
            expires_at=parse_iso_datetime(token_payload.get("ExpiresAt")),
            created_at=parse_iso_datetime(token_payload.get("GmtCreated")),
            valid=_as_boolish(token_payload.get("Valid")),
        )
    raise ValueError(f"Token id {token_id} was not found in the authenticated token list.")


def normalize_create_token_output(payload: dict[str, Any], *, token_id: int) -> CreateTokenOutput:
    detail = normalize_token_detail(payload, token_id=token_id)
    return CreateTokenOutput(**detail.model_dump())


def normalize_created_token_response(payload: dict[str, Any]) -> CreateTokenOutput | None:
    data = _data_block(payload)
    token_id = _as_int(data.get("Id"))
    name = _as_str(data.get("SdkTokenName"))
    token = _as_str(data.get("SdkToken"))
    if token_id is None or name is None or token is None:
        return None
    return CreateTokenOutput(
        token_id=token_id,
        name=name,
        token=token,
        expires_at=parse_iso_datetime(data.get("ExpiresAt")),
        created_at=parse_iso_datetime(data.get("GmtCreated")),
        valid=_as_boolish(data.get("Valid")),
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
    if name and "/" in name:
        return name
    if path and "/" in path:
        return path
    if path and name:
        return f"{path}/{name}"
    return _as_str(payload.get("ModelId")) or _as_str(payload.get("model_id"))


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _as_boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "valid"}
    return False


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


def _data_block(payload: dict[str, Any]) -> dict[str, Any]:
    data = _dict_from(payload.get("Data"))
    return data or payload


def _infer_model_slug(payload: dict[str, Any]) -> str:
    data = _data_block(payload)
    return _build_model_slug(data) or "unknown/unknown"
