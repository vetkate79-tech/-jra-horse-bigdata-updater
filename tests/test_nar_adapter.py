"""No external race data: synthetic fixtures test input integrity only."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from build_nar_pre_race_snapshot import build

def fixture():
    return {"source_name":"ODDSPARK","source_url":"https://www.oddspark.com/keiba/",
            "captured_at":"2026-11-21T12:00:00+09:00",
            "race":{"race_id":"TEST_KOCHI","date":"2026-11-21","track":"高知",
                    "race_no":11,"scheduled_at":"2026-11-21T20:20:00+09:00","surface":"ダート","distance_m":1400},
            "runners":[{"horse_no":str(i),"horse_name":"SYNTHETIC_"+str(i),
                        "jockey":"J","trainer":"T","frame_no":str(i),
                        "recent_starts":[{"race_date":"2026-11-01","race_id":"OLD_"+str(i),
                        "course":"高知","surface":"ダート","distance_m":1400,
                        "finish_position":i,"corner_positions":"1 2 3 4"}]}
                       for i in range(1,4)]}

class AdapterTests(unittest.TestCase):
    def test_model_score_is_computed_from_history(self):
        r=build(fixture())
        self.assertEqual(len(r["horses"]),3)
        self.assertEqual(r["model_calibration"],"UNVALIDATED_NAR_TRANSFER")
        self.assertTrue(all(isinstance(h["score"],float) for h in r["horses"]))
    def test_no_history_rejected(self):
        d=fixture();d["runners"][0]["recent_starts"]=[]
        with self.assertRaisesRegex(ValueError,"missing history"):build(d)
    def test_result_leakage_rejected(self):
        d=fixture();d["runners"][0]["recent_starts"][0]["race_date"]="2026-11-21"
        with self.assertRaisesRegex(ValueError,"post-cutoff"):build(d)
    def test_after_start_capture_rejected(self):
        d=fixture();d["captured_at"]="2026-11-21T20:21:00+09:00"
        with self.assertRaisesRegex(ValueError,"post-race capture"):build(d)
    def test_non_oddspark_source_rejected(self):
        d=fixture();d["source_url"]="https://example.com/"
        with self.assertRaisesRegex(ValueError,"Oddspark domain"):build(d)
    def test_odds_leakage_rejected(self):
        d=fixture();d["runners"][0]["odds"]=1.2
        with self.assertRaisesRegex(ValueError,"market/result leakage"):build(d)
    def test_target_results_rejected(self):
        d=fixture();d["results"]={"winner":"1"}
        with self.assertRaisesRegex(ValueError,"market/result leakage"):build(d)
    def test_duplicate_numbers_rejected(self):
        d=fixture();d["runners"][1]["horse_no"]="1"
        with self.assertRaisesRegex(ValueError,"duplicate"):build(d)
if __name__=="__main__":unittest.main()
