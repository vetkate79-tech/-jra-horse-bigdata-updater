#!/usr/bin/env python3
"""Build race-week details and upsert every verified runner into the persistent horse master."""
from __future__ import annotations
import json,re
from pathlib import Path
from bs4 import BeautifulSoup
import sys
sys.path.insert(0,'src')
from collect_upcoming_new_horses import current_week_seeds,fetch,cname_url,extract_links,META,COURSE,normalize_horse_id,runner_rows

CAT=Path('docs/data/horses/catalog.json');OUT=Path('docs/data/horses/weekly_runner_details.json');STATUS=Path('status/weekly_runner_details.json')

def canonical_id(v):
    s=normalize_horse_id(v)
    if '/' in s:
        head,tail=s.rsplit('/',1);s=head.lower()+'/'+tail.upper()
    return s

def load_catalog_doc():
    if not CAT.exists():return {'summary':{},'horses':[]}
    return json.loads(CAT.read_text(encoding='utf-8'))

def race_title(soup):
    heads=[]
    for n in soup.find_all(['h1','h2','h3']):
        t=' '.join(n.stripped_strings).strip()
        if not t or any(x in t for x in ('検索ウィンドウ','関連メニュー','開催選択','レース選択','ここから本文','本賞金','出馬表','緊急情報','お知らせ','インフォメーション')):continue
        heads.append(t)
    pat=re.compile(r'(未勝利|メイクデビュー|新馬|オープン|特別|ステークス|カップ|杯|賞|記念|クラス|障害|リステッド|重賞|ハンデキャップ|G[123]|Ｇ[ⅠⅡⅢ])')
    for t in heads:
        if pat.search(t) and len(t)<=60:return t
    for t in heads:
        if len(t)<=40 and not re.search(r'\d{4}年\d{1,2}月\d{1,2}日',t):return t
    return ''

def race_condition(soup):
    text=' '.join(soup.stripped_strings);m=re.search(r'コース[:：]\s*([0-9,]+)\s*メートル\s*[（(]\s*(芝|ダート)',text)
    if m:return m.group(2),int(m.group(1).replace(',',''))
    m=re.search(r'(芝|ダート|ダ)\s*([0-9]{3,4})\s*[mｍ]?',text)
    return (('芝' if m and m.group(1)=='芝' else 'ダート'),int(m.group(2))) if m else ('',None)

def start_time(soup):
    text=' '.join(soup.stripped_strings);m=re.search(r'発走時刻[:：]\s*(\d{1,2})時(\d{2})分',text)
    return f'{int(m.group(1)):02d}:{m.group(2)}' if m else ''

def class_from_page(soup,title):
    """Resolve the JRA class from the current official card, never from odds/results."""
    text=' '.join(soup.stripped_strings)
    probes=[str(title or ''),text[:7000]]
    for s in probes:
        if 'メイクデビュー' in s or re.search(r'\b新馬\b',s):return 'NEW','新馬'
        if '未勝利' in s:return 'MAIDEN','未勝利'
        if re.search(r'3勝クラス',s):return '3WIN','3勝クラス'
        if re.search(r'2勝クラス',s):return '2WIN','2勝クラス'
        if re.search(r'1勝クラス',s):return '1WIN','1勝クラス'
        if any(x in s for x in ('オープン','リステッド','重賞','G1','G2','G3','ＧⅠ','ＧⅡ','ＧⅢ')):return 'OPEN','オープン以上'
    # JRA named special races usually expose the underlying class elsewhere in the card.
    m=re.search(r'([123])勝クラス',text)
    if m:return {'1':'1WIN','2':'2WIN','3':'3WIN'}[m.group(1)],m.group(0)
    if '未勝利' in text:return 'MAIDEN','未勝利'
    if '新馬' in text or 'メイクデビュー' in text:return 'NEW','新馬'
    if any(x in text for x in ('オープン','リステッド','重賞')):return 'OPEN','オープン以上'
    return '', ''

