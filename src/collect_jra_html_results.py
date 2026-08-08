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
MONTH=re.compile(rf"pw01skl10{YEAR}(\d{{2}})/[A-F0-9]{{2}}")
DAY=re.compile(r"pw01srl\d+/[A-F0-9]{2}")
RACE=re.compile(r"pw01sde\d+/[A-F0-9]{2}")
META=re.compile(r"pw01sde10(?P<course>\d{2})(?P<year>\d{4})(?P<meeting>\d{2})(?P<day>\d{2})(?P<race>\d{2})(?P<date>\d{8})")
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
 race_name=""
 title=soup.title.get_text(" ",strip=True) if soup.title else ""
 h1=soup.find(["h1","h2"],string=re.compile("レース"))
 if h1:race_name=h1.get_text(" ",strip=True)
 surface="障害" if "障害" in text[:5000] else ("ダート" if "ダート" in text[:5000] else ("芝" if "芝" in text[:5000] else ""))
 distance=(re.search(r"(\d{3,4})\s*メートル",text[:5000]) or re.search(r"(\d{3,4})\s*[ｍm]",text[:5000]))
 rows=[]
 for _,r in table.iterrows():
  name=re.sub(r"\s+","",str(r.get("horse_name","")))
  if not name or name=="nan":continue
  row={k:("" if pd.isna(v) else str(v)) for k,v in r.items()}
  row.update({"race_id":cname.split("/")[0],"race_date":f'{meta["date"][:4]}-{meta["date"][4:6]}-{meta["date"][6:]}',
   "course":COURSES.get(meta["course"],meta["course"]),"meeting_no":meta["meeting"],"meeting_day":meta["day"],
   "race_no":meta["race"],"race_name":race_name or title,"surface":surface,
   "distance_m":distance.group(1) if distance else "","horse_name":name,"horse_id":links.get(name,""),
   "source_url":ENDPOINT+"?CNAME="+urllib.parse.quote(cname,safe=""),"data_status":"PASS_HTML"})
  rows.append(row)
 # Hard gates: unique starters and plausible structured values.
 names=[x["horse_name"] for x in rows];numbers=[x.get("horse_no","") for x in rows]
 errors=[]
 if not 3<=len(rows)<=18:errors.append("runner_count")
 if len(names)!=len(set(names)):errors.append("duplicate_name")
 if any(not re.fullmatch(r"\d{1,2}",str(x).replace(".0","")) for x in numbers):errors.append("horse_no")
 if not any(str(x.get("finish_position")) in ("1","1.0") for x in rows):errors.append("winner")
 if errors:
  for x in rows:x["data_status"]="QUARANTINED_HTML:"+",".join(errors)
 return cname,rows,errors

def atomic_csv(path,rows):
 fields=sorted(set().union(*(r.keys() for r in rows))) if rows else []
 tmp=path.with_suffix(".tmp")
 with tmp.open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
 tmp.replace(path)

def main():
 DATA.mkdir(exist_ok=True);STATUS.mkdir(exist_ok=True);CACHE.mkdir(parents=True,exist_ok=True)
 months,days,races=discover();all_rows=[];errors=[]
 with ThreadPoolExecutor(max_workers=4) as ex:
  futures={ex.submit(extract_race,c):c for c in races}
  for i,f in enumerate(as_completed(futures),1):
   try:
    _,rows,err=f.result();all_rows.extend(rows)
    if err:errors.append({"race":futures[f],"errors":err})
   except Exception as e:errors.append({"race":futures[f],"errors":[repr(e)]})
   if i%100==0:print(f"races {i}/{len(races)} rows {len(all_rows)} errors {len(errors)}")
 passed=[r for r in all_rows if r["data_status"]=="PASS_HTML"]
 atomic_csv(OUT,all_rows)
 horse_map={}
 for r in passed:
  h=horse_map.setdefault(r["horse_name"],{"horse_name":r["horse_name"],"horse_id":r["horse_id"],
   "sex_age":r.get("sex_age",""),"starts_2025":0,"first_race_date":r["race_date"],"last_race_date":r["race_date"]})
  h["starts_2025"]+=1;h["last_race_date"]=max(h["last_race_date"],r["race_date"])
  if not h["horse_id"] and r["horse_id"]:h["horse_id"]=r["horse_id"]
 atomic_csv(HORSES,sorted(horse_map.values(),key=lambda x:x["horse_name"]))
 state={"year":YEAR,"months":len(months),"meeting_days":len(days),"races_discovered":len(races),
  "rows_total":len(all_rows),"rows_passed":len(passed),"horses_linked":len(horse_map),"errors":errors,
  "status":"PASS" if len(passed)>30000 and len(horse_map)>7000 else "INCOMPLETE"}
 (STATUS/f"html_collection_{YEAR}.json").write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({k:v for k,v in state.items() if k!="errors"},ensure_ascii=False))

if __name__=="__main__":main()
