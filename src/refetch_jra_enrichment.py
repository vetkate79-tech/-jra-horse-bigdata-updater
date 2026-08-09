#!/usr/bin/env python3
"""Fast enrichment backfill from already verified race URLs (no race rediscovery)."""
import argparse,csv,json,re,time,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from bs4 import BeautifulSoup

UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
def atomic(path,rows):
 fields=sorted(set().union(*(r.keys() for r in rows))) if rows else [];tmp=path.with_suffix('.tmp')
 with tmp.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 tmp.replace(path)
def get(url):
 for n in range(5):
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':UA}),timeout=60) as r:b=r.read()
   if len(b)<70000:raise RuntimeError('short response')
   return b.decode('shift_jis','replace')
  except Exception:
   if n==4:raise
   time.sleep(2**n)
def text(soup,selector):
 x=soup.select_one(selector);return x.get_text(' ',strip=True) if x else ''
def one(item):
 race_id,date,url=item; soup=BeautifulSoup(get(url),'html.parser')
 context={'race_id':race_id,'race_date':date,'race_name':text(soup,'#race_result .race_name'),
  'weather':text(soup,'#race_result .weather .txt'),'track_condition':text(soup,'#race_result .baba li.turf .txt, #race_result .baba li.dirt .txt'),
  'race_class':text(soup,'#race_result .race_title .class'),'race_category':text(soup,'#race_result .race_title .category'),
  'race_rule':text(soup,'#race_result .race_title .rule'),'weight_rule':text(soup,'#race_result .race_title .weight'),
  'scheduled_start':text(soup,'#race_result .date_line .time strong'),'source_url':url,'data_status':'PASS_HTML'}
 payouts=[]
 for li in soup.select('#race_result .refund_area li'):
  bet=text(li,'dt')
  for line in li.select('.line'):
   selection=text(line,'.num');yen=re.sub(r'\D','',text(line,'.yen'));pop=re.sub(r'\D','',text(line,'.pop'))
   if bet and selection and yen:payouts.append({'race_id':race_id,'race_date':date,'bet_type':bet,
    'winning_selection':selection,'payout_per_100_yen':yen,'payout_popularity':pop,'source_url':url,'data_status':'PASS_HTML'})
 errors=[]
 for key in ('race_name','weather','track_condition','race_class','scheduled_start'):
  if not context[key]:errors.append(key)
 if not payouts:errors.append('payouts')
 if errors:
  context['data_status']='QUARANTINED:'+','.join(errors)
  for p in payouts:p['data_status']=context['data_status']
 return context,payouts,errors
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--results',type=Path,required=True);ap.add_argument('--year',type=int,required=True)
 ap.add_argument('--workers',type=int,default=12);ap.add_argument('--checkpoint',type=Path,default=Path('work/enrichment'))
 a=ap.parse_args();a.checkpoint.mkdir(parents=True,exist_ok=True);done=a.checkpoint/f'done_{a.year}.jsonl'
 with a.results.open(encoding='utf-8-sig',newline='') as f:
  items={(r['race_id'],r['race_date'],r['source_url']) for r in csv.DictReader(f)}
 completed={}
 if done.exists():
  for line in done.read_text(encoding='utf-8').splitlines():
   x=json.loads(line);completed[x['context']['race_id']]=x
 pending=[x for x in sorted(items) if x[0] not in completed]
 with ThreadPoolExecutor(max_workers=a.workers) as ex,done.open('a',encoding='utf-8') as log:
  futures={ex.submit(one,x):x for x in pending}
  for i,f in enumerate(as_completed(futures),1):
   try:c,p,e=f.result();record={'context':c,'payouts':p,'errors':e}
   except Exception as exc:
    rid,date,url=futures[f];record={'context':{'race_id':rid,'race_date':date,'source_url':url,'data_status':'FAILED'},'payouts':[],'errors':[repr(exc)]}
   completed[record['context']['race_id']]=record;log.write(json.dumps(record,ensure_ascii=False)+'\n');log.flush()
   if i%100==0:print(f'enrichment {i}/{len(pending)}')
 contexts=[x['context'] for x in completed.values()];payouts=[p for x in completed.values() for p in x['payouts']]
 atomic(Path(f'data/race_context_{a.year}.csv'),contexts);atomic(Path(f'data/race_payouts_{a.year}.csv'),payouts)
 report={'races':len(items),'completed':len(contexts),'payout_rows':len(payouts),'failed':sum(x['context']['data_status']!='PASS_HTML' for x in completed.values())}
 Path(f'status/enrichment_{a.year}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report))
if __name__=='__main__':main()
