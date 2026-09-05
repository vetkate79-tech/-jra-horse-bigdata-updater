#!/usr/bin/env python3
import datetime as dt,hashlib,json
from pathlib import Path

P=Path('docs/data/horses/weekly_runner_details.json')
HISTORY=Path('docs/data/horses/weekly_runner_history')
JST=dt.timezone(dt.timedelta(hours=9))

def archive_snapshot(doc):
    rows=doc.get('runners') or []
    if not rows:
        return []
    raw=json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    digest=hashlib.sha256(raw).hexdigest()
    dates=sorted({str((r.get('race') or {}).get('date') or '') for r in rows if (r.get('race') or {}).get('date')})
    archived=[]
    for date in dates or ['undated']:
        d=HISTORY/date
        d.mkdir(parents=True,exist_ok=True)
        out=d/f'{digest}.json'
        if not out.exists():
            out.write_bytes(raw)
        # Verify persistence before any working-set pruning.
        if hashlib.sha256(out.read_bytes()).hexdigest()!=digest:
            raise RuntimeError(f'weekly runner archive verification failed: {out}')
        archived.append(str(out))
    return archived

def main():
    if not P.exists():
        print(json.dumps({'status':'NO_FILE'}));return
    doc=json.loads(P.read_text(encoding='utf-8'))
    rows=doc.get('runners',[])
    archived=archive_snapshot(doc)
    today=dt.datetime.now(JST).date().isoformat()
    kept=[r for r in rows if str((r.get('race') or {}).get('date') or '')>=today]
    expired=[r for r in rows if r not in kept]
    dates=sorted({(r.get('race') or {}).get('date') for r in kept if (r.get('race') or {}).get('date')})
    s=dict(doc.get('summary') or {})
    s.update({
        'runner_count':len(kept),
        'dates':dates,
        'expired_before':today,
        'archived_snapshot_count':len(archived),
        'history_root':str(HISTORY),
        'policy':'past race-week detail may leave the active working set only after an immutable verified snapshot is stored'
    })
    P.write_text(json.dumps({'summary':s,'runners':kept},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    # No source row is allowed to disappear from the system without an archive.
    if expired and not archived:
        raise RuntimeError('refusing to prune race-week rows without verified archive')
    print(json.dumps({'before':len(rows),'after':len(kept),'expired_from_working_set':len(expired),'archived_snapshots':archived},ensure_ascii=False))

if __name__=='__main__':main()
