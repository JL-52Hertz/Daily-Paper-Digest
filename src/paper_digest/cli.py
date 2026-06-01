from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from paper_digest.collector import PaperCollector, parse_collect_sources
from paper_digest.config import Config
from paper_digest.dashboard import serve_dashboard
from paper_digest.importer import ImportOptions, PaperImporter
from paper_digest.library import PaperLibrary
from paper_digest.progress import StageProgress
from paper_digest.runner import PaperDigestRunner
from paper_digest.schedule import cron_lines, launchd_plist, windows_task_commands
from paper_digest.topic_generator import (
    add_topic_to_file,
    ensure_topic_can_be_added,
    generate_topic,
    topic_id_from_name,
    topic_to_dict,
)
from paper_digest.topics import load_topic_catalog
from paper_digest.topics import load_active_topics


def main(argv: list[str] | None = None) -> int:
    load_dotenv(Path(".env"))
    parser = build_parser()
    args = parser.parse_args(argv)
    load_topics = not (args.command == "topics" and getattr(args, "topics_command", None) == "add")
    config = Config.from_env(load_topics=load_topics)
    if getattr(args, "db", None):
        config.db_path = Path(args.db)
    if getattr(args, "timeout", None):
        config.http_timeout = args.timeout
    if getattr(args, "run_time", None):
        config.run_time = args.run_time

    if args.command == "run":
        progress = StageProgress(total=10, enabled=not args.quiet)
        rotate_topics = args.send or bool(args.run_time)
        result = PaperDigestRunner(config, progress=progress).run(
            send=args.send,
            refresh_summary=args.refresh_summary,
            rotate_topics=rotate_topics,
            refresh_library=args.refresh_library,
        )
        print(result.message)
        if result.markdown:
            print()
            print(result.markdown)
        return 0 if (result.sent or not args.send) else 2

    if args.command == "db":
        with PaperLibrary(config.db_path) as library:
            if args.db_command == "init":
                print(f"Initialized database: {config.db_path}")
                return 0
            if args.db_command == "stats":
                stats = library.stats()
                for key, value in stats.items():
                    print(f"{key}: {value}")
                return 0

    if args.command == "topics":
        catalog = load_topic_catalog(config.topic_config_path)
        if args.topics_command == "list":
            for topic in catalog.values():
                active = " *" if topic.id in config.topic_ids else ""
                print(f"{topic.id}{active}: {topic.name}")
                if topic.description:
                    print(f"  {topic.description}")
            return 0
        if args.topics_command == "add":
            topic_id = topic_id_from_name(args.id or args.name)
            ensure_topic_can_be_added(config.topic_config_path, topic_id, force=args.force)
            topic = generate_topic(args.name, config=config, topic_id=topic_id, use_llm=not args.no_llm)
            if args.dry_run:
                print(json.dumps(topic_to_dict(topic), ensure_ascii=False, indent=2))
                return 0
            add_topic_to_file(config.topic_config_path, topic, force=args.force)
            print(f"Added topic: {topic.id} - {topic.name}")
            print(f"Update .env to enable it: PAPER_DIGEST_TOPICS={topic.id}")
            return 0

    if args.command == "import":
        with PaperLibrary(config.db_path) as library:
            importer = PaperImporter(config, library)
            options = ImportOptions(
                title=args.title,
                authors=_split_authors(args.authors),
                venue=args.venue,
                year=args.year,
                paper_url=args.paper_url,
                code_url=args.code_url,
                abstract=args.abstract,
                topics=tuple(args.topic or ()) or None,
                force_sent=args.sent,
            )
            if args.import_command == "url":
                print(
                    "Importing PDF URL"
                    + (" without PDF text extraction..." if args.no_pdf_text else " and extracting PDF text..."),
                    file=sys.stderr,
                    flush=True,
                )
                result = importer.import_url(
                    args.pdf_url,
                    options,
                    extract_text=not args.no_pdf_text,
                    show_progress=not args.quiet,
                )
            elif args.import_command == "file":
                print(
                    "Importing local PDF"
                    + (" without PDF text extraction..." if args.no_pdf_text else " and extracting PDF text..."),
                    file=sys.stderr,
                    flush=True,
                )
                result = importer.import_file(
                    args.pdf_path,
                    options,
                    extract_text=not args.no_pdf_text,
                    show_progress=not args.quiet,
                )
            else:
                parser.print_help()
                return 1
            print(result.message)
            print(f"title: {result.paper.title}")
            print(f"venue/year: {result.paper.venue_year_text}")
            print(f"topics: {result.paper.topics_text}")
            return 0

    if args.command == "collect":
        topic_ids = _split_csv(args.topics) or config.topic_ids
        years = _split_ints(args.years) or config.venue_years
        sources = parse_collect_sources(args.sources)
        config.topic_ids = topic_ids
        config.topics = load_active_topics(config.topic_config_path, topic_ids)
        progress = StageProgress(total=len(sources) + 3, enabled=not args.quiet)
        result = PaperCollector(config, progress=progress).collect(
            topic_ids=topic_ids,
            years=years,
            sources=sources,
            limit=args.limit,
            include_existing=args.include_existing,
            balance=not args.no_balance,
        )
        print(f"candidates: {result.candidates}")
        print(f"selected: {result.selected}")
        print(f"upserted: {result.upserted}")
        for source, count in result.source_counts.items():
            print(f"{source}: {count}")
        if result.errors:
            print("errors:")
            for error in result.errors:
                print(f"- {error}")
        return 0

    if args.command == "schedule":
        if args.schedule_command == "show":
            print("send_times: " + ", ".join(config.send_times))
            print(f"timezone: {config.timezone}")
            if config.time_topic_ids:
                print("time_topics:")
                for send_time in config.send_times:
                    topics = config.time_topic_ids.get(send_time, config.topic_ids)
                    print(f"  {send_time}: {', '.join(topics)}")
            else:
                print("topics: " + ", ".join(config.topic_ids))
            return 0
        if args.schedule_command == "cron":
            workdir = Path(args.workdir).resolve() if args.workdir else Path.cwd()
            for line in cron_lines(
                config.send_times,
                workdir=workdir,
                timezone=config.timezone,
                uv_path=args.uv,
                log_path=args.log,
            ):
                print(line)
            return 0
        if args.schedule_command == "launchd":
            workdir = Path(args.workdir).resolve() if args.workdir else Path.cwd()
            print(
                launchd_plist(
                    config.send_times,
                    workdir=workdir,
                    timezone=config.timezone,
                    uv_path=args.uv,
                    label=args.label,
                    stdout_path=args.stdout,
                    stderr_path=args.stderr,
                )
            )
            return 0
        if args.schedule_command == "windows":
            workdir = Path(args.workdir) if args.workdir else Path.cwd()
            for command in windows_task_commands(
                config.send_times,
                workdir=workdir,
                timezone=config.timezone,
                uv_path=args.uv,
                task_prefix=args.task_prefix,
                log_path=args.log,
            ):
                print(command)
            return 0

    if args.command == "web":
        serve_dashboard(config, host=args.host, port=args.port)
        return 0

    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paper-digest", description="Daily research paper digest for WeCom.")
    parser.add_argument("--db", help="SQLite database path. Defaults to PAPER_DIGEST_DB or data/papers.db.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Discover, summarize, and optionally send one paper.")
    mode = run.add_mutually_exclusive_group()
    mode.add_argument("--send", action="store_true", help="Send the digest to WeCom.")
    mode.add_argument("--dry-run", action="store_true", help="Preview without sending. This is the default.")
    run.add_argument("--refresh-summary", action="store_true", help="Regenerate summary even if one is cached.")
    run.add_argument("--refresh-library", action="store_true", help="Fetch online sources before selecting a paper.")
    run.add_argument("--run-time", help="Schedule slot being executed, for example 08:00. Used for per-time topics.")
    run.add_argument("--quiet", action="store_true", help="Hide run progress output.")

    db = subparsers.add_parser("db", help="Manage the local paper library.")
    db_sub = db.add_subparsers(dest="db_command", required=True)
    db_sub.add_parser("init", help="Initialize the SQLite database.")
    db_sub.add_parser("stats", help="Show database counts.")

    import_parser = subparsers.add_parser("import", help="Import a paper from a PDF URL or local PDF file.")
    import_sub = import_parser.add_subparsers(dest="import_command", required=True)
    import_url = import_sub.add_parser("url", help="Import a paper from a PDF URL.")
    import_url.add_argument("pdf_url", help="PDF URL to download and import.")
    _add_import_options(import_url)
    import_file = import_sub.add_parser("file", help="Import a paper from a local PDF file.")
    import_file.add_argument("pdf_path", help="Local PDF path to import.")
    _add_import_options(import_file)

    collect = subparsers.add_parser("collect", help="Fetch online paper metadata into the local library.")
    collect.add_argument("--topics", help="Comma-separated topic ids. Defaults to PAPER_DIGEST_TOPICS.")
    collect.add_argument("--years", help="Comma-separated years. Defaults to PAPER_DIGEST_VENUE_YEARS.")
    collect.add_argument("--limit", type=int, default=100, help="Maximum number of new papers to store.")
    collect.add_argument(
        "--sources",
        default="cvf,openreview",
        help="Comma-separated sources: cvf,openreview,arxiv,semantic_scholar,tpami.",
    )
    collect.add_argument("--include-existing", action="store_true", help="Allow updating papers already in the DB.")
    collect.add_argument("--no-balance", action="store_true", help="Do not balance selection across topics.")
    collect.add_argument("--quiet", action="store_true", help="Hide collection progress output.")

    topics = subparsers.add_parser("topics", help="Inspect configured research topics.")
    topics_sub = topics.add_subparsers(dest="topics_command", required=True)
    topics_sub.add_parser("list", help="List available topics. Active topics are marked with '*'.")
    topics_add = topics_sub.add_parser("add", help="Generate and add a new topic from a short name.")
    topics_add.add_argument("name", help='Topic name, for example "Efficient training".')
    topics_add.add_argument("--id", help="Override generated topic id.")
    topics_add.add_argument("--dry-run", action="store_true", help="Print generated topic JSON without writing topics.json.")
    topics_add.add_argument("--force", action="store_true", help="Overwrite an existing topic with the same id.")
    topics_add.add_argument("--no-llm", action="store_true", help="Use local heuristic generation even if an LLM is configured.")

    schedule = subparsers.add_parser("schedule", help="Inspect or generate send schedules.")
    schedule_sub = schedule.add_subparsers(dest="schedule_command", required=True)
    schedule_sub.add_parser("show", help="Show configured send times.")
    cron = schedule_sub.add_parser("cron", help="Print crontab lines for configured send times.")
    cron.add_argument("--workdir", help="Project directory for the cron command. Defaults to current directory.")
    cron.add_argument("--uv", help="uv executable path. Defaults to the uv found in PATH.")
    cron.add_argument("--log", default="logs/paper-digest.log", help="Log path used in cron redirection.")
    launchd = schedule_sub.add_parser("launchd", help="Print a macOS launchd plist for configured send times.")
    launchd.add_argument("--workdir", help="Project directory for the launchd job. Defaults to current directory.")
    launchd.add_argument("--uv", help="uv executable path. Use an absolute path for launchd.")
    launchd.add_argument("--label", default="com.paper-digest.daily", help="launchd job label.")
    launchd.add_argument("--stdout", default="logs/paper-digest.log", help="Relative stdout log path.")
    launchd.add_argument("--stderr", default="logs/paper-digest.err.log", help="Relative stderr log path.")
    windows = schedule_sub.add_parser("windows", help="Print PowerShell commands for Windows Task Scheduler.")
    windows.add_argument("--workdir", help="Project directory for the scheduled task. Defaults to current directory.")
    windows.add_argument("--uv", help="uv executable path, for example C:\\Users\\you\\.local\\bin\\uv.exe.")
    windows.add_argument("--task-prefix", default="PaperDigest", help="Scheduled task name prefix.")
    windows.add_argument("--log", default="logs\\paper-digest.log", help="Log path used by the scheduled task.")

    web = subparsers.add_parser("web", help="Start a local web dashboard for the paper database.")
    web.add_argument("--host", default="127.0.0.1", help="Host to bind. Use 0.0.0.0 for server access.")
    web.add_argument("--port", type=int, default=8765, help="Port to bind.")
    return parser


