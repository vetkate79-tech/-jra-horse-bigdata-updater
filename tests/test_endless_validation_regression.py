import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("endless", Path(__file__).resolve().parents[1] / "src/run_endless_validation.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

class DiagnosticRegression(unittest.TestCase):
    def test_invalid_numeric_values(self):
        for value in ("", None, "NaN", "inf", "-1", "unknown"):
            self.assertIsNone(m.num(value))
        self.assertEqual(m.num("0"), 0)

    def test_persistent_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            old_source, old_state = m.SOURCE, m.STATE
            try:
                m.SOURCE = Path(directory) / "input.csv"
                m.STATE = Path(directory) / "state.json"
                fields = ["week", "race_id", "model_version", "stake_yen", "payout_yen", "is_hit", "data_status"]
                rows = []
                for week in range(5):
                    for index in range(6):
                        rows.append([str(week), f"race-{week}-{index}", "A", "100", "200", "1", "PASS"])
                rows.append(["4", "missing", "A", "100", "", "0", "PASS"])
                rows.append(["4", "rejected", "A", "100", "0", "0", "FAIL"])
                with m.SOURCE.open("w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(fields)
                    writer.writerows(rows)
                m.main()
                first = json.loads(m.STATE.read_text())
                self.assertEqual(first["evaluation_scope"], "DIAGNOSTIC_ONLY")
                self.assertEqual(first["race_usage"]["missing"]["purpose"], "QUARANTINE")
                self.assertEqual(first["race_usage"]["rejected"]["purpose"], "QUARANTINE")
                self.assertEqual(first["race_usage"]["race-0-0"]["purpose"], "DIAGNOSTIC_TRAIN")
                self.assertEqual(first["race_usage"]["race-4-0"]["purpose"], "DIAGNOSTIC_TEST")
                self.assertEqual(first["evaluated_weeks"][0]["bets"], 6)
                m.main()
                second = json.loads(m.STATE.read_text())
                self.assertEqual(first["race_usage"], second["race_usage"])
                self.assertEqual(first["evaluated_weeks"], second["evaluated_weeks"])
            finally:
                m.SOURCE, m.STATE = old_source, old_state

if __name__ == "__main__":
    unittest.main()
