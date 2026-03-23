from __future__ import annotations

from collections.abc import Callable
from typing import Any

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


@pytest.mark.live
def test_live_environment_declares_drift_anchor_inputs(
    require_live: None,
    modelscope_known_slug: str,
) -> None:
    assert modelscope_known_slug
