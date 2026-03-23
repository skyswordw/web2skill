from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

parsers = pytest.importorskip(
    "web2skill.providers.modelscope.parsers",
    reason="ModelScope provider slice is still in flight",
)

FixtureLoader = Callable[[str], dict[str, Any]]


def test_search_models_normalizes_network_payload(load_fixture: FixtureLoader) -> None:
    payload = load_fixture("modelscope/search_models.json")

    models = parsers.normalize_search_results(payload)

    assert models[0].model_slug == "Qwen/Qwen2.5-7B-Instruct"


def test_model_overview_normalizer_preserves_slug(load_fixture: FixtureLoader) -> None:
    payload = load_fixture("modelscope/model_overview.json")

    overview = parsers.normalize_model_overview(payload)

    assert overview.model_slug == "Qwen/Qwen2.5-7B-Instruct"


def test_model_files_normalizer_preserves_file_listing(load_fixture: FixtureLoader) -> None:
    payload = load_fixture("modelscope/model_files.json")

    files = parsers.normalize_model_files(payload)

    assert [entry.path for entry in files] == ["README.md", "config.json", "tokenizer.json"]
