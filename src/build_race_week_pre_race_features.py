#!/usr/bin/env python3
"""Build leakage-safe multi-horizon pre-race features for upcoming JRA runners.

Structural big-data evidence dominates. Medium-term form and short-term context are
bounded corrections only. The cutoff is the earliest upcoming race date, so no
result on/after the seal week can enter pure prediction. Frame/draw information
is neutral until officially published; once known, a historical JRA draw prior is
used as a small short-term correction only.
"""
from __future__ import annotations
import csv, json, re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

WEEKLY = Path('docs/data/horses/weekly_runner_details.json')
OUT = Path('docs/data/horses/pre_race_features.json')
STATUS = Path('status/pre_race_features.json')
RESULT_SOURCES = (Path('data/race_results_html_2025.csv'), Path('data/race_results_html_2026.csv'))
STRUCTURAL_WEIGHT=.70; MEDIUM_WEIGHT=.20; SHORT_WEIGHT=.10; SHORT_WEIGHT_MAX=.15

def num(v,d=None):
    try:return float(str(v).replace(',',''))
    except Exception:return d

def integer(v,d=None):
    m=re.search(r'\d+',str(v or ''));return int(m.group()) if m else d

def dt(v):
    try:return datetime.strptime(str(v)[:10],'%Y-%m-%d').date()
    except Exception:return None

def clean_name(v):return re.sub(r'\s+','',str(v or '').strip())

def load_rows():
    out=[]
    for p in RESULT_SOURCES:
        if not p.exists() or p.stat().st_size==0:continue
        with p.open(encoding='utf-8-sig',newline='') as f:out.extend(csv.DictReader(f))
    return out

def norm_surface(v):
    s=str(v or '')
    if '芝' in s:return '芝'
    if 'ダ' in s:return 'ダート'
    return ''

def parse_corners(v):return [int(x) for x in re.findall(r'\d+',str(v or ''))]

def style_from_history(hist,field_sizes):
    samples=[]
    for r in hist:
        rid=r.get('race_id') or '';corners=parse_corners(r.get('corner_positions'));n=field_sizes.get(rid,0)
        if not corners or n<3:continue
        first,last=corners[0],corners[-1];a=max(0,min(1,(first-1)/max(1,n-1)));b=max(0,min(1,(last-1)/max(1,n-1)));samples.append((first,a,b))
    if not samples:return 'UNKNOWN',0
    escape=sum(1 for first,_,_ in samples if first==1)/len(samples);avg=sum((a+b)/2 for _,a,b in samples)/len(samples)
    if escape>=.5 or avg<=.07:return 'ESCAPE',len(samples)
    if avg<=.28:return 'FRONT',len(samples)
    if avg<=.45:return 'STALK',len(samples)
    if avg<=.70:return 'CLOSER',len(samples)
    return 'DEEP_CLOSER',len(samples)

def people_rates(rows,cutoff):
    all_j=defaultdict(lambda:[0,0]);all_t=defaultdict(lambda:[0,0]);rec_j=defaultdict(lambda:[0,0]);rec_t=defaultdict(lambda:[0,0]);cut=dt(cutoff);recent_from=cut-timedelta(days=30)
    for r in rows:
        finish=integer(r.get('finish_position'));d=dt(r.get('race_date'))
        if finish is None:continue
        for name,b in ((str(r.get('jockey') or '').strip(),all_j),(str(r.get('trainer') or '').strip(),all_t)):
            if name:b[name][0]+=1;b[name][1]+=int(finish<=3)
        if d and d>=recent_from:
            for name,b in ((str(r.get('jockey') or '').strip(),rec_j),(str(r.get('trainer') or '').strip(),rec_t)):
                if name:b[name][0]+=1;b[name][1]+=int(finish<=3)
    def rate(bucket,name,prior=.25):
        n,x=bucket.get(str(name or '').strip(),[0,0]);return (x+prior*8)/(n+8) if n else prior
    return (lambda n:rate(all_j,n)),(lambda n:rate(all_t,n)),(lambda n:rate(rec_j,n)),(lambda n:rate(rec_t,n))

