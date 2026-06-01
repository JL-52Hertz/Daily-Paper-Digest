import unittest
from datetime import date
from pathlib import Path

from paper_digest.schedule import (
    cron_lines,
    launchd_plist,
    parse_send_schedule,
    parse_send_times,
    parse_time_topic_map,
    rotate_topic_ids,
    windows_task_commands,
)


class ScheduleTests(unittest.TestCase):
    def test_parse_send_times(self) -> None:
        self.assertEqual(parse_send_times("8:00,12:30,20:05"), ("08:00", "12:30", "20:05"))

    def test_parse_send_times_dedupes(self) -> None:
        self.assertEqual(parse_send_times("08:00,8:00"), ("08:00",))

    def test_invalid_send_time(self) -> None:
        with self.assertRaises(ValueError):
            parse_send_times("25:00")

    def test_parse_time_topic_map(self) -> None:
        mapping = parse_time_topic_map("08:00=vlm,detection;21:00=efficient_training")
        self.assertEqual(mapping["08:00"], ("vlm", "detection"))
        self.assertEqual(mapping["21:00"], ("efficient_training",))

    def test_parse_send_schedule_accepts_plain_times(self) -> None:
        send_times, mapping = parse_send_schedule("08:00,21:00")
        self.assertEqual(send_times, ("08:00", "21:00"))
        self.assertEqual(mapping, {})

    def test_parse_send_schedule_accepts_time_topics(self) -> None:
        send_times, mapping = parse_send_schedule("08:00=vlm,detection;21:00=efficient_training")
        self.assertEqual(send_times, ("08:00", "21:00"))
        self.assertEqual(mapping["08:00"], ("vlm", "detection"))
        self.assertEqual(mapping["21:00"], ("efficient_training",))

    def test_rotate_topic_ids_by_date(self) -> None:
        topics = ("vlm", "detection", "efficient_training")
        self.assertEqual(rotate_topic_ids(topics, date(2026, 6, 2)), ("detection", "efficient_training", "vlm"))

    def test_cron_lines(self) -> None:
        lines = cron_lines(
            ("08:00", "12:30"),
            workdir=Path("/tmp/project"),
            timezone="Asia/Shanghai",
            uv_path="/usr/bin/uv",
        )
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("0 8 * * * "))
        self.assertTrue(lines[1].startswith("30 12 * * * "))
        self.assertIn("/usr/bin/uv run paper-digest run --send", lines[0])
        self.assertIn("--run-time 08:00", lines[0])
        self.assertIn("--run-time 12:30", lines[1])

    def test_launchd_plist(self) -> None:
        plist = launchd_plist(
            ("08:00", "12:30"),
            workdir=Path("/tmp/project"),
            timezone="Asia/Shanghai",
            uv_path="/usr/local/bin/uv",
        )
        self.assertIn("<string>/bin/sh</string>", plist)
        self.assertIn("/usr/local/bin/uv run paper-digest run --send", plist)
        self.assertIn('--run-time "$(date +%H:%M)"', plist)
        self.assertIn("<integer>8</integer>", plist)
        self.assertIn("<integer>30</integer>", plist)
        self.assertIn("Asia/Shanghai", plist)

    def test_windows_task_commands(self) -> None:
        commands = windows_task_commands(
            ("08:00", "12:30"),
            workdir=Path("C:/paper"),
            timezone="Asia/Shanghai",
            uv_path="C:/Users/me/.local/bin/uv.exe",
        )
        self.assertEqual(len(commands), 2)
        self.assertIn("Register-ScheduledTask", commands[0])
        self.assertIn("PaperDigest-0800", commands[0])
        self.assertIn("C:/Users/me/.local/bin/uv.exe", commands[0])
        self.assertIn("--run-time 08:00", commands[0])


if __name__ == "__main__":
    unittest.main()
