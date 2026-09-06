#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
TARGET = os.environ.get("TARGET_DATE", "").strip()
if not TARGET:
    raise SystemExit("TARGET_DATE is required; post-meeting workflow supplies each completed date")
CHAMPION = Path(f"docs/data/live_predictions_champion_{TARGET}.json")
CHALLENGER = Path(f"docs/data/prediction-archive-{TARGET}.json")
RESULTS = Path("data/race_results_html_2026.csv")
PAYOUTS = Path("data/race_payouts_2026.csv")
CONTEXT = Path("data/race_context_2026.csv")
OUT = Path(f"docs/data/erp-report-{TARGET}.json")
LOG = Path("docs/data/erp-report-log.json")
LATEST = Path("docs/data/erp-report-latest.json")


def iv(v):
    try: return int(float(str(v)))
    except Exception: return None


def key(date, track, race_no):
    return str(date or ""), str(track or "").strip().replace("競馬場", ""), iv(race_no)


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def combo(values):
    return "-".join(map(str, sorted(int(x) for x in values)))


def main():
    if not CHAMPION.exists() or not CHALLENGER.exists():
        print(json.dumps({"status":"WAITING_FOR_PREDICTION_ARCHIVES","date":TARGET}, ensure_ascii=False)); return

    champion_doc=json.loads(CHAMPION.read_text(encoding="utf-8"))
    required_races=int(champion_doc.get("sealed_race_count") or len(champion_doc.get("races") or []))+int(champion_doc.get("pending_race_count") or len(champion_doc.get("pending") or []))
    top3 = defaultdict(dict)
    for r in rows(RESULTS):
        k = key(r.get("race_date"), r.get("course"), r.get("race_no"))
        finish, horse_no = iv(r.get("finish_position")), iv(r.get("horse_no"))
        if k[0] == TARGET and finish in (1,2,3) and horse_no is not None:
            top3[k][finish] = horse_no
    complete = {k:[v[1],v[2],v[3]] for k,v in top3.items() if set(v)=={1,2,3}}
    if len(complete) < required_races:
        print(json.dumps({"status":"WAITING_FOR_ALL_RESULTS","date":TARGET,"complete_races":len(complete),"required_races":required_races}, ensure_ascii=False)); return

    context_by = {key(x.get("race_date"),x.get("course"),x.get("race_no")):x for x in rows(CONTEXT)}
    payout_by_id = {}
    for x in rows(PAYOUTS):
        if str(x.get("bet_type")) in ("3連複","三連複"):
            payout_by_id[str(x.get("race_id") or "")] = iv(x.get("payout_per_100_yen")) or 0

    docs = {
        "旧型": champion_doc,
        "新型": json.loads(CHALLENGER.read_text(encoding="utf-8")),
    }
    race_maps = {name:{key(r.get("date"),r.get("track"),r.get("race_no")):r for r in d.get("races") or []} for name,d in docs.items()}

    def score(name):
        out=[]
        for k,p in sorted(race_maps[name].items()):
            if k not in complete: continue
            a=p.get("analysis") or {}; axis=str((a.get("axis") or {}).get("horse_no") or "")
            actual=[str(x) for x in complete[k]]; actual_combo=combo(actual)
            tickets=[str(x) for x in a.get("trio_tickets") or []]
            bought=str(a.get("pre_market_decision") or "PASS")!="PASS" and bool(tickets)
            hit=actual_combo in tickets
            rid=str((context_by.get(k) or {}).get("race_id") or "")
            payout=payout_by_id.get(rid,0)
            out.append({"track":k[1],"race_no":k[2],"race_name":p.get("race_name"),"axis_horse_no":axis,"axis_top3":axis in actual,"decision":a.get("pre_market_decision"),"ticket_count":len(tickets),"trio_hit":hit,"actual_top3":actual,"winning_trio":actual_combo,"stake_yen":100*len(tickets) if bought else 0,"return_yen":payout if hit else 0})
        stake=sum(x["stake_yen"] for x in out); ret=sum(x["return_yen"] for x in out)
        return out,{"scored_races":len(out),"axis_top3":sum(x["axis_top3"] for x in out),"axis_top3_rate_pct":round(sum(x["axis_top3"] for x in out)/len(out)*100,2) if out else 0,"trio_hits":sum(x["trio_hit"] for x in out),"stake_yen":stake,"return_yen":ret,"profit_yen":ret-stake,"roi_pct":round(ret/stake*100,2) if stake else 0}

    old_rows,old=score("旧型"); new_rows,new=score("新型")
    old_by={(x["track"],x["race_no"]):x for x in old_rows}; new_by={(x["track"],x["race_no"]):x for x in new_rows}
    details=[]
    for rk in sorted(set(old_by)|set(new_by)):
        o,n=old_by.get(rk,{}),new_by.get(rk,{})
        details.append({"track":rk[0],"race_no":rk[1],"race_name":n.get("race_name") or o.get("race_name"),"old_axis":o.get("axis_horse_no"),"new_axis":n.get("axis_horse_no"),"axis_changed":o.get("axis_horse_no")!=n.get("axis_horse_no"),"old_axis_top3":o.get("axis_top3"),"new_axis_top3":n.get("axis_top3"),"old_trio_hit":o.get("trio_hit"),"new_trio_hit":n.get("trio_hit"),"actual_top3":n.get("actual_top3") or o.get("actual_top3")})

    axis_delta=new["axis_top3_rate_pct"]-old["axis_top3_rate_pct"]; hit_delta=new["trio_hits"]-old["trio_hits"]; roi_delta=new["roi_pct"]-old["roi_pct"]
    report={"schema_version":1,"status":"COMPLETED","title":f"{TARGET} 新型・旧型 結果比較","generated_at":datetime.now(JST).isoformat(),"trigger":{"owner":"ERP_WORKFLOW","condition":"JRA公式36レースの1〜3着確定","scheduled_runs":"土日16:45/19:30/21:30 JST","gpt_scheduler_used":False},"report_content":{"request":"9/6全レース終了時に、新型と旧型の結果を同じ公式結果で詳細比較し、ERPへ依頼内容・結果・考察を掲載する。","result":f"旧型の軸3着内率{old['axis_top3_rate_pct']}%、新型{new['axis_top3_rate_pct']}%（差{axis_delta:+.2f}pt）。三連複的中は旧型{old['trio_hits']}件、新型{new['trio_hits']}件（差{hit_delta:+d}件）。ROI差は{roi_delta:+.2f}pt。","consideration":("新型は旧型を上回った。変更レースだけでなく全対象の軸残存・買い目変換・ROIを分離して次回昇格判断へ使う。" if axis_delta>0 and hit_delta>=0 else "単開催だけでは昇格させない。軸残存、三連複変換、ROIのどこで差が出たかをレース別明細で確認し、次の独立開催へ継続する。")},"comparison":{"old":old,"new":new,"delta":{"axis_top3_rate_pt":round(axis_delta,2),"trio_hits":hit_delta,"roi_pt":round(roi_delta,2)}},"race_details":details,"sources":{"old_prediction":str(CHAMPION),"new_prediction":str(CHALLENGER),"results":"JRA_OFFICIAL_RESULTS_DB","erp_and_public_same_prediction_source":True}}
    report_text=json.dumps(report,ensure_ascii=False,indent=2)
    OUT.write_text(report_text,encoding="utf-8")
    LATEST.write_text(report_text,encoding="utf-8")
    log={"schema_version":1,"updated_at":report["generated_at"],"reports":[]}
    if LOG.exists():
        try: log=json.loads(LOG.read_text(encoding="utf-8"))
        except Exception: pass
    entry={"id":f"{TARGET}-model-comparison","parent_id":None,"date":TARGET,"title":"新型・旧型 結果比較","status":"COMPLETED","request":report["report_content"]["request"],"result":report["report_content"]["result"],"consideration":report["report_content"]["consideration"],"report_file":OUT.name}
    log["reports"]=[entry]+[x for x in log.get("reports",[]) if x.get("id")!=entry["id"]]
    log["updated_at"]=report["generated_at"]
    LOG.write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":"COMPLETED","output":str(OUT),"old":old,"new":new},ensure_ascii=False))


if __name__ == "__main__": main()
