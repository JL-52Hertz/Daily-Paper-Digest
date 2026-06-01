import unittest
from unittest.mock import patch

from paper_digest.config import Config
from paper_digest.llm import LLMClient
from paper_digest.models import Paper


class LLMTests(unittest.TestCase):
    def test_config_reads_openai_provider(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "openai",
                "OPENAI_API_KEY": "sk-test",
                "OPENAI_MODEL": "gpt-test",
            },
            clear=True,
        ):
            config = Config.from_env(load_topics=False)
        self.assertEqual(config.llm_provider, "openai")
        self.assertEqual(config.llm_api_key, "sk-test")
        self.assertEqual(config.llm_model, "gpt-test")
        self.assertEqual(config.llm_base_url, "https://api.openai.com/v1")

    def test_direct_deepseek_config_remains_available(self) -> None:
        config = Config(deepseek_api_key="deepseek-key")
        self.assertTrue(LLMClient(config).is_available())

    def test_openai_compatible_summary(self) -> None:
        config = Config(
            llm_provider="openai_compatible",
            llm_api_key="token",
            llm_model="model",
            llm_base_url="https://example.com/v1",
        )
        paper = Paper(unique_id="x", title="A Paper", venue="CVPR", year=2026)
        response = {
            "choices": [
                {
                    "message": {
                        "content": '{"title":"A Paper","motivation":"动机","core_problem":"问题","method":"方法","experiments":"实验","contributions_limitations":"贡献"}'
                    }
                }
            ]
        }
        with patch("paper_digest.llm.request_json", return_value=response) as request:
            summary = LLMClient(config).summarize(paper)
        self.assertEqual(summary["title"], "A Paper")
        args, kwargs = request.call_args
        self.assertEqual(args[0], "https://example.com/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer token")
        self.assertEqual(kwargs["json_body"]["response_format"], {"type": "json_object"})

    def test_ollama_does_not_require_api_key(self) -> None:
        config = Config(llm_provider="ollama", llm_model="qwen2.5:7b", llm_base_url="http://localhost:11434")
        self.assertTrue(LLMClient(config).is_available())
        with patch(
            "paper_digest.llm.request_json",
            return_value={"message": {"content": '{"title":"A"}'}},
        ) as request:
            content = LLMClient(config).complete_json(system="s", prompt="p")
        self.assertEqual(content, '{"title":"A"}')
        args, kwargs = request.call_args
        self.assertEqual(args[0], "http://localhost:11434/api/chat")
        self.assertEqual(kwargs["json_body"]["format"], "json")

    def test_anthropic_text_response(self) -> None:
        config = Config(
            llm_provider="anthropic",
            llm_api_key="key",
            llm_model="claude-test",
            llm_base_url="https://api.anthropic.com",
        )
        with patch(
            "paper_digest.llm.request_json",
            return_value={"content": [{"type": "text", "text": '{"title":"A"}'}]},
        ) as request:
            content = LLMClient(config).complete_json(system="s", prompt="p")
        self.assertEqual(content, '{"title":"A"}')
        args, kwargs = request.call_args
        self.assertEqual(args[0], "https://api.anthropic.com/v1/messages")
        self.assertEqual(kwargs["headers"]["x-api-key"], "key")


if __name__ == "__main__":
    unittest.main()
