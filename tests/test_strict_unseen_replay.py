import unittest
from src.strict_unseen_replay import score, summarize


class ReplayTests(unittest.TestCase):
    def row(self, hit=True):
        return {
            "date": "2026-11-15", "track": "京都", "race_no": 11,
            "scheduled_start_time": "2026-11-15T15:40:00+09:00",
            "model_version": "fixed-v1", "decision": "BUY",
            "trio_tickets": ["1-2-3", "1-2-4"], "official_top3": [3, 1, 2] if hit else [3, 5, 6],
            "official_trio_payout_per_100": 15870, "stake_yen": 200,
            "return_yen": 15870 if hit else 0, "axis_horse_no": 1
        }

    def test_trio_is_order_invariant(self):
        self.assertTrue(score(self.row())["hit"])

    def test_no_hit(self):
        self.assertFalse(score(self.row(False))["hit"])

    def test_reject_return_injection(self):
        row = self.row(False)
        row["return_yen"] = 15870
        with self.assertRaises(ValueError):
            score(row)

    def test_reject_ticket_budget_mismatch(self):
        row = self.row()
        row["stake_yen"] = 100
        with self.assertRaises(ValueError):
            score(row)

    def test_largest_payout_exclusion(self):
        result = summarize([score(self.row()), score(self.row(False))])
        self.assertEqual(result["stake_yen"], 400)
        self.assertEqual(result["return_yen"], 15870)
        self.assertEqual(result["roi_ex_largest_pct"], 0.0)
        self.assertEqual(result["high_payout_hits_10000_yen"], 1)


if __name__ == "__main__":
    unittest.main()
