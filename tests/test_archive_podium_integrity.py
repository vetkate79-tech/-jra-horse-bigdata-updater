"""Fail-closed regression: duplicate podium rows cannot certify a complete race."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "src" / "publish_archive_results.py"
spec = importlib.util.spec_from_file_location("jra_archive_podium", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PodiumIntegrityTest(unittest.TestCase):
    def test_duplicate_first_place_does_not_certify_race(self):
        date = "2026-11-22"
        rows = [
            {"race_date": date, "course": "東京", "race_no": "4",
             "finish_position": pos, "horse_no": horse, "race_id": "test"}
            for pos, horse in [(1, 1), (1, 1), (2, 2)]
        ]
        with patch.object(module, "target", date), \
             patch.object(module, "RES", Path("dummy_results.csv")), \
             patch.object(module, "PAY", Path("dummy_payouts.csv")), \
             patch.object(module, "read_csv", side_effect=[rows, []]), \
             patch.object(module, "expected_completed_race_count", return_value=1), \
             patch.object(module, "existing_complete_results", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "incomplete result reconstruction"):
                module.build_results({"races": []})


if __name__ == "__main__":
    unittest.main()