def draw_priors(rows):
    buckets=defaultdict(lambda:[0,0])
    for r in rows:
        finish=integer(r.get('finish_position'));frame=integer(r.get('枠'));dist=integer(r.get('distance_m'));track=str(r.get('course') or '').strip();surface=norm_surface(r.get('surface'))
        if finish is None or frame is None or not track or not surface or not dist:continue
        band=int(round(dist/200.0)*200);k=(track,surface,band,frame);buckets[k][0]+=1;buckets[k][1]+=int(finish<=3)
    def prior(track,surface,dist,frame):
        if not frame or not track or not surface or not dist:return .30,0
        n,x=buckets.get((track,surface,int(round(dist/200.0)*200),frame),[0,0]);return ((x+.30*12)/(n+12) if n else .30),n
    return prior

def continuity(hist,race):
    if not hist:return .5,.5,None
    last=hist[0];target_surface=norm_surface(race.get('surface'));last_surface=norm_surface(last.get('surface'))
    td=integer(race.get('distance_m'));ld=integer(last.get('distance_m'));surface_score=1.0 if target_surface and target_surface==last_surface else .35
    distance_score=.5 if not td or not ld else max(0.0,1-abs(td-ld)/800)
    rd=dt(race.get('date'));ldate=dt(last.get('race_date'));days=(rd-ldate).days if rd and ldate else None
    if days is None:rest=.5
    elif 14<=days<=56:rest=1.0
    elif 8<=days<=84:rest=.75
    elif days<5 or days>180:rest=.2
    else:rest=.5
    return surface_score,distance_score,(days,rest)

def feature_for(runner,hist,rates,field_sizes,draw_rate):
    race=runner.get('race') or {};starts=len(hist);top3=sum(integer(x.get('finish_position'),99)<=3 for x in hist);show=(top3+1.5)/(starts+5) if starts else .30
    recent=hist[:5]
    if recent:
        ws=[5,4,3,2,1][:len(recent)];rec=sum(w*(1/max(1,min(18,integer(x.get('finish_position'),18)))) for w,x in zip(ws,recent))/sum(ws);rec=min(1,rec*3.2)
    else:rec=.35
    target_surface=norm_surface(race.get('surface'));target_distance=integer(race.get('distance_m'));matches=[]
    if target_surface and target_distance:
        for x in hist:
            surface=norm_surface(x.get('surface'));distance=integer(x.get('distance_m'))
            if surface==target_surface and distance and abs(distance-target_distance)<=300:matches.append(x)
    cond=(sum(integer(x.get('finish_position'),99)<=3 for x in matches)+1)/(len(matches)+3) if matches else show
    last3f=[num(x.get('last3f')) for x in recent];last3f=[x for x in last3f if x is not None];l3=.5 if not last3f else max(0,min(1,(40-min(last3f))/8));uncertainty=1-min(1,starts/5)
    j_all,t_all,j30,t30=rates;jockey=runner.get('jockey') or '';trainer=runner.get('trainer') or '';ja=j_all(jockey);ta=t_all(trainer);jr=j30(jockey);tr=t30(trainer)
    style,style_starts=style_from_history(hist,field_sizes);surf_cont,dist_cont,rest_info=continuity(hist,race);days_since,rest_fit=rest_info if rest_info else (None,.5)
    frame=integer(runner.get('frame_no'));draw,draw_n=draw_rate(str(race.get('track') or ''),target_surface,target_distance,frame);frame_known=frame is not None
    structural=100*(.65*show+.25*cond+.05*ja+.05*ta);medium=100*(.70*rec+.30*l3);short=100*(.25*jr+.25*tr+.20*rest_fit+.10*surf_cont+.10*dist_cont+.10*draw)
    score=STRUCTURAL_WEIGHT*structural+MEDIUM_WEIGHT*medium+SHORT_WEIGHT*short-8*uncertainty
    return {'starts_before':starts,'show_rate_prior':round(show,4),'recent_form':round(rec,4),'condition_fit':round(cond,4),'uncertainty':round(uncertainty,4),'jockey_show_prior':round(ja,4),'trainer_show_prior':round(ta,4),'jockey_show_30d':round(jr,4),'trainer_show_30d':round(tr,4),'last3f_signal':round(l3,4),'days_since_last_start':days_since,'surface_continuity':round(surf_cont,4),'distance_continuity':round(dist_cont,4),'frame_no':str(frame) if frame_known else '','frame_known':frame_known,'draw_show_prior':round(draw,4),'draw_history_starts':draw_n,'pre_race_running_style':style,'running_style_sample_starts':style_starts,'structural_big_data_score':round(structural,3),'medium_term_form_score':round(medium,3),'short_term_context_score':round(short,3),'structural_weight':STRUCTURAL_WEIGHT,'medium_weight':MEDIUM_WEIGHT,'short_term_weight':SHORT_WEIGHT,'short_term_weight_cap':SHORT_WEIGHT_MAX,'pre_race_score':round(score,3),'pre_race_score_source':'JRA_MULTI_HORIZON_STRICT_CUTOFF_V3_DRAW_SAFE'}

