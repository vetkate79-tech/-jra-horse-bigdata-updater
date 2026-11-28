#!/usr/bin/env python3
"""Synthetic regression tests for the retrospective Kochi audit (no race outcomes)."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from audit_kochi11_completeness import audit
from parse_nar_rakuten_card import parse

def fixture():
    return {"horses": [
        {"horse_name": f"synthetic_{i}", "recent_starts": [
            {"race_date": "2026-11-01", "finish_position": 2},
            {"race_date": "2026-10-01", "finish_position": 3},
            {"race_date": "2026-09-01", "finish_position": 1},
            {"race_date": "2026-08-01", "finish_position": 4},
        ]} for i in range(11)]}

class AuditRegression(unittest.TestCase):
    def test_parser_never_turns_scratch_with_digits_into_finish(self):
        html = """<table><tr><td><span class="mainHorse"><a href="/horse/123">synthetic</a></span></td>
        <td class="race"><div class="firstInfo"><span class="place">除外 1</span></div>
        26.10.01 1200 ダ</td>
        <td class="race"><div class="firstInfo"><span class="place">2着</span></div>
        26.09.01 1200 ダ</td></tr></table>"""
        result = parse(html, '2026-11-21')
        self.assertEqual(len(result["horses"][0]["recent_starts"]), 1)
        self.assertEqual(result["horses"][0]["recent_starts"][0]["finish_position"], 2)

    def test_generic_cutoff_allows_other_dates(self):
        html = """<tr><td><span class="mainHorse"><a href="/horse/123">synthetic</a></span></td>
        <td class="race"><div class="firstInfo"><span class="place">2着</span></div>
        26.11.22 1200 ダ</td></tr>"""
        result = parse(html, "2026-11-24")
        self.assertEqual(result["horses"][0]["recent_starts"][0]["race_date"], "2026-11-22")
        with self.assertRaisesRegex(ValueError, "target result leakage"):
            parse(html, "2026-11-22")

    def test_invalid_calendar_dates_fail_closed(self):
        html = """<tr><td><span class="mainHorse"><a href="/horse/123">synthetic</a></span></td>
        <td class="race"><div class="firstInfo"><span class="place">2着</span></div>
        26.02.30 1200 ダ</td></tr>"""
        with self.assertRaisesRegex(ValueError, "invalid historical race date"):
            parse(html, "2026-11-21")
        with self.assertRaisesRegex(ValueError, "valid target_date"):
            parse(html, "2026-02-30")

    def test_clean_research_only(self):
        result = audit(fixture())
        self.assertEqual(result["status"], "BLOCKED_INCOMPLETE_HISTORY")
        self.assertEqual(result["five_run_coverage"], 0)
        self.assertFalse(result["formal_tickets_generated"])
        self.assertEqual(result["pre_start_seal"], "NOT_VERIFIED")

    def test_five_runs_required_for_completeness(self):
        data = fixture()
        for horse in data["horses"]:
            horse["recent_starts"].append({"race_date": "2026-07-01", "finish_position": 2})
        result = audit(data)
        self.assertEqual(result["status"], "HISTORY_COMPLETE_RESEARCH_ONLY")
        self.assertEqual(result["five_run_coverage"], 11)

    def test_market_aliases_rejected(self):
        for key in ("odds_value", "popularityRank", "market-rank", "raceResult"):
            with self.subTest(key=key):
                data = fixture()
                data["horses"][0]["recent_starts"][0][key] = 5
                with self.assertRaisesRegex(ValueError, "leakage"):
                    audit(data)

    def test_unknown_fields_fail_closed(self):
        for level in ("root", "horse", "start"):
            with self.subTest(level=level):
                data = fixture()
                target = data if level == "root" else data["horses"][0] if level == "horse" else data["horses"][0]["recent_starts"][0]
                target["unrecognized_signal"] = 0.8
                with self.assertRaisesRegex(ValueError, "unapproved field"):
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

    def test_incomplete_history_still_rejects_target_date(self):
        data = fixture()
        data["horses"][0]["recent_starts"] = [{"race_date": "2026-11-22", "finish_position": 1}]
        with self.assertRaisesRegex(ValueError, "target-date leakage"):
            audit(data)

    def test_incomplete_history_still_rejects_invalid_finish(self):
        data = fixture()
        data["horses"][0]["recent_starts"] = [{"race_date": "2026-11-01", "finish_position": 0}]
        with self.assertRaisesRegex(ValueError, "invalid past finish"):
            audit(data)

    def test_missing_history_research_block(self):
        data = fixture()
        data["horses"][0]["recent_starts"] = []
        self.assertEqual(audit(data)["status"], "BLOCKED_INCOMPLETE_HISTORY")

    def test_runner_count_mismatch_rejected(self):
        data = fixture()
        data["horse_count"] = 10
        with self.assertRaisesRegex(ValueError, "horse_count"):
            audit(data)

    def test_boolean_finish_rejected(self):
        data = fixture()
        data["horses"][0]["recent_starts"][0]["finish_position"] = True
        with self.assertRaisesRegex(ValueError, "invalid past finish"):
            audit(data)

    def test_entry_count_rejected(self):
        data = fixture()
        data["horses"].pop()
        with self.assertRaisesRegex(ValueError, "expected 11"):
            audit(data)

if __name__ == "__main__":
    unittest.main()
