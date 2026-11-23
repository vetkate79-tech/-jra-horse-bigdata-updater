"""Certified result archives must not be rewritten by subsequent CSV refreshes."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "src" / "publish_archive_results.py"
spec = importlib.util.spec_from_file_location("jra_archive_immutability", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ArchiveImmutabilityTest(unittest.TestCase):
    def test_existing_certified_results_are_returned_without_rewrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.json"
            payload = {"date": "2026-11-22", "summary": {"complete": True, "checked": 1}, "races": [{"track": "東京", "race_no": 4, "top3": "1－2－3"}]}
            original = json.dumps(payload, ensure_ascii=False, indent=2)
            path.write_text(original, encoding="utf-8")
            with patch.object(module, "target", "2026-11-22"), patch.object(module, "RESULT_OUT", path), patch.object(module, "read_csv", side_effect=AssertionError("must not refresh CSV")):
                result, source = module.build_results({"races": []})
            self.assertEqual(result, payload)
            self.assertEqual(source, "EXISTING_COMPLETE_RESULT_IMMUTABLE")
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
