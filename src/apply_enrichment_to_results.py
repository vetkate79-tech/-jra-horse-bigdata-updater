#!/usr/bin/env python3
"""Apply verified race-level enrichment to every runner while preserving provenance."""
import argparse,csv,json
from pathlib import Path
FIELDS=('race_name','weather','track_condition','race_class','race_category','race_rule','weight_rule','scheduled_start')
def read(path):
 with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--results',type=Path,required=True);ap.add_argument('--context',type=Path,required=True)
 ap.add_argument('--out',type=Path,required=True);ap.add_argument('--audit',type=Path,required=True);a=ap.parse_args()
 rows=read(a.results);contexts={x['race_id']:x for x in read(a.context) if x.get('data_status')=='PASS_HTML'}
 changed=0;missing=set();conflicts=[]
 for r in rows:
  c=contexts.get(r['race_id'])
  if not c:missing.add(r['race_id']);continue
  original={};updates={}
  for field in FIELDS:
   value=c.get(field,'')
   if value and r.get(field,'')!=value:original[field]=r.get(field,'');r[field]=value;updates[field]=value
  if updates:
   changed+=1;r['enrichment_original_json']=json.dumps(original,ensure_ascii=False,sort_keys=True)
   r['enrichment_fields_json']=json.dumps(sorted(updates),ensure_ascii=False);r['enrichment_status']='PASS_HTML_CONTEXT'
 fields=sorted(set().union(*(x.keys() for x in rows)));tmp=a.out.with_suffix('.tmp');a.out.parent.mkdir(parents=True,exist_ok=True)
 with tmp.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 tmp.replace(a.out);report={'source_rows':len(rows),'contexts':len(contexts),'changed_rows':changed,'missing_race_ids':sorted(missing),
  'status':'PASS' if not missing else 'INCOMPLETE'}
 a.audit.parent.mkdir(parents=True,exist_ok=True);a.audit.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report))
 if missing:raise SystemExit('missing verified context')
if __name__=='__main__':main()
