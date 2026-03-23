from __future__ import annotations

import uuid
from typing import Any

import httpx
from pydantic import ValidationError

from web2skill.core.contracts import (
    CapabilityDescriptor as CoreCapabilityDescriptor,
)
from web2skill.core.contracts import (
    ExecutionContext,
    RiskLevel,
)
from web2skill.core.contracts import (
    SkillError as CoreSkillError,
)
from web2skill.core.contracts import (
    SkillResult as CoreSkillResult,
)
from web2skill.core.contracts import (
    Strategy as CoreStrategy,
)
from web2skill.core.sessions import SessionStore

from .contracts import (
    AccountProfile,
    CapabilityName,
    GetAccountProfileInput,
    ListModelFilesOutput,
    ModelOverview,
    ModelSlugInput,
    QuickstartSnippet,
    SearchModelsInput,
    SearchModelsOutput,
    StrategyUsed,
    TraceEvent,
)
from .contracts import (
    SkillResult as ProviderSkillResult,
)
from .login import storage_state_cookies
from .parsers import (
    build_search_models_output,
    extract_embedded_detail_data,
    extract_quickstart_from_markdown,
    normalize_account_profile,
    normalize_model_overview,
    normalize_repo_files,
)
from .selectors import (
    BASE_URL,
    LOGIN_INFO_API,
    MODEL_PAGE_URL,
    MODEL_REPO_FILES_API,
    MODEL_REVISIONS_API,
    SEARCH_MODELS_API,
)


