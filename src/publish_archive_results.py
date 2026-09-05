#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Tokyo")
target = os.getenv("TARGET_DATE") or datetime.now(TZ).date().isoformat()
year = target[:4]

RES = Path(f"data/race_results_html_{year}.csv")
PAY = Path(f"data/race_payouts_{year}.csv")
LIVE_PRED = Path("docs/data/live_predictions_sealed.json")
RESULT_OUT = Path(f"docs/data/today-results-{target}.json")
PRED_ARCHIVE = Path(f"docs/data/prediction-archive-{target}.json")
REPLAY_OUT = Path(f"docs/data/replay-{target}.json")
POST_STATUS = Path("status/jra_post_meeting_update.json")


def integer(v, default=None):
    try:
        return int(float(str(v).strip()))
    except Exception:
        return default


def combo(xs):
    return "-".join(map(str, sorted(int(x) for x in xs)))


def read_csv(path: Path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_json(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def valid_prediction_archive(payload):
    return (
        isinstance(payload, dict)
        and payload.get("date") == target
        and payload.get("mode") == "IMMUTABLE_PREDICTION_ARCHIVE"
        and bool((payload.get("races") or []) or (payload.get("pending") or []))
    )


def load_prediction_archive():
    existing = load_json(PRED_ARCHIVE, {})
    if valid_prediction_archive(existing):
        return existing, "IMMUTABLE_ARCHIVE"

    live = load_json(LIVE_PRED, {"races": [], "pending": []})
    archived_races = [p for p in (live.get("races") or []) if p.get("date") == target]
    archived_pending = [p for p in (live.get("pending") or []) if p.get("date") == target]
    if not (archived_races or archived_pending):
        raise RuntimeError(
            f"no immutable prediction archive for {target}, and current live seal has no target-date predictions; "
            "refusing to overwrite historical archive"
        )

    archive = {
        "schema_version": live.get("schema_version"),
        "mode": "IMMUTABLE_PREDICTION_ARCHIVE",
        "source_mode": live.get("mode"),
        "model_version": live.get("model_version"),
        "sealed_generated_at": live.get("generated_at"),
        "prediction_hash_sha256": live.get("prediction_hash_sha256"),
        "date": target,
        "odds_popularity_used": live.get("odds_popularity_used", False),
        "results_used": live.get("results_used", False),
        "races": archived_races,
        "pending": archived_pending,
    }
    PRED_ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    PRED_ARCHIVE.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    return archive, "LIVE_SEAL_INITIAL_ARCHIVE"


def existing_complete_results():
    payload = load_json(RESULT_OUT, {})
    summary = payload.get("summary") or {}
    races = payload.get("races") or []
    if summary.get("complete") is True and races:
        return payload
    return None


def expected_completed_race_count():
    status = load_json(POST_STATUS, {})
    compact = target.replace("-", "")
    if compact not in (status.get("complete_dates") or []):
        return None
    return integer(status.get("discovered_races"))


def build_results(pred_archive):
    result_rows = [r for r in read_csv(RES) if str(r.get("race_date")) == target]
    payout_rows = [r for r in read_csv(PAY) if str(r.get("race_date")) == target]

    by_race = defaultdict(list)
    for r in result_rows:
        key = (str(r.get("course", "")).replace("競馬場", ""), integer(r.get("race_no")))
        if key[0] and key[1] is not None:
            by_race[key].append(r)

    payout = {}
    for r in payout_rows:
        bet = str(r.get("bet_type", ""))
        if "三連複" in bet or "3連複" in bet:
            payout[str(r.get("race_id", ""))] = r.get("payout_per_100_yen") or ""

    pred_by = {
        (str(p.get("track", "")).replace("競馬場", ""), integer(p.get("race_no"))): p
        for p in (pred_archive.get("races") or [])
    }

    out = []
    for key, rows in sorted(by_race.items(), key=lambda kv: (kv[0][0], kv[0][1] or 99)):
        top = sorted(
            [x for x in rows if integer(x.get("finish_position")) in (1, 2, 3)],
            key=lambda x: integer(x.get("finish_position")) or 99,
        )
        if len(top) != 3:
            continue

        pred = pred_by.get(key)
        nums = [str(integer(x.get("horse_no"))) for x in top]
        actual = combo(nums)
        analysis = (pred or {}).get("analysis") or {}
        tickets = set(analysis.get("trio_tickets") or [])
        hit = (actual in tickets) if pred else None
        race_id = str(top[0].get("race_id") or "")
        pay = payout.get(race_id, "")

        out.append(
            {
                "date": target,
                "track": key[0],
                "race_no": key[1],
                "race_name": (pred or {}).get("race_name") or top[0].get("race_name") or "",
                "top3": "－".join(nums),
                "top3_rows": [
                    {
                        "finish": idx + 1,
                        "horse_no": nums[idx],
                        "horse_name": top[idx].get("horse_name") or "",
                    }
                    for idx in range(3)
                ],
                "has_sealed_prediction": bool(pred),
                "axis_horse_no": str((analysis.get("axis") or {}).get("horse_no") or ""),
                "axis_horse_name": str((analysis.get("axis") or {}).get("horse_name") or ""),
                "trio_hit": hit,
                "trio_payout": (
                    f"{int(pay):,}円"
                    if str(pay).isdigit()
                    else ("払戻確認中" if hit else "")
                ),
                "source": top[0].get("source_url") or "",
            }
        )

    expected = expected_completed_race_count()
    complete = bool(out) and len(out) == len(by_race)
    if expected is not None:
        complete = complete and len(out) == expected

    if not complete:
        existing = existing_complete_results()
        if existing is not None:
            return existing, "EXISTING_COMPLETE_RESULT_FALLBACK"
        raise RuntimeError(
            f"incomplete result reconstruction for {target}: "
            f"result_rows={len(result_rows)} race_keys={len(by_race)} completed={len(out)} expected={expected}; "
            "refusing to overwrite confirmed archive"
        )

    payload = {
        "date": target,
        "summary": {"checked": len(out), "complete": True},
        "races": out,
        "source": "JRA_OFFICIAL_RESULTS_DB",
    }
    RESULT_OUT.parent.mkdir(parents=True, exist_ok=True)
    RESULT_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload, "CURRENT_OFFICIAL_RESULTS"


def build_replay(pred_archive, results):
    pred_map = {
        (str(p.get("track", "")).replace("競馬場", ""), integer(p.get("race_no"))): p
        for p in (pred_archive.get("races") or [])
    }
    replay_rows = []

    for r in results.get("races") or []:
        key = (r["track"], integer(r["race_no"]))
        pred = pred_map.get(key)
        analysis = (pred or {}).get("analysis") or {}
        axis_no = str((analysis.get("axis") or {}).get("horse_no") or r.get("axis_horse_no") or "")
        axis_name = str((analysis.get("axis") or {}).get("horse_name") or r.get("axis_horse_name") or "")
        top3_rows = r.get("top3_rows") or []

        finish = None
        if axis_no:
            for row in top3_rows:
                if str(row.get("horse_no")) == axis_no:
                    finish = integer(row.get("finish"))
                    break
            if finish is None and len(top3_rows) == 3:
                finish = 4

        replay_rows.append(
            {
                "date": target,
                "track": r["track"],
                "race_no": r["race_no"],
                "race_name": r.get("race_name") or "",
                "prediction": (
                    {
                        "sealed": True,
                        "axis_no": axis_no,
                        "axis_name": axis_name,
                        "decision": analysis.get("pre_market_decision") or analysis.get("classification") or "—",
                        "candidate": [
                            " ".join(
                                str(v)
                                for v in (x.get("horse_no"), x.get("horse_name"))
                                if v not in (None, "")
                            )
                            for x in (analysis.get("partner_roles") or [])[:5]
                        ],
                        "tickets": analysis.get("trio_tickets") or [],
                    }
                    if pred
                    else {"sealed": False}
                ),
                "result": {
                    "axis_finish": finish,
                    "top3": top3_rows,
                    "trio_hit": r.get("trio_hit"),
                    "trio_payout": r.get("trio_payout") or "",
                    "source": r.get("source") or "",
                },
            }
        )

    if not replay_rows:
        raise RuntimeError(f"refusing to write empty replay archive for {target}")

    replay_payload = {
        "schema_version": 1,
        "mode": "CANONICAL_REPLAY_DATE",
        "date": target,
        "summary": {
            "races": len(replay_rows),
            "sealed": sum(1 for x in replay_rows if x["prediction"].get("sealed") is not False),
            "results": sum(1 for x in replay_rows if len(x["result"].get("top3") or []) == 3),
        },
        "races": replay_rows,
    }
    REPLAY_OUT.write_text(json.dumps(replay_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return replay_payload


def main():
    pred_archive, pred_source = load_prediction_archive()
    if pred_archive.get("odds_popularity_used") is not False or pred_archive.get("results_used") is not False:
        raise RuntimeError("prediction archive firewall violation")

    results, result_source = build_results(pred_archive)
    replay = build_replay(pred_archive, results)

    print(
        json.dumps(
            {
                "status": "PASS",
                "date": target,
                "prediction_source": pred_source,
                "result_source": result_source,
                "prediction_archive": {
                    "sealed": len(pred_archive.get("races") or []),
                    "pending": len(pred_archive.get("pending") or []),
                },
                "results": results.get("summary"),
                "replay": replay.get("summary"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
