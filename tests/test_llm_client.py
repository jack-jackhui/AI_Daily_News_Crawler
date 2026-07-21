import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils.llm_client import LLMChainError, get_llm_client, get_llm_model  # noqa: E402


class ProviderFailure(Exception):
    def __init__(self, status_code):
        super().__init__(f"provider status {status_code}")
        self.status_code = status_code


class FakeCompletions:
    def __init__(self, outcome, calls, provider):
        self.outcome = outcome
        self.calls = calls
        self.provider = provider

    def create(self, **kwargs):
        self.calls.append((self.provider, kwargs))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class FakeClient:
    def __init__(self, outcome, calls, provider):
        self.chat = SimpleNamespace(
            completions=FakeCompletions(outcome, calls, provider)
        )


class LLMClientChainTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "LLM_PROVIDER": "gemini",
            "LLM_FALLBACK_PROVIDERS": "cloudflare,openrouter,openrouter_super",
            "GEMINI_API_KEY": "gemini-test-key",
            "GEMINI_MODEL": "gemini-3.5-flash",
            "CLOUDFLARE_API_TOKEN": "cloudflare-test-token",
            "CLOUDFLARE_ACCOUNT_ID": "cloudflare-test-account",
            "CLOUDFLARE_AI_MODEL": "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
            "OPENROUTER_API_KEY": "openrouter-test-key",
            "OPENROUTER_MODEL": "nvidia/nemotron-3-ultra-550b-a55b:free",
            "OPENROUTER_SUPER_MODEL": "nvidia/nemotron-3-super-120b-a12b:free",
        }
        self.response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='[{"ok": true}]'))]
        )

    def _run(self, outcomes):
        calls = []
        provider_names = iter(
            ["gemini", "cloudflare", "openrouter", "openrouter_super"]
        )

        def make_client(**kwargs):
            provider = next(provider_names)
            return FakeClient(outcomes[provider], calls, provider)

        with patch.dict(os.environ, self.env, clear=True), patch(
            "utils.llm_client.OpenAI", side_effect=make_client
        ):
            client = get_llm_client()
            result = client.chat.completions.create(
                model=get_llm_model(),
                messages=[{"role": "user", "content": "safe test"}],
                response_format={"type": "json_object"},
            )
        return result, calls

    def test_gemini_success_only_calls_gemini(self):
        result, calls = self._run({"gemini": self.response})
        self.assertIs(result, self.response)
        self.assertEqual([name for name, _ in calls], ["gemini"])
        self.assertEqual(calls[0][1]["model"], "gemini-3.5-flash")
        self.assertEqual(calls[0][1]["response_format"], {"type": "json_object"})

    def test_retryable_gemini_failure_falls_back_to_cloudflare_once(self):
        result, calls = self._run(
            {"gemini": ProviderFailure(429), "cloudflare": self.response}
        )
        self.assertIs(result, self.response)
        self.assertEqual([name for name, _ in calls], ["gemini", "cloudflare"])
        self.assertEqual(
            calls[1][1]["model"], "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
        )

    def test_two_retryable_failures_fall_back_to_ultra_once(self):
        result, calls = self._run(
            {
                "gemini": ProviderFailure(503),
                "cloudflare": ProviderFailure(429),
                "openrouter": self.response,
            }
        )
        self.assertIs(result, self.response)
        self.assertEqual(
            [name for name, _ in calls], ["gemini", "cloudflare", "openrouter"]
        )
        self.assertEqual(
            calls[2][1]["model"], "nvidia/nemotron-3-ultra-550b-a55b:free"
        )

    def test_three_retryable_failures_fall_back_to_super_once(self):
        result, calls = self._run(
            {
                "gemini": ProviderFailure(503),
                "cloudflare": ProviderFailure(408),
                "openrouter": ProviderFailure(500),
                "openrouter_super": self.response,
            }
        )
        self.assertIs(result, self.response)
        self.assertEqual(
            [name for name, _ in calls],
            ["gemini", "cloudflare", "openrouter", "openrouter_super"],
        )
        self.assertEqual(
            calls[3][1]["model"], "nvidia/nemotron-3-super-120b-a12b:free"
        )

    def test_non_retryable_primary_400_does_not_fall_back(self):
        with self.assertRaises(ProviderFailure) as raised:
            self._run({"gemini": ProviderFailure(400)})
        self.assertEqual(raised.exception.status_code, 400)

    def test_non_retryable_cloudflare_400_does_not_fall_back(self):
        with self.assertRaises(ProviderFailure) as raised:
            self._run(
                {"gemini": ProviderFailure(429), "cloudflare": ProviderFailure(400)}
            )
        self.assertEqual(raised.exception.status_code, 400)

    def test_all_tiers_fail_with_clear_error(self):
        with self.assertRaises(LLMChainError) as raised:
            self._run(
                {
                    "gemini": ProviderFailure(429),
                    "cloudflare": ProviderFailure(503),
                    "openrouter": ProviderFailure(500),
                    "openrouter_super": ProviderFailure(503),
                }
            )
        message = str(raised.exception)
        self.assertIn("All configured LLM tiers failed", message)
        self.assertLess(message.index("gemini-3.5-flash"), message.index("llama-3.3"))
        self.assertLess(message.index("llama-3.3"), message.index("ultra"))
        self.assertLess(message.index("ultra"), message.index("super"))

    def test_key_files_and_legacy_openrouter_configuration(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            key_file = Path(directory) / "openrouter.key"
            key_file.write_text("file-key\n", encoding="utf-8")
            env = {
                "LLM_PROVIDER": "openrouter",
                "OPENROUTER_API_KEY_FILE": str(key_file),
                "OPENROUTER_MODEL": "legacy-model",
            }

            def make_client(**kwargs):
                self.assertEqual(kwargs["api_key"], "file-key")
                self.assertEqual(kwargs["max_retries"], 2)
                return FakeClient(self.response, calls, "openrouter")

            with patch.dict(os.environ, env, clear=True), patch(
                "utils.llm_client.OpenAI", side_effect=make_client
            ):
                client = get_llm_client()
                client.chat.completions.create(model=get_llm_model(), messages=[])

        self.assertEqual([name for name, _ in calls], ["openrouter"])
        self.assertEqual(calls[0][1]["model"], "legacy-model")

    def test_cloudflare_key_file_and_account_build_openai_base_url(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            key_file = Path(directory) / "cloudflare.key"
            key_file.write_text("cloudflare-file-token\n", encoding="utf-8")
            env = {
                "LLM_PROVIDER": "cloudflare",
                "CLOUDFLARE_API_TOKEN_FILE": str(key_file),
                "CLOUDFLARE_ACCOUNT_ID": "account-123",
                "CLOUDFLARE_AI_MODEL": "cloudflare-model",
            }

            def make_client(**kwargs):
                self.assertEqual(kwargs["api_key"], "cloudflare-file-token")
                self.assertEqual(
                    str(kwargs["base_url"]),
                    "https://api.cloudflare.com/client/v4/accounts/account-123/ai/v1",
                )
                self.assertEqual(kwargs["max_retries"], 2)
                return FakeClient(self.response, calls, "cloudflare")

            with patch.dict(os.environ, env, clear=True), patch(
                "utils.llm_client.OpenAI", side_effect=make_client
            ):
                client = get_llm_client()
                client.chat.completions.create(model=get_llm_model(), messages=[])

        self.assertEqual([name for name, _ in calls], ["cloudflare"])
        self.assertEqual(calls[0][1]["model"], "cloudflare-model")

    def test_azure_remains_available_for_rollback(self):
        env = {
            "LLM_PROVIDER": "azure",
            "AZURE_OPENAI_API_KEY": "azure-key",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            "AZURE_OPENAI_MODEL": "azure-deployment",
        }
        calls = []

        def make_client(**kwargs):
            self.assertEqual(kwargs["max_retries"], 2)
            return FakeClient(self.response, calls, "azure")

        with patch.dict(os.environ, env, clear=True), patch(
            "utils.llm_client.AzureOpenAI", side_effect=make_client
        ):
            client = get_llm_client()
            client.chat.completions.create(model=get_llm_model(), messages=[])

        self.assertEqual(calls[0][1]["model"], "azure-deployment")


if __name__ == "__main__":
    unittest.main()
