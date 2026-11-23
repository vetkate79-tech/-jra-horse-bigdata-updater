"""Regression tests for date-scoped JRA archive completeness metadata."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "src" / "publish_archive_results.py"
spec = importlib.util.spec_from_file_location("jra_archive_date_count", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DATE = module.target.replace("-", "")


class DateScopedCountTest(unittest.TestCase):
    def expected(self, status):
        with patch.object(module, "load_json", return_value=status):
            return module.expected_completed_race_count()

    def test_multiple_dates_use_only_target_date(self):
        self.assertEqual(self.expected({
            "complete_dates": [DATE, "20260101"],
            "discovered_races": 48,
            "discovered_races_by_date": {DATE: 24, "20260101": 24},
        }), 24)

    def test_multiple_dates_without_per_date_count_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, "ambiguous global"):
            self.expected({"complete_dates": [DATE, "20260101"], "discovered_races": 48})

    def test_invalid_date_count_rejected(self):
        for value in (0, -1, "invalid"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "invalid per-date"):
                    self.expected({
                        "complete_dates": [DATE],
                        "discovered_races_by_date": {DATE: value},
                    })

    def test_unverified_date_is_not_certified(self):
        self.assertIsNone(self.expected({
            "complete_dates": ["20260101"],
            "discovered_races_by_date": {DATE: 24},
        }))

    def test_legacy_single_date_supported(self):
        self.assertEqual(self.expected({
            "complete_dates": [DATE], "discovered_races": 24,
        }), 24)


if __name__ == "__main__":
    unittest.main()
