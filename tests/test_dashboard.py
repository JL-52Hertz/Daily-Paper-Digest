import tempfile
import unittest
from pathlib import Path

from paper_digest.config import Config
from paper_digest.dashboard import render_dashboard, render_topic_page
from paper_digest.library import PaperLibrary
from paper_digest.models import Paper


class DashboardTests(unittest.TestCase):
    def test_dashboard_renders_topic_counts(self) -> None:
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
                        topic_scores={"segmentation": 3},
                    )
                )
                library.mark_sent("paper:1")

            html = render_dashboard(Config(db_path=db_path, topic_config_path=Path("config/topics.json")))
        self.assertIn("Paper Digest Dashboard", html)
        self.assertIn("Segmentation", html)
        self.assertIn("View sent papers", html)
        self.assertIn("conic-gradient", html)

    def test_topic_page_lists_sent_papers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "papers.db"
            with PaperLibrary(db_path) as library:
                library.upsert_paper(
                    Paper(
                        unique_id="paper:1",
                        title="Tracking Paper",
                        venue="CVPR",
                        year=2026,
                        topics=["tracking"],
                        topic_scores={"tracking": 3},
                    )
                )
                library.mark_sent("paper:1")

            html = render_topic_page(Config(db_path=db_path, topic_config_path=Path("config/topics.json")), "tracking")
        self.assertIn("Tracking", html)
        self.assertIn("Sent Papers", html)
        self.assertIn("Tracking Paper", html)


if __name__ == "__main__":
    unittest.main()
