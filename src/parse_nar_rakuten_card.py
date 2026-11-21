#!/usr/bin/env python3
"""Parse published Rakuten NAR race card prior-run cells. Research only.

Never infer capture time from publication or assert a post-start fetch was sealed.
"""
import argparse,json,re
from pathlib import Path
from bs4 import BeautifulSoup

def parse(html):
    soup=BeautifulSoup(html,"lxml")
    names=["クラックオブドーン","ミラクルドリーム","ヒマワリクン","ビックス","ファストワン","ウォーターレモン","ユキノマリア","ストーミーデイ","マイネルフォーコン","ムサシフウジン","ブルグミューラー"]
    horses=[]
    for name in names:
        a=next((a for a in soup.select("span.mainHorse a") if a.get_text(strip=True)==name),None)
        if a is None:raise ValueError("missing horse row "+name)
        tr=a.find_parent("tr")
        if tr is None:raise ValueError("horse row missing "+name)
        history=[]
        for cell in tr.select("td.race"):
            first=cell.select_one(".firstInfo .place")
            match=re.search(r"(\d{2})\.(\d{2})\.(\d{2})",cell.get_text(" ",strip=True))
            distance=re.search(r"(\d{3,4})\s*右?\s*([ダ芝])",cell.get_text(" ",strip=True))
            if not (first and match and distance):continue
            date=f"20{match.group(1)}-{match.group(2)}-{match.group(3)}"
            finish=re.search(r"\d+",first.get_text(strip=True))
            if not finish:continue
            if date>="2026-11-21":raise ValueError("target result leakage")
            text=cell.get_text(" ",strip=True)
            corners=re.search(r"\b\d+-\d+(?:-\d+){1,3}\b",text)
            last3f=re.search(r"\b(\d{2}\.\d)\s+\d{3}k",text)
            history.append({"race_date":date,"finish_position":int(finish.group()),"surface":"ダート" if distance.group(2)=="ダ" else "芝","distance_m":int(distance.group(1)),"course":text.split(" ",1)[0],"corner_positions":corners.group() if corners else "","last3f":last3f.group(1) if last3f else None})
        if not history:
            print("HISTORY_MISSING",name,"race_cells",len(tr.select("td.race")),"sample",tr.get_text(" ",strip=True)[:1200])
        horses.append({"horse_name":name,"horse_id":a.get("href","").split("/")[-1],"recent_starts":history})
    return {"status":"POST_START_SOURCE_UNSEALED_RESEARCH_ONLY","horse_count":len(horses),"horses":horses}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--html",required=True);p.add_argument("--output",required=True);a=p.parse_args()
    result=parse(Path(a.html).read_text(encoding="utf-8"))
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":result["status"],"horse_count":result["horse_count"],"history_counts":[[x["horse_name"],len(x["recent_starts"])] for x in result["horses"]]},ensure_ascii=False))
