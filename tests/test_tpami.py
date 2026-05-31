import unittest
from unittest.mock import patch

from paper_digest.config import Config
from paper_digest.sources.tpami import TPAMISource
from paper_digest.topics import load_active_topics


class TPAMITests(unittest.TestCase):
    @patch("paper_digest.sources.tpami.time.sleep")
    @patch("paper_digest.sources.tpami.request_json")
    def test_fetch_candidates_filters_tpami(self, request_json, _sleep) -> None:
        request_json.return_value = {
            "data": [
                {
                    "paperId": "tpami-1",
                    "title": "Object Detection with Detection Transformers",
                    "authors": [{"name": "Alice"}],
                    "venue": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
                    "year": 2025,
                    "url": "https://example.com/tpami",
                    "abstract": "A paper about object detection.",
                    "externalIds": {},
                },
                {
                    "paperId": "other-1",
                    "title": "Object Detection Elsewhere",
                    "authors": [{"name": "Bob"}],
                    "venue": "Some Other Venue",
                    "year": 2025,
                    "url": "https://example.com/other",
                    "abstract": "A paper about object detection.",
                    "externalIds": {},
                },
            ]
        }
        config = Config(
            topic_ids=("detection",),
            topics=load_active_topics(Config().topic_config_path, ("detection",)),
        )
        papers = TPAMISource(config).fetch_candidates((2025,))
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0].venue, "IEEE TPAMI")
        self.assertEqual(papers[0].source, "tpami_semantic_scholar")


if __name__ == "__main__":
    unittest.main()
