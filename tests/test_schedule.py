import unittest
from pathlib import Path

from paper_digest.schedule import cron_lines, launchd_plist, parse_send_times, windows_task_commands


class ScheduleTests(unittest.TestCase):
    def test_parse_send_times(self) -> None:
        self.assertEqual(parse_send_times("8:00,12:30,20:05"), ("08:00", "12:30", "20:05"))

    def test_parse_send_times_dedupes(self) -> None:
        self.assertEqual(parse_send_times("08:00,8:00"), ("08:00",))

    def test_invalid_send_time(self) -> None:
        with self.assertRaises(ValueError):
            parse_send_times("25:00")

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

    def test_launchd_plist(self) -> None:
        plist = launchd_plist(
            ("08:00", "12:30"),
            workdir=Path("/tmp/project"),
            timezone="Asia/Shanghai",
            uv_path="/usr/local/bin/uv",
        )
        self.assertIn("<string>/usr/local/bin/uv</string>", plist)
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


if __name__ == "__main__":
    unittest.main()
