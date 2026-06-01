import tempfile
import unittest
from pathlib import Path

from paper_digest.library import PaperLibrary
from paper_digest.models import Paper
from paper_digest.config import Config
from paper_digest.runner import PaperDigestRunner


class LibraryTests(unittest.TestCase):
    def test_upsert_dedupe_and_choose_target_unsent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "papers.db"
            with PaperLibrary(db_path) as library:
                first = Paper(
                    unique_id="arxiv:1",
                    title="Vision Language Paper",
                    venue="CVPR",
                    year=2025,
                    vlm_score=4.0,
                    published_at="2025-01-01",
                )
                duplicate = Paper(
                    unique_id="arxiv:1",
                    title="Vision Language Paper",
                    venue="CVPR",
                    year=2025,
                    code_url="https://github.com/example/repo",
                    vlm_score=5.0,
                )
                lower = Paper(
                    unique_id="arxiv:2",
                    title="Other VLM Paper",
                    venue=None,
                    year=2026,
                    vlm_score=10.0,
                    published_at="2026-01-01",
                )
                library.upsert_many([first, duplicate, lower])
                chosen = library.choose_next_paper((2026, 2025, 2024))
                self.assertIsNotNone(chosen)
                assert chosen is not None
                self.assertEqual(chosen.unique_id, "arxiv:1")
                self.assertEqual(chosen.code_url, "https://github.com/example/repo")
                self.assertEqual(library.stats()["total"], 2)

    def test_mark_sent_prevents_repeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "papers.db"
            with PaperLibrary(db_path) as library:
                paper = Paper(unique_id="arxiv:1", title="Vision Language Paper", venue="CVPR", year=2025, vlm_score=4)
                library.upsert_paper(paper)
                self.assertIsNotNone(library.choose_next_paper((2025,)))
                library.mark_sent("arxiv:1")
                self.assertIsNone(library.choose_next_paper((2025,)))

    def test_non_target_venue_is_not_selected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "papers.db"
            with PaperLibrary(db_path) as library:
                paper = Paper(unique_id="arxiv:1", title="Vision Language Paper", venue=None, year=2025, vlm_score=10)
                library.upsert_paper(paper)
                self.assertIsNone(library.choose_next_paper((2025,)))

    def test_active_topic_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "papers.db"
            with PaperLibrary(db_path) as library:
                vlm = Paper(
                    unique_id="arxiv:1",
                    title="Vision Language Paper",
                    venue="CVPR",
                    year=2025,
                    vlm_score=10,
                    topics=["vlm"],
                    topic_scores={"vlm": 10},
                )
                detection = Paper(
                    unique_id="arxiv:2",
                    title="Object Detection Paper",
                    venue="CVPR",
                    year=2025,
                    vlm_score=5,
                    topics=["detection"],
                    topic_scores={"detection": 5},
                )
                library.upsert_many([vlm, detection])
                chosen = library.choose_next_paper((2025,), ("detection",))
                self.assertIsNotNone(chosen)
                assert chosen is not None
                self.assertEqual(chosen.unique_id, "arxiv:2")

    def test_upsert_merges_topics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "papers.db"
            with PaperLibrary(db_path) as library:
                library.upsert_paper(
                    Paper(
                        unique_id="arxiv:1",
                        title="A Paper",
                        venue="CVPR",
                        year=2025,
                        vlm_score=3,
                        topics=["vlm"],
                        topic_scores={"vlm": 3},
                    )
                )
                library.upsert_paper(
                    Paper(
                        unique_id="arxiv:1",
                        title="A Paper",
                        venue="CVPR",
                        year=2025,
                        vlm_score=4,
                        topics=["detection"],
                        topic_scores={"detection": 4},
                    )
                )
                paper = library.get_paper("arxiv:1")
                self.assertIsNotNone(paper)
                assert paper is not None
                self.assertEqual(paper.topics, ["detection", "vlm"])
                self.assertEqual(paper.topic_scores["detection"], 4)
                self.assertEqual(paper.topic_scores["vlm"], 3)

    def test_topic_stats_and_sent_papers_by_topic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "papers.db"
            with PaperLibrary(db_path) as library:
                library.upsert_paper(
                    Paper(
                        unique_id="paper:1",
                        title="Segmentation Paper",
                        venue="CVPR",
                        year=2026,
                        topics=["segmentation"],
                        topic_scores={"segmentation": 2.0},
                    )
                )
                library.upsert_paper(
                    Paper(
                        unique_id="paper:2",
                        title="Tracking Paper",
                        venue="CVPR",
                        year=2026,
                        topics=["tracking"],
                        topic_scores={"tracking": 2.0},
                    )
                )
                library.mark_sent("paper:1")

                stats = {item["topic_id"]: item for item in library.topic_stats()}
                self.assertEqual(stats["segmentation"]["total"], 1)
                self.assertEqual(stats["segmentation"]["sent"], 1)
                self.assertEqual(stats["tracking"]["unsent"], 1)
                sent_papers = library.sent_papers_by_topic("segmentation")
                self.assertEqual([paper.title for paper in sent_papers], ["Segmentation Paper"])

    def test_runner_uses_topic_priority_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "papers.db"
            with PaperLibrary(db_path) as library:
                library.upsert_many(
                    [
                        Paper(
                            unique_id="arxiv:1",
                            title="Vision Language Paper",
                            venue="CVPR",
                            year=2025,
                            vlm_score=9,
                            topics=["vlm"],
                            topic_scores={"vlm": 9},
                        ),
                        Paper(
                            unique_id="arxiv:2",
                            title="Detection Paper",
                            venue="CVPR",
                            year=2025,
                            vlm_score=4,
                            topics=["detection"],
                            topic_scores={"detection": 4},
                        ),
                    ]
                )
                runner = PaperDigestRunner(Config(venue_years=(2025,)))
                paper, topic_ids = runner._choose_next_paper(library, ("detection", "vlm"))
                self.assertIsNotNone(paper)
                assert paper is not None
                self.assertEqual(paper.unique_id, "arxiv:2")
                self.assertEqual(topic_ids, ("detection",))


if __name__ == "__main__":
    unittest.main()
