from __future__ import annotations

import json
import os
import time
import uuid
from http.cookiejar import Cookie
from pathlib import Path
from typing import Any, cast

import httpx

from .contracts import LoginBootstrapResult
from .selectors import LOGIN_INFO_API, MODEL_DETAIL_SELECTORS, MODEL_FILES_PAGE_URL

DEFAULT_STORAGE_STATE_PATH = Path(".web2skill") / "modelscope-storage-state.json"
DEFAULT_BROWSER_PROFILE_PATH = Path(".web2skill") / "modelscope-login-profile"
PREFERRED_BROWSER_CHANNELS = ("chrome", "msedge")
SUPPORTED_BROWSER_IMPORTS = {
    "auto": "load",
    "chrome": "chrome",
    "chromium": "chromium",
    "edge": "edge",
    "safari": "safari",
}


def resolve_storage_state_path(path: str | Path | None = None) -> Path:
    candidate = (
        path
        or os.getenv("WEB2SKILL_MODELSCOPE_STORAGE_STATE_PATH")
        or os.getenv("WEB2SKILL_STORAGE_STATE_PATH")
        or DEFAULT_STORAGE_STATE_PATH
    )
    return Path(candidate).expanduser().resolve()


def resolve_browser_profile_path(path: str | Path | None = None) -> Path:
    candidate = path if path is not None else DEFAULT_BROWSER_PROFILE_PATH
    return Path(candidate).expanduser().resolve()


def load_storage_state(path: str | Path | None) -> dict[str, Any] | None:
    resolved = resolve_storage_state_path(path)
    if not resolved.exists():
        return None
    raw_state = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(raw_state, dict):
        return None
    return _normalize_storage_state(cast(dict[str, Any], raw_state))


def storage_state_cookies(path: str | Path | None) -> list[dict[str, Any]]:
    state = load_storage_state(path)
    if not state:
        return []
    cookies = state.get("cookies")
    if not isinstance(cookies, list):
        return []
    return [cast(dict[str, Any], item) for item in cookies if isinstance(item, dict)]


def create_browser_context(
    playwright: Any,
    *,
    headless: bool,
    storage_state_path: str | Path | None = None,
    prefer_human_browser: bool = False,
    user_data_dir: str | Path | None = None,
) -> tuple[Any | None, Any]:
    if prefer_human_browser and not headless:
        profile_path = resolve_browser_profile_path(user_data_dir)
        profile_path.mkdir(parents=True, exist_ok=True)
        for channel in PREFERRED_BROWSER_CHANNELS:
            try:
                context = playwright.chromium.launch_persistent_context(
                    str(profile_path),
                    channel=channel,
                    headless=headless,
                )
                return None, context
            except Exception:
                continue
    browser = playwright.chromium.launch(headless=headless)
    storage_state: str | dict[str, Any] | None = None
    resolved = resolve_storage_state_path(storage_state_path)
    if resolved.exists():
        storage_state = load_storage_state(resolved)
    context = browser.new_context(storage_state=storage_state)
    return browser, context


def save_storage_state(context: Any, path: str | Path | None = None) -> Path:
    resolved = resolve_storage_state_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(resolved))
    return resolved


def login_info_response_is_authenticated(payload: dict[str, Any]) -> bool:
    if payload.get("Success") is True and payload.get("Data"):
        return True
    code = payload.get("Code")
    return isinstance(code, int) and code == 200


def import_browser_storage_state(
    *,
    browser_name: str = "auto",
    storage_state_path: str | Path | None = None,
) -> LoginBootstrapResult:
    trace_id = uuid.uuid4().hex
    target_path = resolve_storage_state_path(storage_state_path)
    try:
        cookies = _load_browser_cookies(browser_name, domain_name="modelscope.cn")
    except Exception as exc:
        return LoginBootstrapResult(
            trace_id=trace_id,
            storage_state_path=str(target_path),
            authenticated=False,
            message=f"Failed to load ModelScope cookies from browser '{browser_name}': {exc}",
        )
    if not cookies:
        return LoginBootstrapResult(
            trace_id=trace_id,
            storage_state_path=str(target_path),
            authenticated=False,
            message=f"No ModelScope cookies were found in browser '{browser_name}'.",
        )
    if not _cookies_are_authenticated(cookies):
        return LoginBootstrapResult(
            trace_id=trace_id,
            storage_state_path=str(target_path),
            authenticated=False,
            message=(
                f"Imported ModelScope cookies from browser '{browser_name}', "
                "but they do not represent an authenticated session."
            ),
        )
    payload = {"cookies": [_cookie_to_storage_entry(cookie) for cookie in cookies], "origins": []}
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return LoginBootstrapResult(
        trace_id=trace_id,
        storage_state_path=str(target_path),
        authenticated=True,
        message=f"Imported authenticated ModelScope cookies from browser '{browser_name}'.",
    )


