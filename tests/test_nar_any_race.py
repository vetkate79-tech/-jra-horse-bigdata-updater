"""Fail-closed identity and model-routing checks for generic NAR entry point."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import run_nar_any_race as generic


class GenericNARRoutingTests(unittest.TestCase):
    def setUp(self):
        self.source = {"race": {"track": "大井", "race_no": 11, "date": "2026-11-24"}}

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