def frame_and_horse_no(tr,cells):
    # JRA renders the frame as an image (e.g. alt="枠6緑"), so stripped_strings
    # contains the horse number but not the frame number. Read the official
    # frame image directly instead of guessing from numeric cells.
    frame_no=''
    if tr is not None:
        for img in tr.find_all('img'):
            m=re.search(r'枠\s*([1-8])',str(img.get('alt') or ''))
            if m:
                frame_no=m.group(1);break
    nums=[x.strip() for x in cells[:5] if re.fullmatch(r'\d{1,2}',x.strip())]
    horse_no=nums[0] if nums else ''
    return frame_no,horse_no

def row_meta(row_text):
    sex_age='';carried='';jockey='';m=re.search(r'(牡|牝|せん)\s*(\d+)',row_text)
    if m:sex_age=f'{m.group(1)}{m.group(2)}'
    m=re.search(r'(\d{2}(?:\.\d)?)\s*kg\s*([▲△★☆◇]?[^0-9]+?)(?=\s*20\d{2}年|\s*$)',row_text)
    if m:carried=m.group(1);jockey=' '.join(m.group(2).split()).strip()
    return sex_age,carried,jockey

def prior_starts(row_text):
    out=[]
    parts=re.split(r'(?=20\d{2}年\s*\d{1,2}月\s*\d{1,2}日)',row_text)
    for p in parts:
        dm=re.match(r'(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日\s*([^\s]+)',p)
        fm=re.search(r'(\d+)\s*着',p);cm=re.search(r'([0-9,]{3,5})\s*(芝|ダ)',p)
        if not dm or not fm or not cm:continue
        lm=re.search(r'3F\s*(\d+(?:\.\d+)?)',p);dist=int(cm.group(1).replace(',',''))
        if dist<800 or dist>4000:continue
        out.append({'race_date':f'{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}','course':dm.group(4),'finish_position':int(fm.group(1)),'distance_m':dist,'surface':'芝' if cm.group(2)=='芝' else 'ダート','last3f':float(lm.group(1)) if lm else None,'source':'JRA_CURRENT_RACECARD_PRIOR_START'})
    out.sort(key=lambda x:x['race_date'],reverse=True);return out[:4]

def parse_card(cname,raw):
    m=META.search(cname)
    if not m:return None
    soup=BeautifulSoup(raw,'html.parser');d=m.group('date');date=f'{d[:4]}-{d[4:6]}-{d[6:]}';surface,distance_m=race_condition(soup);title=race_title(soup);cls,cls_label=class_from_page(soup,title)
    race={'race_id':m.group(0),'date':date,'track':COURSE.get(m.group('course'),m.group('course')),'race_no':int(m.group('race')),'race_name':title,'surface':surface,'distance_m':distance_m,'start_time':start_time(soup),'current_class':cls,'current_class_label':cls_label,'source_url':cname_url(cname),'runners':[]};seen=set()
    for a,hid,name,row_text in runner_rows(soup):
        hid=canonical_id(hid)
        if hid in seen:continue
        seen.add(hid);tr=a.find_parent('tr');cells=[' '.join(x.stripped_strings) for x in tr.find_all(['th','td'])] if tr else [];frame_no,horse_no=frame_and_horse_no(tr,cells);sex_age,carried,jockey=row_meta(row_text)
        race['runners'].append({'horse_id':hid,'horse_name':name,'frame_no':frame_no,'horse_no':horse_no,'sex_age':sex_age,'carried_weight':carried,'jockey':jockey,'recent_starts_from_card':prior_starts(row_text),'official_row_text':row_text})
    return race if race['runners'] else None

def hist_key(x):
    return (str(x.get('race_id') or ''),str(x.get('race_date') or x.get('date') or ''),str(x.get('course') or x.get('track') or ''),str(x.get('distance_m') or ''),str(x.get('finish_position') or x.get('finish') or ''))

