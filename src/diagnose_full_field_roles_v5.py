#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures,json
from pathlib import Path
import sys
sys.path.insert(0,'src')
from run_oral_golden_fast_v3 import profile_history,result_class,track_code,feats

CARDS=Path('docs/data/race_cards.json');V4=Path('docs/data/oral-golden-fast-v4.json');OUT=Path('status/oral-full-field-role-diagnostic-v5.json')
def key(r):return(str(r.get('date')),str(r.get('track')),int(r.get('race_no') or 0))

def main():
 cards=json.loads(CARDS.read_text());v4=json.loads(V4.read_text());cm={key(r):r for r in cards['races']};targets=v4['races'];ids=sorted({str(h.get('horse_id')) for r in targets for h in cm[key(r)].get('horses',[]) if h.get('horse_id')});hist={};errors=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
  fs={ex.submit(profile_history,i):i for i in ids}
  for fu in concurrent.futures.as_completed(fs):
   i=fs[fu]
   try:hist[i]=fu.result()
   except Exception as e:hist[i]=[];errors.append({'horse_id':i,'error':repr(e)})
 urls=sorted({x['href'] for hs in hist.values() for x in hs[:8] if x.get('href')});classmap={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
  fs={ex.submit(result_class,u):u for u in urls}
  for fu in concurrent.futures.as_completed(fs):classmap[fs[fu]]=fu.result()
 rows=[]
 for r in targets:
  card=cm[key(r)];known={str(x.get('n')):x for x in r.get('ranked_snapshot',[])};target_class=r.get('target_class');tc=track_code(card.get('race_id'));dist=int(card.get('distance_m') or 0);horses=[]
  for h in card.get('horses',[]):
   hid=str(h.get('horse_id') or '');ff=feats(hist.get(hid,[]),str(card['date']),dist,tc,target_class,classmap);pre=[x for x in hist.get(hid,[]) if x.get('date','')<card['date'] and x.get('finish')];recent=pre[:5];same=[x for x in pre if target_class and classmap.get(x.get('href'))==target_class];exact=[x for x in same if x.get('distance_m')==dist]
   avg_recent=sum(x['finish'] for x in recent)/len(recent) if recent else None;best_recent=min((x['finish'] for x in recent),default=None);top3_count=sum(x['finish']<=3 for x in exact);role_score=30*ff['recent_top3_rate']+25*ff['same_class_top3_rate']+25*ff['exact_class_top3_rate']+(12 if best_recent and best_recent<=3 else 0)+(8 if ff.get('latest_finish') and ff['latest_finish']<=5 else 0)+(4 if len(exact)>=3 else 0)
   horses.append({'n':str(h.get('n')),'name':h.get('name'),'horse_id':hid,'in_v4_top10':str(h.get('n')) in known,'v4_score':known.get(str(h.get('n')),{}).get('score'),'recent_starts':len(recent),'same_class_starts':len(same),'exact_class_starts':len(exact),'exact_class_top3_count':top3_count,'avg_recent_finish':None if avg_recent is None else round(avg_recent,3),'best_recent_finish':best_recent,**ff,'secondary_role_score':round(role_score,3)})
  horses.sort(key=lambda x:(-x['secondary_role_score'],int(x['n'])));rows.append({'date':card['date'],'track':card['track'],'race_no':card['race_no'],'race_name':card['race_name'],'target_class':target_class,'runner_count':len(horses),'all_field_roles':horses})
 OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps({'version':'ORAL_FULL_FIELD_ROLE_DIAGNOSTIC_V5','result_data_used':False,'odds_popularity_used':False,'history_errors':errors,'class_resolved':sum(v is not None for v in classmap.values()),'races':rows},ensure_ascii=False,indent=2));print(json.dumps({'races':[(r['track'],r['race_no'],[(h['n'],h['name'],h['secondary_role_score']) for h in r['all_field_roles'][:12]]) for r in rows],'errors':len(errors)},ensure_ascii=False))
if __name__=='__main__':main()
