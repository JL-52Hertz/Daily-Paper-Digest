import unittest

from paper_digest.collector import parse_collect_sources, select_papers_for_collection
from paper_digest.models import Paper


class CollectorTests(unittest.TestCase):
    def test_parse_collect_sources_defaults_to_cvf_and_openreview(self) -> None:
        self.assertEqual(parse_collect_sources(None), ("cvf", "openreview"))

    def test_parse_collect_sources_rejects_unknown_source(self) -> None:
        with self.assertRaises(ValueError):
            parse_collect_sources("cvf,unknown")

    def test_select_papers_balances_topics_and_skips_existing(self) -> None:
        candidates = [
            Paper(
                unique_id="existing",
                title="Existing Detection Paper",
                topics=["detection"],
                topic_scores={"detection": 10},
            ),
            Paper(
                unique_id="seg-1",
                title="Segmentation Paper",
                topics=["segmentation"],
                topic_scores={"segmentation": 9},
            ),
            Paper(
                unique_id="track-1",
                title="Tracking Paper",
                topics=["tracking"],
                topic_scores={"tracking": 8},
            ),
            Paper(
                unique_id="det-1",
                title="Detection Paper",
                topics=["detection"],
                topic_scores={"detection": 7},
            ),
        ]
        selected = select_papers_for_collection(
            candidates,
            topic_ids=("detection", "segmentation", "tracking"),
            limit=3,
            existing_ids={"existing"},
        )
        self.assertEqual({paper.unique_id for paper in selected}, {"det-1", "seg-1", "track-1"})


if __name__ == "__main__":
    unittest.main()
