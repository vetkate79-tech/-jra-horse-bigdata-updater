"""Fail-closed tests for cross-date entries in immutable prediction archives."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "src" / "publish_archive_results.py"
spec = importlib.util.spec_from_file_location("jra_prediction_archive_guard", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
TARGET = "2026-11-22"


class ImmutablePredictionDateGuardTest(unittest.TestCase):
    def check(self, races, pending):
        payload = {
            "date": TARGET,
            "mode": "IMMUTABLE_PREDICTION_ARCHIVE",
            "races": races,
            "pending": pending,
        }
        with patch.object(module, "target", TARGET), patch.object(module, "load_json", return_value=payload):
            return module.load_prediction_archive()

    def test_matching_date_is_reused(self):
        archive, source = self.check([{"date": TARGET, "race_no": 4}], [])
        self.assertEqual(source, "IMMUTABLE_ARCHIVE")
        self.assertEqual(archive["races"][0]["race_no"], 4)

    def test_cross_date_race_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "cross-date entries"):
            self.check([{"date": "2026-11-21", "race_no": 4}], [])

    def test_cross_date_pending_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "cross-date entries"):
            self.check([{"date": TARGET, "race_no": 4}], [{"date": "2026-11-21"}])

    def test_missing_entry_date_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "cross-date entries"):
            self.check([{"race_no": 4}], [])


if __name__ == "__main__":
    unittest.main()
