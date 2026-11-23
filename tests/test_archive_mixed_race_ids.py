"""Reject top-three rows assembled from different official race IDs."""
import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "src" / "publish_archive_results.py"
spec = importlib.util.spec_from_file_location("jra_archive_mixed_ids", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MixedRaceIdTest(unittest.TestCase):
    def test_mixed_race_ids_do_not_certify_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = root / "results.csv"
            with results.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["race_date", "course", "race_no", "race_id", "finish_position", "horse_no"])
                writer.writeheader()
                for finish, race_id in [(1, "race-A"), (2, "race-B"), (3, "race-A")]:
                    writer.writerow({"race_date": "2026-11-22", "course": "東京", "race_no": 4, "race_id": race_id, "finish_position": finish, "horse_no": finish})
            with patch.object(module, "target", "2026-11-22"), patch.object(module, "RES", results), patch.object(module, "PAY", root / "missing.csv"), patch.object(module, "RESULT_OUT", root / "out.json"), patch.object(module, "expected_completed_race_count", return_value=1):
                with self.assertRaisesRegex(RuntimeError, "incomplete result reconstruction"):
                    module.build_results({"races": []})
                self.assertFalse((root / "out.json").exists())


if __name__ == "__main__":
    unittest.main()
