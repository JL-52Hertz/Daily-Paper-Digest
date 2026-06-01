from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
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
            if parsed.path == "/assets/logo.png":
                self._send_logo()
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

        def _send_logo(self) -> None:
            logo_path = _logo_path()
            if logo_path is None:
                self.send_error(404, "Logo not found")
                return
            data = logo_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "public, max-age=3600")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

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
  <div class="hero-copy">
    <p class="eyebrow">SQLite Library</p>
    <h1>Paper Digest Dashboard</h1>
    <p class="lede">A local, read-only view of your paper library, delivery status, and topic coverage.</p>
    <p class="muted">Database path: <code>{escape(db_path)}</code></p>
  </div>
  <div class="hero-side">
    {_logo_panel()}
    {_pie(sent, unsent, "Sent", "Unsent")}
  </div>
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
  <div class="hero-copy">
    <p class="eyebrow">{escape(topic_id)}</p>
    <h1>{escape(topic_name)}</h1>
    <p class="lede">{description}</p>
  </div>
  <div class="hero-side">
    {_logo_panel(compact=True)}
    {_pie(sent, unsent, "Sent", "Unsent")}
  </div>
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


def _logo_panel(*, compact: bool = False) -> str:
    class_name = "logo-panel compact" if compact else "logo-panel"
    return f"""
<div class="{class_name}">
  <img src="/assets/logo.png" alt="Daily Paper Digest logo">
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


def _logo_path() -> Path | None:
    candidates = [
        Path.cwd() / "assets" / "logo.png",
        Path(__file__).resolve().parents[2] / "assets" / "logo.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --bg: #edf4fb;
      --panel: #ffffff;
      --panel-soft: #f8fbff;
      --text: #172033;
      --muted: #64748b;
      --line: #d4e0ee;
      --sent: #0f86b6;
      --unsent: #d9e7f6;
      --accent: #0f766e;
      --accent-2: #2563eb;
      --shadow: 0 18px 50px rgba(35, 57, 90, .12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        linear-gradient(180deg, rgba(255,255,255,.78), rgba(237,244,251,.88)),
        linear-gradient(135deg, #e8f5ff 0%, #f7fbff 46%, #e8f8f4 100%);
    }}
    main {{
      width: min(1180px, calc(100% - 32px));
      margin: 22px auto 56px;
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
    .topbar {{
      width: min(1180px, calc(100% - 32px));
      margin: 18px auto 0;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }}
    .brand-mark {{
      display: grid;
      place-items: center;
      width: 72px;
      height: 42px;
      border: 1px solid rgba(212,224,238,.9);
      border-radius: 10px;
      background: #07111f;
      overflow: hidden;
      box-shadow: 0 10px 28px rgba(15, 23, 42, .12);
    }}
    .brand-mark img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
    }}
    .brand-title {{
      font-weight: 800;
      font-size: 18px;
      white-space: nowrap;
    }}
    .brand-subtitle {{
      color: var(--muted);
      font-size: 13px;
    }}
    .topbar-pill {{
      padding: 9px 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255,255,255,.72);
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(270px, 390px);
      gap: 24px;
      align-items: center;
      padding: 30px;
      border: 1px solid rgba(212,224,238,.9);
      border-radius: 18px;
      background:
        linear-gradient(135deg, rgba(255,255,255,.96), rgba(242,249,255,.92)),
        var(--panel);
      box-shadow: var(--shadow);
      overflow: hidden;
      position: relative;
    }}
    .hero::before {{
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(90deg, rgba(15,134,182,.08), transparent 34%),
        linear-gradient(180deg, transparent, rgba(15,118,110,.06));
      pointer-events: none;
    }}
    .hero-copy, .hero-side {{
      position: relative;
      z-index: 1;
    }}
    .hero-side {{
      display: grid;
      gap: 14px;
    }}
    .eyebrow {{
      margin-bottom: 8px;
      color: var(--accent);
      font-weight: 700;
      letter-spacing: .04em;
      text-transform: uppercase;
    }}
    .lede {{
      max-width: 660px;
      color: #475569;
      font-size: 17px;
      line-height: 1.65;
    }}
    .muted {{ color: var(--muted); }}
    .small {{ margin-top: 4px; font-size: 13px; }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
      margin: 20px 0 30px;
    }}
    .card, .chart-card {{
      border: 1px solid rgba(212,224,238,.92);
      border-radius: 14px;
      background: rgba(255,255,255,.88);
      padding: 18px;
      box-shadow: 0 12px 30px rgba(35,57,90,.08);
    }}
    .card {{
      background:
        linear-gradient(180deg, rgba(255,255,255,.98), rgba(246,250,255,.96)),
        var(--panel);
    }}
    .metric {{
      color: #0f172a;
      font-size: 38px;
      font-weight: 800;
      line-height: 1;
      margin-bottom: 8px;
    }}
    .chart-card {{
      display: grid;
      justify-items: center;
      gap: 12px;
      min-width: 0;
      background: linear-gradient(180deg, #ffffff, #f4f8fd);
    }}
    .logo-panel {{
      border: 1px solid rgba(212,224,238,.88);
      border-radius: 16px;
      background: #07111f;
      padding: 10px;
      box-shadow: 0 16px 34px rgba(15, 23, 42, .18);
    }}
    .logo-panel.compact {{
      padding: 8px;
    }}
    .logo-panel img {{
      display: block;
      width: 100%;
      min-height: 132px;
      max-height: 190px;
      object-fit: cover;
      border-radius: 10px;
    }}
    .logo-panel.compact img {{
      min-height: 104px;
      max-height: 132px;
    }}
    .pie, .mini-pie {{
      border-radius: 50%;
      background: conic-gradient(var(--sent) 0 var(--sent-angle), var(--unsent) var(--sent-angle) 360deg);
      position: relative;
    }}
    .pie {{
      width: 142px;
      height: 142px;
      box-shadow: inset 0 0 0 1px rgba(15,23,42,.04), 0 14px 28px rgba(15,134,182,.16);
    }}
    .pie::after, .mini-pie::after {{
      content: "";
      position: absolute;
      border-radius: 50%;
      background: #ffffff;
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
      border: 1px solid rgba(212,224,238,.9);
      border-radius: 16px;
      background: rgba(255,255,255,.9);
      box-shadow: 0 14px 32px rgba(35,57,90,.08);
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
      background: #f4f8fd;
      color: #334155;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: .04em;
    }}
    tbody tr {{
      transition: background .16s ease;
    }}
    tbody tr:hover {{
      background: #f8fbff;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    .button {{
      display: inline-block;
      padding: 9px 12px;
      border: 1px solid #b9d7ee;
      border-radius: 999px;
      background: #ecf7ff;
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
      .topbar {{ width: min(100% - 20px, 1180px); align-items: flex-start; }}
      .topbar-pill {{ display: none; }}
      .brand-title {{ white-space: normal; }}
    }}
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand">
      <div class="brand-mark"><img src="/assets/logo.png" alt="Daily Paper Digest logo"></div>
      <div>
        <div class="brand-title">Daily Paper Digest</div>
        <div class="brand-subtitle">Local paper library dashboard</div>
      </div>
    </div>
    <div class="topbar-pill">Read-only SQLite view</div>
  </header>
  <main>
    {body}
  </main>
</body>
</html>"""
