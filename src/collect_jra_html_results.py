#!/usr/bin/env python3
"""Collect structured JRA HTML results and horse IDs. PDF/OCR remains cross-check only."""
import csv, json, os, re, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import StringIO
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup

BASE="https://www.jra.go.jp"
ENDPOINT=BASE+"/JRADB/accessS.html"
YEAR=int(os.getenv("TARGET_YEAR","2025"))
START_CNAME=os.getenv("JRA_MONTH_SEED","pw01skl10202508/E1")
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
DATA=Path("data");STATUS=Path("status");CACHE=Path("cache/html")/str(YEAR)
OUT=DATA/f"race_results_html_{YEAR}.csv";HORSES=DATA/f"horse_ids_{YEAR}.csv"
PAYOUTS=DATA/f"race_payouts_{YEAR}.csv";CONTEXT=DATA/f"race_context_{YEAR}.csv"
MONTH=re.compile(rf"pw01skl10{YEAR}(\d{{2}})/[A-F0-9]{{2}}")
DAY=re.compile(r"pw01srl\d+/[A-F0-9]{2}")
RACE=re.compile(r"pw01sde\d+/[A-F0-9]{2}")
META=re.compile(r"pw01sde(?:10|01)(?P<course>\d{2})(?P<year>\d{4})(?P<meeting>\d{2})(?P<day>\d{2})(?P<race>\d{2})(?P<date>\d{8})")
COURSES={"01":"札幌","02":"函館","03":"福島","04":"新潟","05":"東京","06":"中山","07":"中京","08":"京都","09":"阪神","10":"小倉"}

def request(cname,post=False,retries=5):
 data=urllib.parse.urlencode({"cname":cname}).encode() if post else None
 url=ENDPOINT if post else ENDPOINT+"?CNAME="+urllib.parse.quote(cname,safe="")
 req=urllib.request.Request(url,data=data,headers={"User-Agent":UA,"Referer":ENDPOINT,
  "Content-Type":"application/x-www-form-urlencoded"})
 for attempt in range(retries):
  try:
   with urllib.request.urlopen(req,timeout=60) as r:raw=r.read()
   if len(raw)<70000:raise RuntimeError(f"short response {len(raw)}")
   return raw.decode("shift_jis","replace")
  except Exception:
   if attempt==retries-1:raise
   time.sleep(2**attempt)
 raise RuntimeError("unreachable")

def cnames(pattern,html):
 return list(dict.fromkeys(pattern.findall(html)))

def discover():
 months={START_CNAME};queue=[START_CNAME];days=set()
 while queue:
  cname=queue.pop(0);html=request(cname,post=True)
  days.update(cnames(DAY,html))
  for full in re.findall(rf"pw01skl10{YEAR}\d{{2}}/[A-F0-9]{{2}}",html):
   if full not in months:months.add(full);queue.append(full)
  if len(months)>=12 and not queue:break
 if len(months)!=12:raise RuntimeError(f"month discovery failed: {len(months)}")
 races=set()
 for i,cname in enumerate(sorted(days)):
  html=request(cname,post=True);races.update(cnames(RACE,html))
  if i%20==0:print(f"days {i+1}/{len(days)} races {len(races)}")
 if len(races)<3000:raise RuntimeError(f"race discovery quality gate: {len(races)}")
 return sorted(months),sorted(days),sorted(races)

def flat_col(x):
 if isinstance(x,tuple):return " ".join(str(v) for v in x if str(v)!="nan").strip()
 return str(x).strip()

def horse_links(soup):
 out={}
 for a in soup.select('a[href*="accessU.html"][href*="CNAME="]'):
  name=re.sub(r"\s+","",a.get_text())
  m=re.search(r"CNAME=([^&]+)",a.get("href",""))
  if name and m:out[name]=urllib.parse.unquote(m.group(1))
 return out

