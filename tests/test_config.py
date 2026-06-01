import unittest
from datetime import date
from unittest.mock import patch

from paper_digest.config import Config


class ConfigTests(unittest.TestCase):
    def test_time_topic_map_extends_active_topic_ids(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "PAPER_DIGEST_TOPICS": "vlm,detection,efficient_training",
                "PAPER_DIGEST_SEND_TIMES": "08:00,21:00",
                "PAPER_DIGEST_TIME_TOPICS": "08:00=vlm,detection;21:00=efficient_training",
            },
            clear=True,
        ):
            config = Config.from_env(load_topics=False)
        self.assertEqual(config.topic_ids, ("vlm", "detection", "efficient_training"))
        self.assertEqual(config.time_topic_ids["08:00"], ("vlm", "detection"))
        self.assertEqual(config.send_times, ("08:00", "21:00"))

    def test_time_topic_map_rejects_unknown_time(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "PAPER_DIGEST_TOPICS": "vlm",
                "PAPER_DIGEST_SEND_TIMES": "08:00",
                "PAPER_DIGEST_TIME_TOPICS": "21:00=vlm",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "not listed in PAPER_DIGEST_SEND_TIMES"):
                Config.from_env(load_topics=False)

    def test_time_topic_map_rejects_unknown_topic(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "PAPER_DIGEST_TOPICS": "vlm",
                "PAPER_DIGEST_SEND_TIMES": "08:00",
                "PAPER_DIGEST_TIME_TOPICS": "08:00=detection",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "not listed in PAPER_DIGEST_TOPICS"):
                Config.from_env(load_topics=False)

    def test_time_topic_map_still_works_without_loading_topics(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "PAPER_DIGEST_TOPICS": "vlm,efficient_training",
                "PAPER_DIGEST_SEND_TIMES": "08:00,21:00",
                "PAPER_DIGEST_TIME_TOPICS": "21:00=efficient_training",
            },
            clear=True,
        ):
            config = Config.from_env(load_topics=False)
        self.assertEqual(config.time_topic_ids["21:00"], ("efficient_training",))

    def test_topic_ids_for_run_uses_time_slot_and_rotates(self) -> None:
        config = Config(
            topic_ids=("vlm", "detection", "efficient_training"),
            run_time="08:00",
            time_topic_ids={"08:00": ("vlm", "detection")},
        )
        self.assertEqual(config.topic_ids_for_run(on_date=date(2026, 6, 1)), ("detection", "vlm"))

    def test_summary_language_can_be_english(self) -> None:
        with patch.dict("os.environ", {"PAPER_DIGEST_SUMMARY_LANGUAGE": "english"}, clear=True):
            config = Config.from_env(load_topics=False)
        self.assertEqual(config.summary_language, "en")


if __name__ == "__main__":
    unittest.main()
