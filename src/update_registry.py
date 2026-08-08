#!/usr/bin/env python3
import csv, json, os, re, subprocess, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

YEAR=int(os.getenv("TARGET_YEAR","2025"))
MODE=os.getenv("UPDATE_MODE","all")
INDEX=f"https://www.jra.go.jp/datafile/seiseki/report/{YEAR}.html"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
CACHE=Path("cache")/str(YEAR); PDF=CACHE/"pdf"; TXT=CACHE/"txt"
DATA=Path("data"); STATUS=Path("status"); OUT=DATA/f"horse_master_{YEAR}.csv"; MASTER=DATA/"horse_master_all.csv"
ROW=re.compile(r"^\\s*(.{2,120}?)\\s+(牡|牝|騸)\\s+(?:黒鹿|青鹿|栃栗|栗|鹿|芦|青|白)(?:\\s|$)")
KATA=re.compile(r"^[ァ-ヶー・ヴヷヸヹヺ]{2,12}$")

def select_result_urls(raw):
 soup=BeautifulSoup(raw,"html.parser",from_encoding="shift_jis")
 scope=os.getenv("UPDATE_SCOPE","full_year")
 if scope!="previous_weekend":
  return list(dict.fromkeys(urljoin(INDEX,a.get("href")) for a in soup.select("a[href$='.pdf']") if f"/report/{YEAR}/" in urljoin(INDEX,a.get("href")) and "-hyo-" not in a.get("href")))
 jst_today=(datetime.now(timezone.utc)+timedelta(hours=9)).date()
 end=jst_today-timedelta(days=jst_today.weekday()+1)
 start=end-timedelta(days=1)
 current=None;urls=[]
 for node in soup.find_all(["h2","h3","a"]):
  if node.name=="h2" and "各競馬場" in node.get_text():break
  if node.name=="h3":
   m=re.search(r"(\\d{1,2})月(\\d{1,2})日",node.get_text())
   current=date(YEAR,int(m.group(1)),int(m.group(2))) if m else None
  elif current and start<=current<=end:
   href=node.get("href","")
   if href.endswith(".pdf") and "-hyo-" not in href:urls.append(urljoin(INDEX,href))
 if not urls:raise RuntimeError(f"No JRA result PDFs for previous weekend {start}..{end}")
 print(f"weekly window: {start}..{end}; {len(urls)} result PDFs")
 return list(dict.fromkeys(urls))

class Links(HTMLParser):
 def __init__(self): super().__init__(); self.items=[]
 def handle_starttag(self,tag,attrs):
  href=dict(attrs).get("href","")
  if tag=="a" and href.lower().endswith(".pdf") and f"/report/{YEAR}/" in href:self.items.append(urljoin(INDEX,href))

def fetch(url,dest=None):
 req=urllib.request.Request(url,headers={"User-Agent":UA,"Referer":"https://www.jra.go.jp/","Accept-Language":"ja,en;q=0.8"})
 with urllib.request.urlopen(req,timeout=90) as r:data=r.read()
 if dest:dest.write_bytes(data)
 return data

