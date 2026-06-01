from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import quote, unquote, urlparse

from paper_digest.config import Config
from paper_digest.library import PaperLibrary
from paper_digest.models import Paper
from paper_digest.topics import TopicProfile, load_topic_catalog


def serve_dashboard(config: Config, *, host: str = "127.0.0.1", port: int = 8765) -> None:
    handler = _make_handler(config)
    server = ThreadingHTTPServer((host, port), handler)
    try:
        print(f"Paper Digest dashboard: http://{host}:{port}")
        print("Press Ctrl+C to stop.")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


def render_dashboard(config: Config) -> str:
    with PaperLibrary(config.db_path) as library:
        stats = library.stats()
        topic_stats = library.topic_stats()
    topics = load_topic_catalog(config.topic_config_path)
    return _page(
        "Paper Digest Dashboard",
        _overview_content(stats, topic_stats, topics, db_path=str(config.db_path)),
    )


def render_topic_page(config: Config, topic_id: str) -> str:
    normalized_topic_id = topic_id.strip().lower()
    with PaperLibrary(config.db_path) as library:
        topic_stats = {str(item["topic_id"]): item for item in library.topic_stats()}
        sent_papers = library.sent_papers_by_topic(normalized_topic_id)
    topics = load_topic_catalog(config.topic_config_path)
    topic = topics.get(normalized_topic_id)
    topic_name = topic.name if topic else normalized_topic_id
    stat = topic_stats.get(normalized_topic_id, {"topic_id": normalized_topic_id, "total": 0, "sent": 0, "unsent": 0})
    return _page(
        f"{topic_name} Sent Papers",
        _topic_content(normalized_topic_id, topic_name, stat, sent_papers, topic),
    )


def _make_handler(config: Config) -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/index.html"}:
                self._send_html(render_dashboard(config))
                return
            if parsed.path.startswith("/topic/"):
                topic_id = unquote(parsed.path.removeprefix("/topic/"))
                self._send_html(render_topic_page(config, topic_id))
                return
            if parsed.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            self.send_error(404, "Not found")

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_html(self, content: str) -> None:
            encoded = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return DashboardHandler


def _overview_content(
    stats: dict[str, int],
    topic_stats: list[dict[str, int | str]],
    topics: dict[str, TopicProfile],
    *,
    db_path: str,
) -> str:
    total = stats.get("total", 0)
    sent = stats.get("sent", 0)
    unsent = stats.get("unsent", 0)
    topic_rows = "\n".join(_topic_row(item, topics) for item in topic_stats)
    if not topic_rows:
        topic_rows = '<tr><td colspan="6" class="empty">No papers in the database yet.</td></tr>'
    return f"""
<section class="hero">
  <div>
    <p class="eyebrow">SQLite Library</p>
    <h1>Paper Digest Dashboard</h1>
    <p class="muted">Database path: <code>{escape(db_path)}</code></p>
  </div>
  {_pie(sent, unsent, "Sent", "Unsent")}
</section>

<section class="cards">
  {_metric_card("Total Papers", total)}
  {_metric_card("Sent", sent)}
  {_metric_card("Unsent", unsent)}
  {_metric_card("Target Venue", stats.get("target_venue", 0))}
</section>

<section>
  <div class="section-title">
    <h2>Topics</h2>
    <p class="muted">A paper tagged with multiple topics is counted once in each topic.</p>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Topic</th>
          <th>Total</th>
          <th>Sent</th>
          <th>Unsent</th>
          <th>Sent Ratio</th>
          <th>Sent Papers</th>
        </tr>
      </thead>
      <tbody>
        {topic_rows}
      </tbody>
    </table>
  </div>
</section>
""".strip()


def _topic_content(
    topic_id: str,
    topic_name: str,
    stat: dict[str, int | str],
    sent_papers: list[Paper],
    topic: TopicProfile | None,
) -> str:
    sent = int(stat["sent"])
    unsent = int(stat["unsent"])
    rows = "\n".join(_paper_row(paper) for paper in sent_papers)
    if not rows:
        rows = '<tr><td colspan="4" class="empty">No sent papers for this topic yet.</td></tr>'
    description = escape(topic.description) if topic and topic.description else "Sent paper history for this topic."
    return f"""
<p><a class="back" href="/">Back to dashboard</a></p>
<section class="hero">
  <div>
    <p class="eyebrow">{escape(topic_id)}</p>
    <h1>{escape(topic_name)}</h1>
    <p class="muted">{description}</p>
  </div>
  {_pie(sent, unsent, "Sent", "Unsent")}
</section>

<section class="cards">
  {_metric_card("Total", int(stat["total"]))}
  {_metric_card("Sent", sent)}
  {_metric_card("Unsent", unsent)}
</section>

<section>
  <div class="section-title">
    <h2>Sent Papers</h2>
    <p class="muted">Paper names already delivered to WeCom.</p>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Title</th>
          <th>Venue/Year</th>
          <th>Sent At</th>
          <th>Link</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
  </div>
</section>
""".strip()


