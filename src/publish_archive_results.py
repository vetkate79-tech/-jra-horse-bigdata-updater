#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo("Asia/Tokyo")
target=os.getenv("TARGET_DATE") or datetime.now(TZ).date().isoformat()
year=target[:4]

RES=Path(f"data/race_results_html_{year}.csv")
PAY=Path(f"data/race_payouts_{year}.csv")
LIVE=Path("docs/data/live_predictions_sealed.json")
RESULT_OUT=Path(f"docs/data/today-results-{target}.json")
PRED_ARCHIVE=Path(f"docs/data/prediction-archive-{target}.json")
REPLAY_OUT=Path(f"docs/data/replay-{target}.json")

def integer(v):
    try:
        return int(float(str(v).strip()))
    except Exception:
        return None

def combo(values):
    return "-".join(map(str,sorted(int(x) for x in values)))

def read_csv(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def load_json(path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))

def target_live_snapshot(live):
    races=[p for p in (live.get("races") or []) if p.get("date")==target]
    pending=[p for p in (live.get("pending") or []) if p.get("date")==target]
    return races,pending

def load_or_create_immutable_archive(live):
    if PRED_ARCHIVE.exists():
        archive=load_json(PRED_ARCHIVE)
        if archive.get("mode")!="IMMUTABLE_PREDICTION_ARCHIVE":
            raise RuntimeError(f"{PRED_ARCHIVE} is not an immutable prediction archive")
        if archive.get("date")!=target:
            raise RuntimeError(f"{PRED_ARCHIVE} date mismatch: {archive.get('date')} != {target}")
        if archive.get("odds_popularity_used") is True or archive.get("results_used") is True:
            raise RuntimeError(f"{PRED_ARCHIVE} violates the pre-race firewall")
        return archive,False

    races,pending=target_live_snapshot(live)
    archive={
        "schema_version":live.get("schema_version"),
        "mode":"IMMUTABLE_PREDICTION_ARCHIVE",
        "source_mode":live.get("mode"),
        "model_version":live.get("model_version"),
        "sealed_generated_at":live.get("generated_at"),
        "prediction_hash_sha256":live.get("prediction_hash_sha256"),
        "date":target,
        "odds_popularity_used":live.get("odds_popularity_used",False),
        "results_used":live.get("results_used",False),
        "races":races,
        "pending":pending,
    }
    PRED_ARCHIVE.parent.mkdir(parents=True,exist_ok=True)
    PRED_ARCHIVE.write_text(json.dumps(archive,ensure_ascii=False,indent=2),encoding="utf-8")
    return archive,True

