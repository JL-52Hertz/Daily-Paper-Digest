# 每日论文精选推送

<p align="center">
  <img src="assets/logo.png" alt="Daily Paper Digest logo" width="85%">
</p>

语言：中文 | [English](README.en.md)

作者：JL-52Hertz  
邮箱：63718897@qq.com

---

## 中文说明

### 1. 这个项目是做什么的？

这是一个自动化论文精选工具。它会在你设置的时间自动搜索指定研究方向的论文，使用你配置的大模型生成中文结构化总结，然后发送到企业微信群机器人。

默认可以关注 VLM，也可以改成目标检测、高效训练，或者你自己新增的方向。

它会做这些事：

- 从 arXiv、CVF OpenAccess、Semantic Scholar、OpenReview、TPAMI 来源收集论文。
- 用本地 SQLite 建立论文库，默认路径是 `data/papers.db`。
- 自动去重，避免同一篇论文重复发送。
- 每次发送 1 篇论文，发送成功后标记为已发送。
- 支持 Windows、Linux、macOS。
- 支持一天多个发送时间。
- 支持手动导入 PDF 链接或本地 PDF 文件。

发送到微信的内容标题现在是通用的：

```text
每日论文精选
研究方向：Object Detection
```

不会再固定写成“每日 VLM 论文精选”。

### 2. 安装前需要准备什么？

你需要：

- Python 3.11 或更高版本
- uv
- 一个大模型接口：DeepSeek、OpenAI、Claude/Anthropic、阿里 DashScope、字节火山方舟、百度千帆、OpenAI-compatible、本地 Ollama 或 llama.cpp
- 企业微信群机器人 Webhook
- 可选：Semantic Scholar API Key

