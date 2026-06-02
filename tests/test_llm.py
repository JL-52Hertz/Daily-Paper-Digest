import unittest
from unittest.mock import patch

from paper_digest.config import Config
from paper_digest.llm import LLMClient, fallback_summary, normalize_summary
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

    def test_config_reads_llm_timeout(self) -> None:
        with patch.dict("os.environ", {"PAPER_DIGEST_LLM_TIMEOUT": "240"}, clear=True):
            config = Config.from_env(load_topics=False)
        self.assertEqual(config.llm_timeout, 240)

    def test_config_reads_dashscope_provider_alias(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "aliyun",
                "DASHSCOPE_API_KEY": "dashscope-key",
            },
            clear=True,
        ):
            config = Config.from_env(load_topics=False)
        self.assertEqual(config.llm_provider, "dashscope")
        self.assertEqual(config.llm_api_key, "dashscope-key")
        self.assertEqual(config.llm_model, "qwen-plus")
        self.assertEqual(config.llm_base_url, "https://dashscope.aliyuncs.com/compatible-mode/v1")

    def test_config_reads_volcengine_provider_alias(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "doubao",
                "ARK_API_KEY": "ark-key",
            },
            clear=True,
        ):
            config = Config.from_env(load_topics=False)
        self.assertEqual(config.llm_provider, "volcengine")
        self.assertEqual(config.llm_api_key, "ark-key")
        self.assertEqual(config.llm_model, "doubao-seed-1-6-251015")
        self.assertEqual(config.llm_base_url, "https://ark.cn-beijing.volces.com/api/v3")

    def test_config_reads_qianfan_provider_alias(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "baidu",
                "QIANFAN_API_KEY": "qianfan-key",
            },
            clear=True,
        ):
            config = Config.from_env(load_topics=False)
        self.assertEqual(config.llm_provider, "qianfan")
        self.assertEqual(config.llm_api_key, "qianfan-key")
        self.assertEqual(config.llm_model, "ernie-4.0-turbo-128k")
        self.assertEqual(config.llm_base_url, "https://qianfan.baidubce.com/v2")

    def test_direct_deepseek_config_remains_available(self) -> None:
        config = Config(deepseek_api_key="deepseek-key")
        self.assertTrue(LLMClient(config).is_available())

    def test_english_summary_normalization(self) -> None:
        paper = Paper(unique_id="x", title="A Paper")
        summary = normalize_summary({"title": "A Paper"}, paper, language="en")
        self.assertEqual(summary["authors"], "Authors not confirmed")
        self.assertEqual(summary["venue_year"], "venue/year not confirmed")
        self.assertEqual(summary["code_url"], "No public code yet")
        self.assertIn("Model analysis", summary["limitations"])
        self.assertEqual(summary["_language"], "en")

    def test_english_fallback_summary(self) -> None:
        paper = Paper(unique_id="x", title="A Paper", topics=["detection"])
        summary = fallback_summary(paper, provider_name="Local LLM", language="en")
        self.assertEqual(summary["_language"], "en")
        self.assertIn("no-LLM preview summary", summary["core_problem"])

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
        self.assertEqual(summary["contributions"], "贡献")
        self.assertIn("模型分析", summary["limitations"])
        args, kwargs = request.call_args
        self.assertEqual(args[0], "https://example.com/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer token")
        self.assertEqual(kwargs["json_body"]["response_format"], {"type": "json_object"})
        self.assertEqual(kwargs["timeout"], config.llm_timeout)

    def test_dashscope_uses_openai_compatible_chat_completions(self) -> None:
        config = Config(
            llm_provider="dashscope",
            llm_api_key="token",
            llm_model="qwen-plus",
            llm_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        with patch(
            "paper_digest.llm.request_json",
            return_value={"choices": [{"message": {"content": '{"title":"A"}'}}]},
        ) as request:
            content = LLMClient(config).complete_json(system="s", prompt="p")
        self.assertEqual(content, '{"title":"A"}')
        args, kwargs = request.call_args
        self.assertEqual(args[0], "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer token")
        self.assertEqual(kwargs["json_body"]["response_format"], {"type": "json_object"})

    def test_qianfan_uses_openai_compatible_chat_completions_without_response_format(self) -> None:
        config = Config(
            llm_provider="qianfan",
            llm_api_key="token",
            llm_model="ernie-4.0-turbo-128k",
            llm_base_url="https://qianfan.baidubce.com/v2",
        )
        with patch(
            "paper_digest.llm.request_json",
            return_value={"choices": [{"message": {"content": '{"title":"A"}'}}]},
        ) as request:
            content = LLMClient(config).complete_json(system="s", prompt="p")
        self.assertEqual(content, '{"title":"A"}')
        args, kwargs = request.call_args
        self.assertEqual(args[0], "https://qianfan.baidubce.com/v2/chat/completions")
        self.assertNotIn("response_format", kwargs["json_body"])

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
