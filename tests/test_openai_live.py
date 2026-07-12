"""Paid live smoke test; skipped unless the operator explicitly opts in."""

import os

import pytest

from real_worker_runtime.openai_provider import OpenAIConfig, OpenAIProvider


pytestmark = pytest.mark.skipif(
    not (
        os.environ.get("OPENAI_API_KEY")
        and os.environ.get("AI_FACTORY_RUN_LIVE_OPENAI_TESTS") == "1"
    ),
    reason="requires OPENAI_API_KEY and AI_FACTORY_RUN_LIVE_OPENAI_TESTS=1",
)


def test_live_openai_smoke():
    result = OpenAIProvider(OpenAIConfig.from_env()).generate(
        "pm_worker", "Return a minimal plan for printing hello.", {"outputs": {}}
    )
    assert result["_provider"]["provider"] == "openai"
    assert result["goal"]
