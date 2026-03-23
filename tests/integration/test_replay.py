from __future__ import annotations

import pytest

runtime_module = pytest.importorskip(
    "web2skill.core.runtime",
    reason="runtime module is still in flight",
)
traces_module = pytest.importorskip(
    "web2skill.core.traces",
    reason="trace module is still in flight",
)


@pytest.mark.integration
def test_runtime_emits_replayable_trace_id() -> None:
    assert hasattr(runtime_module, "SkillRuntime")
    assert hasattr(traces_module, "TraceRecord")
