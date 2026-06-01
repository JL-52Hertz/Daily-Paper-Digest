import unittest
from datetime import date
from unittest.mock import patch

from paper_digest.config import Config


class ConfigTests(unittest.TestCase):
    def test_time_topic_map_extends_active_topic_ids(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "PAPER_DIGEST_TOPICS": "vlm",
                "PAPER_DIGEST_SEND_TIMES": "08:00=vlm,detection;21:00=efficient_training",
            },
            clear=True,
        ):
            config = Config.from_env(load_topics=False)
        self.assertEqual(config.topic_ids, ("vlm", "detection", "efficient_training"))
        self.assertEqual(config.time_topic_ids["08:00"], ("vlm", "detection"))
        self.assertEqual(config.send_times, ("08:00", "21:00"))

    def test_legacy_time_topic_map_still_works(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "PAPER_DIGEST_TOPICS": "vlm",
                "PAPER_DIGEST_SEND_TIMES": "08:00,21:00",
                "PAPER_DIGEST_TIME_TOPICS": "08:00=vlm,detection;21:00=efficient_training",
            },
            clear=True,
        ):
            config = Config.from_env(load_topics=False)
        self.assertEqual(config.topic_ids, ("vlm", "detection", "efficient_training"))
        self.assertEqual(config.time_topic_ids["21:00"], ("efficient_training",))

    def test_topic_ids_for_run_uses_time_slot_and_rotates(self) -> None:
        config = Config(
            topic_ids=("vlm", "detection", "efficient_training"),
            run_time="08:00",
            time_topic_ids={"08:00": ("vlm", "detection")},
        )
        self.assertEqual(config.topic_ids_for_run(on_date=date(2026, 6, 1)), ("detection", "vlm"))


if __name__ == "__main__":
    unittest.main()
