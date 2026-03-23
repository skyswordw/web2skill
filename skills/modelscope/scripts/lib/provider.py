# ruff: noqa: E501

from __future__ import annotations

import os
import uuid
from typing import Any, cast

import httpx
from pydantic import ValidationError

from .contracts import (
    AccountProfile,
    CapabilityName,
    CreateTokenInput,
    CreateTokenOutput,
    GetAccountProfileInput,
    GetTokenInput,
    ListModelFilesOutput,
    ListTokensInput,
    ListTokensOutput,
    ModelOverview,
    ModelSlugInput,
    QuickstartSnippet,
    SearchModelsInput,
    SearchModelsOutput,
    SkillResult,
    StrategyUsed,
    TokenDetail,
    TraceEvent,
)
from .login import storage_state_cookies
from .parsers import (
    build_search_models_output,
    extract_embedded_detail_data,
    extract_quickstart_from_markdown,
    normalize_account_profile,
    normalize_create_token_output,
    normalize_created_token_response,
    normalize_model_overview,
    normalize_repo_files,
    normalize_token_detail,
    normalize_token_list,
)
from .selectors import (
    BASE_URL,
    LOGIN_INFO_API,
    MODEL_PAGE_URL,
    MODEL_REPO_FILES_API,
    MODEL_REVISIONS_API,
    SEARCH_MODELS_API,
    TOKEN_CREATE_API,
    TOKEN_LIST_API,
)


