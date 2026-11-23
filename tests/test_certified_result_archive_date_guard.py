"""Certified result archives must not be reused across meeting dates."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "src" / "publish_archive_results.py"
spec = importlib.util.spec_from_file_location("jra_result_archive_date_guard", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CertifiedResultDateGuardTest(unittest.TestCase):
    def test_matching_date_reused(self):
        payload = {"date": "2026-11-22", "summary": {"complete": True},
                   "races": [{"date": "2026-11-22", "track": "東京", "race_no": 4}]}
        with patch.object(module, "target", "2026-11-22"), patch.object(module, "load_json", return_value=payload):
            self.assertEqual(module.existing_complete_results(), payload)

    def test_wrong_archive_date_rejected(self):
        payload = {"date": "2026-11-21", "summary": {"complete": True},
                   "races": [{"date": "2026-11-21", "track": "東京", "race_no": 4}]}
        with patch.object(module, "target", "2026-11-22"), patch.object(module, "load_json", return_value=payload):
            with self.assertRaisesRegex(RuntimeError, "date mismatch"):
                module.existing_complete_results()

    def test_mixed_race_dates_rejected(self):
        payload = {"date": "2026-11-22", "summary": {"complete": True},
                   "races": [{"date": "2026-11-21", "track": "東京", "race_no": 4}]}
        with patch.object(module, "target", "2026-11-22"), patch.object(module, "load_json", return_value=payload):
            with self.assertRaisesRegex(RuntimeError, "date mismatch"):
                module.existing_complete_results()


if __name__ == "__main__":
    unittest.main()
