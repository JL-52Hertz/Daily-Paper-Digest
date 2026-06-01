# Daily Paper Digest

<p align="center">
  <img src="assets/logo.png" alt="Daily Paper Digest logo" width="85%">
</p>

Language: [中文](README.md) | English

Author: JL-52Hertz  
Email: 63718897@qq.com

---

## English Guide

### 1. What is this project?

Daily Paper Digest is a small automation tool for research paper sharing. It searches papers for your configured research topics, asks your configured LLM to write a structured digest in your chosen output language, stores everything in a local SQLite paper library, and sends one selected paper to a WeCom group robot.

It supports:

- Windows, Linux, and macOS.
- Multiple research topics.
- Multiple send times per day.
- Automatic deduplication.
- Manual PDF URL or local PDF import.
- WeCom `text` mode for better compatibility with regular WeChat clients.

The WeCom message starts with a generic heading:

```text
Daily Paper Digest
Research Topic: Object Detection
```

It no longer hardcodes “Daily VLM Paper”.

### 2. Requirements

You need:

- Python 3.11+
- uv
- One LLM backend: DeepSeek, OpenAI, Claude/Anthropic, Alibaba DashScope, Volcengine Ark, Baidu Qianfan, OpenAI-compatible, local Ollama, or llama.cpp
- WeCom group robot webhook
- Optional: Semantic Scholar API key

Install uv from the [official uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).

The simplest install commands are:

Linux/macOS:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installation, reopen your terminal and verify uv:

```bash
uv --version
```