def get_text(url):
 name=url.rsplit("/",1)[-1]; pdf=PDF/name; txt=TXT/name.replace(".pdf",".txt")
 if not pdf.exists() or pdf.stat().st_size<10000:
  for n in range(3):
   try:fetch(url,pdf);break
   except Exception:
    if n==2:raise
    time.sleep(3*(n+1))
 if not txt.exists() or txt.stat().st_size==0:
  subprocess.run(["pdftotext","-layout",str(pdf),str(txt)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 return name,txt

def clean(raw):
 parts=[x for x in re.split(r"\\s{2,}",raw.strip()) if x]
 x=re.sub(r"\\s+","",parts[-1] if parts else raw)
 x=re.sub(r"^[!#%&()*+,.0-9:;<>?@A-Z\\[\\]^_`a-z{|}~（）〔〕・]+","",x)
 return x if KATA.fullmatch(x) else None

def parse(source,txt):
 for line in txt.read_text(encoding="utf-8",errors="ignore").splitlines():
  m=ROW.search(line)
  if m:
   name=clean(m.group(1))
   if name:yield name,m.group(2),source

def sync_sheet(rows):
 raw=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON","").strip()
 if not raw:return "SKIPPED_NO_SECRET"
 import gspread
 from google.oauth2.service_account import Credentials
 cfg=json.loads(Path("config.json").read_text())
 creds=Credentials.from_service_account_info(json.loads(raw),scopes=["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"])
 ws=gspread.authorize(creds).open_by_key(cfg["spreadsheet_id"]).worksheet(cfg["registry_sheet"])
 values=ws.get_all_values()
 required=["queue_no","horse_id","horse_name","sex","first_seen_pdf","first_seen_year","last_seen_year","active_years","profile_status","history_status","source_url"]
 if not values:
  ws.append_row(required,value_input_option="RAW");values=[required]
 headers=values[0]
 missing=[h for h in required if h not in headers]
 if missing:
  headers=headers+missing
  ws.update("1:1",[headers],value_input_option="RAW")
 col={h:headers.index(h) for h in required}
 existing={r[col["horse_name"]]:i+2 for i,r in enumerate(values[1:]) if len(r)>col["horse_name"] and r[col["horse_name"]]}
 append=[]
 for item in rows:
  name=item["horse_name"]
  if name in existing:
   row=existing[name]
   ws.update_cell(row,col["sex"]+1,item["sex"])
   old=values[row-1] if row-1<len(values) else []
   first=(old[col["first_seen_year"]] if len(old)>col["first_seen_year"] else "") or item["first_seen_year"]
   years=(old[col["active_years"]] if len(old)>col["active_years"] else "")
   years=",".join(sorted(set(filter(None,years.split(",")+[str(YEAR)]))))
   ws.update_cell(row,col["first_seen_year"]+1,first)
   ws.update_cell(row,col["last_seen_year"]+1,str(YEAR))
   ws.update_cell(row,col["active_years"]+1,years)
  else:
   new=[""]*len(headers)
   new[col["queue_no"]]=str(len(values)+len(append))
   new[col["horse_name"]]=name;new[col["sex"]]=item["sex"];new[col["first_seen_pdf"]]=item["first_seen_pdf"]
   new[col["first_seen_year"]]=item["first_seen_year"];new[col["last_seen_year"]]=item["last_seen_year"];new[col["active_years"]]=item["active_years"]
   new[col["profile_status"]]="PENDING_ID_RESOLUTION";new[col["history_status"]]="PENDING";new[col["source_url"]]=INDEX
   append.append(new)
 if append:ws.append_rows(append,value_input_option="RAW")
 return f"UPSERTED_EXISTING_{len(rows)-len(append)}_ADDED_{len(append)}"

def main():
 for p in (PDF,TXT,DATA,STATUS):p.mkdir(parents=True,exist_ok=True)
 if MODE not in ("registry","all"):
  (STATUS/"checkpoint.json").write_text(json.dumps({"mode":MODE,"status":"QUEUED_ENRICHMENT_MODULE"},ensure_ascii=False,indent=2));return
 urls=select_result_urls(fetch(INDEX));unique={};errors=[]
 for start in range(0,len(urls),48):
  batch=urls[start:start+48];results=[]
  with ThreadPoolExecutor(max_workers=12) as ex:
   futures={ex.submit(get_text,u):u for u in batch}
   for f in as_completed(futures):
    try:results.append(f.result())
    except Exception as e:errors.append({"url":futures[f],"error":repr(e)})
  for source,txt in sorted(results):
   for name,sex,src in parse(source,txt):unique.setdefault(name,{"horse_name":name,"sex":sex,"first_seen_pdf":src,"first_seen_year":str(YEAR),"last_seen_year":str(YEAR),"active_years":str(YEAR)})
  print(f"{min(start+48,len(urls))}/{len(urls)} PDFs; {len(unique)} horses")
 if len(unique)<1000:raise RuntimeError(f"Quality gate failed: only {len(unique)} horses")
 rows=list(unique.values())
 for i,r in enumerate(rows,1):r["queue_no"]=i
 fields=["queue_no","horse_name","sex","first_seen_pdf","first_seen_year","last_seen_year","active_years"];tmp=OUT.with_suffix(".tmp")
 with tmp.open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 tmp.replace(OUT)
 cumulative={}
 if MASTER.exists():
  with MASTER.open(encoding="utf-8-sig",newline="") as f:
   for old in csv.DictReader(f):
    if old.get("horse_name"):cumulative[old["horse_name"]]=old
 for item in rows:
  name=item["horse_name"]
  if name in cumulative:
   old=cumulative[name];years=set(filter(None,old.get("active_years","").split(",")));years.add(str(YEAR))
   old["sex"]=item["sex"];old["last_seen_year"]=str(YEAR);old["active_years"]=",".join(sorted(years))
   old["first_seen_year"]=old.get("first_seen_year") or str(YEAR);old["first_seen_pdf"]=old.get("first_seen_pdf") or item["first_seen_pdf"]
  else:cumulative[name]=dict(item)
 master_rows=sorted(cumulative.values(),key=lambda x:(int(x.get("first_seen_year") or YEAR),x["horse_name"]))
 for i,item in enumerate(master_rows,1):item["queue_no"]=i
 master_tmp=MASTER.with_suffix(".tmp")
 with master_tmp.open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(master_rows)
 master_tmp.replace(MASTER);sheet=sync_sheet(rows)
 state={"year":YEAR,"mode":MODE,"pdf_total":len(urls),"horse_total":len(rows),"cumulative_horse_total":len(master_rows),"errors":errors,"sheet":sheet,"completed_at":datetime.now(timezone.utc).isoformat()}
 (STATUS/"checkpoint.json").write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(state,ensure_ascii=False))

if __name__=="__main__":main()
