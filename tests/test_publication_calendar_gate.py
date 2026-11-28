import unittest
from src.publication_calendar_gate import publication_eligible

class PublicationCalendarGateTest(unittest.TestCase):
    def test_calendar_cases(self):
        for day, count in [
            ("2026-11-27", 0), ("2026-11-28", 24),
            ("2026-11-29", 24), ("2026-11-30", 12),
            ("2026-12-26", 24), ("2026-12-27", 24),
            ("2026-12-28", 0), ("2027-01-04", 24),
            ("2027-01-05", 24),
        ]:
            with self.subTest(day=day):
                keys = [f"{day}:{i}" for i in range(count)]
                self.assertEqual(publication_eligible(day, "SEALED", keys, keys, keys), bool(count))
                if count:
                    with self.assertRaisesRegex(RuntimeError, "CURRENT_MEETING_INCOMPLETE"):
                        publication_eligible(day, "SEALED", keys, keys, keys[:-1])

    def test_unknown(self):
        with self.assertRaisesRegex(RuntimeError, "OFFICIAL_MEETING_UNKNOWN"):
            publication_eligible("2026-11-27", "SEALED", None, [], [])

    def test_duplicates(self):
        for index, source in enumerate(("official", "weekly", "sealed")):
            args = [["a"], ["a"], ["a"]]
            args[index].append("a")
            with self.subTest(source=source):
                with self.assertRaisesRegex(RuntimeError, "DUPLICATE_RACE_KEYS:" + source):
                    publication_eligible("2026-11-28", "SEALED", *args)

    def test_nonmeeting_conflict(self):
        with self.assertRaisesRegex(RuntimeError, "NON_MEETING_CARD_CONFLICT"):
            publication_eligible("2026-11-27", "SEALED", [], ["a"], [])

if __name__ == "__main__":
    unittest.main()
