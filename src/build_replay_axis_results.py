#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re
from pathlib import Path

REPLAY=Path('docs/data/replay-demo-2026-08-29-30.json')
RESULTS=Path('data/race_results_html_2026.csv')
OUT=Path('docs/data/replay-axis-results.json')
STATUS=Path('status/replay-axis-results.json')

def axis_no(v):
    m=re.match(r'\s*(\d+)',str(v or ''))
    return m.group(1) if m else ''

def ri(v):
    try:return int(float(str(v).strip()))
    except:return None

def norm_track(v):
    return str(v or '').strip().replace('競馬場','')

def main():
    replay=json.loads(REPLAY.read_text())
    with RESULTS.open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    idx={}
    for r in rows:
        k=(str(r.get('race_date') or ''),norm_track(r.get('course')),ri(r.get('race_no')),str(r.get('horse_no') or '').lstrip('0') or '0')
        idx[k]=r
    out=[];matched=0
    for r in replay.get('races',[]):
        n=axis_no(r.get('axis'))
        if not n:continue
        k=(str(r.get('date') or ''),norm_track(r.get('track')),ri(r.get('race_no')),str(int(n)))
        rr=idx.get(k)
        item={'date':k[0],'track':k[1],'race_no':k[2],'axis_horse_no':n,'axis_horse_name':re.sub(r'^\s*\d+\s*','',str(r.get('axis') or '')).strip()}
        if rr:
            finish=ri(rr.get('finish_position'));pop=ri(rr.get('popularity'))
            if finish==1:grade='HIT';label='予想的中';symbol='◎'
            elif finish is not None and finish<=3:grade='PLACE';label='馬券内';symbol='△'
            else:grade='MISS';label='不的中';symbol='×'
            item.update({'matched':True,'finish':finish,'popularity':pop,'horse_name':rr.get('horse_name') or item['axis_horse_name'],'evaluation':grade,'label':label,'symbol':symbol})
            matched+=1
        else:
            item.update({'matched':False,'finish':None,'popularity':None,'evaluation':'UNKNOWN','label':'結果未接続','symbol':'–'})
        out.append(item)
    payload={'mode':'POST_RESULT_AXIS_EVALUATION_ONLY','prediction_input_use':False,'policy':'Popularity and finish are result-display-only and must never be used by the sealed pre-race model.','race_count':len(out),'matched_count':matched,'rows':out}
    txt=json.dumps(payload,ensure_ascii=False,indent=2)
    OUT.write_text(txt);STATUS.parent.mkdir(exist_ok=True);STATUS.write_text(txt)
    print(json.dumps({'race_count':len(out),'matched_count':matched},ensure_ascii=False))
if __name__=='__main__':main()
