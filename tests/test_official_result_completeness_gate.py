"""Regression: incomplete discovery must never certify a new official result archive."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "src" / "publish_archive_results.py"
spec = importlib.util.spec_from_file_location("publish_archive_results_gate", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OfficialResultCompletenessGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / "today-results.json"
        self.rows = [
            {
                "race_date": module.target, "course": "東京", "race_no": "4",
                "race_id": "fixture-race", "horse_no": str(i),
                "finish_position": str(i), "horse_name": f"horse{i}",
            }
            for i in (1, 2, 3)
        ]

    def run_gate(self, expected):
        def csv_rows(path):
            return self.rows if path == module.RES else []
        with (
            patch.object(module, "read_csv", side_effect=csv_rows),
            patch.object(module, "expected_completed_race_count", return_value=expected),
            patch.object(module, "existing_complete_results", return_value=None),
            patch.object(module, "RESULT_OUT", self.out),
        ):
            return module.build_results({"races": []})

    def test_unknown_expected_count_rejects_partial_discovery(self):
        with self.assertRaisesRegex(RuntimeError, "incomplete result reconstruction"):
            self.run_gate(None)
        self.assertFalse(self.out.exists())

    def test_wrong_expected_count_rejects_partial_discovery(self):
        with self.assertRaises(RuntimeError):
            self.run_gate(2)
        self.assertFalse(self.out.exists())

    def test_verified_expected_count_can_publish(self):
        payload, source = self.run_gate(1)
        self.assertEqual(source, "CURRENT_OFFICIAL_RESULTS")
        self.assertTrue(payload["summary"]["complete"])
        self.assertTrue(self.out.exists())


if __name__ == "__main__":
    unittest.main()