def merge_history(items):
    seen=set();out=[]
    for x in items:
        if not isinstance(x,dict):continue
        k=hist_key(x)
        if k in seen:continue
        seen.add(k);out.append(x)
    out.sort(key=lambda x:str(x.get('race_date') or x.get('date') or ''),reverse=True)
    return out

def merge_duplicate_records(dst,src):
    for k,v in src.items():
        if k in ('horse_id','upcoming_starts','recent_starts','tags'):continue
        if dst.get(k) in (None,'',[],{}) and v not in (None,'',[],{}):dst[k]=v
    dst['tags']=sorted(set((dst.get('tags') or [])+(src.get('tags') or [])))
    starts=[];seen=set()
    for x in (dst.get('upcoming_starts') or [])+(src.get('upcoming_starts') or []):
        if not isinstance(x,dict):continue
        rid=str(x.get('race_id') or '')
        if rid and rid in seen:continue
        if rid:seen.add(rid)
        starts.append(x)
    if starts:dst['upcoming_starts']=starts
    hist=merge_history((dst.get('recent_starts') or [])+(src.get('recent_starts') or []))
    if hist:dst['recent_starts']=hist[:20]

def upsert_catalog(cards):
    doc=load_catalog_doc();raw_horses=doc.get('horses') or [];by_id={};deduped=[];merged_duplicates=0
    for h in raw_horses:
        hid=canonical_id(h.get('horse_id'))
        if not hid:continue
        h['horse_id']=hid
        if hid in by_id:
            merge_duplicate_records(by_id[hid],h);merged_duplicates+=1;continue
        by_id[hid]=h;deduped.append(h)
    added=updated=0;unresolved_class=0
    for race in cards:
        for row in race['runners']:
            hid=canonical_id(row.get('horse_id'));row['horse_id']=hid;h=by_id.get(hid)
            if h is None:
                h={'horse_id':hid,'horse_name':row.get('horse_name') or '','sex_age':row.get('sex_age') or '','trainer':'','tags':[],'recent_starts':[],'upcoming_starts':[]};by_id[hid]=h;deduped.append(h);added+=1
            else:updated+=1
            if row.get('horse_name'):h['horse_name']=row['horse_name']
            if row.get('sex_age'):h['sex_age']=row['sex_age']
            h['active']=True
            if race.get('current_class'):
                h['current_class']=race['current_class'];h['current_class_label']=race.get('current_class_label') or race['current_class']
            elif not h.get('current_class'):
                unresolved_class+=1
            hist=merge_history((row.get('recent_starts_from_card') or [])+(h.get('recent_starts') or []));h['recent_starts']=hist[:20]
            if hist and not h.get('latest_race_date'):h['latest_race_date']=hist[0].get('race_date')
            starts=h.setdefault('upcoming_starts',[]);item={k:race.get(k) for k in ('race_id','date','track','race_no','race_name','source_url')};item['horse_no']=row.get('horse_no','');item['frame_no']=row.get('frame_no','')
            pos=next((i for i,x in enumerate(starts) if isinstance(x,dict) and x.get('race_id')==item['race_id']),None)
            if pos is None:starts.append(item)
            else:starts[pos]={**starts[pos],**item}
    deduped.sort(key=lambda h:(h.get('horse_name',''),h.get('horse_id','')))
    s=dict(doc.get('summary') or {});s.update({'unified_horse_count':len(deduped),'weekly_runner_master_added':added,'weekly_runner_master_updated':updated,'canonical_duplicate_records_merged':merged_duplicates,'weekly_runner_unresolved_class':unresolved_class,'horse_identity_policy':'ONE_CANONICAL_JRA_HORSE_ID_ONE_RECORD'})
    doc['summary']=s;doc['horses']=deduped;CAT.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    return by_id,added,updated,merged_duplicates,unresolved_class

