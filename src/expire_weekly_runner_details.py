#!/usr/bin/env python3
import datetime as dt,json
from pathlib import Path

P=Path('docs/data/horses/weekly_runner_details.json')
JST=dt.timezone(dt.timedelta(hours=9))

def main():
    if not P.exists():
        print(json.dumps({'status':'NO_FILE'}));return
    doc=json.loads(P.read_text(encoding='utf-8'))
    today=dt.datetime.now(JST).date().isoformat()
    rows=doc.get('runners',[])
    kept=[r for r in rows if str((r.get('race') or {}).get('date') or '')>=today]
    dates=sorted({(r.get('race') or {}).get('date') for r in kept if (r.get('race') or {}).get('date')})
    s=dict(doc.get('summary') or {})
    s.update({'runner_count':len(kept),'dates':dates,'expired_before':today,'policy':'past race-week detail is removed; summary remains in base horse master'})
    P.write_text(json.dumps({'summary':s,'runners':kept},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'before':len(rows),'after':len(kept),'expired':len(rows)-len(kept)},ensure_ascii=False))

if __name__=='__main__':main()
