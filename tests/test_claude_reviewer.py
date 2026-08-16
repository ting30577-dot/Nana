from __future__ import annotations

from unittest.mock import patch
from types import SimpleNamespace
import unittest

import httpx

from nana_core.ai.claude_reviewer import (
    DEFAULT_MODEL,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    NANA_API_KEY_ENV,
    NANA_BASE_URL_ENV,
    NANA_MODEL_ENV,
    ClaudeReviewer,
)


class _FakeStream:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def get_final_message(self):
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="thinking"),
                SimpleNamespace(type="text", text="独立评审结论"),
            ],
            model="claude-test",
            usage=SimpleNamespace(
                input_tokens=120,
                output_tokens=30,
                cache_read_input_tokens=80,
            ),
        )


class _FakeMessages:
    def __init__(self):
        self.kwargs = None

    def stream(self, **kwargs):
        self.kwargs = kwargs
        return _FakeStream()


class _InterruptedStream(_FakeStream):
    def get_final_message(self):
        raise httpx.RemoteProtocolError("incomplete chunked read")


class _RetryMessages(_FakeMessages):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def stream(self, **kwargs):
        self.kwargs = kwargs
        self.calls += 1
        if self.calls == 1:
            return _InterruptedStream()
        return _FakeStream()


class _RateLimitedStream(_FakeStream):
    def get_final_message(self):
        raise RuntimeError(
            "HTTP 200: {'type': 'error', 'error': {'type': 'rate_limit_error', "
            "'message': 'Concurrency limit exceeded'}}"
        )


class _RateLimitedMessages(_FakeMessages):
    def __init__(self):
        super().__init__()
        self.calls = 0
        self.max_tokens = []

    def stream(self, **kwargs):
        self.kwargs = kwargs
        self.calls += 1
        self.max_tokens.append(kwargs["max_tokens"])
        return _RateLimitedStream() if self.calls == 1 else _FakeStream()


class ClaudeReviewerTests(unittest.TestCase):
    def test_review_uses_read_only_review_prompt_and_returns_usage(self):
        messages = _FakeMessages()
        client = SimpleNamespace(messages=messages)

        result = ClaudeReviewer(client=client).review("是否应该增加 Web 端？", "桌面优先")

        self.assertEqual("独立评审结论", result.text)
        self.assertEqual(80, result.cache_read_input_tokens)
        self.assertEqual("adaptive", messages.kwargs["thinking"]["type"])
        self.assertEqual("ephemeral", messages.kwargs["cache_control"]["type"])
        self.assertIn("桌面优先", messages.kwargs["messages"][0]["content"])

    def test_review_rejects_empty_question(self):
        with self.assertRaises(ValueError):
            ClaudeReviewer(client=object()).review("  ")

    def test_interrupted_stream_is_retried_once(self):
        messages = _RetryMessages()
        client = SimpleNamespace(messages=messages)

        result = ClaudeReviewer(client=client).review("检查连接")

        self.assertEqual("独立评审结论", result.text)
        self.assertEqual(2, messages.calls)

    def test_rate_limit_retries_with_smaller_output_budget(self):
        messages = _RateLimitedMessages()
        result = ClaudeReviewer(client=SimpleNamespace(messages=messages)).review(
            "检查连接"
        )

        self.assertTrue(result.text)
        self.assertEqual([16_000, 4_096], messages.max_tokens)

    def test_model_can_be_selected_with_environment_variable(self):
        with patch.dict(
            "os.environ", {NANA_MODEL_ENV: "claude-sonnet-4-6"}, clear=False
        ):
            reviewer = ClaudeReviewer(client=object())

        self.assertEqual("claude-sonnet-4-6", reviewer.model)

    def test_explicit_model_overrides_environment_variable(self):
        with patch.dict(
            "os.environ", {NANA_MODEL_ENV: "claude-sonnet-4-6"}, clear=False
        ):
            reviewer = ClaudeReviewer(model=DEFAULT_MODEL, client=object())

        self.assertEqual(DEFAULT_MODEL, reviewer.model)

    def test_gateway_base_url_does_not_duplicate_v1(self):
        with patch.dict(
            "os.environ",
            {
                NANA_API_KEY_ENV: "test-key",
                NANA_BASE_URL_ENV: "https://wawapi.top/v1",
            },
            clear=False,
        ):
            with patch(
                "anthropic.Anthropic",
                return_value=SimpleNamespace(base_url="https://wawapi.top"),
            ) as anthropic_client:
                client = ClaudeReviewer._create_client()

        self.assertEqual("https://wawapi.top", str(client.base_url))
        self.assertEqual(
            DEFAULT_REQUEST_TIMEOUT_SECONDS,
            anthropic_client.call_args.kwargs["timeout"],
        )

    def test_gateway_is_required_and_official_key_is_ignored(self):
        with patch.dict(
            "os.environ",
            {"ANTHROPIC_API_KEY": "official-key"},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "NANA_CLAUDE_API_KEY"):
                ClaudeReviewer._create_client()

    def test_official_anthropic_base_url_is_rejected(self):
        with patch.dict(
            "os.environ",
            {
                NANA_API_KEY_ENV: "relay-key",
                NANA_BASE_URL_ENV: "https://api.anthropic.com/v1",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "只允许使用中转站"):
                ClaudeReviewer._create_client()


if __name__ == "__main__":
    unittest.main()