def bootstrap_interactive_login(
    *,
    storage_state_path: str | Path | None = None,
    entry_model_slug: str = "Qwen/Qwen2.5-7B-Instruct",
    timeout_seconds: int = 300,
) -> LoginBootstrapResult:
    from playwright.sync_api import sync_playwright

    trace_id = uuid.uuid4().hex
    target_path = resolve_storage_state_path(storage_state_path)
    model_url = MODEL_FILES_PAGE_URL.format(model_slug=entry_model_slug)
    with sync_playwright() as playwright:
        browser, context = create_browser_context(
            playwright,
            headless=False,
            storage_state_path=None,
            prefer_human_browser=True,
        )
        try:
            page = context.new_page()
            authenticated = False

            def _capture_login_response(response: Any) -> None:
                nonlocal authenticated
                if response.url != LOGIN_INFO_API or response.status != 200:
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
            if browser is not None:
                browser.close()


def doctor_storage_state(path: str | Path | None) -> tuple[bool, str]:
    resolved = resolve_storage_state_path(path)
    state = load_storage_state(resolved)
    if state is None:
        return False, f"No ModelScope storage state found at {resolved}."
    if not storage_state_cookies(resolved):
        return False, f"Storage state at {resolved} did not include any cookies."
    return True, f"Storage state at {resolved} is present and includes cookies."


def _load_browser_cookies(browser_name: str, domain_name: str) -> list[Cookie]:
    import browser_cookie3

    loader_name = SUPPORTED_BROWSER_IMPORTS.get(browser_name.lower())
    if loader_name is None:
        supported = ", ".join(sorted(SUPPORTED_BROWSER_IMPORTS))
        raise ValueError(f"Unsupported browser '{browser_name}'. Expected one of: {supported}.")
    loader = getattr(browser_cookie3, loader_name)
    return list(loader(domain_name=domain_name))


def _cookie_to_storage_entry(cookie: Cookie) -> dict[str, Any]:
    return {
        "name": cookie.name,
        "value": cookie.value,
        "domain": cookie.domain,
        "path": cookie.path,
        "expires": cookie.expires if cookie.expires is not None else -1,
        "httpOnly": _cookie_is_http_only(cookie),
        "secure": bool(cookie.secure),
        "sameSite": _cookie_same_site(cookie),
    }


def _cookies_are_authenticated(cookies: list[Cookie]) -> bool:
    cookie_mapping = {
        cookie.name: cookie.value
        for cookie in cookies
        if cookie.domain.endswith("modelscope.cn") and cookie.value is not None
    }
    if not cookie_mapping:
        return False
    with httpx.Client(follow_redirects=True, timeout=30.0) as client:
        response = client.get(LOGIN_INFO_API, cookies=cookie_mapping)
    if response.status_code != 200:
        return False
    try:
        raw_payload = response.json()
    except ValueError:
        return False
    if not isinstance(raw_payload, dict):
        return False
    return login_info_response_is_authenticated(cast(dict[str, Any], raw_payload))


def _normalize_storage_state(state: dict[str, Any]) -> dict[str, Any]:
    cookies = state.get("cookies")
    raw_cookies = cast(list[object], cookies) if isinstance(cookies, list) else []
    return {
        "cookies": [
            _normalize_storage_cookie(cast(dict[str, Any], item))
            for item in raw_cookies
            if isinstance(item, dict)
        ],
        "origins": cast(list[dict[str, Any]], state.get("origins"))
        if isinstance(state.get("origins"), list)
        else [],
    }


def _normalize_storage_cookie(cookie: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(cookie)
    normalized["secure"] = bool(cookie.get("secure"))
    normalized["httpOnly"] = bool(cookie.get("httpOnly"))
    same_site = cookie.get("sameSite")
    if same_site not in {"Lax", "None", "Strict"}:
        same_site = "Lax"
    normalized["sameSite"] = same_site
    return normalized


def _cookie_rest(cookie: Cookie) -> dict[str, str]:
    return cast(dict[str, str], getattr(cookie, "_rest", {}))


def _cookie_same_site(cookie: Cookie) -> str:
    rest = _cookie_rest(cookie)
    raw_same_site = rest.get("SameSite") or rest.get("sameSite")
    if isinstance(raw_same_site, str) and raw_same_site in {"Lax", "None", "Strict"}:
        return raw_same_site
    return "Lax"


def _cookie_is_http_only(cookie: Cookie) -> bool:
    return "httponly" in {key.lower() for key in _cookie_rest(cookie)}
