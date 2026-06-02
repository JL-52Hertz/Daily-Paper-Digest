import unittest

from paper_digest.deepseek import normalize_summary, parse_json_object
from paper_digest.models import Paper


class DeepSeekTests(unittest.TestCase):
    def test_parse_json_from_wrapped_content(self) -> None:
        parsed = parse_json_object('```json\n{"title":"A"}\n```')
        self.assertEqual(parsed["title"], "A")

    def test_normalize_fills_missing_fields(self) -> None:
        paper = Paper(unique_id="x", title="A", authors=["Alice"], venue="CVPR", year=2025)
        summary = normalize_summary({"title": "A"}, paper)
        self.assertEqual(summary["authors"], "Alice")
        self.assertEqual(summary["venue_year"], "CVPR 2025")
        self.assertEqual(summary["code_url"], "暂无公开代码")
        self.assertIn("以下为模型分析", summary["limitations"])


if __name__ == "__main__":
    unittest.main()
