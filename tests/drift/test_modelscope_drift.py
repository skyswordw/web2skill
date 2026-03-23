from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

pytestmark = pytest.mark.drift
FixtureLoader = Callable[[str], dict[str, Any]]


def test_search_models_fixture_keeps_expected_shape(load_fixture: FixtureLoader) -> None:
    payload = load_fixture("modelscope/search_models.json")

    assert payload["Success"] is True
    assert isinstance(payload["Data"]["Models"], list)
    assert {"Name", "Path", "Task", "Downloads", "Likes"} <= set(payload["Data"]["Models"][0])


def test_model_overview_fixture_keeps_expected_shape(load_fixture: FixtureLoader) -> None:
    payload = load_fixture("modelscope/model_overview.json")

    assert payload["Success"] is True
    assert {"Path", "Name", "Summary", "License", "Tags"} <= set(payload["Data"])


def test_model_files_fixture_keeps_expected_shape(load_fixture: FixtureLoader) -> None:
    payload = load_fixture("modelscope/model_files.json")

    assert payload["Success"] is True
    assert {"Path", "Size"} <= set(payload["Data"]["Files"][0])


def test_token_list_fixture_keeps_expected_shape(load_fixture: FixtureLoader) -> None:
    payload = load_fixture("modelscope/token_list.json")

    assert payload["Success"] is True
    assert {"Id", "SdkToken", "SdkTokenName", "ExpiresAt", "GmtCreated", "Valid"} <= set(
        payload["Data"]["SdkTokens"][0]
    )


@pytest.mark.live
def test_live_environment_declares_drift_anchor_inputs(
    require_live: None,
    modelscope_known_slug: str,
) -> None:
    assert modelscope_known_slug


@pytest.mark.live
def test_live_token_page_exposes_create_dialog_anchors(
    require_live: None,
    modelscope_storage_state_path: Path | None,
) -> None:
    if modelscope_storage_state_path is None:
        pytest.skip("live token drift coverage requires WEB2SKILL_MODELSCOPE_STORAGE_STATE")

    raw_state_object = json.loads(modelscope_storage_state_path.read_text(encoding="utf-8"))
    if not isinstance(raw_state_object, dict):
        pytest.skip("configured ModelScope storage state could not be loaded")
    raw_state = cast(dict[str, Any], raw_state_object)
    state = _normalize_storage_state(raw_state)

    playwright_module = pytest.importorskip(
        "playwright.sync_api",
        reason="Playwright must be installed for live DOM drift coverage",
    )
    with playwright_module.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(storage_state=state)
        page = context.new_page()
        try:
            page.goto(
                "https://www.modelscope.cn/my/access/token",
                wait_until="networkidle",
                timeout=120_000,
            )
            page.get_by_role("button", name="Create Your Token").click()
            dialog = page.locator('[role="dialog"]')
            assert dialog.locator("#TokenName").is_visible()
            assert dialog.get_by_text("Token validity").is_visible()
            assert dialog.get_by_role("button", name="Create Token").is_visible()
        finally:
            browser.close()


def _normalize_storage_state(raw_state: dict[str, Any]) -> dict[str, Any]:
    cookies = raw_state.get("cookies")
    raw_cookies: list[object] = cast(list[object], cookies) if isinstance(cookies, list) else []
    normalized_cookies: list[dict[str, Any]] = []
    for raw_cookie in raw_cookies:
        if not isinstance(raw_cookie, dict):
            continue
        cookie = dict(cast(dict[str, Any], raw_cookie))
        cookie["secure"] = bool(cookie.get("secure"))
        cookie["httpOnly"] = bool(cookie.get("httpOnly"))
        same_site = cookie.get("sameSite")
        if same_site not in {"Lax", "None", "Strict"}:
            cookie["sameSite"] = "Lax"
        normalized_cookies.append(cookie)

    origins = raw_state.get("origins")
    normalized_origins: list[object] = (
        cast(list[object], origins) if isinstance(origins, list) else []
    )
    return {
        "cookies": normalized_cookies,
        "origins": normalized_origins,
    }
