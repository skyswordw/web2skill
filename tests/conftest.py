from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: exercises interactions across runtime, CLI, and provider boundaries",
    )
    config.addinivalue_line(
        "markers",
        "e2e: executes live ModelScope flows and requires explicit environment opt-in",
    )
    config.addinivalue_line(
        "markers",
        "drift: validates response-shape and DOM-anchor stability for provider capabilities",
    )
    config.addinivalue_line(
        "markers",
        "live: requires network access and a prepared provider session or credentials",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_live = _is_truthy(config.getoption("--run-live") or os.getenv("WEB2SKILL_RUN_LIVE"))
    if run_live:
        return

    skip_live = pytest.mark.skip(
        reason="live coverage disabled; set WEB2SKILL_RUN_LIVE=1 or pass --run-live",
    )
    for item in items:
        if item.get_closest_marker("live") or item.get_closest_marker("e2e"):
            item.add_marker(skip_live)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="Run live/e2e ModelScope coverage that talks to external services.",
    )


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def load_fixture(fixtures_dir: Path) -> Callable[[str], Any]:
    def _load_fixture(relative_path: str) -> Any:
        fixture_path = fixtures_dir / relative_path
        return json.loads(fixture_path.read_text())

    return _load_fixture


@pytest.fixture(scope="session")
def modelscope_known_slug() -> str:
    return os.getenv("WEB2SKILL_MODELSCOPE_KNOWN_SLUG", "Qwen/Qwen2.5-7B-Instruct")


@pytest.fixture(scope="session")
def live_opt_in() -> bool:
    return _is_truthy(os.getenv("WEB2SKILL_RUN_LIVE"))


@pytest.fixture(scope="session")
def require_live(live_opt_in: bool) -> None:
    if not live_opt_in:
        pytest.skip("live coverage disabled; set WEB2SKILL_RUN_LIVE=1 to enable")


@pytest.fixture(scope="session")
def modelscope_session_id() -> str | None:
    return os.getenv("WEB2SKILL_MODELSCOPE_SESSION_ID")


@pytest.fixture(scope="session")
def modelscope_storage_state_path() -> Path | None:
    raw_path = os.getenv("WEB2SKILL_MODELSCOPE_STORAGE_STATE")
    return Path(raw_path).expanduser() if raw_path else None


@pytest.fixture()
def assert_skill_result_contract() -> Callable[[dict[str, Any]], None]:
    def _assert_skill_result_contract(payload: dict[str, Any]) -> None:
        assert "trace_id" in payload
        assert isinstance(payload["trace_id"], str)
        assert payload["trace_id"]
        assert "strategy_used" in payload
        assert isinstance(payload["strategy_used"], str)
        assert payload["strategy_used"] in {"network", "dom", "guided_ui"}
        assert "requires_human" in payload
        assert isinstance(payload["requires_human"], bool)

    return _assert_skill_result_contract


@pytest.fixture()
def env_override(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[str, str | None], None]]:
    def _override(key: str, value: str | None) -> None:
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    yield _override


def _is_truthy(raw_value: object) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    if raw_value is None:
        return False
    return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}
