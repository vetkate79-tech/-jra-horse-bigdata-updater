#!/usr/bin/env python3
"""Build the lightweight public horse master from the internal catalog.

The internal catalog remains lossless for validation/backfill. The public base
catalog intentionally contains only stable identity/profile fields plus a light
running-style summary derived from recorded JRA result positions. Race-week
analytics live in weekly_runner_details.json instead.
"""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

SRC=Path('docs/data/horses/catalog.json')
OUT=Path('docs/data/horses/base_catalog.json')
RESULT_SOURCES=(Path('data/race_results_html_2026.csv'),)

BASE_FIELDS=(
    'horse_name','horse_id','sex_age','trainer','sire','damsire',
    'current_class','current_class_label','active','latest_race_date','latest_finish',
    'unbeaten','wins'
)
KEEP_TAGS={'GRADED','OPEN','NEW','NEW_ENTRY'}
STYLE_LABELS={
    'ESCAPE':'逃げ',
    'FRONT':'先行',
    'STALK':'好位差し',
    'CLOSER':'差し',
    'DEEP_CLOSER':'追込',
    'UNKNOWN':'判定待ち',
}

def parse_corners(value):
    if not value:
        return []
    return [int(x) for x in re.findall(r'\d+', str(value))]

def load_running_styles():
    """Return horse_id -> lightweight style summary.

    Uses only recorded corner positions. One/two-race samples are deliberately
    marked provisional; they are still useful as a basic browsing label and are
    recalculated as cumulative official results grow.
    """
    rows=[]
    for path in RESULT_SOURCES:
        if not path.exists() or path.stat().st_size == 0:
            continue
        with path.open(encoding='utf-8-sig', newline='') as f:
            rows.extend(csv.DictReader(f))

    field_sizes=defaultdict(int)
    for r in rows:
        rid=r.get('race_id') or ''
        if rid and r.get('horse_id'):
            field_sizes[rid]+=1

    samples=defaultdict(list)
    for r in rows:
        hid=r.get('horse_id') or ''
        rid=r.get('race_id') or ''
        corners=parse_corners(r.get('corner_positions'))
        n=field_sizes.get(rid,0)
        if not hid or not corners or n < 3:
            continue
        first,last=corners[0],corners[-1]
        # Position ratio is robust across different field sizes.
        first_ratio=max(0.0,min(1.0,(first-1)/max(1,n-1)))
        last_ratio=max(0.0,min(1.0,(last-1)/max(1,n-1)))
        samples[hid].append((first,last,first_ratio,last_ratio))

    out={}
    for hid,ss in samples.items():
        starts=len(ss)
        escape_rate=sum(1 for first,_,_,_ in ss if first==1)/starts
        avg_ratio=sum((a+b)/2 for _,_,a,b in ss)/starts
        if escape_rate >= 0.5 or avg_ratio <= 0.07:
            code='ESCAPE'
        elif avg_ratio <= 0.28:
            code='FRONT'
        elif avg_ratio <= 0.45:
            code='STALK'
        elif avg_ratio <= 0.70:
            code='CLOSER'
        else:
            code='DEEP_CLOSER'
        out[hid]={
            'running_style':code,
            'running_style_label':STYLE_LABELS[code],
            'running_style_sample_starts':starts,
            'running_style_provisional':starts < 3,
        }
    return out

def compact(h, styles):
    x={k:h.get(k) for k in BASE_FIELDS if h.get(k) not in (None,'')}
    tags=[t for t in (h.get('tags') or []) if t in KEEP_TAGS]
    if tags:x['tags']=sorted(set(tags))
    style=styles.get(h.get('horse_id'))
    if style:
        x.update(style)
    else:
        x.update({'running_style':'UNKNOWN','running_style_label':STYLE_LABELS['UNKNOWN'],'running_style_sample_starts':0,'running_style_provisional':True})
    is_new=(h.get('current_class')=='NEW' or 'NEW' in tags or 'NEW_ENTRY' in tags)
    if is_new:
        p=h.get('pedigree_summary') or {}
        pedigree={k:p.get(k) for k in ('sire','damsire','dam') if p.get(k)}
        if pedigree:x['pedigree_summary']=pedigree
        if h.get('training_summary'):x['training_summary']=h['training_summary']
    return x

def main():
    doc=json.loads(SRC.read_text(encoding='utf-8')) if SRC.exists() else {'summary':{},'horses':[]}
    styles=load_running_styles()
    horses=[compact(h,styles) for h in doc.get('horses',[]) if h.get('horse_id') and h.get('horse_name')]
    horses.sort(key=lambda h:h.get('horse_name',''))
    style_counts=defaultdict(int)
    for h in horses:
        style_counts[h.get('running_style_label','判定待ち')]+=1
    summary={
        'horse_count':len(horses),
        'source':'INTERNAL_HORSE_CATALOG',
        'mode':'LIGHTWEIGHT_BASE_MASTER',
        'detail_policy':'expand only horses on verified upcoming JRA racecards',
        'new_horse_policy':'keep light pedigree/training memo before debut',
        'running_style_policy':'derive from recorded JRA corner positions; under 3 starts is provisional',
        'running_style_counts':dict(sorted(style_counts.items())),
        'ui_fields':['horse_name','sex_age','trainer','sire','damsire','current_class','active','latest_race_date','latest_finish','running_style']
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({'summary':summary,'horses':horses},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':main()
