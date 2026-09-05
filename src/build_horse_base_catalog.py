#!/usr/bin/env python3
"""Build the lightweight public horse master from the internal catalog.

Stable profile fields live here. Race-week analytics live in
weekly_runner_details.json. OPEN/GRADED browsing tags are derived only from
recorded JRA results plus JRA's official graded-race list.
"""
import csv
import html as html_lib
import json
import re
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path

SRC=Path('docs/data/horses/catalog.json')
OUT=Path('docs/data/horses/base_catalog.json')
RESULT_SOURCES=(Path('data/race_results_html_2026.csv'),)
PROFILE_2025=Path('data/horse_profiles_2025.csv')
GRADE_URL='https://www.jra.go.jp/datafile/seiseki/replay/2026/jyusyo.html'
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'

BASE_FIELDS=(
    'horse_name','horse_id','sex_age','trainer','sire','damsire',
    'current_class','current_class_label','active','latest_race_date','latest_finish',
    'starts','wins','unbeaten'
)
KEEP_TAGS={'GRADED','OPEN','NEW','NEW_ENTRY'}
STYLE_LABELS={
    'ESCAPE':'逃げ','FRONT':'先行','STALK':'好位差し','CLOSER':'差し',
    'DEEP_CLOSER':'追込','UNKNOWN':'判定待ち',
}
FALLBACK_GRADED={'新潟記念':'G3','中京2歳ステークス':'G3'}

def clean(v): return str(v or '').strip()

def normalize_race_name(v):
    s=unicodedata.normalize('NFKC',clean(v))
    s=s.replace('農林水産省賞典','')
    return re.sub(r'[\s　（）()・･]','',s)

def grade_code(raw):
    s=raw.upper().replace('Ｇ','G')
    if 'Ⅰ' in s or s.endswith('1') or s=='GI': return 'G1'
    if 'Ⅱ' in s or s.endswith('2') or s=='GII': return 'G2'
    if 'Ⅲ' in s or s.endswith('3') or s=='GIII': return 'G3'
    return ''

def official_graded_races():
    races=dict(FALLBACK_GRADED)
    try:
        req=urllib.request.Request(GRADE_URL,headers={'User-Agent':UA,'Accept-Language':'ja'})
        with urllib.request.urlopen(req,timeout=30) as resp: raw=resp.read()
        enc='utf-8' if b'utf-8' in raw[:3000].lower() else 'cp932'
        text=html_lib.unescape(raw.decode(enc,'replace'))
        text=re.sub(r'<script.*?</script>|<style.*?</style>',' ',text,flags=re.S|re.I)
        text=re.sub(r'<[^>]+>',' ',text)
        text=re.sub(r'\s+',' ',text)
        pat=re.compile(r'((?:G|Ｇ)(?:Ⅰ|Ⅱ|Ⅲ|1|2|3|I{1,3}))\s*([^\s|]{2,40})',re.I)
        for m in pat.finditer(text):
            prefix=text[max(0,m.start()-3):m.start()]
            if 'J・' in prefix or 'J-' in prefix: continue
            g=grade_code(m.group(1)); name=m.group(2).strip('：:')
            if g and name and not name.startswith('レース'): races[name]=g
    except Exception as e:
        print('graded race list fallback:',repr(e))
    return races

def load_results():
    rows=[]
    for path in RESULT_SOURCES:
        if not path.exists() or path.stat().st_size==0: continue
        with path.open(encoding='utf-8-sig',newline='') as f: rows.extend(csv.DictReader(f))
    return rows

