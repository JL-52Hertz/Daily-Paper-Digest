import tempfile
import unittest
from pathlib import Path

from paper_digest.topic_generator import add_topic_to_file, generate_topic, topic_id_from_name
from paper_digest.topics import load_active_topics, load_topic_catalog
from paper_digest.config import Config


class TopicTests(unittest.TestCase):
    def test_builtin_topics_available(self) -> None:
        catalog = load_topic_catalog(Path("missing-topics.json"))
        self.assertIn("vlm", catalog)
        self.assertIn("detection", catalog)

    def test_load_custom_topic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topics.json"
            path.write_text(
                """
                {
                  "topics": [
                    {
                      "id": "segmentation",
                      "name": "Segmentation",
                      "keywords": ["semantic segmentation"],
                      "arxiv_terms": ["semantic segmentation"],
                      "semantic_scholar_query": "semantic segmentation"
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )
            topics = load_active_topics(path, ("segmentation",))
            self.assertEqual(topics[0].id, "segmentation")

    def test_topic_id_from_name(self) -> None:
        self.assertEqual(topic_id_from_name("Efficient training"), "efficient_training")

    def test_generate_heuristic_efficient_training(self) -> None:
        topic = generate_topic("Efficient training", config=Config(deepseek_api_key=None), use_llm=False)
        self.assertEqual(topic.id, "efficient_training")
        self.assertIn("efficient training", topic.keywords)
        self.assertIn("cs.LG", topic.categories)

    def test_add_topic_to_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topics.json"
            topic = generate_topic("Efficient training", config=Config(deepseek_api_key=None), use_llm=False)
            add_topic_to_file(path, topic)
            catalog = load_topic_catalog(path)
            self.assertIn("efficient_training", catalog)


if __name__ == "__main__":
    unittest.main()