def runner_detail(race,row,h):
    card_recent=row.get('recent_starts_from_card') or [];master_recent=(h.get('recent_starts') or [])[:20];recent=merge_history(card_recent+master_recent)
    detail={'horse_id':row['horse_id'],'horse_name':row['horse_name'],'frame_no':row.get('frame_no',''),'horse_no':row.get('horse_no',''),'jockey':row.get('jockey',''),'carried_weight':row.get('carried_weight',''),'race':{k:race.get(k) for k in ('race_id','date','track','race_no','race_name','surface','distance_m','start_time','source_url')},'sex_age':row.get('sex_age') or h.get('sex_age'),'trainer':h.get('trainer'),'current_class':h.get('current_class'),'current_class_label':h.get('current_class_label'),'recent_starts':recent[:5],'detail_scope':'RACE_WEEK_ONLY','source_policy':'JRA_OFFICIAL_RACECARD_PLUS_STORED_JRA_HISTORY'}
    for k in ('win_rate','quinella_rate','show_rate','sire','dam','damsire','pedigree_summary','training_summary'):
        if h.get(k) not in (None,''):detail[k]=h[k]
    return detail

def main():
    seeds=current_week_seeds();cards=[];errors=[]
    for key,seed in seeds.items():
        try:
            raw=fetch(cname_url(seed));links=extract_links(raw)+[seed];logical=set()
            for c in links:
                m=META.search(c)
                if not m or (m.group('date'),m.group('course'))!=key:continue
                lk=(m.group('date'),m.group('course'),m.group('race'))
                if lk in logical:continue
                logical.add(lk)
                try:
                    card=parse_card(c,fetch(cname_url(c)))
                    if card:cards.append(card)
                except Exception as e:errors.append({'race':c,'error':repr(e)})
        except Exception as e:errors.append({'seed':seed,'error':repr(e)})
    cards=sorted({c['race_id']:c for c in cards}.values(),key=lambda x:(x['date'],x['track'],x['race_no']))
    by_id,added,updated,merged_duplicates,unresolved_class=upsert_catalog(cards) if cards else ({},0,0,0,0);runners=[];missing=[]
    for race in cards:
        for row in race['runners']:
            h=by_id.get(row['horse_id'])
            if h is None:missing.append(row['horse_id']);h={'horse_id':row['horse_id'],'horse_name':row['horse_name']}
            runners.append(runner_detail(race,row,h))
    dates=sorted({r['race']['date'] for r in runners});frame_known=sum(1 for r in runners if r.get('frame_no'));prior_rows=sum(len(r.get('recent_starts') or []) for r in runners)
    payload={'summary':{'status':'READY' if runners else 'NO_UPCOMING_RACECARDS','race_count':len(cards),'runner_count':len(runners),'dates':dates,'race_name_resolved_count':sum(1 for c in cards if c.get('race_name') and c.get('race_name')!='検索ウィンドウ'),'race_condition_resolved_count':sum(1 for c in cards if c.get('surface') and c.get('distance_m')),'class_resolved_race_count':sum(1 for c in cards if c.get('current_class')),'card_prior_start_rows':prior_rows,'frame_known_count':frame_known,'frame_pending_count':len(runners)-frame_known,'master_added_count':added,'master_updated_count':updated,'canonical_duplicate_records_merged':merged_duplicates,'unresolved_class_runner_count':unresolved_class,'missing_master_count':len(set(missing)),'policy':'heavy detail exists only for verified upcoming JRA runners; persistent master is canonical horse-id upsert'},'runners':runners};forbidden={'odds','popularity','market_rank','betting_odds','win_odds'}
    def contains_forbidden_market(obj):
        if isinstance(obj,dict):
            return any(str(k).lower() in forbidden or contains_forbidden_market(v) for k,v in obj.items())
        if isinstance(obj,list):return any(contains_forbidden_market(v) for v in obj)
        return False
    if contains_forbidden_market(payload):raise RuntimeError('market field entered race-week runner details')
    OUT.parent.mkdir(parents=True,exist_ok=True);STATUS.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8');STATUS.write_text(json.dumps({**payload['summary'],'errors':errors,'missing_master_ids':sorted(set(missing))},ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(payload['summary'],ensure_ascii=False))
if __name__=='__main__':main()
