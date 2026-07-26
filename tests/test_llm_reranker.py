import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from processors.llm_reranker import re_rank_and_summarize_with_llm  # noqa: E402
from utils.llm_client import FallbackLLMClient, ProviderConfig  # noqa: E402


def response(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


class FakeClient:
    def __init__(self, provider, content, calls):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.provider = provider
        self.content = content
        self.calls = calls

    def _create(self, **kwargs):
        self.calls.append(self.provider)
        return response(self.content)


class LLMRerankerTests(unittest.TestCase):
    def test_malformed_json_falls_back_and_validates_fields(self):
        calls = []
        providers = [
            ProviderConfig(
                "first",
                "first-model",
                lambda: FakeClient("first", "Here is your digest (not JSON)", calls),
            ),
            ProviderConfig(
                "second",
                "second-model",
                lambda: FakeClient(
                    "second",
                    '[{"title":"News", "summary":"Summary", "url":"https://example.com"}]',
                    calls,
                ),
            ),
        ]

        with patch(
            "processors.llm_reranker.get_llm_client",
            return_value=FallbackLLMClient(providers),
        ), patch("processors.llm_reranker.get_llm_provider", return_value="first"), patch(
            "processors.llm_reranker.get_llm_model", return_value="first-model"
        ):
            result = re_rank_and_summarize_with_llm(
                [{"title": "Input", "content": "Body", "url": "https://input"}]
            )

        self.assertEqual(calls, ["first", "second"])
        self.assertEqual(
            result,
            [{
                "title": "News",
                "summary": "Summary",
                "url": "https://example.com",
                "icon": "🤖",
            }],
        )


if __name__ == "__main__":
    unittest.main()
