import json
import time
import uuid
from pathlib import Path
from typing import Any, cast

from playwright.sync_api import Browser, BrowserContext, Playwright, sync_playwright

from .contracts import LoginBootstrapResult
from .selectors import LOGIN_INFO_API, MODEL_DETAIL_SELECTORS, MODEL_FILES_PAGE_URL

DEFAULT_STORAGE_STATE_PATH = Path(".web2skill") / "modelscope-storage-state.json"


def resolve_storage_state_path(path: str | Path | None = None) -> Path:
    candidate = Path(path) if path is not None else DEFAULT_STORAGE_STATE_PATH
    return candidate.expanduser().resolve()


def load_storage_state(path: str | Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    resolved = resolve_storage_state_path(path)
    if not resolved.exists():
        return None
    return json.loads(resolved.read_text(encoding="utf-8"))


def storage_state_cookies(path: str | Path | None) -> list[dict[str, Any]]:
    state = load_storage_state(path)
    if not state:
        return []
    cookies = state.get("cookies")
    if not isinstance(cookies, list):
        return []
    cookie_items = cast(list[object], cookies)
    output: list[dict[str, Any]] = []
    for raw_cookie in cookie_items:
        if isinstance(raw_cookie, dict):
            output.append(cast(dict[str, Any], raw_cookie))
    return output


def create_browser_context(
    playwright: Playwright,
    *,
    headless: bool,
    storage_state_path: str | Path | None = None,
) -> tuple[Browser, BrowserContext]:
    browser = playwright.chromium.launch(headless=headless)
    storage_state: str | None = None
    if storage_state_path is not None:
        resolved = resolve_storage_state_path(storage_state_path)
        if resolved.exists():
            storage_state = str(resolved)
    context = browser.new_context(storage_state=storage_state)
    return browser, context


def save_storage_state(context: BrowserContext, path: str | Path | None = None) -> Path:
    resolved = resolve_storage_state_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(resolved))
    return resolved


def login_info_response_is_authenticated(payload: dict[str, Any]) -> bool:
    if payload.get("Success") is True and payload.get("Data"):
        return True
    code = payload.get("Code")
    return isinstance(code, int) and code == 200


def bootstrap_interactive_login(
    *,
    storage_state_path: str | Path | None = None,
    entry_model_slug: str = "Qwen/Qwen2.5-7B-Instruct",
    timeout_seconds: int = 300,
) -> LoginBootstrapResult:
    trace_id = uuid.uuid4().hex
    target_path = resolve_storage_state_path(storage_state_path)
    model_url = MODEL_FILES_PAGE_URL.format(model_slug=entry_model_slug)

    with sync_playwright() as playwright:
        browser, context = create_browser_context(
            playwright,
            headless=False,
            storage_state_path=None,
        )
        try:
            page = context.new_page()
            authenticated = False

            def _capture_login_response(response: Any) -> None:
                nonlocal authenticated
                if response.url != LOGIN_INFO_API:
                    return
                if response.status != 200:
                    return
                payload = response.json()
                if login_info_response_is_authenticated(payload):
                    authenticated = True

            page.on("response", _capture_login_response)
            page.goto(model_url, wait_until="networkidle", timeout=120_000)
            page.locator(MODEL_DETAIL_SELECTORS.login_button).click()
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline and not authenticated:
                page.wait_for_timeout(1_000)
                try:
                    response = context.request.get(LOGIN_INFO_API)
                except Exception:
                    continue
                if response.status == 200 and login_info_response_is_authenticated(response.json()):
                    authenticated = True
                    break

            if authenticated:
                save_storage_state(context, target_path)
                message = (
                    "Authenticated ModelScope storage state captured. "
                    "Reuse this file for future provider sessions."
                )
            else:
                message = (
                    "Timed out waiting for interactive login. "
                    "The browser was available for manual completion, but no authenticated "
                    "session was detected."
                )

            return LoginBootstrapResult(
                trace_id=trace_id,
                storage_state_path=str(target_path),
                authenticated=authenticated,
                message=message,
            )
        finally:
            context.close()
            browser.close()


def doctor_storage_state(path: str | Path | None) -> tuple[bool, str]:
    resolved = resolve_storage_state_path(path)
    state = load_storage_state(resolved)
    if state is None:
        return False, f"No ModelScope storage state found at {resolved}."
    if not storage_state_cookies(resolved):
        return False, f"Storage state at {resolved} did not include any cookies."
    return True, f"Storage state at {resolved} is present and includes cookies."
