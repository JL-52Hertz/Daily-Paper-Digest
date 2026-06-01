import io
import unittest
from unittest.mock import patch

from paper_digest.progress import Progress, StageProgress


class ProgressTests(unittest.TestCase):
    def test_progress_renders_percent(self) -> None:
        stderr = io.StringIO()
        with patch("sys.stderr", stderr):
            progress = Progress(label="Downloading", total=100, enabled=True, unit="B")
            progress.start()
            progress.update(50)
            progress.finish()
        output = stderr.getvalue()
        self.assertIn("Downloading", output)
        self.assertIn("100%", output)

    def test_progress_disabled_is_silent(self) -> None:
        stderr = io.StringIO()
        with patch("sys.stderr", stderr):
            progress = Progress(label="Silent", total=10, enabled=False)
            progress.start()
            progress.update(5)
            progress.finish()
        self.assertEqual(stderr.getvalue(), "")

    def test_stage_progress_renders_steps(self) -> None:
        stderr = io.StringIO()
        with patch("sys.stderr", stderr):
            progress = StageProgress(total=2)
            progress.step("Fetching papers")
            progress.info("arXiv: 3 papers")
            progress.finish("Done")
        output = stderr.getvalue()
        self.assertIn("1/2 Fetching papers", output)
        self.assertIn("arXiv: 3 papers", output)
        self.assertIn("2/2 Done", output)


if __name__ == "__main__":
    unittest.main()