Useful docs: [DeepSeek API](https://api-docs.deepseek.com/), [OpenAI API](https://platform.openai.com/docs/api-reference/chat/create), [Anthropic Claude API](https://docs.anthropic.com/en/api/messages), [Alibaba DashScope OpenAI-compatible mode](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope), [Volcengine Ark](https://www.volcengine.com/docs/82379/1399008), [Baidu Qianfan](https://cloud.baidu.com/doc/qianfan/index.html), and [WeCom group robot](https://developer.work.weixin.qq.com/document/path/91770).

### 3. Install

Clone the project first:

```bash
git clone https://github.com/JL-52Hertz/Daily-Paper-Digest.git daily-paper-digest
cd daily-paper-digest
```

If your machine does not have Python 3.11 yet, install it and pin this project to Python 3.11 after entering the project directory:

```bash
uv python install 3.11
uv python pin 3.11
```

After `uv python pin 3.11`, uv creates a `.python-version` file in the project directory. Future `uv run ...` commands in this project will prefer Python 3.11 without changing your system Python.

Install dependencies:

```bash
uv sync
```

Check the Python version used by this project:

```bash
uv run python --version
```

Create your local `.env` file.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux/macOS:

```bash
cp .env.example .env
```

Edit `.env` with your keys.

### 4. Configure `.env`

Minimal configuration:

```env
LLM_PROVIDER=deepseek
LLM_API_KEY=your_llm_api_key
LLM_MODEL=deepseek-v4-pro
LLM_BASE_URL=https://api.deepseek.com
WECOM_WEBHOOK_URL=your_wecom_webhook_url
WECOM_MESSAGE_TYPE=text
WECOM_TEXT_CHUNK_CHARS=1800
PAPER_DIGEST_SUMMARY_LANGUAGE=en
PAPER_DIGEST_TOPICS=vlm
PAPER_DIGEST_SEND_TIMES=08:00
TZ=Asia/Shanghai
```

Optional configuration:

```env
S2_API_KEY=your_semantic_scholar_api_key
PAPER_DIGEST_TOPIC_CONFIG=config/topics.json
PAPER_DIGEST_DB=data/papers.db
PAPER_DIGEST_SEND_TIMES="08:00=vlm,detection;21:00=efficient_training"
PAPER_DIGEST_VENUE_YEARS=2026,2025,2024
PAPER_DIGEST_LOOKBACK_DAYS=3
PAPER_DIGEST_CANDIDATE_LIMIT=50
PAPER_DIGEST_HTTP_TIMEOUT=30
PAPER_DIGEST_MAX_PDF_CHARS=24000
```

`PAPER_DIGEST_SUMMARY_LANGUAGE` controls the WeCom message language. Use `en` for English digests or `zh` for Chinese digests.

Backward compatibility: existing `DEEPSEEK_API_KEY` and `DEEPSEEK_MODEL` still work. New deployments should use only the unified `LLM_*` variables to avoid duplicate settings.

China cloud provider aliases:

- Alibaba DashScope / Qwen: `dashscope`; aliases: `aliyun`, `alibaba`, `qwen`, `bailian`
- Volcengine Ark / Doubao: `volcengine`; aliases: `ark`, `doubao`, `bytedance`
- Baidu Qianfan / ERNIE: `qianfan`; aliases: `baidu`, `wenxin`, `ernie`

Common LLM examples:

DeepSeek:

```env
LLM_PROVIDER=deepseek
LLM_API_KEY=your_deepseek_key
LLM_MODEL=deepseek-v4-pro
LLM_BASE_URL=https://api.deepseek.com
```

OpenAI:

```env
LLM_PROVIDER=openai
LLM_API_KEY=your_openai_key
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1
```

Claude / Anthropic:

```env
LLM_PROVIDER=anthropic
LLM_API_KEY=your_anthropic_key
LLM_MODEL=claude-3-5-sonnet-latest
LLM_BASE_URL=https://api.anthropic.com
```

Alibaba DashScope / Qwen:

```env
LLM_PROVIDER=dashscope
LLM_API_KEY=your_dashscope_key
LLM_MODEL=qwen-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

Volcengine Ark / Doubao:

```env
LLM_PROVIDER=volcengine
LLM_API_KEY=your_volcengine_ark_key
LLM_MODEL=doubao-seed-1-6-251015
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
```

Baidu Qianfan / ERNIE:

```env
LLM_PROVIDER=qianfan
LLM_API_KEY=your_qianfan_key
LLM_MODEL=ernie-4.0-turbo-128k
LLM_BASE_URL=https://qianfan.baidubce.com/v2
```

OpenAI-compatible services such as vLLM, LM Studio, SiliconFlow, OpenRouter, or other compatible gateways:

```env
LLM_PROVIDER=openai_compatible
LLM_API_KEY=your_api_key
LLM_MODEL=your_model_name
LLM_BASE_URL=https://your-provider.example/v1
```

Local Ollama:

```env
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b
LLM_BASE_URL=http://localhost:11434
```

Local llama.cpp server:

```env
LLM_PROVIDER=llama_cpp
LLM_MODEL=local-model
LLM_BASE_URL=http://localhost:8080/v1
```

### 5. First run

Check the paper database:

```bash
uv run paper-digest db stats
```

Preview without sending:

```bash
uv run paper-digest run --dry-run
```

The run command prints stage progress, including which source is being fetched, whether the PDF is being downloaded, and when the LLM is being called. If you prefer silent output:

```bash
uv run paper-digest run --dry-run --quiet
```

Send to WeCom:

```bash
uv run paper-digest run --send
```

Regenerate a cached summary:

```bash
uv run paper-digest run --dry-run --refresh-summary
```

### 6. Research topics

List topics:

```bash
uv run paper-digest topics list
```

Use one topic:

```env
PAPER_DIGEST_TOPICS=detection
```

Use multiple topics:

```env
PAPER_DIGEST_TOPICS=vlm,detection,efficient_training
```

If one send time has multiple topics, the system rotates the preferred topic by date for better diversity. For example:

```env
PAPER_DIGEST_TOPICS=vlm,detection
PAPER_DIGEST_SEND_TIMES=08:00
```

The 08:00 run alternates its preferred topic between `vlm` and `detection` day by day. If the preferred topic has no unsent paper, the system falls back to other topics in the same group.

Generate a new topic from a short name:

```bash
uv run paper-digest topics add "Efficient training"
```

Preview generated JSON only:

```bash
uv run paper-digest topics add "Efficient training" --dry-run
```

Generate without calling an LLM:

```bash
uv run paper-digest topics add "Efficient training" --no-llm
```

Enable the new topic in `.env`:

```env
PAPER_DIGEST_TOPICS=efficient_training
```

### 7. Paper sources

Automatic discovery currently uses:

- arXiv
- CVF OpenAccess for CVPR, ICCV, ECCV
- Semantic Scholar
- OpenReview for ICLR, NeurIPS, ICML, AAAI
- IEEE TPAMI through Semantic Scholar

All discovered papers are stored in `data/papers.db` and deduplicated.

### 8. Manual import

Import from a PDF URL:

```bash
uv run paper-digest import url "https://example.com/paper.pdf" \
  --topic detection \
  --venue CVPR \
  --year 2026
```

Skip PDF text extraction:

```bash
uv run paper-digest import url "https://example.com/paper.pdf" \
  --topic detection \
  --venue CVPR \
  --year 2026 \
  --no-pdf-text
```

Import from a local PDF:

```bash
uv run paper-digest import file /path/to/paper.pdf \
  --topic detection \
  --venue CVPR \
  --year 2026
```

Override metadata:

```bash
uv run paper-digest import file /path/to/paper.pdf \
  --title "A Sample Paper About Efficient Object Detection" \
  --authors "Alice, Bob" \
  --topic detection \
  --venue CVPR \
  --year 2026
```

### 9. Scheduling

One send time:

```env
PAPER_DIGEST_SEND_TIMES=08:00
```

Multiple send times:

```env
PAPER_DIGEST_SEND_TIMES=08:00,12:30,20:00
```

Route topics by send time:

```env
PAPER_DIGEST_TOPICS=vlm,detection,efficient_training
PAPER_DIGEST_SEND_TIMES="08:00=vlm,detection;21:00=efficient_training"
```

This means:

- `08:00` rotates the preferred topic between `vlm` and `detection` each day.
- `21:00` always uses `efficient_training`.

Show schedule:

```bash
uv run paper-digest schedule show
```

Linux cron:

```bash
uv run paper-digest schedule cron --workdir /path/to/wechat_paper
```

macOS launchd:

```bash
uv run paper-digest schedule launchd --workdir /path/to/wechat_paper --uv "$(which uv)" > ~/Library/LaunchAgents/com.paper-digest.daily.plist
launchctl load ~/Library/LaunchAgents/com.paper-digest.daily.plist
```

Windows Task Scheduler:

```powershell
where.exe uv
uv run paper-digest schedule windows --workdir C:\path\to\wechat_paper --uv C:\path\to\uv.exe
```

Copy and run the generated PowerShell commands.

### 10. Command reference

Global:

| Command | Description |
| --- | --- |
| `paper-digest --db PATH ...` | Use a custom SQLite database |

Run:

| Command | Description |
| --- | --- |
| `paper-digest run --dry-run` | Preview only |
| `paper-digest run --send` | Send to WeCom |
| `paper-digest run --refresh-summary` | Regenerate cached summary |
| `paper-digest run --run-time HH:MM` | Select the current send-time slot for per-time topic routing |
| `paper-digest run --quiet` | Hide run stage progress |

Database:

| Command | Description |
| --- | --- |
| `paper-digest db init` | Initialize database |
| `paper-digest db stats` | Show database stats |

Topics:

| Command / Option | Description |
| --- | --- |
| `paper-digest topics list` | List topics |
| `paper-digest topics add NAME` | Generate and add a topic |
| `--id ID` | Override generated topic id |
| `--dry-run` | Preview only |
| `--force` | Overwrite existing topic |
| `--no-llm` | Use local heuristic generation without calling an LLM |

Import:

| Option | Description |
| --- | --- |
| `import url PDF_URL` | Import from PDF URL |
| `import file PDF_PATH` | Import from local PDF |
| `--title` | Override title |
| `--authors` | Comma-separated authors |
| `--venue` | Venue, for example CVPR |
| `--year` | Publication year |
| `--paper-url` | Canonical paper page |
| `--code-url` | Code/project URL |
| `--abstract` | Override abstract |
| `--topic` | Topic id, repeatable |
| `--sent` | Mark as already sent |
| `--no-pdf-text` | Skip PDF text extraction |
| `--timeout` | HTTP timeout in seconds |
| `--quiet` | Hide progress output |

Schedule:

| Command | Description |
| --- | --- |
| `schedule show` | Show configured send times |
| `schedule cron` | Generate Linux cron lines |
| `schedule launchd` | Generate macOS launchd plist |
| `schedule windows` | Generate Windows Task Scheduler commands |

### 11. Troubleshooting

If regular WeChat cannot read the robot message, use:

```env
WECOM_MESSAGE_TYPE=text
```

If PDF download is slow, use a proxy. The `http://your-proxy-host:port` value below is a placeholder. Replace it with your own proxy address and port.

```bash
HTTPS_PROXY=http://your-proxy-host:port uv run paper-digest import url "PDF_URL" --topic detection --venue CVPR --year 2026
```

For example, some proxy tools use `http://127.0.0.1:7890`, some use `http://127.0.0.1:1087`, and some networks provide a different proxy address.

If you only want to register a paper first:

```bash
uv run paper-digest import url "PDF_URL" --topic detection --venue CVPR --year 2026 --no-pdf-text
```

If scheduled jobs fail, generate scheduler config with an absolute uv path and check logs.

Quick API connectivity checks:

```bash
curl -I https://export.arxiv.org
curl -I https://api.deepseek.com        # DeepSeek
curl -I https://api.openai.com          # OpenAI
curl -I https://api.anthropic.com       # Claude/Anthropic
curl -I https://dashscope.aliyuncs.com  # Alibaba DashScope
curl -I https://ark.cn-beijing.volces.com # Volcengine Ark
curl -I https://qianfan.baidubce.com    # Baidu Qianfan
curl -I http://localhost:11434          # Ollama local model
curl -I http://localhost:8080/v1/models # llama.cpp server local model
curl -I https://qyapi.weixin.qq.com
```
