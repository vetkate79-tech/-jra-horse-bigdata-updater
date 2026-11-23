"""Regression: never replace a malformed historical prediction seal with live data."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "src" / "publish_archive_results.py"


class ImmutableMalformedSealTests(unittest.TestCase):
    def test_malformed_existing_archive_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing = root / "prediction-archive.json"
            live = root / "live.json"
            existing.write_text(json.dumps({"date": "2026-11-21", "mode": "BROKEN", "races": []}), encoding="utf-8")
            live.write_text(json.dumps({"races": [{"date": "2026-11-22", "track": "東京", "race_no": 4}]}), encoding="utf-8")
            spec = importlib.util.spec_from_file_location("archive_regression_target", SCRIPT)
            module = importlib.util.module_from_spec(spec)
            with patch.dict(os.environ, {"TARGET_DATE": "2026-11-22"}):
                spec.loader.exec_module(module)
            module.PRED_ARCHIVE = existing
            module.LIVE_PRED = live
            before = existing.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "invalid immutable prediction archive"):
                module.load_prediction_archive()
            self.assertEqual(existing.read_bytes(), before)

    def test_missing_archive_still_allows_first_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live = root / "live.json"
            live.write_text(json.dumps({"races": [{"date": "2026-11-22", "track": "東京", "race_no": 4}], "results_used": False, "odds_popularity_used": False}), encoding="utf-8")
            spec = importlib.util.spec_from_file_location("archive_regression_first", SCRIPT)
            module = importlib.util.module_from_spec(spec)
            with patch.dict(os.environ, {"TARGET_DATE": "2026-11-22"}):
                spec.loader.exec_module(module)
            module.PRED_ARCHIVE = root / "prediction-archive.json"
            module.LIVE_PRED = live
            archive, source = module.load_prediction_archive()
            self.assertEqual(source, "LIVE_SEAL_INITIAL_ARCHIVE")
            self.assertEqual(len(archive["races"]), 1)


if __name__ == "__main__":
    unittest.main()