def career_unbeaten_stats(rows):
    """Build career starts/wins without guessing.

    The 2025 horse profile is the historical baseline through 2025.
    Verified 2026 JRA result rows are then added once per race/horse.
    Horses first appearing in 2026 use their complete 2026 result history.
    """
    baseline_by_id={};baseline_by_name={}
    if PROFILE_2025.exists() and PROFILE_2025.stat().st_size:
        with PROFILE_2025.open(encoding='utf-8-sig',newline='') as f:
            for r in csv.DictReader(f):
                hid=clean(r.get('horse_id'));name=clean(r.get('horse_name'))
                try:starts=int(float(r.get('starts') or 0))
                except Exception:starts=0
                try:wins=int(float(r.get('wins') or 0))
                except Exception:wins=0
                if starts<0 or wins<0 or wins>starts:continue
                item={'starts':starts,'wins':wins,'source':'JRA_HORSE_PROFILE_2025'}
                if hid:baseline_by_id[hid]=item
                if name:baseline_by_name[name]=item

    current=defaultdict(dict);current_name={}
    for r in rows:
        hid=clean(r.get('horse_id'));name=clean(r.get('horse_name'))
        if not hid and not name:continue
        finish=clean(r.get('finish_position'))
        try:finish_i=int(float(finish))
        except Exception:continue
        if finish_i<=0:continue
        rid=clean(r.get('race_id'))
        if not rid:continue
        key=hid or ('NAME:'+name)
        current[key][rid]=finish_i
        if name:current_name[key]=name

    out={}
    for key,starts_by_race in current.items():
        hid='' if key.startswith('NAME:') else key
        name=current_name.get(key) or (key[5:] if key.startswith('NAME:') else '')
        base=baseline_by_id.get(hid) or baseline_by_name.get(name)
        starts=(base or {}).get('starts',0)
        wins=(base or {}).get('wins',0)
        finishes=list(starts_by_race.values())
        starts+=len(finishes)
        wins+=sum(1 for x in finishes if x==1)
        item={
            'starts':starts,
            'wins':wins,
            'unbeaten':bool(starts>=2 and wins==starts),
            'unbeaten_source':'JRA_PROFILE_2025_PLUS_OFFICIAL_2026_RESULTS' if base else 'JRA_OFFICIAL_2026_RESULTS_ONLY',
        }
        out[key]=item
        if name:out['NAME:'+name]=item
    return out

def parse_corners(value): return [int(x) for x in re.findall(r'\d+',str(value or ''))]

def load_running_styles(rows):
    field_sizes=defaultdict(int)
    for r in rows:
        rid=r.get('race_id') or ''
        if rid and r.get('horse_id'): field_sizes[rid]+=1
    samples=defaultdict(list)
    for r in rows:
        hid=r.get('horse_id') or ''; rid=r.get('race_id') or ''
        corners=parse_corners(r.get('corner_positions')); n=field_sizes.get(rid,0)
        if not hid or not corners or n<3: continue
        first,last=corners[0],corners[-1]
        first_ratio=max(0.0,min(1.0,(first-1)/max(1,n-1)))
        last_ratio=max(0.0,min(1.0,(last-1)/max(1,n-1)))
        samples[hid].append((first,last,first_ratio,last_ratio))
    out={}
    for hid,ss in samples.items():
        starts=len(ss); escape_rate=sum(1 for first,_,_,_ in ss if first==1)/starts
        avg_ratio=sum((a+b)/2 for _,_,a,b in ss)/starts
        if escape_rate>=0.5 or avg_ratio<=0.07: code='ESCAPE'
        elif avg_ratio<=0.28: code='FRONT'
        elif avg_ratio<=0.45: code='STALK'
        elif avg_ratio<=0.70: code='CLOSER'
        else: code='DEEP_CLOSER'
        out[hid]={'running_style':code,'running_style_label':STYLE_LABELS[code],
                  'running_style_sample_starts':starts,'running_style_provisional':starts<3}
    return out

def load_class_tags(rows,graded_names):
    latest={}; graded=defaultdict(dict)
    grade_items=[(normalize_race_name(name),grade,name) for name,grade in graded_names.items()]
    for r in rows:
        hid=clean(r.get('horse_id')); date=clean(r.get('race_date')); rid=clean(r.get('race_id'))
        if not hid: continue
        key=(date,rid)
        if hid not in latest or key>latest[hid][0]: latest[hid]=(key,clean(r.get('race_class')))
        rn=normalize_race_name(r.get('race_name'))
        for gn,g,official_name in grade_items:
            if gn and rn and (gn in rn or rn in gn): graded[hid][g]=official_name
    out={}
    for hid in set(latest)|set(graded):
        cls=latest.get(hid,(None,''))[1]
        grades=sorted(graded.get(hid,{}),key=lambda g:{'G1':1,'G2':2,'G3':3}.get(g,9))
        out[hid]={'latest_recorded_class':cls,'is_open':cls=='オープン','grades':grades,
                  'graded_races':list(graded.get(hid,{}).values())}
    return out

