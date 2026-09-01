#!/usr/bin/env python3
from pathlib import Path
import json,re,sys
from bs4 import BeautifulSoup
sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile

GOLD=Path('docs/data/oral-chat-golden-cases.json');BASE=Path('docs/data/replay-2026-08-29-30-sealed.json');OUT=Path('status/profile-race-link-diagnostic.json')
def key(r):return(str(r.get('date')),str(r.get('track')),int(r.get('race_no') or 0))
def no(v):
 m=re.match(r'\s*(\d+)',str(v));return m.group(1) if m else ''

def main():
 g=json.loads(GOLD.read_text());b=json.loads(BASE.read_text());bm={key(r):r for r in b['races']};rows=[]
 for c in g['cases'][:2]:
  r=bm[key(c)];n=no(c['axis']);h=next(x for x in r['ranked_snapshot'] if str(x.get('n'))==n);html=request_profile(h['horse_id']);soup=BeautifulSoup(html,'html.parser');links=[]
  for a in soup.find_all('a',href=True):
   href=a.get('href','');text=' '.join(a.stripped_strings)
   if 'accessS' in href or 'sde' in href or 'result' in href.lower():links.append({'text':text,'href':href})
  rows.append({'case':key(c),'axis':c['axis'],'horse_id':h['horse_id'],'link_count':len(links),'links':links[:30]})
 OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps({'cases':rows},ensure_ascii=False,indent=2));print(json.dumps({'cases':[{'axis':x['axis'],'link_count':x['link_count'],'sample':x['links'][:5]} for x in rows]},ensure_ascii=False))
if __name__=='__main__':main()
