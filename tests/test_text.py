import unittest

from paper_digest.text import build_unique_id, extract_code_url, normalize_venue, score_topic_relevance, score_vlm_relevance
from paper_digest.topics import BUILTIN_TOPICS


class TextTests(unittest.TestCase):
    def test_unique_id_priority(self) -> None:
        self.assertEqual(
            build_unique_id(
                title="A Paper",
                doi="10.123/ABC",
                arxiv_id="2501.00001",
                openreview_id="abc",
                semantic_scholar_id="s2",
            ),
            "doi:10.123/abc",
        )
        self.assertEqual(build_unique_id(title="A Paper", arxiv_id="2501.00001v2"), "arxiv:2501.00001v2")

    def test_code_url_extraction(self) -> None:
        url = extract_code_url("Project: https://github.com/example/repo.")
        self.assertEqual(url, "https://github.com/example/repo")

    def test_vlm_score(self) -> None:
        score = score_vlm_relevance("Vision-Language Models", "A multimodal LLM for visual question answering.")
        self.assertGreater(score, 3)

    def test_venue_normalization(self) -> None:
        self.assertEqual(normalize_venue("IEEE Transactions on Pattern Analysis and Machine Intelligence"), "IEEE TPAMI")
        self.assertEqual(normalize_venue("Advances in Neural Information Processing Systems"), "NeurIPS")

    def test_detection_score(self) -> None:
        scores = score_topic_relevance(
            "Open Vocabulary Object Detection with Detection Transformers",
            "We improve DETR for zero-shot detection.",
            (BUILTIN_TOPICS["detection"],),
        )
        self.assertGreater(scores["detection"], 2)


if __name__ == "__main__":
    unittest.main()