def compact(h,styles,class_tags,career_stats):
    x={k:h.get(k) for k in BASE_FIELDS if h.get(k) not in (None,'')}
    hid=clean(h.get('horse_id'));name=clean(h.get('horse_name'));st=career_stats.get(hid) or career_stats.get('NAME:'+name)
    if st:
        x['starts']=st['starts'];x['wins']=st['wins'];x['unbeaten']=st['unbeaten'];x['unbeaten_source']=st['unbeaten_source']
    tags=[t for t in (h.get('tags') or []) if t in KEEP_TAGS]
    c=class_tags.get(h.get('horse_id'),{})
    if c.get('is_open'):
        tags.append('OPEN'); x['current_class']='OPEN'; x['current_class_label']='オープン'
    if c.get('grades'): tags.append('GRADED')
    if tags: x['tags']=sorted(set(tags))
    if c.get('grades'):
        x['graded_experience']=c['grades']; x['graded_race_names']=c['graded_races'][-5:]
    style=styles.get(h.get('horse_id'))
    if style: x.update(style)
    else: x.update({'running_style':'UNKNOWN','running_style_label':STYLE_LABELS['UNKNOWN'],
                    'running_style_sample_starts':0,'running_style_provisional':True})
    is_new=(h.get('current_class')=='NEW' or 'NEW' in tags or 'NEW_ENTRY' in tags)
    if is_new:
        p=h.get('pedigree_summary') or {}
        pedigree={k:p.get(k) for k in ('sire','damsire','dam') if p.get(k)}
        if pedigree:x['pedigree_summary']=pedigree
        if h.get('training_summary'):x['training_summary']=h['training_summary']
    return x

def main():
    doc=json.loads(SRC.read_text(encoding='utf-8')) if SRC.exists() else {'summary':{},'horses':[]}
    rows=load_results(); graded_names=official_graded_races(); career_stats=career_unbeaten_stats(rows)
    styles=load_running_styles(rows); class_tags=load_class_tags(rows,graded_names)
    horses=[compact(h,styles,class_tags,career_stats) for h in doc.get('horses',[]) if h.get('horse_id') and h.get('horse_name')]
    horses.sort(key=lambda h:h.get('horse_name',''))
    style_counts=defaultdict(int)
    for h in horses: style_counts[h.get('running_style_label','判定待ち')]+=1
    open_count=sum('OPEN' in (h.get('tags') or []) for h in horses)
    graded_count=sum('GRADED' in (h.get('tags') or []) for h in horses)
    unbeaten_count=sum(h.get('unbeaten') is True and int(h.get('wins') or 0)>=2 for h in horses)
    summary={'horse_count':len(horses),'source':'INTERNAL_HORSE_CATALOG + JRA_OFFICIAL_RESULTS',
      'mode':'LIGHTWEIGHT_BASE_MASTER','detail_policy':'expand only horses on verified upcoming JRA racecards',
      'new_horse_policy':'keep light pedigree/training memo before debut',
      'running_style_policy':'derive from recorded JRA corner positions; under 3 starts is provisional',
      'elite_tag_policy':'OPEN=latest recorded JRA class is open; GRADED=recorded start in JRA official 2026 flat graded race',
      'official_graded_race_names_loaded':len(graded_names),'open_count':open_count,'graded_count':graded_count,'unbeaten_count':unbeaten_count,
      'running_style_counts':dict(sorted(style_counts.items())),
      'unbeaten_policy':'career starts >= 2 and career wins == career starts; 2025 profile baseline + deduplicated official 2026 JRA results',
      'ui_fields':['horse_name','sex_age','trainer','sire','damsire','current_class','active','latest_race_date','latest_finish','starts','wins','unbeaten','running_style','OPEN','GRADED']}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({'summary':summary,'horses':horses},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':main()
