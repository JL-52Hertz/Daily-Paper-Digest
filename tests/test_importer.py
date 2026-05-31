import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paper_digest.config import Config
from paper_digest.importer import ImportOptions, PaperImporter
from paper_digest.library import PaperLibrary
from paper_digest.topics import load_active_topics


class ImporterTests(unittest.TestCase):
    def _config(self, tmp: str) -> Config:
        topic_path = Path("config/topics.json")
        return Config(
            db_path=Path(tmp) / "papers.db",
            topic_config_path=topic_path,
            topic_ids=("detection",),
            topics=load_active_topics(topic_path, ("detection",)),
        )

    @patch("paper_digest.importer.extract_pdf_text")
    @patch("paper_digest.importer.request_bytes_with_progress")
    def test_import_url_and_dedupe(self, request_bytes_with_progress, extract_pdf_text) -> None:
        request_bytes_with_progress.return_value = b"%PDF"
        extract_pdf_text.return_value = (
            "Does YOLO Really Need to See Every Training Image in CVPR 2026 "
            "Abstract This paper studies object detection and YOLO training efficiency. "
            "1 Introduction"
        )
        with tempfile.TemporaryDirectory() as tmp:
            config = self._config(tmp)
            with PaperLibrary(config.db_path) as library:
                importer = PaperImporter(config, library)
                url = "https://openaccess.thecvf.com/content/CVPR2026/papers/Xie_Does_YOLO_Really_Need_to_See_Every_Training_Image_in_CVPR_2026_paper.pdf"
                first = importer.import_url(url, ImportOptions(topics=("detection",)), show_progress=False)
                second = importer.import_url(url, ImportOptions(topics=("detection",)), show_progress=False)
                self.assertTrue(first.inserted)
                self.assertFalse(second.inserted)
                self.assertEqual(library.stats()["total"], 1)
                self.assertEqual(first.paper.venue, "CVPR")
                self.assertEqual(first.paper.year, 2026)
                self.assertIn("detection", first.paper.topics)

    @patch("paper_digest.importer.request_bytes_with_progress")
    def test_import_url_without_pdf_text(self, request_bytes_with_progress) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = self._config(tmp)
            with PaperLibrary(config.db_path) as library:
                importer = PaperImporter(config, library)
                url = "https://openaccess.thecvf.com/content/CVPR2026/papers/Xie_Does_YOLO_Really_Need_to_See_Every_Training_Image_in_CVPR_2026_paper.pdf"
                result = importer.import_url(
                    url,
                    ImportOptions(topics=("detection",), venue="CVPR", year=2026),
                    extract_text=False,
                    show_progress=False,
                )
                self.assertTrue(result.inserted)
                self.assertFalse(request_bytes_with_progress.called)
                self.assertEqual(result.paper.venue, "CVPR")

    @patch("paper_digest.importer.extract_pdf_text")
    def test_import_file(self, extract_pdf_text) -> None:
        extract_pdf_text.return_value = "Abstract Object detection with DETR. 1 Introduction"
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "A_Great_Object_Detection_Paper.pdf"
            pdf_path.write_bytes(b"%PDF")
            config = self._config(tmp)
            with PaperLibrary(config.db_path) as library:
                importer = PaperImporter(config, library)
                result = importer.import_file(
                    pdf_path,
                    ImportOptions(venue="CVPR", year=2025, topics=("detection",)),
                    show_progress=False,
                )
                self.assertTrue(result.inserted)
                self.assertEqual(result.paper.title, "A Great Object Detection Paper")
                self.assertEqual(result.paper.venue, "CVPR")


if __name__ == "__main__":
    unittest.main()