class ModelScopeBundle:
    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        storage_state_path: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._storage_state_path = storage_state_path
        self._client = httpx.Client(
            base_url=BASE_URL,
            timeout=timeout_seconds,
            headers={
                "Accept": "application/json, text/html;q=0.9",
                "Content-Type": "application/json",
                "User-Agent": "web2skill-modelscope-bundle/0.1.0",
            },
            cookies=self._cookies_from_storage_state(storage_state_path),
            follow_redirects=True,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ModelScopeBundle:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def search_models(self, payload: dict[str, Any]) -> SkillResult[SearchModelsOutput]:
        trace_id = uuid.uuid4().hex
        try:
            request = SearchModelsInput.model_validate(payload)
        except ValidationError as exc:
            return self._validation_error_result(trace_id, CapabilityName.SEARCH_MODELS, exc)
        trace = [self._trace("request_validation", "Validated search_models input with Pydantic.")]
        response = self._client.request(
            "PUT",
            SEARCH_MODELS_API,
            json={
                "PageSize": 30,
                "PageNumber": request.page,
                "SortBy": self._map_sort(request.sort),
                "Target": request.task or "",
                "SingleCriterion": [],
                "Name": request.query,
                "Criterion": [],
            },
        )
        response.raise_for_status()
        trace.append(self._trace("network_fetch", f"Fetched search results from {SEARCH_MODELS_API}."))
        return SkillResult(
            trace_id=trace_id,
            capability=CapabilityName.SEARCH_MODELS.value,
            strategy_used=StrategyUsed.NETWORK,
            requires_human=False,
            data=build_search_models_output(response.json(), query=request.query, page=request.page),
            trace=trace,
        )

    def get_model_overview(self, payload: dict[str, Any]) -> SkillResult[ModelOverview]:
        trace_id = uuid.uuid4().hex
        try:
            request = ModelSlugInput.model_validate(payload)
        except ValidationError as exc:
            return self._validation_error_result(trace_id, CapabilityName.GET_MODEL_OVERVIEW, exc)
        return self._model_detail_result(
            trace_id=trace_id,
            capability=CapabilityName.GET_MODEL_OVERVIEW,
            model_slug=request.model_slug,
        )

    def list_model_files(self, payload: dict[str, Any]) -> SkillResult[ListModelFilesOutput]:
        trace_id = uuid.uuid4().hex
        try:
            request = ModelSlugInput.model_validate(payload)
        except ValidationError as exc:
            return self._validation_error_result(trace_id, CapabilityName.LIST_MODEL_FILES, exc)
        trace = [self._trace("request_validation", "Validated list_model_files input with Pydantic.")]
        revisions = self._client.get(MODEL_REVISIONS_API.format(model_slug=request.model_slug))
        revisions.raise_for_status()
        revisions_payload = revisions.json()
        revision = (
            revisions_payload.get("Data", {})
            .get("RevisionMap", {})
            .get("Branches", [{}])[0]
            .get("Revision", "master")
        )
        files_response = self._client.get(
            MODEL_REPO_FILES_API.format(model_slug=request.model_slug),
            params={"Revision": revision, "Root": ""},
        )
        files_response.raise_for_status()
        trace.append(self._trace("network_fetch", f"Resolved current revision {revision}."))
        trace.append(self._trace("network_fetch", "Fetched repo file listing from ModelScope API."))
        return SkillResult(
            trace_id=trace_id,
            capability=CapabilityName.LIST_MODEL_FILES.value,
            strategy_used=StrategyUsed.NETWORK,
            requires_human=False,
            data=normalize_repo_files(
                files_response.json(),
                model_slug=request.model_slug,
                revision=revision,
            ),
            trace=trace,
        )

    def get_quickstart(self, payload: dict[str, Any]) -> SkillResult[QuickstartSnippet]:
        trace_id = uuid.uuid4().hex
        try:
            request = ModelSlugInput.model_validate(payload)
        except ValidationError as exc:
            return self._validation_error_result(trace_id, CapabilityName.GET_QUICKSTART, exc)
        detail_result = self._model_detail_result(
            trace_id=trace_id,
            capability=CapabilityName.GET_QUICKSTART,
            model_slug=request.model_slug,
        )
        if detail_result.data is None:
            return SkillResult(
                trace_id=trace_id,
                capability=CapabilityName.GET_QUICKSTART.value,
                strategy_used=detail_result.strategy_used,
                requires_human=detail_result.requires_human,
                errors=detail_result.errors,
                trace=detail_result.trace,
            )
        quickstart = extract_quickstart_from_markdown(request.model_slug, detail_result.data.readme_markdown)
        trace = list(detail_result.trace)
        trace.append(self._trace("parse_quickstart", "Extracted the Quickstart section from README markdown.", detail_result.strategy_used))
        return SkillResult(
            trace_id=trace_id,
            capability=CapabilityName.GET_QUICKSTART.value,
            strategy_used=detail_result.strategy_used,
            requires_human=False,
            data=quickstart,
            trace=trace,
        )

    def get_account_profile(self, payload: dict[str, Any]) -> SkillResult[AccountProfile]:
        trace_id = uuid.uuid4().hex
        try:
            GetAccountProfileInput.model_validate(payload)
        except ValidationError as exc:
            return self._validation_error_result(trace_id, CapabilityName.GET_ACCOUNT_PROFILE, exc)
        trace = [self._trace("request_validation", "Validated get_account_profile input with Pydantic.")]
        response = self._client.get(LOGIN_INFO_API)
        if response.status_code == 401:
            trace.append(self._trace("auth_check", "ModelScope login info endpoint returned 401. Interactive login or storage-state reuse is required."))
            return SkillResult(
                trace_id=trace_id,
                capability=CapabilityName.GET_ACCOUNT_PROFILE.value,
                strategy_used=StrategyUsed.NETWORK,
                requires_human=True,
                errors=["ModelScope session is not authenticated."],
                trace=trace,
            )
        response.raise_for_status()
        trace.append(self._trace("network_fetch", f"Fetched account profile from {LOGIN_INFO_API}."))
        return SkillResult(
            trace_id=trace_id,
            capability=CapabilityName.GET_ACCOUNT_PROFILE.value,
            strategy_used=StrategyUsed.NETWORK,
            requires_human=False,
            data=normalize_account_profile(response.json()),
            trace=trace,
        )

    def list_tokens(self, payload: dict[str, Any]) -> SkillResult[ListTokensOutput]:
        trace_id = uuid.uuid4().hex
        try:
            ListTokensInput.model_validate(payload)
        except ValidationError as exc:
            return self._validation_error_result(trace_id, CapabilityName.LIST_TOKENS, exc)
        trace = [self._trace("request_validation", "Validated list_tokens input with Pydantic.")]
        response = self._client.get(TOKEN_LIST_API)
        if response.status_code == 401:
            return self._unauthenticated_result(trace_id=trace_id, capability=CapabilityName.LIST_TOKENS, trace=trace)
        response.raise_for_status()
        trace.append(self._trace("network_fetch", f"Fetched token metadata from {TOKEN_LIST_API}."))
        return SkillResult(
            trace_id=trace_id,
            capability=CapabilityName.LIST_TOKENS.value,
            strategy_used=StrategyUsed.NETWORK,
            requires_human=False,
            data=normalize_token_list(response.json()),
            trace=trace,
        )

    def get_token(self, payload: dict[str, Any]) -> SkillResult[TokenDetail]:
        trace_id = uuid.uuid4().hex
        try:
            request = GetTokenInput.model_validate(payload)
        except ValidationError as exc:
            return self._validation_error_result(trace_id, CapabilityName.GET_TOKEN, exc)
        trace = [self._trace("request_validation", "Validated get_token input with Pydantic.")]
        if not request.confirm_reveal:
            trace.append(self._trace("confirmation_required", "Explicit confirmation is required before revealing a raw token."))
            return SkillResult(
                trace_id=trace_id,
                capability=CapabilityName.GET_TOKEN.value,
                strategy_used=StrategyUsed.NETWORK,
                requires_human=True,
                errors=["Explicit confirmation is required before revealing a raw token."],
                trace=trace,
            )
        response = self._client.get(TOKEN_LIST_API)
        if response.status_code == 401:
            return self._unauthenticated_result(trace_id=trace_id, capability=CapabilityName.GET_TOKEN, trace=trace)
        response.raise_for_status()
        try:
            detail = normalize_token_detail(response.json(), token_id=request.token_id)
        except ValueError as exc:
            return SkillResult(
                trace_id=trace_id,
                capability=CapabilityName.GET_TOKEN.value,
                strategy_used=StrategyUsed.NETWORK,
                requires_human=False,
                errors=[str(exc)],
                trace=trace,
            )
        trace.append(self._trace("network_fetch", f"Fetched token record {request.token_id} from {TOKEN_LIST_API}."))
        return SkillResult(
            trace_id=trace_id,
            capability=CapabilityName.GET_TOKEN.value,
            strategy_used=StrategyUsed.NETWORK,
            requires_human=False,
            data=detail,
            trace=trace,
        )

    def create_token(self, payload: dict[str, Any]) -> SkillResult[CreateTokenOutput]:
        trace_id = uuid.uuid4().hex
        try:
            request = CreateTokenInput.model_validate(payload)
        except ValidationError as exc:
            return self._validation_error_result(trace_id, CapabilityName.CREATE_TOKEN, exc)
        trace = [self._trace("request_validation", "Validated create_token input with Pydantic.")]
        if not request.confirm_create:
            trace.append(self._trace("confirmation_required", "Explicit confirmation is required before creating a token."))
            return SkillResult(
                trace_id=trace_id,
                capability=CapabilityName.CREATE_TOKEN.value,
                strategy_used=StrategyUsed.NETWORK,
                requires_human=True,
                errors=["Explicit confirmation is required before creating a token."],
                trace=trace,
            )
        before_response = self._client.get(TOKEN_LIST_API)
        if before_response.status_code == 401:
            return self._unauthenticated_result(trace_id=trace_id, capability=CapabilityName.CREATE_TOKEN, trace=trace)
        before_response.raise_for_status()
        before_payload = before_response.json()
        trace.append(self._trace("network_fetch", "Fetched current token metadata before creation to compute the create diff."))
        request_payload: dict[str, object] = {"TokenName": request.name}
        if request.validity.value == "permanent":
            request_payload["ExpireMonths"] = 1200
        create_response = self._client.post(TOKEN_CREATE_API, json=request_payload)
        if create_response.status_code == 401:
            return self._unauthenticated_result(trace_id=trace_id, capability=CapabilityName.CREATE_TOKEN, trace=trace)
        create_payload = self._response_json_dict(create_response)
        if create_response.is_error or not self._response_is_success(create_response, create_payload):
            trace.append(self._trace("network_error", f"ModelScope token creation request failed at {TOKEN_CREATE_API}."))
            return SkillResult(
                trace_id=trace_id,
                capability=CapabilityName.CREATE_TOKEN.value,
                strategy_used=StrategyUsed.NETWORK,
                requires_human=False,
                errors=self._response_error_messages(create_response, create_payload),
                trace=trace,
            )
        trace.append(self._trace("network_mutation", "Submitted the authenticated create-token request to ModelScope."))
        after_response = self._client.get(TOKEN_LIST_API)
        if after_response.status_code == 401:
            return self._unauthenticated_result(trace_id=trace_id, capability=CapabilityName.CREATE_TOKEN, trace=trace)
        after_response.raise_for_status()
        after_payload = after_response.json()
        trace.append(self._trace("network_fetch", "Fetched refreshed token metadata after creation to resolve the created token."))
        try:
            created_token = self._resolve_created_token(
                before_payload=before_payload,
                after_payload=after_payload,
                create_payload=create_payload,
                requested_name=request.name,
            )
        except ValueError as exc:
            return SkillResult(
                trace_id=trace_id,
                capability=CapabilityName.CREATE_TOKEN.value,
                strategy_used=StrategyUsed.NETWORK,
                requires_human=False,
                errors=[str(exc)],
                trace=trace,
            )
        trace.append(self._trace("create_token", "Resolved the newly created token from the refreshed authenticated token list."))
        return SkillResult(
            trace_id=trace_id,
            capability=CapabilityName.CREATE_TOKEN.value,
            strategy_used=StrategyUsed.NETWORK,
            requires_human=False,
            data=created_token,
            trace=trace,
        )

    def _model_detail_result(
        self,
        *,
        trace_id: str,
        capability: CapabilityName,
        model_slug: str,
    ) -> SkillResult[ModelOverview]:
        trace = [self._trace("request_validation", f"Validated {capability.value} input with Pydantic.")]
        page_url = MODEL_PAGE_URL.format(model_slug=model_slug)
        response = self._client.get(page_url)
        response.raise_for_status()
        try:
            detail_payload = extract_embedded_detail_data(response.text)
            strategy = StrategyUsed.NETWORK
            trace.append(self._trace("network_fetch", "Parsed embedded JSON detail payload from the model page.", strategy))
        except ValueError:
            strategy = StrategyUsed.DOM
            detail_payload = self._detail_payload_from_dom(page_url)
            trace.append(self._trace("dom_fallback", "Embedded detail JSON was unavailable; fetched detail payload from DOM script content.", strategy))
        if "/" not in model_slug:
            inferred_path, inferred_name = model_slug, model_slug
        else:
            inferred_path, inferred_name = model_slug.split("/", 1)
        detail_payload.setdefault("Path", inferred_path)
        detail_payload.setdefault("Name", inferred_name)
        return SkillResult(
            trace_id=trace_id,
            capability=capability.value,
            strategy_used=strategy,
            requires_human=False,
            data=normalize_model_overview(detail_payload),
            trace=trace,
        )

    def _detail_payload_from_dom(self, page_url: str) -> dict[str, Any]:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(page_url, wait_until="networkidle", timeout=120_000)
                for script in page.locator("script").all_inner_texts():
                    if "window.__detail_data__ = " in script:
                        return extract_embedded_detail_data(f"<script>{script}</script>")
            finally:
                browser.close()
        raise ValueError("ModelScope detail payload not found in DOM fallback path.")

    def _validation_error_result(
        self,
        trace_id: str,
        capability: CapabilityName,
        exc: ValidationError,
    ) -> SkillResult[Any]:
        return SkillResult(
            trace_id=trace_id,
            capability=capability.value,
            strategy_used=StrategyUsed.NETWORK,
            requires_human=False,
            errors=[exc.json()],
            trace=[self._trace("request_validation", "Input validation failed.")],
        )

    def _unauthenticated_result(
        self,
        *,
        trace_id: str,
        capability: CapabilityName,
        trace: list[TraceEvent],
    ) -> SkillResult[Any]:
        trace.append(self._trace("auth_check", "ModelScope session is not authenticated for this token-management request."))
        return SkillResult(
            trace_id=trace_id,
            capability=capability.value,
            strategy_used=StrategyUsed.NETWORK,
            requires_human=True,
            errors=["ModelScope session is not authenticated."],
            trace=trace,
        )

    def _resolve_created_token(
        self,
        *,
        before_payload: dict[str, Any],
        after_payload: dict[str, Any],
        create_payload: dict[str, Any] | None,
        requested_name: str,
    ) -> CreateTokenOutput:
        before_ids = {item.token_id for item in normalize_token_list(before_payload).items}
        after_list = normalize_token_list(after_payload)
        after_ids = {item.token_id for item in after_list.items}
        new_ids = after_ids - before_ids
        if len(new_ids) == 1:
            return normalize_create_token_output(after_payload, token_id=next(iter(new_ids)))
        matching_new_ids = [
            token_id
            for token_id in new_ids
            if self._token_name(after_payload, token_id=token_id) == requested_name
        ]
        if matching_new_ids:
            return normalize_create_token_output(after_payload, token_id=max(matching_new_ids))
        direct_output = normalize_created_token_response(create_payload) if create_payload is not None else None
        if direct_output is not None:
            return direct_output
        matching_existing = [
            item.token_id for item in after_list.items if item.name == requested_name
        ]
        if matching_existing:
            return normalize_create_token_output(after_payload, token_id=max(matching_existing))
        raise ValueError(
            "ModelScope reported token creation success, but the created token could not be resolved from the refreshed token list."
        )

    def _token_name(self, payload: dict[str, Any], *, token_id: int) -> str | None:
        try:
            return normalize_token_detail(payload, token_id=token_id).name
        except ValueError:
            return None

    def _cookies_from_storage_state(self, path: str | None) -> dict[str, str]:
        cookie_map: dict[str, str] = {}
        for cookie in storage_state_cookies(path):
            domain = cookie.get("domain")
            if isinstance(domain, str) and "modelscope.cn" not in domain:
                continue
            name = cookie.get("name")
            value = cookie.get("value")
            if isinstance(name, str) and isinstance(value, str):
                cookie_map[name] = value
        return cookie_map

    def _map_sort(self, sort: str) -> str:
        normalized = sort.lower()
        if normalized in {"relevance", "default"}:
            return "Default"
        if normalized in {"downloads", "download"}:
            return "DownloadCount"
        if normalized in {"stars", "star"}:
            return "StarCount"
        if normalized in {"updated", "recent", "latest"}:
            return "GmtModified"
        return sort

    def _response_json_dict(self, response: httpx.Response) -> dict[str, Any] | None:
        try:
            payload = response.json()
        except ValueError:
            return None
        return cast(dict[str, Any], payload) if isinstance(payload, dict) else None

    def _response_is_success(
        self,
        response: httpx.Response,
        payload: dict[str, Any] | None,
    ) -> bool:
        if not response.is_success:
            return False
        if payload is None:
            return True
        if payload.get("Success") is False:
            return False
        code = payload.get("Code")
        return not (isinstance(code, int) and code >= 400)

    def _response_error_messages(
        self,
        response: httpx.Response,
        payload: dict[str, Any] | None,
    ) -> list[str]:
        if payload is not None:
            message = payload.get("Message")
            if isinstance(message, str) and message:
                return [message]
        return [f"ModelScope API request failed with status {response.status_code}."]

    def _trace(
        self,
        stage: str,
        detail: str,
        strategy: StrategyUsed = StrategyUsed.NETWORK,
    ) -> TraceEvent:
        return TraceEvent(stage=stage, detail=detail, strategy=strategy)


def resolve_storage_state_path_from_request(request: dict[str, Any]) -> str | None:
    metadata = request.get("metadata")
    if isinstance(metadata, dict):
        for key in ("storage_state_path", "modelscope_storage_state_path"):
            value = metadata.get(key)
            if isinstance(value, str) and value:
                return value
        session = metadata.get("session")
        if isinstance(session, dict):
            value = session.get("storage_state_path")
            if isinstance(value, str) and value:
                return value
    session = request.get("session")
    if isinstance(session, dict):
        value = session.get("storage_state_path")
        if isinstance(value, str) and value:
            return value
    for key in ("storage_state_path",):
        value = request.get(key)
        if isinstance(value, str) and value:
            return value
    return (
        os.getenv("WEB2SKILL_MODELSCOPE_STORAGE_STATE_PATH")
        or os.getenv("WEB2SKILL_STORAGE_STATE_PATH")
        or None
    )
