import unittest

from paper_digest.config import Config
from paper_digest.sources.cvf import CVFSource
from paper_digest.topics import load_active_topics


CVF_HTML = """
<html><body><dl>
<dt class="ptitle"><br><a href="content/CVPR2026/html/Xie_Does_YOLO_Really_Need_to_See_Every_Training_Image_in_CVPR_2026_paper.html">Does YOLO Really Need to See Every Training Image in CVPR 2026</a></dt>
<dd>Wei Xie, Alice Wang</dd>
<dd>
  <a href="content/CVPR2026/papers/Xie_Does_YOLO_Really_Need_to_See_Every_Training_Image_in_CVPR_2026_paper.pdf">pdf</a>
</dd>
</dl></body></html>
"""


class CVFTests(unittest.TestCase):
    def test_parse_listing(self) -> None:
        config = Config(
            topic_ids=("detection",),
            topics=load_active_topics(Config().topic_config_path, ("detection",)),
        )
        papers = CVFSource(config)._parse_listing(
            CVF_HTML,
            venue="CVPR",
            year=2026,
            listing_url="https://openaccess.thecvf.com/CVPR2026?day=all",
        )
        self.assertEqual(len(papers), 1)
        paper = papers[0]
        self.assertEqual(paper.venue, "CVPR")
        self.assertEqual(paper.year, 2026)
        self.assertIn("detection", paper.topics)
        self.assertTrue(paper.pdf_url and paper.pdf_url.endswith(".pdf"))
        self.assertTrue(paper.unique_id.startswith("cvf:"))


if __name__ == "__main__":
    unittest.main()
