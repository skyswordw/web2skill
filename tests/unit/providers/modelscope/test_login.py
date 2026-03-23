from __future__ import annotations

import json
from http.cookiejar import Cookie
from pathlib import Path
from typing import Any

import pytest

login = pytest.importorskip(
    "web2skill.providers.modelscope.login",
    reason="ModelScope login slice is still in flight",
)


class FakeContext:
    pass


class FakeBrowser:
    def __init__(self) -> None:
        self.new_context_calls: list[dict[str, object]] = []
        self.context = FakeContext()

    def new_context(self, **kwargs: object) -> FakeContext:
        self.new_context_calls.append(kwargs)
        return self.context


class FakeChromium:
    def __init__(self) -> None:
        self.persistent_calls: list[dict[str, object]] = []
        self.launch_calls: list[dict[str, object]] = []
        self.context = FakeContext()

    def launch_persistent_context(self, user_data_dir: str, **kwargs: object) -> FakeContext:
        self.persistent_calls.append(
            {
                "user_data_dir": user_data_dir,
                **kwargs,
            }
        )
        return self.context

    def launch(self, **kwargs: object) -> object:
        self.launch_calls.append(kwargs)
        raise AssertionError("fallback launch should not be used when Chrome is available")


class FakePlaywright:
    def __init__(self) -> None:
        self.chromium = FakeChromium()


class FallbackChromium(FakeChromium):
    def __init__(self) -> None:
        super().__init__()
        self.browser = FakeBrowser()

    def launch_persistent_context(self, user_data_dir: str, **kwargs: object) -> FakeContext:
        self.persistent_calls.append(
            {
                "user_data_dir": user_data_dir,
                **kwargs,
            }
        )
        raise RuntimeError("preferred browser channel unavailable")

    def launch(self, **kwargs: object) -> FakeBrowser:
        self.launch_calls.append(kwargs)
        return self.browser


class FallbackPlaywright:
    def __init__(self) -> None:
        self.chromium = FallbackChromium()


def make_cookie(
    *,
    name: str,
    value: str,
    domain: str = ".modelscope.cn",
    path: str = "/",
    secure: Any = True,
    expires: int = 123,
    rest: dict[str, str] | None = None,
) -> Cookie:
    return Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=True,
        domain_initial_dot=domain.startswith("."),
        path=path,
        path_specified=True,
        secure=secure,
        expires=expires,
        discard=False,
        comment=None,
        comment_url=None,
        rest=rest or {"HttpOnly": "", "SameSite": "Lax"},
        rfc2109=False,
    )


def test_create_browser_context_prefers_installed_chrome_for_interactive_login(
    tmp_path: Path,
) -> None:
    playwright = FakePlaywright()
    profile_path = tmp_path / "modelscope-login-profile"

    browser, context = login.create_browser_context(
        playwright,
        headless=False,
        storage_state_path=None,
        prefer_human_browser=True,
        user_data_dir=profile_path,
    )

    assert browser is None
    assert context is playwright.chromium.context
    assert profile_path.exists()
    assert playwright.chromium.launch_calls == []
    assert playwright.chromium.persistent_calls == [
        {
            "user_data_dir": str(profile_path.resolve()),
            "channel": "chrome",
            "headless": False,
        }
    ]


def test_create_browser_context_falls_back_to_standard_context_when_channels_fail(
    tmp_path: Path,
) -> None:
    playwright = FallbackPlaywright()
    profile_path = tmp_path / "modelscope-login-profile"
    storage_state_path = tmp_path / "modelscope-storage-state.json"
    storage_state_path.write_text("{}", encoding="utf-8")

    browser, context = login.create_browser_context(
        playwright,
        headless=False,
        storage_state_path=storage_state_path,
        prefer_human_browser=True,
        user_data_dir=profile_path,
    )

    assert browser is playwright.chromium.browser
    assert context is playwright.chromium.browser.context
    assert [call["channel"] for call in playwright.chromium.persistent_calls] == [
        "chrome",
        "msedge",
    ]
    assert playwright.chromium.launch_calls == [{"headless": False}]
    assert playwright.chromium.browser.new_context_calls == [
        {
            "storage_state": {
                "cookies": [],
                "origins": [],
            },
        }
    ]


def test_import_browser_storage_state_persists_authenticated_cookies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_state_path = tmp_path / "modelscope-storage-state.json"
    imported_cookie = make_cookie(name="m_session_id", value="session-token")

    def fake_load_browser_cookies(browser_name: str, domain_name: str) -> list[Cookie]:
        assert browser_name == "chrome"
        assert domain_name == "modelscope.cn"
        return [imported_cookie]

    def fake_cookies_are_authenticated(cookies: list[Cookie]) -> bool:
        assert cookies == [imported_cookie]
        return True

    monkeypatch.setattr(
        login,
        "_load_browser_cookies",
        fake_load_browser_cookies,
    )
    monkeypatch.setattr(login, "_cookies_are_authenticated", fake_cookies_are_authenticated)

    result = login.import_browser_storage_state(
        browser_name="chrome",
        storage_state_path=storage_state_path,
    )

    assert result.authenticated is True
    assert result.storage_state_path == str(storage_state_path.resolve())
    payload = json.loads(storage_state_path.read_text(encoding="utf-8"))
    assert payload == {
        "cookies": [
            {
                "domain": ".modelscope.cn",
                "expires": 123,
                "httpOnly": True,
                "name": "m_session_id",
                "path": "/",
                "sameSite": "Lax",
                "secure": True,
                "value": "session-token",
            }
        ],
        "origins": [],
    }


def test_import_browser_storage_state_writes_boolean_secure_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_state_path = tmp_path / "modelscope-storage-state.json"
    imported_cookie = make_cookie(name="m_session_id", value="session-token", secure=1)

    def fake_load_browser_cookies(browser_name: str, domain_name: str) -> list[Cookie]:
        assert browser_name == "chrome"
        assert domain_name == "modelscope.cn"
        return [imported_cookie]

    def fake_cookies_are_authenticated(cookies: list[Cookie]) -> bool:
        assert cookies == [imported_cookie]
        return True

    monkeypatch.setattr(login, "_load_browser_cookies", fake_load_browser_cookies)
    monkeypatch.setattr(login, "_cookies_are_authenticated", fake_cookies_are_authenticated)

    login.import_browser_storage_state(
        browser_name="chrome",
        storage_state_path=storage_state_path,
    )

    payload = json.loads(storage_state_path.read_text(encoding="utf-8"))
    assert isinstance(payload["cookies"][0]["secure"], bool)
    assert payload["cookies"][0]["secure"] is True
