#!/usr/bin/env python3
import csv,json,re
from pathlib import Path
from collections import defaultdict

ROOT=Path('.')
CAT=ROOT/'docs/data/horses/catalog.json'
RESULTS=[ROOT/'data/race_results_html_2025.csv',ROOT/'data/race_results_html_2026_weekend.csv',ROOT/'data/race_results_html_2026.csv']

PRIORITY=['GRADED','OPEN','2WIN','1WIN','MAIDEN','NEW']
LABELS={'GRADED':'重賞馬','OPEN':'オープンクラス','2WIN':'2勝クラス','1WIN':'1勝クラス','MAIDEN':'未勝利馬','NEW':'新馬'}

def clean(v):
    if v is None:return ''
    s=str(v).strip()
    return '' if s.lower()=='nan' else s

def load_rows():
    rows=[]
    for p in RESULTS:
        if not p.exists():continue
        with p.open(encoding='utf-8-sig',newline='') as f: rows.extend(csv.DictReader(f))
    return rows

def category_from_race_name(name):
    n=clean(name)
    if re.search(r'(G1|G2|G3|GⅠ|GⅡ|GⅢ|ＧⅠ|ＧⅡ|ＧⅢ)',n,re.I): return 'GRADED'
    if 'オープン' in n or 'リステッド' in n or re.search(r'\bL\b',n): return 'OPEN'
    if '2勝クラス' in n: return '2WIN'
    if '1勝クラス' in n: return '1WIN'
    if '未勝利' in n: return 'MAIDEN'
    if 'メイクデビュー' in n or '新馬' in n: return 'NEW'
    return ''

def main():
    if not CAT.exists(): raise SystemExit('catalog missing')
    doc=json.loads(CAT.read_text(encoding='utf-8'))
    horses=doc.get('horses',[])
    by_id={h.get('horse_id'):h for h in horses if h.get('horse_id')}
    by_name={h.get('horse_name'):h for h in horses if h.get('horse_name')}
    latest=defaultdict(list)
    for r in load_rows():
        hid=clean(r.get('horse_id')); name=clean(r.get('horse_name')); cat=category_from_race_name(r.get('race_name'))
        if not cat: continue
        key=hid or name
        if key: latest[key].append((clean(r.get('race_date')),cat,clean(r.get('race_name'))))
    changed=0
    for key,rows in latest.items():
        rows.sort(key=lambda x:x[0])
        _,cat,race_name=rows[-1]
        h=by_id.get(key) or by_name.get(key)
        if not h: continue
        tags=set(h.get('tags') or [])
        if cat=='GRADED': tags.add('GRADED')
        if cat=='OPEN': tags.add('OPEN')
        # Do not downgrade authoritative OPEN/GRADED overlays.
        if h.get('current_class') not in ('OPEN','GRADED') and cat in ('2WIN','1WIN','MAIDEN','NEW'):
            h['current_class']=cat; h['current_class_label']=LABELS[cat]
        h['tags']=sorted(tags)
        h['category_evidence_race']=race_name
        changed+=1
    summary=dict(doc.get('summary') or {})
    summary['category_counts']={k:sum(1 for h in horses if h.get('current_class')==k or k in (h.get('tags') or [])) for k in PRIORITY}
    summary['category_priority']=PRIORITY
    summary['category_policy']='authoritative OPEN/GRADED overlays first; lower classes use latest verified JRA race evidence until stronger registration data is connected'
    summary['category_records_touched']=changed
    doc['summary']=summary
    CAT.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps(summary['category_counts'],ensure_ascii=False,indent=2))
if __name__=='__main__': main()
