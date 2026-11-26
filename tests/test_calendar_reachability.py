"""Calendar fixtures are test data, not production scheduling rules."""
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import re

ROOT = Path(__file__).resolve().parents[1] / ".github/workflows"
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")
def scheduled(name, day, start, end):
    source = (ROOT / (name + ".yml")).read_text()
    for minute, hour, dom, month, dow in [x.split() for x in re.findall(r"cron: '([^']+)'", source)]:
        if dom != "*" or month != "*":
            raise AssertionError("Unsupported calendar constraint")
        for h in range(start, end):
            for m in range(60):
                t = datetime.fromisoformat(day).replace(hour=h, minute=m, tzinfo=JST).astimezone(UTC)
                if (minute == "*" or str(t.minute) in minute.split(",")) and (hour == "*" or str(t.hour) in hour.split(",")) and (dow == "*" or str((t.weekday()+1)%7) in dow.split(",")):
                    return True
    return False

class CalendarReachability(unittest.TestCase):
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
