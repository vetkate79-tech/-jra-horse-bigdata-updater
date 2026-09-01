#!/usr/bin/env python3
import csv,json,re
from pathlib import Path
from collections import defaultdict

ROOT=Path('.')
CAT=ROOT/'docs/data/horses/catalog.json'
RESULTS=[ROOT/'data/race_results_html_2025.csv',ROOT/'data/race_results_html_2026_weekend.csv',ROOT/'data/race_results_html_2026.csv']

PRIORITY=['GRADED','OPEN','3WIN','2WIN','1WIN','MAIDEN','NEW']
LABELS={'GRADED':'重賞馬','OPEN':'オープンクラス','3WIN':'3勝クラス','2WIN':'2勝クラス','1WIN':'1勝クラス','MAIDEN':'未勝利馬','NEW':'新馬'}

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

def category_from_text(*parts):
    # JRA result collectors expose class/category separately from race_name.
    # Use every verified official field because race_name can be a named race
    # (or legacy parser noise) while race_class still carries the class truth.
    n=' '.join(clean(x) for x in parts if clean(x))
    if not n:return ''
    if re.search(r'(G1|G2|G3|GⅠ|GⅡ|GⅢ|ＧⅠ|ＧⅡ|ＧⅢ)',n,re.I): return 'GRADED'
    if 'オープン' in n or 'リステッド' in n or 'Listed' in n or re.search(r'(?<![A-Za-z])L(?![A-Za-z])',n): return 'OPEN'
    if re.search(r'(3勝クラス|３勝クラス)',n): return '3WIN'
    if re.search(r'(2勝クラス|２勝クラス)',n): return '2WIN'
    if re.search(r'(1勝クラス|１勝クラス)',n): return '1WIN'
    if '未勝利' in n: return 'MAIDEN'
    if 'メイクデビュー' in n or '新馬' in n: return 'NEW'
    return ''

def category_from_prize(h):
    p=h.get('flat_acquired_prize_yen')
    try:p=int(p)
    except Exception:return ''
    if p>16_000_000:return 'OPEN'
    if p>10_000_000:return '3WIN'
    if p>5_000_000:return '2WIN'
    if p>0:return '1WIN'
    return ''

def main():
    if not CAT.exists(): raise SystemExit('catalog missing')
    doc=json.loads(CAT.read_text(encoding='utf-8'))
    horses=doc.get('horses',[])
    by_id={h.get('horse_id'):h for h in horses if h.get('horse_id')}
    by_name={h.get('horse_name'):h for h in horses if h.get('horse_name')}
    latest=defaultdict(list)
    verified_rows=0
    for r in load_rows():
        status=clean(r.get('data_status'))
        # Never promote quarantined/unverified scraped rows into the master.
        if status and status!='PASS_HTML':
            continue
        cat=category_from_text(r.get('race_class'),r.get('race_category'),r.get('race_rule'),r.get('race_name'))
        if not cat: continue
        verified_rows+=1
        hid=clean(r.get('horse_id')); name=clean(r.get('horse_name')); key=hid or name
        if key:
            latest[key].append((clean(r.get('race_date')),cat,clean(r.get('race_name')),clean(r.get('race_class')),clean(r.get('source_url'))))

    changed=0
    for h in horses:
        prize_cat=category_from_prize(h)
        if prize_cat:
            h['current_class']=prize_cat;h['current_class_label']=LABELS[prize_cat];h['class_source']='JRA_OFFICIAL_ACQUIRED_PRIZE'
            tags=set(h.get('tags') or []);tags.add(prize_cat);h['tags']=sorted(tags);changed+=1

    for key,rows in latest.items():
        rows.sort(key=lambda x:x[0])
        _,cat,race_name,race_class,source_url=rows[-1]
        h=by_id.get(key) or by_name.get(key)
        if not h: continue
        tags=set(h.get('tags') or [])
        if cat=='GRADED': tags.add('GRADED')
        if cat=='OPEN': tags.add('OPEN')
        # Acquired-prize class is authoritative when available. Otherwise the
        # latest verified JRA result class/category is accepted as evidence.
        if h.get('class_source')!='JRA_OFFICIAL_ACQUIRED_PRIZE':
            if cat in ('3WIN','2WIN','1WIN','MAIDEN','NEW'):
                h['current_class']=cat;h['current_class_label']=LABELS[cat];h['class_source']='JRA_OFFICIAL_RESULT_CLASS'
            elif cat=='OPEN':
                h['current_class']='OPEN';h['current_class_label']=LABELS['OPEN'];h['class_source']='JRA_OFFICIAL_RESULT_CLASS'
        h['tags']=sorted(tags)
        h['category_evidence_race']=race_name
        if race_class:h['category_evidence_class']=race_class
        if source_url:h['category_evidence_url']=source_url
        changed+=1

    # Profile-derived graded history is independent verified evidence and counts
    # as a category even when current class cannot safely be inferred.
    for h in horses:
        if h.get('graded_starts'):
            tags=set(h.get('tags') or []);tags.add('GRADED');h['tags']=sorted(tags)
        if h.get('open_or_higher_history') and not h.get('current_class'):
            # Do not infer OPEN current class from historical participation alone;
            # retain only the evidence tag when an official profile/race proves it.
            pass

    summary=dict(doc.get('summary') or {})
    summary['category_counts']={k:sum(1 for h in horses if h.get('current_class')==k or k in (h.get('tags') or [])) for k in PRIORITY}
    summary['category_priority']=PRIORITY
    summary['category_policy']='JRA official acquired prize first; otherwise latest PASS_HTML JRA result class/category; graded history retained as verified tag; quarantined rows excluded'
    summary['category_records_touched']=changed
    summary['verified_category_rows_used']=verified_rows
    doc['summary']=summary
    CAT.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps(summary['category_counts'],ensure_ascii=False,indent=2))
if __name__=='__main__': main()