def _add_import_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--title", help="Override paper title.")
    parser.add_argument("--authors", help="Comma-separated authors.")
    parser.add_argument("--venue", help="Override venue, for example CVPR.")
    parser.add_argument("--year", type=int, help="Override publication year.")
    parser.add_argument("--paper-url", help="Canonical paper page URL.")
    parser.add_argument("--code-url", help="Code/project URL.")
    parser.add_argument("--abstract", help="Override abstract.")
    parser.add_argument("--topic", action="append", help="Topic id. Can be repeated; defaults to active topics.")
    parser.add_argument("--sent", action="store_true", help="Import as already sent.")
    parser.add_argument("--no-pdf-text", action="store_true", help="Skip PDF download/text extraction; import metadata only.")
    parser.add_argument("--timeout", type=float, help="HTTP timeout in seconds for URL imports.")
    parser.add_argument("--quiet", action="store_true", help="Hide import progress output.")


def _split_authors(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return [author.strip() for author in value.split(",") if author.strip()]


def _split_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return tuple()
    return tuple(dict.fromkeys(item.strip().lower() for item in value.split(",") if item.strip()))


def _split_ints(value: str | None) -> tuple[int, ...]:
    if not value:
        return tuple()
    return tuple(int(item.strip()) for item in value.split(",") if item.strip())


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
