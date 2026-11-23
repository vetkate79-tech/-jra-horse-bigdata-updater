import unittest
from src.strict_unseen_batch_gate import classify


class StrictBatchGateTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "date": "2026-11-15", "track": "京都", "race_no": 11,
            "race_id": "202611150811", "seal_commit_sha": "abc",
            "prediction_sha256": "def", "model_version": "fixed-v1",
            "official_result_source": "jra-result", "official_payout_source": "jra-payout",
            "seal_commit_time": "2026-11-15T05:00:00+09:00",
            "prediction_generated_time": "2026-11-15T04:59:00+09:00",
            "scheduled_start_time": "2026-11-15T15:40:00+09:00",
            "feature_source_times": ["2026-11-14T23:00:00+09:00"],
            "entry_count": 16, "sealed_entry_count": 16,
            "independent_seal_evidence": True, "upstream_lineage_verified": True, "official_result_verified": True,
            "official_payout_verified": True, "trio_tickets": ["1-2-3"],
            "decision": "BUY", "stake_yen": 100, "return_yen": 0
        }

    def test_complete_candidate(self):
        self.assertEqual(classify(self.row)[1], [])

    def test_post_start_seal(self):
        self.row["seal_commit_time"] = "2026-11-15T15:41:00+09:00"
        self.assertIn("POST_START_SEAL", classify(self.row)[1])

    def test_feature_leak(self):
        self.row["feature_source_times"] = ["2026-11-15T15:41:00+09:00"]
        self.assertIn("FEATURE_TIME_LEAK", classify(self.row)[1])

    def test_missing_field(self):
        self.row["sealed_entry_count"] = 15
        self.assertIn("INCOMPLETE_FIELD", classify(self.row)[1])

    def test_unverified_lineage(self):
        self.row["upstream_lineage_verified"] = False
        self.assertIn("UNVERIFIED_UPSTREAM_LINEAGE", classify(self.row)[1])

    def test_missing_timezone(self):
        self.row["seal_commit_time"] = "2026-11-15T05:00:00"
        self.assertIn("UNVERIFIED_TIME_LINEAGE", classify(self.row)[1])


if __name__ == "__main__":
    unittest.main()
