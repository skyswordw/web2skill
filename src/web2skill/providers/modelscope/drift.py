from typing import cast

import httpx
from playwright.sync_api import sync_playwright

from .contracts import DriftProbe, DriftProbeKind
from .selectors import (
    LOGIN_INFO_API,
    MODEL_DETAIL_SELECTORS,
    MODEL_DETAIL_TABS,
    MODEL_FILES_PAGE_URL,
    MODEL_REPO_FILES_API,
    MODEL_SEARCH_PAGE_URL,
    SEARCH_MODELS_API,
    SEARCH_PAGE_QUERY_INPUT,
)

DEFAULT_MODEL_SLUG = "Qwen/Qwen2.5-7B-Instruct"


def default_drift_probes(model_slug: str = DEFAULT_MODEL_SLUG) -> list[DriftProbe]:
    return [
        DriftProbe(
            name="search_models_api_shape",
            kind=DriftProbeKind.API,
            target=SEARCH_MODELS_API,
            expectation="JSON response contains Data.Model.Models[].Path and Name.",
        ),
        DriftProbe(
            name="repo_files_api_shape",
            kind=DriftProbeKind.API,
            target=MODEL_REPO_FILES_API.format(model_slug=model_slug),
            expectation="JSON response contains Data.Files[].Path, Name, Type, and Revision.",
        ),
        DriftProbe(
            name="login_info_endpoint",
            kind=DriftProbeKind.API,
            target=LOGIN_INFO_API,
            expectation=(
                "Unauthenticated responses should still be structured JSON with Code and Success."
            ),
        ),
        DriftProbe(
            name="search_page_query_input",
            kind=DriftProbeKind.DOM,
            target=MODEL_SEARCH_PAGE_URL,
            expectation=f"Page contains selector {SEARCH_PAGE_QUERY_INPUT}.",
        ),
        DriftProbe(
            name="model_detail_tabs",
            kind=DriftProbeKind.DOM,
            target=MODEL_FILES_PAGE_URL.format(model_slug=model_slug),
            expectation="Page contains the standard detail tabs and login button.",
        ),
    ]


def run_api_probe(client: httpx.Client, probe: DriftProbe) -> tuple[bool, str]:
    response = client.get(probe.target)
    if response.status_code >= 400 and probe.target != LOGIN_INFO_API:
        return False, f"{probe.name}: unexpected HTTP {response.status_code}"

    payload = response.json()
    if probe.target == LOGIN_INFO_API:
        if not isinstance(payload, dict):
            return False, f"{probe.name}: login info response was not a JSON object"
        payload_dict = cast(dict[str, object], payload)
        ok = "Code" in payload_dict and "Success" in payload_dict
        keys = [str(key) for key in payload_dict]
        keys.sort()
        return ok, f"{probe.name}: login info payload keys -> {keys}"

    if not isinstance(payload, dict):
        return False, f"{probe.name}: response was not a JSON object"
    payload_dict = cast(dict[str, object], payload)
    data = _dict_from(payload_dict.get("Data"))

    if "/repo/files" in probe.target:
        files = _list_from(data.get("Files"))
        ok = bool(files)
        count = len(files)
        return ok, f"{probe.name}: files count -> {count}"

    model_block = _dict_from(data.get("Model"))
    models = _list_from(model_block.get("Models"))
    ok = True
    count = len(models)
    return ok, f"{probe.name}: models count -> {count}"


def run_dom_probe(probe: DriftProbe) -> tuple[bool, str]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(probe.target, wait_until="networkidle", timeout=120_000)
            if probe.name == "search_page_query_input":
                count = page.locator(SEARCH_PAGE_QUERY_INPUT).count()
                return count > 0, f"{probe.name}: found {count} matching search inputs"

            tabs_present = [page.locator(selector).count() > 0 for selector in MODEL_DETAIL_TABS]
            login_present = page.locator(MODEL_DETAIL_SELECTORS.login_button).count() > 0
            return all(tabs_present) and login_present, (
                f"{probe.name}: tabs={tabs_present}, login_button={login_present}"
            )
        finally:
            browser.close()


def _dict_from(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _list_from(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []
