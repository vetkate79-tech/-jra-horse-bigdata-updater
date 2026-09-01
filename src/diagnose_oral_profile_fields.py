#!/usr/bin/env python3
from __future__ import annotations
import json,re,sys
from pathlib import Path
sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile, normalized_tables

BASE=Path('docs/data/replay-2026-08-29-30-sealed.json')
GOLD=Path('docs/data/oral-chat-golden-cases.json')
OUT=Path('status/oral-profile-field-diagnostic.json')

def key(r):return (str(r.get('date') or ''),str(r.get('track') or ''),int(r.get('race_no') or 0))
def no(v):
 m=re.match(r'\s*(\d+)',str(v or ''));return m.group(1) if m else ''

def ndate(v):
 s=str(v or '').replace('年','-').replace('月','-').replace('日','').replace('/','-').replace('.','-')
 m=re.search(r'(20\d{2})-(\d{1,2})-(\d{1,2})',s)
 return f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}' if m else ''

def main():
 base=json.loads(BASE.read_text());gold=json.loads(GOLD.read_text());bm={key(r):r for r in base.get('races',[])}
 rows=[]
 for g in gold['cases']:
  b=bm.get(key(g),{});n=no(g['axis']);snap=next((x for x in b.get('ranked_snapshot',[]) if str(x.get('n')).lstrip('0')==n.lstrip('0')),None)
  diag={'race':{'date':g['date'],'track':g['track'],'race_no':g['race_no']},'axis':g['axis'],'base_found':bool(b),'snapshot_found':bool(snap)}
  if not snap:
   diag['base_ranked_nos']=[str(x.get('n')) for x in b.get('ranked_snapshot',[])];rows.append(diag);continue
  hid=snap.get('horse_id');diag['horse_id']=hid
  try:
   html=request_profile(hid);tables=normalized_tables(html);diag['table_count']=len(tables);diag['tables']=[]
   for ti,t in enumerate(tables[:12]):
    cols=[str(c) for c in t.columns];sample=[]
    for _,rr in t.head(3).iterrows():sample.append({str(c):str(v).strip() for c,v in rr.items()})
    diag['tables'].append({'table_index':ti,'columns':cols,'sample':sample})
   found=[]
   for ti,t in enumerate(tables):
    cols=[str(c) for c in t.columns]
    if not any(('レース名' in c or '競走名' in c) for c in cols):continue
    for _,rr in t.head(20).iterrows():
     d={str(c):str(v).strip() for c,v in rr.items()};date=''
     for c,v in d.items():
      if '年月日' in c or '日付' in c:date=ndate(v);break
     if date and date>=g['date']:continue
     found.append({'date':date,'values':d})
     if len(found)>=5:break
    if found:
     diag['matched_history_table']=ti;diag['pre_target_rows']=found;break
  except Exception as e:diag['error']=repr(e)
  rows.append(diag)
 OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps({'cases':rows},ensure_ascii=False,indent=2));print(json.dumps({'case_count':len(rows),'summaries':[{'axis':x['axis'],'table_count':x.get('table_count'),'error':x.get('error'),'matched':x.get('matched_history_table')} for x in rows]},ensure_ascii=False))
if __name__=='__main__':main()
