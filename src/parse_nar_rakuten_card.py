#!/usr/bin/env python3
"""Parse published Rakuten NAR race card prior-run cells. Research only.

Never infer capture time from publication or assert a post-start fetch was sealed.
"""
import argparse,json,re
from datetime import date
from pathlib import Path
from bs4 import BeautifulSoup

def parse(html, target_date):
    """Only accept completed starts strictly before the requested race date."""
    try:
        cutoff = date.fromisoformat(target_date)
    except (TypeError, ValueError) as exc:
        raise ValueError('valid target_date YYYY-MM-DD required') from exc
    if cutoff.isoformat() != target_date:
        raise ValueError('canonical target_date YYYY-MM-DD required')
    soup=BeautifulSoup(html,"lxml")
    anchors=soup.select("span.mainHorse a")
    if not anchors:raise ValueError("no horses found in race-card body")
    horses=[]
    seen_rows=set()
    seen_ids=set()
    for a in anchors:
        name=a.get_text(strip=True)
        horse_id=a.get("href","").rstrip("/").split("/")[-1]
        if not name or not horse_id:raise ValueError("missing horse identity")
        tr=a.find_parent("tr")
        if tr is None:raise ValueError("horse row missing "+name)
        if id(tr) in seen_rows or horse_id in seen_ids:
            raise ValueError("duplicate horse row or identity "+name)
        seen_rows.add(id(tr))
        seen_ids.add(horse_id)
        history=[]
        for cell in tr.select("td.race"):
            first=cell.select_one(".firstInfo .place")
            match=re.search(r"(\d{2})\.(\d{2})\.(\d{2})",cell.get_text(" ",strip=True))
            distance=re.search(r"(\d{3,4})\s*[左右直]?\s*([ダ芝])",cell.get_text(" ",strip=True))
            if not (first and match and distance):continue
            start_date=f"20{match.group(1)}-{match.group(2)}-{match.group(3)}"
            try:
                start_day=date.fromisoformat(start_date)
            except ValueError as exc:
                raise ValueError(f"invalid historical race date {start_date}") from exc
            finish=re.fullmatch(r"([1-9][0-9]*)\s*着?",first.get_text(" ",strip=True))
            if not finish:continue
            if start_day >= cutoff:raise ValueError("target result leakage")
            text=cell.get_text(" ",strip=True)
            corners=re.search(r"\b\d+-\d+(?:-\d+){1,3}\b",text)
            last3f=re.search(r"\b(\d{2}\.\d)\s+\d{3}k",text)
            history.append({"race_date":start_date,"finish_position":int(finish.group(1)),"surface":"ダート" if distance.group(2)=="ダ" else "芝","distance_m":int(distance.group(1)),"course":text.split(" ",1)[0],"corner_positions":corners.group() if corners else "","last3f":last3f.group(1) if last3f else None})
        if not history:
            print("HISTORY_MISSING",name,"race_cells",len(tr.select("td.race")),"sample",tr.get_text(" ",strip=True)[:1200])
        horses.append({"horse_name":name,"horse_id":horse_id,"recent_starts":history})
    return {"status":"UNSEALED_RESEARCH_ONLY","horse_count":len(horses),"horses":horses}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--html",required=True);p.add_argument("--output",required=True);p.add_argument("--target-date",required=True,help="YYYY-MM-DD requested race date");a=p.parse_args()
    result=parse(Path(a.html).read_text(encoding="utf-8"), a.target_date)
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":result["status"],"horse_count":result["horse_count"],"history_counts":[[x["horse_name"],len(x["recent_starts"])] for x in result["horses"]]},ensure_ascii=False))