def main():
    weekly=json.loads(WEEKLY.read_text(encoding='utf-8')) if WEEKLY.exists() else {'runners':[]};runners=weekly.get('runners') or [];dates=sorted({str((x.get('race') or {}).get('date') or '') for x in runners if (x.get('race') or {}).get('date')})
    if not dates:
        payload={'summary':{'status':'NO_UPCOMING_RACECARDS','runner_count':0},'features':[]};OUT.parent.mkdir(parents=True,exist_ok=True);STATUS.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8');STATUS.write_text(json.dumps(payload['summary'],ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(payload['summary'],ensure_ascii=False));return
    cutoff=dates[0];rows=[r for r in load_rows() if str(r.get('race_date') or '') and str(r.get('race_date'))<cutoff];rows.sort(key=lambda r:str(r.get('race_date') or ''),reverse=True)
    by_horse=defaultdict(list);by_name=defaultdict(list);name_ids=defaultdict(set);field_sizes=defaultdict(int)
    for r in rows:
        hid=str(r.get('horse_id') or '');rid=str(r.get('race_id') or '');name=clean_name(r.get('horse_name'))
        if hid:by_horse[hid].append(r)
        if name:by_name[name].append(r);name_ids[name].add(hid)
        if hid and rid:field_sizes[rid]+=1
    rates=people_rates(rows,cutoff);draw_rate=draw_priors(rows);feats=[];id_joins=name_joins=0
    for x in runners:
        race=x.get('race') or {};hid=str(x.get('horse_id') or '');name=clean_name(x.get('horse_name'));hist=by_horse.get(hid,[]);join_source='HORSE_ID'
        if hist:id_joins+=1
        elif name and len({z for z in name_ids.get(name,set()) if z})==1:
            hist=by_name.get(name,[]);join_source='EXACT_HORSE_NAME';name_joins+=int(bool(hist))
        else:join_source='NO_HISTORY_MATCH'
        f=feature_for(x,hist,rates,field_sizes,draw_rate)
        feats.append({'race_id':race.get('race_id'),'date':race.get('date'),'track':race.get('track'),'race_no':race.get('race_no'),'horse_id':hid,'horse_name':x.get('horse_name'),'history_join_source':join_source,'frame_no':x.get('frame_no'),'horse_no':x.get('horse_no'),**f})
    evidence=sum(1 for x in feats if x['starts_before']>0);frame_known=sum(1 for x in feats if x['frame_known']);summary={'status':'READY','cutoff_date':cutoff,'runner_count':len(feats),'history_rows_before_cutoff':len(rows),'runners_with_history':evidence,'runners_without_history':len(feats)-evidence,'history_join_by_id_count':id_joins,'history_join_by_exact_name_count':name_joins,'frame_known_count':frame_known,'frame_pending_count':len(feats)-frame_known,'draw_feature_applied':frame_known>0,'results_on_or_after_cutoff_used':False,'odds_popularity_used':False,'multi_horizon_weights':{'structural':STRUCTURAL_WEIGHT,'medium':MEDIUM_WEIGHT,'short':SHORT_WEIGHT,'short_cap':SHORT_WEIGHT_MAX}}
    payload={'summary':summary,'features':feats};OUT.parent.mkdir(parents=True,exist_ok=True);STATUS.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8');STATUS.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':main()