def extract_race(cname):
 m=META.search(cname)
 if not m:raise RuntimeError("bad race cname "+cname)
 cache=CACHE/(cname.replace("/","_")+".html")
 if cache.exists() and cache.stat().st_size>70000:html=cache.read_text(encoding="utf-8")
 else:
  html=request(cname);cache.parent.mkdir(parents=True,exist_ok=True);cache.write_text(html,encoding="utf-8")
 soup=BeautifulSoup(html,"html.parser");links=horse_links(soup)
 tables=pd.read_html(StringIO(html))
 if not tables:raise RuntimeError("no result table")
 table=tables[0];table.columns=[flat_col(x) for x in table.columns]
 rename={"馬 番":"horse_no","馬番":"horse_no","馬名":"horse_name","性齢":"sex_age","負担 重量":"carried_weight",
 "負担重量":"carried_weight","騎手名":"jockey","タイム":"time","着差":"margin","コーナー 通過順位":"corner_positions",
 "コーナー通過順位":"corner_positions","推定上り":"last3f","馬体重 （増減）":"body_weight_delta",
 "馬体重（増減）":"body_weight_delta","調教師名":"trainer","単勝 人気":"popularity","単勝人気":"popularity",
 "着順":"finish_position","Rt":"rating"}
 table=table.rename(columns={k:v for k,v in rename.items() if k in table.columns})
 meta=m.groupdict();text=soup.get_text(" ",strip=True)
 title=soup.title.get_text(" ",strip=True) if soup.title else ""
 result_table_tag=next((t for t in soup.find_all("table") if "馬名" in t.get_text() and "着順" in t.get_text()),None)
 race_name_tag=soup.select_one("#race_result .race_name") or soup.select_one("span.race_name")
 race_name=race_name_tag.get_text(" ",strip=True) if race_name_tag else ""
 weather_tag=soup.select_one("#race_result .weather .txt")
 condition_tag=soup.select_one("#race_result .baba .turf .txt") or soup.select_one("#race_result .baba .dirt .txt")
 class_tag=soup.select_one("#race_result .race_title .class")
 category_tag=soup.select_one("#race_result .race_title .category")
 rule_tag=soup.select_one("#race_result .race_title .rule")
 weight_rule_tag=soup.select_one("#race_result .race_title .weight")
 start_time_tag=soup.select_one("#race_result .date_line .time strong")
 distance_match=(re.search(r"コース[：:]\s*(\d{1,2}(?:,\d{3})|\d{3,4})\s*メートル",text) or
  re.search(r"(?<![\d,])(\d{1,2}(?:,\d{3})|\d{3,4})\s*[ｍm]",text[:7000]))
 distance_m=distance_match.group(1).replace(",","") if distance_match else ""
 course_window=text[max(0,distance_match.start()-200):distance_match.end()+120] if distance_match else text[:5000]
 surface="障害" if "障害" in race_name else ("ダート" if "ダート" in course_window else ("芝" if "芝" in course_window else ""))
 rows=[]
 for _,r in table.iterrows():
  name=re.sub(r"\s+","",str(r.get("horse_name","")))
  if not name or name=="nan":continue
  row={k:("" if pd.isna(v) else str(v)) for k,v in r.items()}
  row.update({"race_id":cname.split("/")[0],"race_date":f'{meta["date"][:4]}-{meta["date"][4:6]}-{meta["date"][6:]}',
   "course":COURSES.get(meta["course"],meta["course"]),"meeting_no":meta["meeting"],"meeting_day":meta["day"],
   "race_no":meta["race"],"race_name":race_name,"surface":surface,
   "weather":weather_tag.get_text(" ",strip=True) if weather_tag else "",
   "track_condition":condition_tag.get_text(" ",strip=True) if condition_tag else "",
   "race_class":class_tag.get_text(" ",strip=True) if class_tag else "",
   "race_category":category_tag.get_text(" ",strip=True) if category_tag else "",
   "race_rule":rule_tag.get_text(" ",strip=True) if rule_tag else "",
   "weight_rule":weight_rule_tag.get_text(" ",strip=True) if weight_rule_tag else "",
   "scheduled_start":start_time_tag.get_text(" ",strip=True) if start_time_tag else "",
   "distance_m":distance_m,"horse_name":name,"horse_id":links.get(name,""),
   "source_url":ENDPOINT+"?CNAME="+urllib.parse.quote(cname,safe=""),"data_status":"PASS_HTML"})
  rows.append(row)
 payout_rows=[]
 for item in soup.select("#race_result .refund_area li"):
  label=item.find("dt");bet_type=label.get_text(" ",strip=True) if label else ""
  for line in item.select(".line"):
   selection=line.select_one(".num");yen=line.select_one(".yen");pop=line.select_one(".pop")
   selection_text=selection.get_text(" ",strip=True) if selection else ""
   yen_text=re.sub(r"\D","",yen.get_text(" ",strip=True) if yen else "")
   if bet_type and selection_text and yen_text:
    payout_rows.append({"race_id":cname.split("/")[0],"race_date":f'{meta["date"][:4]}-{meta["date"][4:6]}-{meta["date"][6:]}',
     "bet_type":bet_type,"winning_selection":selection_text,"payout_per_100_yen":yen_text,
     "payout_popularity":re.sub(r"\D","",pop.get_text(" ",strip=True)) if pop else "",
     "source_url":ENDPOINT+"?CNAME="+urllib.parse.quote(cname,safe=""),"data_status":"PASS_HTML"})
 context={"race_id":cname.split("/")[0],"race_date":f'{meta["date"][:4]}-{meta["date"][4:6]}-{meta["date"][6:]}',
  "course":COURSES.get(meta["course"],meta["course"]),"race_no":meta["race"],"race_name":race_name,
  "weather":weather_tag.get_text(" ",strip=True) if weather_tag else "",
  "track_condition":condition_tag.get_text(" ",strip=True) if condition_tag else "",
  "race_class":class_tag.get_text(" ",strip=True) if class_tag else "",
  "race_category":category_tag.get_text(" ",strip=True) if category_tag else "",
  "race_rule":rule_tag.get_text(" ",strip=True) if rule_tag else "",
  "weight_rule":weight_rule_tag.get_text(" ",strip=True) if weight_rule_tag else "",
  "scheduled_start":start_time_tag.get_text(" ",strip=True) if start_time_tag else "",
  "surface":surface,"distance_m":distance_m,"field_size":len(rows),
  "source_url":ENDPOINT+"?CNAME="+urllib.parse.quote(cname,safe=""),"data_status":"PASS_HTML"}
 # Hard gates: unique starters and plausible structured values.
 names=[x["horse_name"] for x in rows];numbers=[x.get("horse_no","") for x in rows]
 errors=[]
 if not 3<=len(rows)<=18:errors.append("runner_count")
 if len(names)!=len(set(names)):errors.append("duplicate_name")
 if any(not re.fullmatch(r"\d{1,2}",str(x).replace(".0","")) for x in numbers):errors.append("horse_no")
 if not any(str(x.get("finish_position")) in ("1","1.0") for x in rows):errors.append("winner")
 if not distance_m or not distance_m.isdigit() or not 1000<=int(distance_m)<=5000:errors.append("distance")
 if not race_name or race_name in ("レース結果","レース結果 JRA","レース結果　JRA"):errors.append("race_name")
 if not weather_tag:errors.append("weather")
 if not condition_tag:errors.append("track_condition")
 if not class_tag:errors.append("race_class")
 if not start_time_tag:errors.append("scheduled_start")
 if surface not in ("芝","ダート","障害"):errors.append("surface")
 if any(not x.get("horse_id") for x in rows):errors.append("missing_horse_id")
 if not payout_rows:errors.append("payouts")
 if errors:
  for x in rows:x["data_status"]="QUARANTINED_HTML:"+",".join(errors)
  for x in payout_rows:x["data_status"]="QUARANTINED_HTML:"+",".join(errors)
  context["data_status"]="QUARANTINED_HTML:"+",".join(errors)
 return cname,rows,payout_rows,context,errors

