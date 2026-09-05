import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from axis_survival_shadow import reorder_with_survival_axis, select_survival_axis


def horse(n, score, show, recent, condition, uncertainty, starts):
    return {
        "n": str(n),
        "name": f"horse-{n}",
        "score": score,
        "show_rate_prior": show,
        "recent_form": recent,
        "condition_fit": condition,
        "uncertainty": uncertainty,
        "starts_before": starts,
    }


class AxisSurvivalChallengerTest(unittest.TestCase):
    def test_switches_only_when_exact_r2_gate_is_satisfied(self):
        ranked = [
            horse(1, 35, .30, .35, .30, .75, 4),
            horse(9, 34, .36, .42, .32, .55, 5),
            horse(3, 30, .28, .34, .30, .60, 4),
        ]
        selection = select_survival_axis(ranked)
        self.assertTrue(selection["switch_gate"]["allowed"])
        self.assertEqual(selection["axis"]["horse_no"], "9")
        self.assertEqual(reorder_with_survival_axis(ranked, selection)[0]["n"], "9")

    def test_keeps_champion_when_original_uncertainty_is_below_gate(self):
        ranked = [
            horse(1, 35, .30, .35, .30, .69, 4),
            horse(9, 34, .40, .48, .35, .40, 6),
            horse(3, 30, .28, .34, .30, .60, 4),
        ]
        selection = select_survival_axis(ranked)
        self.assertFalse(selection["switch_gate"]["allowed"])
        self.assertEqual(selection["axis"]["horse_no"], "1")


if __name__ == "__main__":
    unittest.main()