class ModelScopeProvider:
    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        storage_state_path: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._storage_state_path = storage_state_path
        cookies = self._cookies_from_storage_state(storage_state_path)
        self._client = httpx.Client(
            base_url=BASE_URL,
            timeout=timeout_seconds,
            headers={
                "Accept": "application/json, text/html;q=0.9",
                "Content-Type": "application/json",
                "User-Agent": "web2skill-modelscope-provider/0.1.0",
            },
            cookies=cookies,
            follow_redirects=True,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ModelScopeProvider:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def invoke(self, capability_name: str, payload: dict[str, Any]) -> ProviderSkillResult[Any]:
        capability = CapabilityName(capability_name)
        handlers = {
            CapabilityName.SEARCH_MODELS: self.search_models,
            CapabilityName.GET_MODEL_OVERVIEW: self.get_model_overview,
            CapabilityName.LIST_MODEL_FILES: self.list_model_files,
            CapabilityName.GET_QUICKSTART: self.get_quickstart,
            CapabilityName.GET_ACCOUNT_PROFILE: self.get_account_profile,
        }
        return handlers[capability](payload)

    def capabilities(self) -> list[str]:
        return [capability.value for capability in CapabilityName]

    def search_models(self, payload: dict[str, Any]) -> ProviderSkillResult[SearchModelsOutput]:
        trace_id = uuid.uuid4().hex
        try:
            request = SearchModelsInput.model_validate(payload)
        except ValidationError as exc:
            return self._validation_error_result(trace_id, CapabilityName.SEARCH_MODELS, exc)

        trace = [
            TraceEvent(
                stage="request_validation",
                detail="Validated search_models input with Pydantic.",
                strategy=StrategyUsed.NETWORK,
            )
        ]

        network_payload: dict[str, object] = {
            "PageSize": 30,
            "PageNumber": request.page,
            "SortBy": self._map_sort(request.sort),
            "Target": request.task or "",
            "SingleCriterion": [],
            "Name": request.query,
            "Criterion": [],
        }
        response = self._client.request("PUT", SEARCH_MODELS_API, json=network_payload)
        response.raise_for_status()
        data = response.json()
        trace.append(
            TraceEvent(
                stage="network_fetch",
                detail=f"Fetched search results from {SEARCH_MODELS_API}.",
                strategy=StrategyUsed.NETWORK,
            )
        )
        normalized = build_search_models_output(data, query=request.query, page=request.page)
        return ProviderSkillResult(
            trace_id=trace_id,
            capability=CapabilityName.SEARCH_MODELS,
            strategy_used=StrategyUsed.NETWORK,
            requires_human=False,
            data=normalized,
            trace=trace,
        )

    def get_model_overview(self, payload: dict[str, Any]) -> ProviderSkillResult[ModelOverview]:
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

    def list_model_files(
        self, payload: dict[str, Any]
    ) -> ProviderSkillResult[ListModelFilesOutput]:
        trace_id = uuid.uuid4().hex
        try:
            request = ModelSlugInput.model_validate(payload)
        except ValidationError as exc:
            return self._validation_error_result(trace_id, CapabilityName.LIST_MODEL_FILES, exc)

        trace = [
            TraceEvent(
                stage="request_validation",
                detail="Validated list_model_files input with Pydantic.",
                strategy=StrategyUsed.NETWORK,
            )
        ]
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
        normalized = normalize_repo_files(
            files_response.json(),
            model_slug=request.model_slug,
            revision=revision,
        )
        trace.extend(
            [
                TraceEvent(
                    stage="network_fetch",
                    detail=f"Resolved current revision {revision}.",
                    strategy=StrategyUsed.NETWORK,
                ),
                TraceEvent(
                    stage="network_fetch",
                    detail="Fetched repo file listing from ModelScope API.",
                    strategy=StrategyUsed.NETWORK,
                ),
            ]
        )
        return ProviderSkillResult(
            trace_id=trace_id,
            capability=CapabilityName.LIST_MODEL_FILES,
            strategy_used=StrategyUsed.NETWORK,
            requires_human=False,
            data=normalized,
            trace=trace,
        )

    def get_quickstart(self, payload: dict[str, Any]) -> ProviderSkillResult[QuickstartSnippet]:
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
        overview = detail_result.data
        if overview is None:
            return ProviderSkillResult(
                trace_id=trace_id,
                capability=CapabilityName.GET_QUICKSTART,
                strategy_used=detail_result.strategy_used,
                requires_human=detail_result.requires_human,
                errors=detail_result.errors,
                trace=detail_result.trace,
            )

        quickstart = extract_quickstart_from_markdown(request.model_slug, overview.readme_markdown)
        trace = list(detail_result.trace)
        trace.append(
            TraceEvent(
                stage="parse_quickstart",
                detail="Extracted the Quickstart section from README markdown.",
                strategy=detail_result.strategy_used,
            )
        )
        return ProviderSkillResult(
            trace_id=trace_id,
            capability=CapabilityName.GET_QUICKSTART,
            strategy_used=detail_result.strategy_used,
            requires_human=False,
            data=quickstart,
            trace=trace,
        )

    def get_account_profile(self, payload: dict[str, Any]) -> ProviderSkillResult[AccountProfile]:
        trace_id = uuid.uuid4().hex
        try:
            GetAccountProfileInput.model_validate(payload)
        except ValidationError as exc:
            return self._validation_error_result(trace_id, CapabilityName.GET_ACCOUNT_PROFILE, exc)

        trace = [
            TraceEvent(
                stage="request_validation",
                detail="Validated get_account_profile input with Pydantic.",
                strategy=StrategyUsed.NETWORK,
            )
        ]
        response = self._client.get(LOGIN_INFO_API)
        if response.status_code == 401:
            trace.append(
                TraceEvent(
                    stage="auth_check",
                    detail=(
                        "ModelScope login info endpoint returned 401. Interactive login "
                        "or storage-state reuse is required."
                    ),
                    strategy=StrategyUsed.NETWORK,
                )
            )
            return ProviderSkillResult(
                trace_id=trace_id,
                capability=CapabilityName.GET_ACCOUNT_PROFILE,
                strategy_used=StrategyUsed.NETWORK,
                requires_human=True,
                errors=["ModelScope session is not authenticated."],
                trace=trace,
            )

        response.raise_for_status()
        profile = normalize_account_profile(response.json())
        trace.append(
            TraceEvent(
                stage="network_fetch",
                detail=f"Fetched account profile from {LOGIN_INFO_API}.",
                strategy=StrategyUsed.NETWORK,
            )
        )
        return ProviderSkillResult(
            trace_id=trace_id,
            capability=CapabilityName.GET_ACCOUNT_PROFILE,
            strategy_used=StrategyUsed.NETWORK,
            requires_human=False,
            data=profile,
            trace=trace,
        )

    def _model_detail_result(
        self,
        *,
        trace_id: str,
        capability: CapabilityName,
        model_slug: str,
    ) -> ProviderSkillResult[ModelOverview]:
        trace = [
            TraceEvent(
                stage="request_validation",
                detail=f"Validated {capability.value} input with Pydantic.",
                strategy=StrategyUsed.NETWORK,
            )
        ]
        page_url = MODEL_PAGE_URL.format(model_slug=model_slug)
        response = self._client.get(page_url)
        response.raise_for_status()
        html = response.text
        try:
            detail_payload = extract_embedded_detail_data(html)
            strategy = StrategyUsed.NETWORK
            trace.append(
                TraceEvent(
                    stage="network_fetch",
                    detail="Parsed embedded JSON detail payload from the model page.",
                    strategy=strategy,
                )
            )
        except ValueError:
            strategy = StrategyUsed.DOM
            detail_payload = self._detail_payload_from_dom(page_url)
            trace.append(
                TraceEvent(
                    stage="dom_fallback",
                    detail=(
                        "Embedded detail JSON was unavailable; fetched detail payload from "
                        "DOM script content."
                    ),
                    strategy=strategy,
                )
            )

        detail_payload.setdefault("Path", model_slug.split("/", 1)[0])
        detail_payload.setdefault("Name", model_slug.split("/", 1)[1])
        overview = normalize_model_overview(detail_payload)
        return ProviderSkillResult(
            trace_id=trace_id,
            capability=capability,
            strategy_used=strategy,
            requires_human=False,
            data=overview,
            trace=trace,
        )

    def _detail_payload_from_dom(self, page_url: str) -> dict[str, Any]:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(page_url, wait_until="networkidle", timeout=120_000)
                script_contents = page.locator("script").all_inner_texts()
                for script in script_contents:
                    if "window.__detail_data__ = " not in script:
                        continue
                    wrapper = f"<script>{script}</script>"
                    return extract_embedded_detail_data(wrapper)
            finally:
                browser.close()
        raise ValueError("ModelScope detail payload not found in DOM fallback path.")

    def _validation_error_result(
        self,
        trace_id: str,
        capability: CapabilityName,
        exc: ValidationError,
    ) -> ProviderSkillResult[Any]:
        return ProviderSkillResult(
            trace_id=trace_id,
            capability=capability,
            strategy_used=StrategyUsed.NETWORK,
            requires_human=False,
            errors=[exc.json()],
            trace=[
                TraceEvent(
                    stage="request_validation",
                    detail="Input validation failed.",
                    strategy=StrategyUsed.NETWORK,
                )
            ],
        )

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


class _ModelScopeHandler:
    def __init__(self, registry: ModelScopeRegistry, capability_name: str) -> None:
        self._registry = registry
        self._capability_name = capability_name

    def execute(self, context: ExecutionContext) -> CoreSkillResult:
        session = (
            self._registry.session_store.get(context.session_id) if context.session_id else None
        )
        storage_state_path = None
        if session is not None and session.storage_state_path is not None:
            storage_state_path = str(session.storage_state_path)

        with ModelScopeProvider(
            storage_state_path=storage_state_path,
            timeout_seconds=self._registry.timeout_seconds,
            transport=self._registry.transport,
        ) as provider:
            provider_result = provider.invoke(self._capability_name, context.payload)
        return _to_core_result(provider_result, context)


class ModelScopeRegistry:
    def __init__(
        self,
        *,
        session_store: SessionStore,
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.session_store = session_store
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def capabilities(self) -> list[str]:
        return [capability.value for capability in CapabilityName]

    def get_descriptor(self, capability_name: str) -> CoreCapabilityDescriptor:
        capability = CapabilityName(capability_name)
        descriptors = {
            CapabilityName.SEARCH_MODELS: CoreCapabilityDescriptor(
                capability_name=capability.value,
                provider_name="modelscope",
                risk_level=RiskLevel.LOW,
                supported_strategies=(CoreStrategy.NETWORK,),
                input_model=SearchModelsInput,
            ),
            CapabilityName.GET_MODEL_OVERVIEW: CoreCapabilityDescriptor(
                capability_name=capability.value,
                provider_name="modelscope",
                risk_level=RiskLevel.LOW,
                supported_strategies=(CoreStrategy.NETWORK, CoreStrategy.DOM),
                input_model=ModelSlugInput,
            ),
            CapabilityName.LIST_MODEL_FILES: CoreCapabilityDescriptor(
                capability_name=capability.value,
                provider_name="modelscope",
                risk_level=RiskLevel.LOW,
                supported_strategies=(CoreStrategy.NETWORK,),
                input_model=ModelSlugInput,
            ),
            CapabilityName.GET_QUICKSTART: CoreCapabilityDescriptor(
                capability_name=capability.value,
                provider_name="modelscope",
                risk_level=RiskLevel.LOW,
                supported_strategies=(CoreStrategy.NETWORK, CoreStrategy.DOM),
                input_model=ModelSlugInput,
            ),
            CapabilityName.GET_ACCOUNT_PROFILE: CoreCapabilityDescriptor(
                capability_name=capability.value,
                provider_name="modelscope",
                risk_level=RiskLevel.LOW,
                supported_strategies=(CoreStrategy.NETWORK,),
                input_model=GetAccountProfileInput,
            ),
        }
        return descriptors[capability]

    def get_handler(self, capability_name: str) -> _ModelScopeHandler:
        return _ModelScopeHandler(self, capability_name)

    def resolve(self, capability_name: str) -> _ModelScopeHandler:
        return self.get_handler(capability_name)


def _to_core_result(
    provider_result: ProviderSkillResult[Any], context: ExecutionContext
) -> CoreSkillResult:
    output: dict[str, Any] | list[Any] | str | int | float | bool | None
    if provider_result.data is None:
        output = None
    elif hasattr(provider_result.data, "model_dump"):
        output = provider_result.data.model_dump(mode="json")
    else:
        output = provider_result.data

    errors = tuple(
        CoreSkillError(code="provider_error", message=message, retriable=False)
        for message in provider_result.errors
    )
    return CoreSkillResult(
        trace_id=provider_result.trace_id,
        capability_name=context.capability_name,
        strategy_used=_to_core_strategy(provider_result.strategy_used),
        requires_human=provider_result.requires_human,
        output=output,
        errors=errors,
        session_id=context.session_id,
        metadata={"provider": "modelscope"},
    )


def _to_core_strategy(strategy: StrategyUsed) -> CoreStrategy:
    mapping = {
        StrategyUsed.NETWORK: CoreStrategy.NETWORK,
        StrategyUsed.DOM: CoreStrategy.DOM,
        StrategyUsed.GUIDED_UI: CoreStrategy.GUIDED_UI,
    }
    return mapping[strategy]
