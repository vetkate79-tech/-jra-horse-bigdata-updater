"""Calendar fixtures are test data, not production scheduling rules."""
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import re

ROOT = Path(__file__).resolve().parents[1] / ".github/workflows"
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")
def matches(field, value, low, high, sunday=False):
    for item in field.split(","):
        base, sep, step = item.partition("/")
        stride = int(step) if sep else 1
        if stride < 1:
            raise ValueError("Invalid cron step")
        if base == "*":
            a, b = low, high
        elif "-" in base:
            a, b = map(int, base.split("-"))
        else:
            a = int(base)
            b = high if sep else a
        if not low <= a <= b <= high:
            raise ValueError("Invalid cron range")
        values = set(range(a, b + 1, stride))
        if sunday and 7 in values:
            values.add(0)
        if value in values:
            return True
    return False

def scheduled(name, day, start, end):
    source = (ROOT / (name + ".yml")).read_text()
    for minute, hour, dom, month, dow in [x.split() for x in re.findall(r"cron: '([^']+)'", source)]:
        if dom != "*" or month != "*":
            raise AssertionError("Unsupported calendar constraint")
        for h in range(start, end):
            for m in range(60):
                t = datetime.fromisoformat(day).replace(hour=h, minute=m, tzinfo=JST).astimezone(UTC)
                if matches(minute,t.minute,0,59) and matches(hour,t.hour,0,23) and matches(dow,(t.weekday()+1)%7,0,7,True):
                    return True
    return False

class CalendarReachability(unittest.TestCase):
    def test_cron_fields(self):
        self.assertTrue(matches("4-6", 5, 0, 7, True))
        self.assertFalse(matches("4-6", 1, 0, 7, True))
        self.assertTrue(matches("*/15", 30, 0, 59))
        self.assertFalse(matches("*/15", 31, 0, 59))
        self.assertTrue(matches("7", 0, 0, 7, True))
        self.assertTrue(matches("1,3-5", 4, 0, 7, True))

    def test_meeting_days(self):
        for day in ("2026-12-26","2026-12-27","2027-01-04","2027-01-05"):
            for workflow, start, end in (("register-upcoming-new-horses",0,10),("race-week-prediction-seal",0,10),("post-jra-meeting-update",16,24)):
                with self.subTest(day=day, workflow=workflow):
                    self.assertTrue(scheduled(workflow,day,start,end))
    def test_nonmeeting_fixture(self):
        # A schedule may poll on non-meeting days; runtime must separately prove no meeting.
        self.assertEqual(datetime.fromisoformat("2026-12-28").weekday(),0)

if __name__ == "__main__":
    unittest.main()
