#!/usr/bin/env python3
"""Gate market collection cadence from sealed prediction completion to post time.

Policy:
- only after today's pure prediction seal exists;
- before T-30: at most once per 60 minutes;
- from T-30 until post: at most once per 5 minutes;
- no market refresh when there are no future races today.
"""
import json, os, re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo("Asia/Tokyo")
SEAL=Path("docs/data/live_predictions_sealed.json")
WEEKLY=Path("docs/data/horses/weekly_runner_details.json")
MARKET=Path("docs/data/current_market_odds.json")

def load(p,d):
    try:return json.loads(p.read_text(encoding="utf-8"))
    except Exception:return d

def clock(v):
    m=re.search(r"(\d{1,2})\s*[時:]\s*(\d{1,2})",str(v or ""))
    return (int(m.group(1)),int(m.group(2))) if m else None

now=datetime.now(TZ); today=now.date().isoformat()
seal=load(SEAL,{}); weekly=load(WEEKLY,{"runners":[]}); market=load(MARKET,{})
sealed_today=any(str(r.get("date") or "")==today for r in seal.get("races") or [])
starts={}
for x in weekly.get("runners") or []:
    r=x.get("race") or {}
    if str(r.get("date") or "")!=today: continue
    c=clock(r.get("start_time"))
    if not c: continue
    k=(r.get("track"),r.get("race_no"))
    starts[k]=now.replace(hour=c[0],minute=c[1],second=0,microsecond=0)
future=sorted(t for t in starts.values() if t>now)
due=False; cadence=None; slot="idle"; reason="no_future_race"
if sealed_today and future:
    mins=min((t-now).total_seconds()/60 for t in future)
    cadence=5 if mins<=30 else 60
    slot="T30_5MIN" if cadence==5 else "HOURLY"
    captured=market.get("captured_at")
    last=None
    if captured:
        try:last=datetime.fromisoformat(str(captured))
        except Exception:last=None
    due=last is None or (now-last).total_seconds() >= cadence*60-30
    reason=f"next_post_in={mins:.1f}m cadence={cadence}m"
elif not sealed_today:
    reason="today_prediction_not_sealed"
out=os.environ.get("GITHUB_OUTPUT")
if out:
    with open(out,"a",encoding="utf-8") as f:
        f.write(f"run_collection={'true' if due else 'false'}\nslot={slot}\n")
print(json.dumps({"run_collection":due,"slot":slot,"reason":reason,"sealed_today":sealed_today},ensure_ascii=False))
