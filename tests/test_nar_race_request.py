import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nar_race_request import resolve, TRACKS

class RaceRequestTests(unittest.TestCase):
    def test_all_tracks_multiple_dates(self):
        for day in ("2026-11-21", "2026-11-26"):
            for track, code in TRACKS.items():
                for number in range(1,13):
                    with self.subTest(day=day, track=track, number=number):
                        r = resolve(f"{track}{number}R", day)
                        q = parse_qs(urlparse(r["card_url"]).query)
                        self.assertEqual(q["k_babaCode"], [str(code)])
                        self.assertEqual(q["k_raceNo"], [str(number)])
                        self.assertEqual(q["k_raceDate"], [day.replace("-", "/")])
                        self.assertEqual(r["status"], "UNVERIFIED_REQUEST")
                        self.assertEqual(r["model"], "banei" if track=="帯広" else "nar_flat")
    def test_invalid(self):
        for request in ("東京11R", "大井0R", "大井13R", "大井", "大井11R余分"):
            with self.assertRaises(ValueError):
                resolve(request, "2026-11-26")
        with self.assertRaises(ValueError):
            resolve("大井11R", "2026-02-30")

if __name__ == "__main__":
    unittest.main()