uv 是一个 Python 项目管理工具，用来安装依赖和运行命令。更完整的说明可以看 [uv 官方安装教程](https://docs.astral.sh/uv/getting-started/installation/)。

最简单的安装方式如下。

Linux/macOS：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

安装完成后，重新打开终端，检查是否安装成功：

```bash
uv --version
```

相关文档入口：[DeepSeek API](https://api-docs.deepseek.com/)、[OpenAI API](https://platform.openai.com/docs/api-reference/chat/create)、[Anthropic Claude API](https://docs.anthropic.com/en/api/messages)、[阿里 DashScope OpenAI 兼容模式](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)、[火山方舟](https://www.volcengine.com/docs/82379/1399008)、[百度千帆](https://cloud.baidu.com/doc/qianfan/index.html)、[企业微信群机器人](https://developer.work.weixin.qq.com/document/path/91770)。

### 3. 第一次安装

先把项目下载到本地：

```bash
git clone https://github.com/JL-52Hertz/Daily-Paper-Digest.git daily-paper-digest
```

进入项目目录：

```bash
cd daily-paper-digest
```

如果你的电脑还没有 Python 3.11，可以在项目目录里让 uv 帮你安装，并固定当前项目使用 Python 3.11：

```bash
uv python install 3.11
uv python pin 3.11
```

执行 `uv python pin 3.11` 后，项目目录里会生成 `.python-version` 文件。以后在这个项目里运行 `uv run ...` 时，uv 会优先使用 Python 3.11，不会修改系统自带的 Python。

安装依赖：

```bash
uv sync
```

检查当前项目使用的 Python 版本：

```bash
uv run python --version
```

如果你在 Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

如果你在 Linux 或 macOS：

```bash
cp .env.example .env
```

然后编辑 `.env`。

Linux/macOS 可以用：

```bash
nano .env
```

Windows 可以用记事本或 VS Code 打开 `.env`。

### 4. 配置 .env

最小配置如下：

```env
LLM_PROVIDER=deepseek
LLM_API_KEY=你的_模型_API_Key
LLM_MODEL=deepseek-v4-pro
LLM_BASE_URL=https://api.deepseek.com
WECOM_WEBHOOK_URL=你的_企业微信群机器人_Webhook
WECOM_MESSAGE_TYPE=text
WECOM_TEXT_CHUNK_CHARS=1800
PAPER_DIGEST_TOPICS=vlm
PAPER_DIGEST_SEND_TIMES=08:00
TZ=Asia/Shanghai
```

可选配置：

```env
S2_API_KEY=你的_Semantic_Scholar_Key
PAPER_DIGEST_TOPIC_CONFIG=config/topics.json
PAPER_DIGEST_DB=data/papers.db
PAPER_DIGEST_SEND_TIMES="08:00=vlm,detection;21:00=efficient_training"
PAPER_DIGEST_VENUE_YEARS=2026,2025,2024
PAPER_DIGEST_LOOKBACK_DAYS=3
PAPER_DIGEST_CANDIDATE_LIMIT=50
PAPER_DIGEST_HTTP_TIMEOUT=30
PAPER_DIGEST_MAX_PDF_CHARS=24000
```

配置解释：

| 变量 | 必填 | 作用 |
| --- | --- | --- |
| `LLM_PROVIDER` | 否 | 大模型提供商，支持 `deepseek`、`openai`、`anthropic`、`dashscope`、`volcengine`、`qianfan`、`openai_compatible`、`ollama`、`llama_cpp` |
| `LLM_API_KEY` | 云端模型必填 | 大模型 API Key；本地 `ollama`/`llama_cpp` 通常不需要 |
| `LLM_MODEL` | 否 | 模型名称，例如 `deepseek-v4-pro`、`gpt-4o-mini`、`qwen-plus`、`doubao-seed-1-6-251015`、`ernie-4.0-turbo-128k`、`qwen2.5:7b` |
| `LLM_BASE_URL` | 否 | API 地址；留空会使用内置默认值，OpenAI-compatible、本地 Ollama、llama.cpp 时常需要改 |
| `WECOM_WEBHOOK_URL` | 是 | 企业微信群机器人 Webhook |
| `WECOM_MESSAGE_TYPE` | 否 | 推荐 `text`，普通微信也能看；`markdown` 只适合企业微信客户端 |
| `WECOM_TEXT_CHUNK_CHARS` | 否 | text 消息过长时自动拆分，每段最大字符数 |
| `S2_API_KEY` | 否 | Semantic Scholar API Key，不填也能跑，但可能更容易限流 |
| `PAPER_DIGEST_TOPICS` | 否 | 研究方向，多个方向用逗号分隔 |
| `PAPER_DIGEST_SEND_TIMES` | 否 | 每天发送时间。可写 `08:00,21:00`，也可写 `08:00=vlm,detection;21:00=efficient_training` 来指定每个时间段的方向 |
| `TZ` | 否 | 时区，建议中国用户使用 `Asia/Shanghai` |
| `PAPER_DIGEST_DB` | 否 | SQLite 论文库路径 |
| `PAPER_DIGEST_VENUE_YEARS` | 否 | 优先回溯哪些年份 |
| `PAPER_DIGEST_LOOKBACK_DAYS` | 否 | arXiv 最近论文回看天数 |
| `PAPER_DIGEST_CANDIDATE_LIMIT` | 否 | 每个来源最多抓多少候选 |
| `PAPER_DIGEST_HTTP_TIMEOUT` | 否 | 网络请求超时时间，单位秒 |
| `PAPER_DIGEST_MAX_PDF_CHARS` | 否 | 送给模型的 PDF 文本最大字符数 |

兼容旧配置：如果老用户已经在 `.env` 里写了 `DEEPSEEK_API_KEY` 和 `DEEPSEEK_MODEL`，仍然可以继续使用。新项目更推荐只使用统一的 `LLM_*` 配置，避免变量重复。

国内厂商别名也可以直接写在 `LLM_PROVIDER`：

- 阿里 DashScope / 通义千问：`dashscope`，也支持 `aliyun`、`alibaba`、`qwen`、`bailian`
- 字节火山方舟 / 豆包：`volcengine`，也支持 `ark`、`doubao`、`bytedance`
- 百度千帆 / 文心：`qianfan`，也支持 `baidu`、`wenxin`、`ernie`

常见模型配置示例：

DeepSeek：

```env
LLM_PROVIDER=deepseek
LLM_API_KEY=你的_DeepSeek_Key
LLM_MODEL=deepseek-v4-pro
LLM_BASE_URL=https://api.deepseek.com
```

OpenAI：

```env
LLM_PROVIDER=openai
LLM_API_KEY=你的_OpenAI_Key
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1
```

Claude / Anthropic：

```env
LLM_PROVIDER=anthropic
LLM_API_KEY=你的_Anthropic_Key
LLM_MODEL=claude-3-5-sonnet-latest
LLM_BASE_URL=https://api.anthropic.com
```

阿里云 DashScope / 通义千问：

```env
LLM_PROVIDER=dashscope
LLM_API_KEY=你的_DashScope_Key
LLM_MODEL=qwen-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

字节跳动火山方舟 / 豆包：

```env
LLM_PROVIDER=volcengine
LLM_API_KEY=你的_火山方舟_API_Key
LLM_MODEL=doubao-seed-1-6-251015
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
```

百度智能云千帆 / 文心：

```env
LLM_PROVIDER=qianfan
LLM_API_KEY=你的_千帆_API_Key
LLM_MODEL=ernie-4.0-turbo-128k
LLM_BASE_URL=https://qianfan.baidubce.com/v2
```

OpenAI-compatible 服务，例如 vLLM、LM Studio、硅基流动、OpenRouter 或其他兼容接口：

```env
LLM_PROVIDER=openai_compatible
LLM_API_KEY=你的_API_Key
LLM_MODEL=你的模型名
LLM_BASE_URL=https://你的服务地址/v1
```

本地 Ollama：

```env
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b
LLM_BASE_URL=http://localhost:11434
```

本地 llama.cpp server：

```env
LLM_PROVIDER=llama_cpp
LLM_MODEL=local-model
LLM_BASE_URL=http://localhost:8080/v1
```

### 5. 先跑通一次

检查数据库：

```bash
uv run paper-digest db stats
```

第一次可能看到：

```text
total: 0
sent: 0
unsent: 0
target_venue: 0
topic_tagged: 0
```

先预览，不发送微信：

```bash
uv run paper-digest run --dry-run
```

运行时会在终端显示阶段进度，例如正在抓取哪个来源、是否正在下载 PDF、是否正在调用大模型。这样网络慢时也能知道程序还在工作。如果你不想显示进度：

```bash
uv run paper-digest run --dry-run --quiet
```

确认内容没问题后正式发送：

```bash
uv run paper-digest run --send
```

如果你想强制重新生成某篇论文的总结：

```bash
uv run paper-digest run --dry-run --refresh-summary
```

### 6. 研究方向怎么改？

查看可用方向：

```bash
uv run paper-digest topics list
```

只看 VLM：

```env
PAPER_DIGEST_TOPICS=vlm
```

只看目标检测：

```env
PAPER_DIGEST_TOPICS=detection
```

同时看多个方向：

```env
PAPER_DIGEST_TOPICS=vlm,detection,efficient_training
```

如果一个发送时间对应多个方向，系统会每天轮换优先方向，尽量让内容更有多样性。例如只有每天 08:00 发送，并设置：

```env
PAPER_DIGEST_TOPICS=vlm,detection
PAPER_DIGEST_SEND_TIMES=08:00
```

那么 08:00 会在 `vlm` 和 `detection` 之间按日期轮换优先方向。如果当天优先方向没有可发论文，系统会自动尝试同一组里的其他方向，避免空跑。

如果你想添加新方向，比如高效训练：

```bash
uv run paper-digest topics add "Efficient training"
```

只预览，不写入文件：

```bash
uv run paper-digest topics add "Efficient training" --dry-run
```

完全离线生成，不调用大模型：

```bash
uv run paper-digest topics add "Efficient training" --no-llm
```

覆盖已有方向：

```bash
uv run paper-digest topics add "Efficient training" --force
```

生成后，把 `.env` 改成：

```env
PAPER_DIGEST_TOPICS=efficient_training
```

### 7. 自动论文来源

项目会从这些地方自动找论文：

- arXiv：按 topic 的 `categories` 和 `arxiv_terms` 搜索最近论文。
- CVF OpenAccess：抓 CVPR、ICCV、ECCV 官方 OpenAccess 页面。
- Semantic Scholar：补充 venue/year、作者、摘要、PDF 等元数据。
- OpenReview：抓 ICLR、NeurIPS、ICML、AAAI 等开放评审会议论文。
- IEEE TPAMI：通过 Semantic Scholar 定向检索 TPAMI 论文。

所有论文都会进入同一个 SQLite 论文库，然后统一去重。

### 8. 手动导入论文

如果你有一个 PDF 链接：

```bash
uv run paper-digest import url "https://example.com/paper.pdf" \
  --topic detection \
  --venue CVPR \
  --year 2026
```

如果网络慢，只想先登记，不下载 PDF 正文：

```bash
uv run paper-digest import url "https://example.com/paper.pdf" \
  --topic detection \
  --venue CVPR \
  --year 2026 \
  --no-pdf-text
```

如果你已经下载好了 PDF：

```bash
uv run paper-digest import file /path/to/paper.pdf \
  --topic detection \
  --venue CVPR \
  --year 2026
```

如果自动解析的标题不好，可以手动指定：

```bash
uv run paper-digest import file /path/to/paper.pdf \
  --title "A Sample Paper About Efficient Object Detection" \
  --authors "Alice, Bob" \
  --topic detection \
  --venue CVPR \
  --year 2026
```

导入命令会显示下载和解析进度条。如果不想显示：

```bash
uv run paper-digest import url "https://example.com/paper.pdf" --quiet
```

### 9. 定时发送

设置每天 08:00 发送：

```env
PAPER_DIGEST_SEND_TIMES=08:00
```

一天发送多次：

```env
PAPER_DIGEST_SEND_TIMES=08:00,12:30,20:00
```

按时间段指定研究方向：

```env
PAPER_DIGEST_TOPICS=vlm,detection,efficient_training
PAPER_DIGEST_SEND_TIMES="08:00=vlm,detection;21:00=efficient_training"
```

这个配置表示：

- `08:00` 在 `vlm` 和 `detection` 之间每天轮换优先方向。
- `21:00` 固定发送 `efficient_training` 方向。

查看当前时间配置：

```bash
uv run paper-digest schedule show
```

#### Linux: cron

生成 cron 行：

```bash
uv run paper-digest schedule cron --workdir /path/to/wechat_paper
```

编辑 crontab：

```bash
crontab -e
```

把生成的行粘进去。

查看日志：

```bash
tail -n 100 logs/paper-digest.log
```

#### macOS: launchd

生成 plist：

```bash
uv run paper-digest schedule launchd --workdir /path/to/wechat_paper --uv "$(which uv)" > ~/Library/LaunchAgents/com.paper-digest.daily.plist
```

加载任务：

```bash
launchctl load ~/Library/LaunchAgents/com.paper-digest.daily.plist
```

重新加载：

```bash
launchctl unload ~/Library/LaunchAgents/com.paper-digest.daily.plist
launchctl load ~/Library/LaunchAgents/com.paper-digest.daily.plist
```

#### Windows: Task Scheduler

先找 uv 路径：

```powershell
where.exe uv
```

生成任务计划命令：

```powershell
uv run paper-digest schedule windows --workdir C:\path\to\wechat_paper --uv C:\path\to\uv.exe
```

复制输出的 PowerShell 命令并执行。每个发送时间会生成一个任务。

### 10. 命令和参数总览

全局参数：

| 命令 | 说明 |
| --- | --- |
| `paper-digest --db PATH ...` | 临时指定 SQLite 数据库路径 |

运行：

| 命令 | 说明 |
| --- | --- |
| `paper-digest run --dry-run` | 预览，不发送微信 |
| `paper-digest run --send` | 正式发送到企业微信 |
| `paper-digest run --refresh-summary` | 忽略缓存，重新生成总结 |
| `paper-digest run --run-time HH:MM` | 指定当前执行的是哪个发送时间段，用于时间段方向映射 |
| `paper-digest run --quiet` | 不显示运行阶段进度 |

数据库：

| 命令 | 说明 |
| --- | --- |
| `paper-digest db init` | 初始化数据库 |
| `paper-digest db stats` | 查看论文库统计 |

研究方向：

| 命令 | 说明 |
| --- | --- |
| `paper-digest topics list` | 查看所有方向 |
| `paper-digest topics add NAME` | 自动生成并添加方向 |
| `--id ID` | 指定方向 ID |
| `--dry-run` | 只预览，不写入 |
| `--force` | 覆盖已有方向 |
| `--no-llm` | 不调用大模型，用本地规则生成 |

导入论文：

| 参数 | 说明 |
| --- | --- |
| `import url PDF_URL` | 从 PDF 链接导入 |
| `import file PDF_PATH` | 从本地 PDF 导入 |
| `--title` | 手动指定标题 |
| `--authors` | 手动指定作者，逗号分隔 |
| `--venue` | 手动指定 venue，例如 CVPR |
| `--year` | 手动指定年份 |
| `--paper-url` | 手动指定论文主页 |
| `--code-url` | 手动指定代码链接 |
| `--abstract` | 手动指定摘要 |
| `--topic` | 手动指定方向，可重复使用 |
| `--sent` | 导入时标记为已发送 |
| `--no-pdf-text` | 不下载/解析 PDF 正文 |
| `--timeout` | URL 导入的 HTTP 超时时间 |
| `--quiet` | 不显示进度条 |

定时任务：

| 命令 | 说明 |
| --- | --- |
| `schedule show` | 查看发送时间 |
| `schedule cron` | 生成 Linux cron 配置 |
| `schedule launchd` | 生成 macOS launchd plist |
| `schedule windows` | 生成 Windows 任务计划命令 |

### 11. 常见问题

**普通微信看不到 markdown 消息怎么办？**

把 `.env` 设置为：

```env
WECOM_MESSAGE_TYPE=text
```

**下载 PDF 很慢怎么办？**

可以使用代理，但每个人的代理地址和端口不一样。下面命令里的 `http://你的代理地址:端口` 是占位写法，请替换成你自己机器上的代理地址。

```bash
HTTPS_PROXY=http://你的代理地址:端口 uv run paper-digest import url "PDF链接" --topic detection --venue CVPR --year 2026
```

例如有些代理软件可能是 `http://127.0.0.1:7890`，有些可能是 `http://127.0.0.1:1087`，也可能是公司或服务器提供的其他地址。

也可以先登记：

```bash
uv run paper-digest import url "PDF链接" --topic detection --venue CVPR --year 2026 --no-pdf-text
```

**cron 不执行怎么办？**

先用绝对路径生成：

```bash
uv run paper-digest schedule cron --workdir /path/to/wechat_paper --uv /absolute/path/to/uv
```

再检查日志：

```bash
tail -n 100 logs/paper-digest.log
```

**如何确认 API 和企业微信能连通？**

```bash
curl -I https://export.arxiv.org
curl -I https://api.deepseek.com        # DeepSeek
curl -I https://api.openai.com          # OpenAI
curl -I https://api.anthropic.com       # Claude/Anthropic
curl -I https://dashscope.aliyuncs.com  # 阿里 DashScope
curl -I https://ark.cn-beijing.volces.com # 火山方舟
curl -I https://qianfan.baidubce.com    # 百度千帆
curl -I http://localhost:11434          # Ollama，本地模型
curl -I http://localhost:8080/v1/models # llama.cpp server，本地模型
curl -I https://qyapi.weixin.qq.com
```

企业微信 webhook 可以用一条 text 消息测试。

---
