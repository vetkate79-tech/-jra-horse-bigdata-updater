#!/usr/bin/env python3
"""Synthetic regression tests for the retrospective Kochi audit (no race outcomes)."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from audit_kochi11_completeness import audit

def fixture():
    return {"horses": [
        {"horse_name": f"synthetic_{i}", "recent_starts": [
            {"race_date": "2026-11-01", "finish_position": 2},
            {"race_date": "2026-10-01", "finish_position": 3},
            {"race_date": "2026-09-01", "finish_position": 1},
            {"race_date": "2026-08-01", "finish_position": 4},
        ]} for i in range(11)]}

class AuditRegression(unittest.TestCase):
    def test_clean_research_only(self):
        result = audit(fixture())
        self.assertEqual(result["status"], "HISTORY_COMPLETE_RESEARCH_ONLY")
        self.assertFalse(result["formal_tickets_generated"])
        self.assertEqual(result["pre_start_seal"], "NOT_VERIFIED")

    def test_market_aliases_rejected(self):
        for key in ("odds_value", "popularityRank", "market-rank", "raceResult"):
            with self.subTest(key=key):
                data = fixture()
                data["horses"][0]["recent_starts"][0][key] = 5
                with self.assertRaisesRegex(ValueError, "leakage"):
                    audit(data)

    def test_target_date_and_later_rejected(self):
        for day in ("2026-11-21", "2026-11-22"):
            with self.subTest(day=day):
                data = fixture()
                data["horses"][0]["recent_starts"][0]["race_date"] = day
                with self.assertRaisesRegex(ValueError, "target-date leakage"):
                    audit(data)

    def test_invalid_dates_and_duplicate_rejected(self):
        for day in ("2026-02-30", "2026-1-1", "2026-10-01"):
            with self.subTest(day=day):
                data = fixture()
                data["horses"][0]["recent_starts"][0]["race_date"] = day
                with self.assertRaises(ValueError):
                    audit(data)

    def test_missing_history_research_block(self):
        data = fixture()
        data["horses"][0]["recent_starts"] = []
        self.assertEqual(audit(data)["status"], "BLOCKED_INCOMPLETE_HISTORY")

    def test_entry_count_rejected(self):
        data = fixture()
        data["horses"].pop()
        with self.assertRaisesRegex(ValueError, "expected 11"):
            audit(data)

if __name__ == "__main__":
    unittest.main()
