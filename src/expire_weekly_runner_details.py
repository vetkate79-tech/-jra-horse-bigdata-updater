#!/usr/bin/env python3
import datetime as dt,json
from collections import defaultdict
from pathlib import Path

P=Path('docs/data/horses/weekly_runner_details.json')
ARCHIVE_DIR=Path('docs/data/horses/weekly_runner_archive')
JST=dt.timezone(dt.timedelta(hours=9))

def _archive_rows(rows):
    by_date=defaultdict(list)
    for r in rows:
        date=str((r.get('race') or {}).get('date') or '')
        if date:
            by_date[date].append(r)
    saved=0
    ARCHIVE_DIR.mkdir(parents=True,exist_ok=True)
    for date,xs in sorted(by_date.items()):
        p=ARCHIVE_DIR/f'{date}.json'
        existing={'date':date,'runners':[]}
        if p.exists():
            try: existing=json.loads(p.read_text(encoding='utf-8'))
            except Exception: pass
        merged={}
        for r in (existing.get('runners') or [])+xs:
            race=r.get('race') or {}
            key=(str(race.get('race_id') or ''),str(r.get('horse_id') or ''),str(r.get('horse_no') or ''))
            if any(key): merged[key]=r
        payload={
            'date':date,
            'mode':'IMMUTABLE_RACE_WEEK_DETAIL_ARCHIVE',
            'runner_count':len(merged),
            'runners':list(merged.values()),
        }
        p.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        saved+=len(xs)
    return saved

def main():
    if not P.exists():
        print(json.dumps({'status':'NO_FILE'}));return
    doc=json.loads(P.read_text(encoding='utf-8'))
    today=dt.datetime.now(JST).date().isoformat()
    rows=doc.get('runners',[])
    expired=[r for r in rows if str((r.get('race') or {}).get('date') or '')<today]
    kept=[r for r in rows if str((r.get('race') or {}).get('date') or '')>=today]

    archived=_archive_rows(expired)
    if archived!=len(expired):
        raise RuntimeError(f'archive count mismatch before active-set pruning: expired={len(expired)} archived={archived}')

    dates=sorted({(r.get('race') or {}).get('date') for r in kept if (r.get('race') or {}).get('date')})
    s=dict(doc.get('summary') or {})
    s.update({
        'runner_count':len(kept),
        'dates':dates,
        'expired_before':today,
        'archived_expired_runner_count':archived,
        'archive_dir':str(ARCHIVE_DIR),
        'policy':'past race-week detail leaves the active working set only after date-partitioned archive persistence; source data is never discarded',
    })
    P.write_text(json.dumps({'summary':s,'runners':kept},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'before':len(rows),'after':len(kept),'expired':len(expired),'archived':archived},ensure_ascii=False))

if __name__=='__main__':main()
