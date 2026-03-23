from __future__ import annotations

import sys
from pathlib import Path

import pytest

runner_module = pytest.importorskip(
    "web2skill.core.script_runner",
    reason="script runner slice is still in flight",
)


def test_script_runner_invokes_bundle_script_over_json_stdio(tmp_path: Path) -> None:
    script_path = tmp_path / "echo.py"
    script_path.write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "",
                "request = json.load(sys.stdin)",
                "json.dump(",
                "    {",
                '        "strategy_used": "network",',
                '        "requires_human": False,',
                '        "data": {',
                '            "trace_id": request["trace_id"],',
                '            "capability_name": request["capability_name"],',
                "        },",
                '        "errors": [],',
                '        "trace": [{"stage": "echo", "detail": "ok", "strategy": "network"}],',
                "    },",
                "    sys.stdout,",
                ")",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    response = runner_module.ScriptRunner().invoke(
        script_path=script_path,
        python_executable=Path(sys.executable),
        request={
            "action": "invoke",
            "capability_name": "modelscope.search_models",
            "payload": {"query": "qwen"},
            "trace_id": "trace-123",
        },
    )

    assert response.strategy_used == "network"
    assert response.requires_human is False
    assert response.data == {
        "trace_id": "trace-123",
        "capability_name": "modelscope.search_models",
    }
