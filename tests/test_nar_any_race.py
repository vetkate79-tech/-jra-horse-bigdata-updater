"""Fail-closed identity and model-routing checks for generic NAR entry point."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import run_nar_any_race as generic


class GenericNARRoutingTests(unittest.TestCase):
    def setUp(self):
        self.source = {"race": {"track": "大井", "race_no": 11, "date": "2026-11-24"},
                       "runners": [
                           {"horse_name": f"horse{i}", "horse_id": f"id{i}",
                            "recent_starts": [{"race_date": f"2026-11-{day:02d}",
                                               "race_id": f"race{day}",
                                               "finish_position": 1}
                                              for day in range(1, 6)]}
                           for i in range(3)]}

    def test_track_mismatch_blocks_before_scoring(self):
        with self.assertRaisesRegex(ValueError, "track"):
            generic.execute(self.source, expected_track="園田")

    def test_race_mismatch_blocks_before_scoring(self):
        with self.assertRaisesRegex(ValueError, "race number"):
            generic.execute(self.source, expected_race_no=10)

    def test_date_mismatch_blocks_before_scoring(self):
        with self.assertRaisesRegex(ValueError, "date"):
            generic.execute(self.source, expected_date="2026-11-23")

    def test_banei_routes_to_separate_model(self):
        self.source["race"]["track"] = "帯広"
        with self.assertRaisesRegex(ValueError, "BANEI_REQUIRES_SEPARATE_MODEL"):
            generic.execute(self.source)

    def test_missing_fifth_history_blocks_scoring(self):
        self.source["runners"][0]["recent_starts"].pop()
        with patch.object(generic, "build") as build:
            with self.assertRaisesRegex(ValueError, "at least 5 valid"):
                generic.execute(self.source)
            build.assert_not_called()

    def test_duplicate_history_blocks_scoring(self):
        starts = self.source["runners"][0]["recent_starts"]
        starts[4] = starts[0].copy()
        with self.assertRaisesRegex(ValueError, "duplicate prior start"):
            generic.execute(self.source)

    def test_missing_horse_id_blocks_scoring(self):
        self.source["runners"][0]["horse_id"] = ""
        with self.assertRaisesRegex(ValueError, "horse_id"):
            generic.execute(self.source)

    def test_excluded_history_blocks_scoring(self):
        self.source["runners"][0]["recent_starts"][0]["finish_position"] = None
        with self.assertRaisesRegex(ValueError, "excluded or unfinished"):
            generic.execute(self.source)

    def test_target_day_history_blocks_before_scoring(self):
        self.source["runners"][0]["recent_starts"][0]["race_date"] = "2026-11-24"
        with patch.object(generic, "build") as build:
            with self.assertRaisesRegex(ValueError, "future or target-date"):
                generic.execute(self.source)
            build.assert_not_called()

    def test_future_history_blocks_before_scoring(self):
        self.source["runners"][0]["recent_starts"][0]["race_date"] = "2026-11-25"
        with self.assertRaisesRegex(ValueError, "future or target-date"):
            generic.execute(self.source)

    def test_invalid_history_date_blocks(self):
        self.source["runners"][0]["recent_starts"][0]["race_date"] = "2026-02-30"
        with self.assertRaisesRegex(ValueError, "invalid prior start date"):
            generic.execute(self.source)

    def test_zero_finish_blocks(self):
        self.source["runners"][0]["recent_starts"][0]["finish_position"] = 0
        with self.assertRaisesRegex(ValueError, "excluded or unfinished"):
            generic.execute(self.source)

    def test_noncanonical_target_date_blocks(self):
        self.source["race"]["date"] = "2026-11-1"
        with self.assertRaisesRegex(ValueError, "noncanonical target race date"):
            generic.execute(self.source)

    def test_verified_flat_race_calls_existing_pipeline(self):
        with patch.object(generic, "build", return_value={"source_type": "NAR"}) as build, \
             patch.object(generic, "run", return_value={"status": "RESEARCH_NAR_UNCALIBRATED"}) as run:
            result = generic.execute(self.source, "大井", 11, "2026-11-24")
            self.assertEqual(result["prediction"]["status"], "RESEARCH_NAR_UNCALIBRATED")
            build.assert_called_once_with(self.source)
            run.assert_called_once()

    def test_unexpected_formal_status_is_rejected(self):
        with patch.object(generic, "build", return_value={}), \
             patch.object(generic, "run", return_value={"status": "COMPUTED_NAR_ISOLATED"}):
            with self.assertRaisesRegex(ValueError, "unexpected research status"):
                generic.execute(self.source)


if __name__ == "__main__":
    unittest.main()
