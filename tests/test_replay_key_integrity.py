"""Fail-closed regression tests for immutable prediction/result replay joins."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "src" / "publish_archive_results.py"
spec = importlib.util.spec_from_file_location("publish_archive_results", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def prediction(track, no):
    return {"date": mod.target, "track": track, "race_no": no, "analysis": {}}


def result(track, no):
    return {"date": mod.target, "track": track, "race_no": no, "top3_rows": [
        {"horse_no": 1, "finish": 1}, {"horse_no": 2, "finish": 2}, {"horse_no": 3, "finish": 3}
    ]}


class ReplayKeyIntegrityTest(unittest.TestCase):
    def check(self, predictions, results, valid):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(mod, "REPLAY_OUT", Path(directory) / "replay.json"):
                archive = {"races": predictions}
                official = {"races": results}
                if valid:
                    output = mod.build_replay(archive, official)
                    self.assertEqual(output["summary"]["sealed"], len(predictions))
                else:
                    with self.assertRaisesRegex(RuntimeError, "immutable replay key mismatch"):
                        mod.build_replay(archive, official)
                    self.assertFalse(mod.REPLAY_OUT.exists())

    def test_matching_keys(self):
        self.check([prediction("東京", 4)], [result("東京", 4)], True)

    def test_missing_prediction(self):
        self.check([], [result("東京", 4)], False)

    def test_missing_result(self):
        self.check([prediction("東京", 4)], [], False)

    def test_duplicate_prediction(self):
        self.check([prediction("東京", 4)] * 2, [result("東京", 4)], False)

    def test_duplicate_result(self):
        self.check([prediction("東京", 4)], [result("東京", 4)] * 2, False)


if __name__ == "__main__":
    unittest.main()
