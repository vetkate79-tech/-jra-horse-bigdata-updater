import copy
import unittest
from prediction_output_gate import PredictionBlocked, validate_official_prediction

BASE = {
    "race_id": "KANAZAWA-20261123-10", "run_id": "123", "model_version": "v1",
    "input_hash": "abc", "model_hash": "def", "status": "success",
    "scratch_status": "verified", "input_time_verified": True,
    "runners": [{"horse_id": str(i), "ability_score": i * 1.1} for i in (1, 2, 3)],
    "scenarios": [{"name": "slow", "results": {"1": .5}},
                  {"name": "fast", "results": {"2": .5}}],
    "tickets": [{"horses": ["1", "2", "3"]}],
}
def check(data, verified={"123"}):
    return validate_official_prediction(data, expected_race_id="KANAZAWA-20261123-10",
        expected_runners={"1", "2", "3"}, verified_run_ids=verified)
class GateTests(unittest.TestCase):
    def test_valid(self): self.assertEqual(check(BASE).run_id, "123")
    def test_no_verified_run(self):
        with self.assertRaises(PredictionBlocked): check(BASE, set())
    def test_missing_score(self):
        x=copy.deepcopy(BASE); del x["runners"][0]["ability_score"]
        with self.assertRaises(PredictionBlocked): check(x)
    def test_missing_runner(self):
        x=copy.deepcopy(BASE); x["runners"].pop()
        with self.assertRaises(PredictionBlocked): check(x)
    def test_missing_scenarios(self):
        x=copy.deepcopy(BASE); x["scenarios"]=[]
        with self.assertRaises(PredictionBlocked): check(x)
    def test_invalid_ticket(self):
        x=copy.deepcopy(BASE); x["tickets"][0]["horses"]=["1","2","4"]
        with self.assertRaises(PredictionBlocked): check(x)
    def test_unverified_scratch(self):
        x=copy.deepcopy(BASE); x["scratch_status"]="unknown"
        with self.assertRaises(PredictionBlocked): check(x)
    def test_result_leak(self):
        x=copy.deepcopy(BASE); x["input_time_verified"]=False
        with self.assertRaises(PredictionBlocked): check(x)
if __name__ == "__main__": unittest.main()
