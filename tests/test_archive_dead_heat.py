"""JRA official dead heats must be certified without admitting duplicate horses."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "src" / "publish_archive_results.py"
spec = importlib.util.spec_from_file_location("jra_dead_heat", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DeadHeatTest(unittest.TestCase):
    def test_valid_dead_heat_podiums(self):
        for positions in ((1, 2, 2), (1, 1, 3), (1, 2, 3)):
            with self.subTest(positions=positions), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                rows = [{"race_date": "2026-11-22", "course": "東京", "race_no": "12",
                         "finish_position": str(pos), "horse_no": str(horse), "race_id": "official-race"}
                        for pos, horse in zip(positions, (12, 4, 13))]
                with patch.object(module, "target", "2026-11-22"), \
                     patch.object(module, "RES", root / "results.csv"), \
                     patch.object(module, "PAY", root / "payouts.csv"), \
                     patch.object(module, "RESULT_OUT", root / "results.json"), \
                     patch.object(module, "read_csv", side_effect=[rows, []]), \
                     patch.object(module, "expected_completed_race_count", return_value=1):
                    payload, source = module.build_results({"races": []})
                self.assertEqual(source, "CURRENT_OFFICIAL_RESULTS")
                self.assertTrue(payload["summary"]["complete"])
                self.assertEqual([r["finish"] for r in payload["races"][0]["top3_rows"]], list(positions))

    def test_duplicate_horse_in_dead_heat_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [{"race_date": "2026-11-22", "course": "東京", "race_no": "12",
                     "finish_position": str(pos), "horse_no": str(horse), "race_id": "official-race"}
                    for pos, horse in ((1, 12), (2, 4), (2, 4))]
            with patch.object(module, "target", "2026-11-22"), \
                 patch.object(module, "RES", root / "results.csv"), \
                 patch.object(module, "PAY", root / "payouts.csv"), \
                 patch.object(module, "read_csv", side_effect=[rows, []]), \
                 patch.object(module, "expected_completed_race_count", return_value=1), \
                 patch.object(module, "existing_complete_results", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "incomplete result reconstruction"):
                    module.build_results({"races": []})


if __name__ == "__main__":
    unittest.main()
