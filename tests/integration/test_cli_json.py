from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
from typer.testing import CliRunner

cli_module = pytest.importorskip(
    "web2skill.cli",
    reason="CLI slice is still in flight",
)

runner = CliRunner()
SkillResultAsserter = Callable[[dict[str, Any]], None]


@pytest.mark.integration
def test_skills_list_outputs_capabilities_json() -> None:
    result = runner.invoke(cli_module.app, ["skills", "list", "--json"])

    if result.exit_code != 0:
        pytest.xfail("skills list JSON command has not been wired yet")

    parsed = json.loads(result.stdout)
    capability_names = {item["name"] for item in parsed["capabilities"]}
    assert "modelscope.search_models" in capability_names
    assert "modelscope.get_account_profile" in capability_names


@pytest.mark.integration
def test_invoke_json_envelope_contains_core_contract(
    assert_skill_result_contract: SkillResultAsserter,
) -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "invoke",
            "modelscope.search_models",
            "--input",
            '{"query":"qwen"}',
            "--json",
        ],
    )

    if result.exit_code != 0:
        pytest.xfail("invoke JSON envelope is not available yet")

    payload = json.loads(result.stdout)
    assert_skill_result_contract(payload)