def main():
    results=[r for r in read_csv(RES) if str(r.get("race_date"))==target]
    payouts=[r for r in read_csv(PAY) if str(r.get("race_date"))==target]
    live=load_json(LIVE,{"races":[],"pending":[]})

    archive,archive_created=load_or_create_immutable_archive(live)
    archived_races=archive.get("races") or []
    archived_pending=archive.get("pending") or []
    pred_by={
        (str(p.get("track","")).replace("競馬場",""),integer(p.get("race_no"))):p
        for p in archived_races
    }

    by_race=defaultdict(list)
    for row in results:
        by_race[(str(row.get("course","")).replace("競馬場",""),integer(row.get("race_no")))].append(row)

    payout_by_race={}
    for row in payouts:
        bet=str(row.get("bet_type",""))
        if "三連複" in bet or "3連複" in bet:
            payout_by_race[str(row.get("race_id",""))]=row.get("payout_per_100_yen") or ""

    result_rows=[]
    for key,rows in sorted(by_race.items(),key=lambda item:(item[0][0],item[0][1] or 99)):
        top=sorted(
            [x for x in rows if integer(x.get("finish_position")) in (1,2,3)],
            key=lambda x:integer(x.get("finish_position")) or 99,
        )
        if len(top)!=3:
            continue

        prediction=pred_by.get(key)
        analysis=(prediction or {}).get("analysis") or {}
        numbers=[str(integer(x.get("horse_no"))) for x in top]
        actual=combo(numbers)
        tickets=set(analysis.get("trio_tickets") or [])
        hit=(actual in tickets) if prediction else None
        race_id=str(top[0].get("race_id") or "")
        payout=payout_by_race.get(race_id,"")

        result_rows.append({
            "date":target,
            "track":key[0],
            "race_no":key[1],
            "race_name":(prediction or {}).get("race_name") or top[0].get("race_name") or "",
            "top3":"－".join(numbers),
            "top3_rows":[
                {
                    "finish":idx+1,
                    "horse_no":numbers[idx],
                    "horse_name":top[idx].get("horse_name") or "",
                }
                for idx in range(3)
            ],
            "has_sealed_prediction":bool(prediction),
            "axis_horse_no":str((analysis.get("axis") or {}).get("horse_no") or ""),
            "axis_horse_name":str((analysis.get("axis") or {}).get("horse_name") or ""),
            "trio_hit":hit,
            "trio_payout":(
                f"{int(payout):,}円"
                if str(payout).isdigit()
                else ("払戻確認中" if hit else "")
            ),
            "source":top[0].get("source_url") or "",
        })

    result_payload={
        "date":target,
        "summary":{"checked":len(result_rows),"complete":len(result_rows)>=36},
        "races":result_rows,
        "source":"JRA_OFFICIAL_RESULTS_DB",
    }
    RESULT_OUT.parent.mkdir(parents=True,exist_ok=True)
    RESULT_OUT.write_text(json.dumps(result_payload,ensure_ascii=False,indent=2),encoding="utf-8")

    replay_rows=[]
    for result in result_rows:
        key=(result["track"],integer(result["race_no"]))
        prediction=pred_by.get(key)
        analysis=(prediction or {}).get("analysis") or {}
        axis_no=str((analysis.get("axis") or {}).get("horse_no") or result.get("axis_horse_no") or "")
        axis_name=str((analysis.get("axis") or {}).get("horse_name") or result.get("axis_horse_name") or "")
        top3=result.get("top3_rows") or []

        axis_finish=None
        if axis_no:
            for row in top3:
                if str(row.get("horse_no"))==axis_no:
                    axis_finish=integer(row.get("finish"))
                    break
            if axis_finish is None and len(top3)==3:
                axis_finish=4

        replay_rows.append({
            "date":target,
            "track":result["track"],
            "race_no":result["race_no"],
            "race_name":result.get("race_name") or "",
            "prediction":(
                {
                    "sealed":True,
                    "axis_no":axis_no,
                    "axis_name":axis_name,
                    "decision":analysis.get("pre_market_decision") or analysis.get("classification") or "—",
                    "candidate":[
                        " ".join(
                            str(v)
                            for v in (x.get("horse_no"),x.get("horse_name"))
                            if v not in (None,"")
                        )
                        for x in (analysis.get("partner_roles") or [])[:5]
                    ],
                    "tickets":analysis.get("trio_tickets") or [],
                }
                if prediction
                else {"sealed":False}
            ),
            "result":{
                "axis_finish":axis_finish,
                "top3":top3,
                "trio_hit":result.get("trio_hit"),
                "trio_payout":result.get("trio_payout") or "",
                "source":result.get("source") or "",
            },
        })

    replay_payload={
        "schema_version":1,
        "mode":"CANONICAL_REPLAY_DATE",
        "date":target,
        "summary":{
            "races":len(replay_rows),
            "sealed":sum(1 for x in replay_rows if x["prediction"].get("sealed") is not False),
            "results":sum(1 for x in replay_rows if len(x["result"].get("top3") or [])==3),
        },
        "races":replay_rows,
    }
    REPLAY_OUT.write_text(json.dumps(replay_payload,ensure_ascii=False,indent=2),encoding="utf-8")

    expected_sealed=len(archived_races)
    if replay_payload["summary"]["sealed"]!=expected_sealed:
        raise RuntimeError(
            f"replay sealed count mismatch: {replay_payload['summary']['sealed']} != archive {expected_sealed}"
        )

    print(json.dumps({
        "results":result_payload["summary"],
        "archive":{
            "created":archive_created,
            "races":len(archived_races),
            "pending":len(archived_pending),
            "hash":archive.get("prediction_hash_sha256"),
        },
        "replay":replay_payload["summary"],
    },ensure_ascii=False))

if __name__=="__main__":
    main()
