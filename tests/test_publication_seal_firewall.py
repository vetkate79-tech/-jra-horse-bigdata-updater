"""Regression: publication must reject leakage flags in either the seal or status."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "src/publish_verified_today_predictions.py"

class PredictionFirewallTests(unittest.TestCase):
    def test_seal_and_status_both_required_clean(self):
        spec = importlib.util.spec_from_file_location("publish_verified_today_predictions", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for field in ("odds_popularity_used", "results_used"):
            for source in ("seal", "status"):
                with self.subTest(field=field, source=source), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    (root / "docs/data/horses").mkdir(parents=True)
                    (root / "status").mkdir()
                    seal = {"prediction_hash_sha256": "testhash", "races": [], "odds_popularity_used": False, "results_used": False}
                    status = {"prediction_hash_sha256": "testhash", "status": "SEALED", "odds_popularity_used": False, "results_used": False}
                    (seal if source == "seal" else status)[field] = True
                    (root / "docs/data/live_predictions_sealed.json").write_text(json.dumps(seal))
                    (root / "docs/data/horses/weekly_runner_details.json").write_text('{"runners":[]}')
                    (root / "status/live_prediction_seal.json").write_text(json.dumps(status))
                    old = Path.cwd()
                    try:
                        os.chdir(root)
                        with self.assertRaisesRegex(RuntimeError, "firewall"):
                            module.main()
                        self.assertFalse((root / "docs/data/live_predictions_today_verified.json").exists())
                    finally:
                        os.chdir(old)

    def test_missing_or_null_firewall_flags_fail_closed(self):
        spec = importlib.util.spec_from_file_location("publish_verified_today_predictions", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for field in ("odds_popularity_used", "results_used"):
            for source in ("seal", "status"):
                for value in ("missing", None):
                    with self.subTest(field=field, source=source, value=value), tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        (root / "docs/data/horses").mkdir(parents=True)
                        (root / "status").mkdir()
                        seal = {"prediction_hash_sha256": "testhash", "races": [],
                                "odds_popularity_used": False, "results_used": False}
                        status = {"prediction_hash_sha256": "testhash", "status": "SEALED",
                                  "odds_popularity_used": False, "results_used": False}
                        target = seal if source == "seal" else status
                        if value == "missing":
                            del target[field]
                        else:
                            target[field] = None
                        (root / "docs/data/live_predictions_sealed.json").write_text(json.dumps(seal))
                        (root / "docs/data/horses/weekly_runner_details.json").write_text('{"runners":[]}')
                        (root / "status/live_prediction_seal.json").write_text(json.dumps(status))
                        old = Path.cwd()
                        try:
                            os.chdir(root)
                            with self.assertRaisesRegex(RuntimeError, "firewall"):
                                module.main()
                            self.assertFalse((root / "docs/data/live_predictions_today_verified.json").exists())
                        finally:
                            os.chdir(old)

    def test_mismatched_or_missing_seal_hash_fails_closed(self):
        spec = importlib.util.spec_from_file_location("publish_verified_today_predictions", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for source_hash, status_hash in (("seal-a", "status-b"), ("seal-a", ""), ("", "status-b")):
            with self.subTest(source_hash=source_hash, status_hash=status_hash), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "docs/data/horses").mkdir(parents=True)
                (root / "status").mkdir()
                seal = {"prediction_hash_sha256": source_hash, "races": [],
                        "odds_popularity_used": False, "results_used": False}
                status = {"prediction_hash_sha256": status_hash, "status": "SEALED",
                          "odds_popularity_used": False, "results_used": False}
                (root / "docs/data/live_predictions_sealed.json").write_text(json.dumps(seal))
                (root / "docs/data/horses/weekly_runner_details.json").write_text('{"runners":[]}')
                (root / "status/live_prediction_seal.json").write_text(json.dumps(status))
                old = Path.cwd()
                try:
                    os.chdir(root)
                    with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
                        module.main()
                    self.assertFalse((root / "docs/data/live_predictions_today_verified.json").exists())
                finally:
                    os.chdir(old)

if __name__ == "__main__":
    unittest.main()
