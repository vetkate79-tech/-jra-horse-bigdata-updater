"""NAR isolated runner regression tests; synthetic data are NOT real predictions."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from run_nar_isolated import run


class NarInputTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {
            "source_type": "NAR", "race_id": "TEST_ONLY", "date": "2026-11-21",
            "track": "高知", "race_no": 11,
            "horses": [
                {"n": str(i), "name": "SYNTHETIC", "score": float(20-i),
                 "score_provenance": "ORAL_VERIFIED_PRE_RACE", "running_style": "FRONT",
                 "show_rate_prior": .3, "recent_form": .4, "condition_fit": .4,
                 "uncertainty": .5, "starts_before": 5}
                for i in range(1, 4)
            ]
        }

    def test_missing_score_is_rejected(self):
        del self.snapshot["horses"][0]["score"]
        with self.assertRaisesRegex(ValueError, "missing score"):
            run(self.snapshot)

    def test_sp_scores_are_rejected(self):
        self.snapshot["horses"][0]["score_provenance"] = "PUBLIC_SP_INDEX"
        with self.assertRaisesRegex(ValueError, "unverified"):
            run(self.snapshot)

    def test_result_leakage_is_rejected(self):
        self.snapshot["results"] = []
        with self.assertRaisesRegex(ValueError, "post-race"):
            run(self.snapshot)

    def test_duplicate_horse_number_is_rejected(self):
        self.snapshot["horses"][1]["n"] = "1"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            run(self.snapshot)

    def test_synthetic_pipeline_completes(self):
        out = run(self.snapshot)
        self.assertEqual(out["status"], "COMPUTED_NAR_ISOLATED")
        self.assertEqual(len(out["ability_ranked"]), 3)
        self.assertEqual(out["simulation"]["runs"], 100_000)
        self.assertEqual(out["axis_shadow"]["status"], "RESEARCH_ONLY")


if __name__ == "__main__":
    unittest.main()