def _topic_row(item: dict[str, int | str], topics: dict[str, TopicProfile]) -> str:
    topic_id = str(item["topic_id"])
    topic = topics.get(topic_id)
    topic_name = topic.name if topic else topic_id
    total = int(item["total"])
    sent = int(item["sent"])
    unsent = int(item["unsent"])
    ratio = _ratio(sent, total)
    return f"""
<tr>
  <td>
    <strong>{escape(topic_name)}</strong>
    <div class="muted small">{escape(topic_id)}</div>
  </td>
  <td>{total}</td>
  <td>{sent}</td>
  <td>{unsent}</td>
  <td>
    <div class="mini-pie" style="--sent-angle: {ratio * 360:.2f}deg"></div>
    <span>{ratio * 100:.1f}%</span>
  </td>
  <td><a class="button" href="/topic/{quote(topic_id)}">View sent papers</a></td>
</tr>
""".strip()


def _paper_row(paper: Paper) -> str:
    link = _external_link(paper.paper_url or paper.pdf_url)
    return f"""
<tr>
  <td><strong>{escape(paper.title)}</strong><div class="muted small">{escape(paper.unique_id)}</div></td>
  <td>{escape(paper.venue_year_text)}</td>
  <td>{escape(paper.sent_at or "")}</td>
  <td>{link}</td>
</tr>
""".strip()


def _metric_card(label: str, value: int) -> str:
    return f"""
<div class="card">
  <div class="metric">{value}</div>
  <div class="muted">{escape(label)}</div>
</div>
""".strip()


def _pie(sent: int, unsent: int, sent_label: str, unsent_label: str) -> str:
    total = sent + unsent
    ratio = _ratio(sent, total)
    return f"""
<div class="chart-card">
  <div class="pie" style="--sent-angle: {ratio * 360:.2f}deg"></div>
  <div class="legend">
    <span><i class="dot sent"></i>{escape(sent_label)}: {sent}</span>
    <span><i class="dot unsent"></i>{escape(unsent_label)}: {unsent}</span>
  </div>
</div>
""".strip()


def _external_link(url: str | None) -> str:
    if not url:
        return '<span class="muted">No link</span>'
    safe_url = escape(url, quote=True)
    return f'<a href="{safe_url}" target="_blank" rel="noreferrer">Open</a>'


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, part / total))


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --bg: #f6f8fb;
      --panel: #ffffff;
      --text: #172033;
      --muted: #64748b;
      --line: #d9e2ef;
      --sent: #2563eb;
      --unsent: #d6e0ee;
      --accent: #0f766e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background: var(--bg);
    }}
    main {{
      width: min(1180px, calc(100% - 32px));
      margin: 32px auto 56px;
    }}
    a {{ color: var(--sent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    h1, h2, p {{ margin-top: 0; }}
    h1 {{ margin-bottom: 8px; font-size: clamp(32px, 4vw, 52px); line-height: 1.05; }}
    h2 {{ margin-bottom: 4px; font-size: 24px; }}
    code {{
      padding: 2px 6px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #f8fafc;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 24px;
      align-items: center;
      padding: 28px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: var(--panel);
    }}
    .eyebrow {{
      margin-bottom: 8px;
      color: var(--accent);
      font-weight: 700;
      letter-spacing: .04em;
      text-transform: uppercase;
    }}
    .muted {{ color: var(--muted); }}
    .small {{ margin-top: 4px; font-size: 13px; }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin: 18px 0 28px;
    }}
    .card, .chart-card {{
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel);
      padding: 18px;
    }}
    .metric {{
      font-size: 34px;
      font-weight: 800;
      line-height: 1;
      margin-bottom: 8px;
    }}
    .chart-card {{
      display: grid;
      justify-items: center;
      gap: 12px;
      min-width: 190px;
    }}
    .pie, .mini-pie {{
      border-radius: 50%;
      background: conic-gradient(var(--sent) 0 var(--sent-angle), var(--unsent) var(--sent-angle) 360deg);
      position: relative;
    }}
    .pie {{ width: 132px; height: 132px; }}
    .pie::after, .mini-pie::after {{
      content: "";
      position: absolute;
      border-radius: 50%;
      background: var(--panel);
    }}
    .pie::after {{ inset: 28px; }}
    .mini-pie {{
      display: inline-block;
      width: 28px;
      height: 28px;
      vertical-align: middle;
      margin-right: 8px;
    }}
    .mini-pie::after {{ inset: 7px; }}
    .legend {{
      display: grid;
      gap: 6px;
      font-size: 14px;
      color: var(--muted);
    }}
    .dot {{
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      margin-right: 8px;
    }}
    .dot.sent {{ background: var(--sent); }}
    .dot.unsent {{ background: var(--unsent); border: 1px solid #bdc8d8; }}
    .section-title {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: end;
      margin-bottom: 12px;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: var(--panel);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 760px;
    }}
    th, td {{
      padding: 14px 16px;
      text-align: left;
      border-bottom: 1px solid var(--line);
      vertical-align: middle;
    }}
    th {{
      background: #f8fafc;
      color: #334155;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: .04em;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    .button {{
      display: inline-block;
      padding: 8px 10px;
      border: 1px solid #bfd1ea;
      border-radius: 8px;
      background: #eff6ff;
      font-weight: 600;
    }}
    .back {{
      display: inline-block;
      margin-bottom: 16px;
      font-weight: 700;
    }}
    .empty {{
      padding: 28px 16px;
      color: var(--muted);
      text-align: center;
    }}
    @media (max-width: 760px) {{
      main {{ width: min(100% - 20px, 1180px); margin-top: 16px; }}
      .hero {{ grid-template-columns: 1fr; padding: 20px; }}
      .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .chart-card {{ justify-items: start; }}
    }}
  </style>
</head>
<body>
  <main>
    {body}
  </main>
</body>
</html>"""
