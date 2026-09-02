#!/usr/bin/env python3
import csv,json
from collections import Counter
from pathlib import Path
P=Path('data/race_results_html_2025.csv');OUT=Path('status/rolling-validation-2025-source.json')
def main():
 with P.open(encoding='utf-8-sig',newline='') as f:
  rd=csv.DictReader(f);rows=list(rd);fields=rd.fieldnames or []
 dates=[r.get('race_date','') for r in rows if r.get('race_date')];racekeys={(r.get('race_date'),r.get('course'),r.get('race_no')) for r in rows};payload={'fields':fields,'row_count':len(rows),'race_count':len(racekeys),'date_min':min(dates) if dates else None,'date_max':max(dates) if dates else None,'nonempty_counts':{k:sum(bool(str(r.get(k,'')).strip()) for r in rows) for k in fields},'course_counts':dict(Counter(r.get('course') for r in rows))}
 OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));print(json.dumps(payload,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
