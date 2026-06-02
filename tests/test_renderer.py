import unittest

from paper_digest.models import Paper
from paper_digest.renderer import render_wecom_markdown, render_wecom_text, split_text_chunks


class RendererTests(unittest.TestCase):
    def test_required_sections(self) -> None:
        paper = Paper(
            unique_id="arxiv:1",
            title="A VLM Paper",
            authors=["Alice", "Bob"],
            venue="ICLR",
            year=2025,
            paper_url="https://example.com/paper",
        )
        markdown = render_wecom_markdown(
            paper,
            {
                "title": "A VLM Paper",
                "authors": "Alice, Bob",
                "venue_year": "ICLR 2025",
                "paper_url": "https://example.com/paper",
                "code_url": "暂无公开代码",
                "motivation": "研究动机",
                "core_problem": "核心问题",
                "method": "方法",
                "experiments": "实验",
                "contributions": "贡献",
                "limitations": "以下为模型分析，论文未明确说明：局限",
            },
        )
        self.assertIn("每日论文精选", markdown)
        self.assertIn("研究方向", markdown)
        self.assertNotIn("每日 VLM 论文精选", markdown)
        for label in ("标题", "作者", "Venue/Year", "论文链接", "代码链接", "研究动机", "核心问题", "方法怎么实施", "实验结论", "贡献", "局限"):
            self.assertIn(label, markdown)

    def test_text_render_has_no_markdown_links(self) -> None:
        paper = Paper(
            unique_id="arxiv:1",
            title="A VLM Paper",
            authors=["Alice"],
            venue="CVPR",
            year=2026,
            paper_url="https://example.com/paper",
        )
        text = render_wecom_text(
            paper,
            {
                "title": "A VLM Paper",
                "authors": "Alice",
                "venue_year": "CVPR 2026",
                "paper_url": "https://example.com/paper",
                "code_url": "暂无公开代码",
                "motivation": "动机",
                "core_problem": "问题",
                "method": "方法",
                "experiments": "实验",
                "contributions": "贡献",
                "limitations": "以下为模型分析，论文未明确说明：局限",
            },
        )
        self.assertIn("论文链接：https://example.com/paper", text)
        self.assertNotIn("](https://example.com/paper)", text)

    def test_english_text_render(self) -> None:
        paper = Paper(
            unique_id="arxiv:1",
            title="A VLM Paper",
            authors=["Alice"],
            venue="CVPR",
            year=2026,
            paper_url="https://example.com/paper",
        )
        text = render_wecom_text(
            paper,
            {
                "title": "A VLM Paper",
                "authors": "Alice",
                "venue_year": "CVPR 2026",
                "paper_url": "https://example.com/paper",
                "code_url": "No public code yet",
                "motivation": "Motivation",
                "core_problem": "Problem",
                "method": "Method",
                "experiments": "Experiments",
                "contributions": "Contributions",
                "limitations": "Model analysis (paper does not explicitly state limitations): limitations",
            },
            language="en",
        )
        self.assertIn("Daily Paper Digest", text)
        self.assertIn("Research Topic", text)
        self.assertIn("Paper Link: https://example.com/paper", text)
        self.assertIn("Code Link: No public code yet", text)
        self.assertNotIn("每日论文精选", text)

    def test_markdown_splits_contributions_and_limitations(self) -> None:
        paper = Paper(unique_id="arxiv:1", title="A Paper")
        markdown = render_wecom_markdown(
            paper,
            {
                "title": "A Paper",
                "contributions": ["提出新任务", "设计新模块"],
                "limitations": "以下为模型分析，论文未明确说明：1）只在小规模数据测试 2）真实部署成本未知",
            },
        )
        self.assertIn("**贡献**：\n1. 提出新任务\n2. 设计新模块", markdown)
        self.assertIn("**局限**：\n以下为模型分析", markdown)
        self.assertIn("\n1）只在小规模数据测试", markdown)
        self.assertIn("\n2）真实部署成本未知", markdown)

    def test_legacy_contributions_limitations_still_renders(self) -> None:
        paper = Paper(unique_id="arxiv:1", title="A Paper")
        markdown = render_wecom_markdown(
            paper,
            {
                "title": "A Paper",
                "contributions_limitations": "旧格式贡献与局限",
            },
        )
        self.assertIn("**贡献**：旧格式贡献与局限", markdown)

    def test_text_splits_contributions_and_limitations(self) -> None:
        paper = Paper(unique_id="arxiv:1", title="A Paper")
        text = render_wecom_text(
            paper,
            {
                "title": "A Paper",
                "contributions": "1. 提出新任务 2. 设计新模块",
                "limitations": ["以下为模型分析，论文未明确说明：数据规模有限", "部署开销仍需验证"],
            },
        )
        self.assertIn("贡献：\n1. 提出新任务\n2. 设计新模块", text)
        self.assertIn("局限：\n1. 以下为模型分析，论文未明确说明：数据规模有限\n2. 部署开销仍需验证", text)
        self.assertNotIn("贡献与局限", text)

    def test_split_text_chunks(self) -> None:
        chunks = split_text_chunks("第一段\n\n" + "x" * 20 + "\n\n第三段", max_chars=12)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(chunks[0].startswith("(1/"))


if __name__ == "__main__":
    unittest.main()
