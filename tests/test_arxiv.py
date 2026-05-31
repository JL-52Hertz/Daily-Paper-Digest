import unittest

from paper_digest.sources.arxiv import ArxivSource


FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2501.00001v2</id>
    <updated>2025-01-02T00:00:00Z</updated>
    <published>2025-01-01T00:00:00Z</published>
    <title> A Vision-Language Model for Document VQA </title>
    <summary> We propose a multimodal LLM for visual question answering. Code: https://github.com/example/vlm </summary>
    <author><name>Alice</name></author>
    <author><name>Bob</name></author>
    <link title="pdf" href="http://arxiv.org/pdf/2501.00001v2" type="application/pdf"/>
    <arxiv:doi>10.123/test</arxiv:doi>
    <arxiv:journal_ref>CVPR 2025</arxiv:journal_ref>
  </entry>
</feed>
"""


class ArxivTests(unittest.TestCase):
    def test_parse_feed(self) -> None:
        papers = ArxivSource._parse_feed(FEED)
        self.assertEqual(len(papers), 1)
        paper = papers[0]
        self.assertEqual(paper.title, "A Vision-Language Model for Document VQA")
        self.assertEqual(paper.authors, ["Alice", "Bob"])
        self.assertEqual(paper.venue, "CVPR")
        self.assertEqual(paper.year, 2025)
        self.assertEqual(paper.arxiv_id, "2501.00001")
        self.assertEqual(paper.code_url, "https://github.com/example/vlm")
        self.assertIn("vlm", paper.topics)


if __name__ == "__main__":
    unittest.main()