def atomic_csv(path,rows):
 fields=sorted(set().union(*(r.keys() for r in rows))) if rows else []
 tmp=path.with_suffix(".tmp")
 with tmp.open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
 tmp.replace(path)

def main():
 DATA.mkdir(exist_ok=True);STATUS.mkdir(exist_ok=True);CACHE.mkdir(parents=True,exist_ok=True)
 months,days,races=discover();all_rows=[];all_payouts=[];all_context=[];errors=[]
 with ThreadPoolExecutor(max_workers=4) as ex:
  futures={ex.submit(extract_race,c):c for c in races}
  for i,f in enumerate(as_completed(futures),1):
   try:
    _,rows,payouts,context,err=f.result();all_rows.extend(rows);all_payouts.extend(payouts);all_context.append(context)
    if err:errors.append({"race":futures[f],"errors":err})
   except Exception as e:errors.append({"race":futures[f],"errors":[repr(e)]})
   if i%100==0:print(f"races {i}/{len(races)} rows {len(all_rows)} errors {len(errors)}")
 passed=[r for r in all_rows if r["data_status"]=="PASS_HTML"]
 atomic_csv(OUT,all_rows)
 atomic_csv(PAYOUTS,all_payouts)
 atomic_csv(CONTEXT,all_context)
 horse_map={}
 for r in passed:
  h=horse_map.setdefault(r["horse_name"],{"horse_name":r["horse_name"],"horse_id":r["horse_id"],
   "sex_age":r.get("sex_age",""),"starts_2025":0,"first_race_date":r["race_date"],"last_race_date":r["race_date"]})
  h["starts_2025"]+=1;h["last_race_date"]=max(h["last_race_date"],r["race_date"])
  if not h["horse_id"] and r["horse_id"]:h["horse_id"]=r["horse_id"]
 atomic_csv(HORSES,sorted(horse_map.values(),key=lambda x:x["horse_name"]))
 passed_races={r["race_id"] for r in passed}
 invalid_distances=sum(not str(r.get("distance_m","")).isdigit() or not 1000<=int(r["distance_m"])<=5000 for r in passed)
 missing_horse_ids=sum(not r.get("horse_id") for r in passed)
 bad_race_names=sum(not r.get("race_name") or r["race_name"] in ("レース結果","レース結果 JRA","レース結果　JRA") for r in passed)
 complete=(len(months)==12 and len(days)>=288 and len(races)>=3455 and len(passed_races)==len(races)
  and len(passed)==len(all_rows) and len(passed)>30000 and len(horse_map)>7000 and not errors
  and invalid_distances==0 and missing_horse_ids==0 and bad_race_names==0)
 state={"year":YEAR,"months":len(months),"meeting_days":len(days),"races_discovered":len(races),
  "races_passed":len(passed_races),"rows_total":len(all_rows),"rows_passed":len(passed),
  "horses_linked":len(horse_map),"invalid_distances":invalid_distances,
  "missing_horse_ids":missing_horse_ids,"bad_race_names":bad_race_names,"errors":errors,
  "payout_rows":len(all_payouts),"context_rows":len(all_context),
  "status":"PASS" if complete else "INCOMPLETE"}
 (STATUS/f"html_collection_{YEAR}.json").write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({k:v for k,v in state.items() if k!="errors"},ensure_ascii=False))
 if state["status"]!="PASS":raise SystemExit("HTML collection quality gate failed")

if __name__=="__main__":main()
