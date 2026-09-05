#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

SEALED = Path("docs/data/live_predictions_sealed.json")
SCORES = Path("docs/data/live_prediction_scores.json")
PDCA = Path("docs/data/live_pdca.json")
UPGRADE_LOG = Path("docs/data/model_upgrade_log.json")
CONTEXT = Path("data/race_context_2026.csv")
PAYOUTS = Path("data/race_payouts_2026.csv")
OUT = Path("docs/data/dashboard.json")
DETAIL = Path("docs/data/management_analytics.json")
STATUS = Path("status/management_erp.json")
JST = timezone(timedelta(hours=9))
REPLAY_GLOB = "replay-????-??-??.json"

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def iv(v):
    try:
        return int(float(str(v).strip()))
    except Exception:
        return None

def fv(v):
    try:
        return float(v)
    except Exception:
        return None

def norm_track(v):
    return str(v or "").strip().replace("競馬場", "")

def race_key(date, track, race_no):
    return (str(date or ""), norm_track(track), iv(race_no))

def read_csv(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def dist_band(n):
    n = iv(n)
    if n is None:
        return "不明"
    if n <= 1200:
        return "1200以下"
    if n <= 1600:
        return "1300-1600"
    if n <= 2000:
        return "1700-2000"
    if n <= 2400:
        return "2100-2400"
    return "2500以上"

def field_band(n):
    n = iv(n)
    if n is None:
        return "不明"
    if n <= 10:
        return "10頭以下"
    if n <= 13:
        return "11-13頭"
    if n <= 16:
        return "14-16頭"
    return "17頭以上"

def percent(num, den):
    return round(num / den * 100, 2) if den else None

def yen_int(v):
    if isinstance(v,(int,float)): return int(v)
    s="".join(ch for ch in str(v or "") if ch.isdigit())
    return int(s) if s else 0

def load_replay_archive():
    out={}
    for p in Path("docs/data").glob(REPLAY_GLOB):
        d=load_json(p,{})
        for r in d.get("races") or []:
            k=race_key(r.get("date") or d.get("date"),r.get("track"),r.get("race_no"))
            if all((k[0],k[1],k[2] is not None)):
                out[k]=r
    return out

def trio_combo(xs):
    vals=[]
    for x in xs or []:
        try: vals.append(int(str(x)))
        except Exception: pass
    return "-".join(map(str, sorted(vals))) if len(vals)==3 else ""

def build_group(rows, field):
    groups=defaultdict(list)
    for r in rows:
        val=r.get(field)
        if val is None or val == "":
            val="不明"
        groups[str(val)].append(r)
    out=[]
    for value, xs in groups.items():
        scored=[x for x in xs if x.get("scored")]
        bought=[x for x in scored if x.get("bought")]
        stake=sum(x.get("stake_yen") or 0 for x in bought)
        ret=sum(x.get("return_yen") or 0 for x in bought)
        hits=sum(1 for x in bought if x.get("trio_hit"))
        axis_top3=sum(1 for x in scored if x.get("axis_finish") in (1,2,3))
        combo_miss=sum(1 for x in bought if x.get("axis_finish") in (1,2,3) and not x.get("trio_hit"))
        out.append({
            "value":value,
            "races":len(xs),
            "scored_races":len(scored),
            "bought_races":len(bought),
            "trio_hits":hits,
            "hit_rate":percent(hits,len(bought)),
            "axis_top3_rate":percent(axis_top3,len(scored)),
            "combo_miss_rate":percent(combo_miss,len(bought)),
            "stake_yen":stake,
            "return_yen":ret,
            "profit_yen":ret-stake,
            "roi":percent(ret,stake),
        })
    return sorted(out, key=lambda x:(-x["scored_races"], x["value"]))

def main():
    sealed=load_json(SEALED, {"races":[]})
    scores=load_json(SCORES, {"summary":{},"races":[],"pending":[]})
    pdca=load_json(PDCA, {})
    upgrade_log=load_json(UPGRADE_LOG, {"schema_version":1,"upgrades":[]})
    contexts=read_csv(CONTEXT)
    payouts=read_csv(PAYOUTS)
    replay_by=load_replay_archive()

    ctx_by={}
    race_id_by={}
    for c in contexts:
        k=race_key(c.get("race_date"),c.get("course") or c.get("track"),c.get("race_no"))
        if k[0] and k[1] and k[2] is not None:
            ctx_by[k]=c
            race_id_by[k]=c.get("race_id")

    payout_by_race={}
    for p in payouts:
        if str(p.get("bet_type") or "") not in ("3連複","三連複"):
            continue
        rid=str(p.get("race_id") or "")
        if rid:
            payout_by_race[rid]={
                "winning_selection":str(p.get("winning_selection") or ""),
                "payout_per_100_yen":iv(p.get("payout_per_100_yen")) or 0,
                "data_status":p.get("data_status"),
            }

    score_by={race_key(x.get("date"),x.get("track"),x.get("race_no")):x for x in scores.get("races") or []}
    pending_by={race_key(x.get("date"),x.get("track"),x.get("race_no")):x for x in scores.get("pending") or []}

    rows=[]
    sealed_races=sealed.get("races") or []
    for p in sealed_races:
        k=race_key(p.get("date"),p.get("track"),p.get("race_no"))
        a=p.get("analysis") or {}
        c=ctx_by.get(k,{})
        s=score_by.get(k)
        rid=race_id_by.get(k) or c.get("race_id")
        pay=payout_by_race.get(str(rid or ""),{})
        tickets=[str(x) for x in (a.get("trio_tickets") or []) if x]
        decision=str(a.get("pre_market_decision") or p.get("decision") or "UNKNOWN")
        scored=bool(s)
        bought=bool(scored and decision!="PASS" and tickets)
        hit=bool(s and s.get("trio_hit"))
        stake=100*len(tickets) if bought else 0
        ret=(pay.get("payout_per_100_yen") or 0) if hit else 0
        axis=a.get("axis") or {}
        row={
            "date":k[0],"track":k[1],"race_no":k[2],
            "race_id":rid,
            "race_name":p.get("race_name") or c.get("race_name") or (s or {}).get("race_name"),
            "race_category":c.get("race_category"),
            "race_class":c.get("race_class"),
            "surface":c.get("surface"),
            "distance_m":iv(c.get("distance_m")),
            "distance_band":dist_band(c.get("distance_m")),
            "track_condition":c.get("track_condition") or "不明",
            "weather":c.get("weather") or "不明",
            "field_size":iv(c.get("field_size")),
            "field_size_band":field_band(c.get("field_size")),
            "scheduled_start":c.get("scheduled_start"),
            "decision":decision,
            "race_state":"SCORED" if scored else ("RESULT_PENDING" if k in pending_by else "SEALED"),
            "axis_horse_no":str(axis.get("horse_no") or (s or {}).get("axis_horse_no") or ""),
            "axis_horse_name":axis.get("horse_name") or (s or {}).get("axis_horse_name"),
            "axis_durability":a.get("axis_durability") or a.get("axis_durability_label") or a.get("axis_confidence"),
            "predicted_scenario":a.get("predicted_scenario") or a.get("scenario"),
            "role_tags":a.get("role_tags") or [],
            "third_place_intrusion_candidates":a.get("third_place_intrusion_candidates") or [],
            "trio_tickets":tickets,
            "ticket_count":len(tickets),
            "scored":scored,
            "bought":bought,
            "axis_finish":(s or {}).get("axis_finish"),
            "axis_grade":(s or {}).get("axis_grade"),
            "actual_top3":(s or {}).get("actual_top3") or [],
            "trio_hit":hit,
            "winning_trio":pay.get("winning_selection"),
            "stake_yen":stake,
            "return_yen":ret,
            "profit_yen":ret-stake,
            "roi":percent(ret,stake),
            "prediction_hash_sha256":(s or {}).get("prediction_hash_sha256") or sealed.get("prediction_hash_sha256"),
            "ticket_value_regime_shadow":a.get("ticket_value_regime_shadow") or {},
            "actual_trio_payout_yen":(pay.get("payout_per_100_yen") or 0) if scored else 0,
            "data_status":c.get("data_status"),
            "payout_data_status":pay.get("data_status"),
        }
        rows.append(row)

    # Include scored rows not present in the current seal so management never silently loses completed history.
    known={(r["date"],r["track"],r["race_no"]) for r in rows}
    for s in scores.get("races") or []:
        k=race_key(s.get("date"),s.get("track"),s.get("race_no"))
        if k in known: continue
        c=ctx_by.get(k,{})
        rid=race_id_by.get(k) or c.get("race_id")
        pay=payout_by_race.get(str(rid or ""),{})
        replay=replay_by.get(k) or {}
        rp=replay.get("prediction") or {}
        rr=replay.get("result") or {}
        tickets=[str(x) for x in (rp.get("tickets") or []) if x]
        decision=rp.get("decision") or s.get("decision")
        bought=bool(decision!="PASS" and tickets)
        trio_hit=bool(rr.get("trio_hit")) if replay else bool(s.get("trio_hit"))
        stake=100*len(tickets) if bought else 0
        replay_return=yen_int(rr.get("trio_payout")) if trio_hit else 0
        ret=replay_return or ((pay.get("payout_per_100_yen") or 0) if trio_hit else 0)
        rows.append({
            "date":k[0],"track":k[1],"race_no":k[2],"race_id":rid,
            "race_name":s.get("race_name") or replay.get("race_name") or c.get("race_name"),
            "race_category":c.get("race_category"),"race_class":c.get("race_class"),
            "surface":c.get("surface"),"distance_m":iv(c.get("distance_m")),
            "distance_band":dist_band(c.get("distance_m")),
            "track_condition":c.get("track_condition") or "不明",
            "weather":c.get("weather") or "不明",
            "field_size":iv(c.get("field_size")),"field_size_band":field_band(c.get("field_size")),
            "scheduled_start":c.get("scheduled_start"),"decision":decision,
            "race_state":"SCORED","axis_horse_no":s.get("axis_horse_no"),"axis_horse_name":s.get("axis_horse_name"),
            "axis_durability":None,"predicted_scenario":None,"role_tags":[],"third_place_intrusion_candidates":[],
            "trio_tickets":tickets,"ticket_count":len(tickets),"scored":True,"bought":bought,
            "axis_finish":s.get("axis_finish"),"axis_grade":s.get("axis_grade"),
            "actual_top3":s.get("actual_top3") or rr.get("top3") or [],"trio_hit":trio_hit,
            "winning_trio":pay.get("winning_selection"),"stake_yen":stake,"return_yen":ret,"profit_yen":ret-stake,"roi":percent(ret,stake),
            "prediction_hash_sha256":s.get("prediction_hash_sha256"),"ticket_value_regime_shadow":{},"actual_trio_payout_yen":yen_int(rr.get("trio_payout")) or (pay.get("payout_per_100_yen") or 0),"data_status":c.get("data_status"),
            "payout_data_status":pay.get("data_status"),
        })

    rows.sort(key=lambda x:(x.get("date") or "",x.get("track") or "",x.get("race_no") or 0))
    scored=[x for x in rows if x.get("scored")]
    bought=[x for x in scored if x.get("bought")]
    stake=sum(x["stake_yen"] for x in bought)
    ret=sum(x["return_yen"] for x in bought)
    hits=sum(1 for x in bought if x.get("trio_hit"))
    axis_top3=sum(1 for x in scored if x.get("axis_finish") in (1,2,3))
    combo_miss=sum(1 for x in bought if x.get("axis_finish") in (1,2,3) and not x.get("trio_hit"))
    returns=sorted((x["return_yen"] for x in bought), reverse=True)
    ret_ex_top=ret-(returns[0] if returns else 0)
    manbaken_opportunities=[x for x in bought if (x.get("actual_trio_payout_yen") or 0)>=10000]
    manbaken_hits=[x for x in manbaken_opportunities if x.get("trio_hit")]
    sub10k_opportunities=[x for x in bought if 0<(x.get("actual_trio_payout_yen") or 0)<10000]
    sub10k_stake=sum(x.get("stake_yen") or 0 for x in sub10k_opportunities)
    sub10k_return=sum(x.get("return_yen") or 0 for x in sub10k_opportunities)
    sub10k_roi=percent(sub10k_return,sub10k_stake)
    sub10k_target_low=80.0
    sub10k_target_high=90.0
    if sub10k_roi is None:
        sub10k_target_status="NO_DATA"
    elif sub10k_target_low<=sub10k_roi<=sub10k_target_high:
        sub10k_target_status="IN_TARGET"
    elif sub10k_roi<sub10k_target_low:
        sub10k_target_status="BELOW_TARGET"
    else:
        sub10k_target_status="ABOVE_TARGET"
    concentrated_shadow=[x for x in rows if ((x.get("ticket_value_regime_shadow") or {}).get("regime")=="CONCENTRATED")]
    high_payout_shadow=[x for x in rows if ((x.get("ticket_value_regime_shadow") or {}).get("regime")=="HIGH_PAYOUT_CAPTURE")]

    dims=[
        "date","track","race_no","race_category","race_class","surface","distance_m","distance_band",
        "track_condition","weather","field_size","field_size_band","decision","axis_grade","race_state"
    ]
    breakdowns={d:build_group(rows,d) for d in dims}
    filters={d:sorted({str(r.get(d)) for r in rows if r.get(d) not in (None,"")}) for d in dims}

    # Automatic optimization queue: diagnostic/shadow only. It never mutates the production model.
    candidates=[]
    for d in ("track","race_class","surface","distance_band","track_condition","field_size_band","decision"):
        for g in breakdowns[d]:
            if g["bought_races"] < 5:
                continue
            roi=g.get("roi")
            combo=g.get("combo_miss_rate")
            axis=g.get("axis_top3_rate")
            if roi is not None and roi < 80:
                candidates.append({
                    "type":"WEAK_SEGMENT","dimension":d,"value":g["value"],
                    "sample":g["bought_races"],"roi":roi,"axis_top3_rate":axis,"combo_miss_rate":combo,
                    "action":"PASS閾値・軸耐久性・買い目変換をChallengerでshadow比較",
                    "status":"SHADOW_ONLY"
                })
            elif roi is not None and roi >= 120:
                candidates.append({
                    "type":"STRONG_SEGMENT","dimension":d,"value":g["value"],
                    "sample":g["bought_races"],"roi":roi,"axis_top3_rate":axis,"combo_miss_rate":combo,
                    "action":"再現性確認用の強条件候補。単独ROIで本番昇格しない",
                    "status":"SHADOW_ONLY"
                })
    candidates.append({
        "type":"TICKET_VALUE_REGIME_SHADOW",
        "dimension":"ticket_policy",
        "value":"CONCENTRATED / BALANCED / HIGH_PAYOUT_CAPTURE / PASS_BIASED",
        "sample":len(rows),
        "roi":percent(ret,stake),
        "axis_top3_rate":percent(axis_top3,len(scored)),
        "combo_miss_rate":percent(combo_miss,len(bought)),
        "action":"固いレースは3〜5点へ圧縮して厚く、荒れレースは万馬券捕捉を優先。軸飛び保険だけの軸なし増加は禁止。券種別実オッズ接続後はトリガミ/低EVを除外。",
        "status":"SHADOW_ONLY",
        "promotion_metrics":["万馬券捕捉率","ROI","万馬券除外ROI","最大払戻除外ROI","平均点数","固い群の的中率","軸飛び時の無駄打ち率"],
        "target":{"metric":"万馬券除外ROI","range_pct":[80,90],"meaning":"実際の三連複払戻が10,000円以上だったレースを投資・払戻ともに除外した基礎回収率。安定域到達を実購入検討の主要条件とする"}
    })
    candidates=sorted(candidates,key=lambda x:(0 if x["type"]=="WEAK_SEGMENT" else 1,-x.get("sample",0)))[:40]

    failure_counts=(pdca.get("failure_counts") or {})
    error_types=[
        {"label":"軸飛び型","value":failure_counts.get("axis_outside_top3",0)},
        {"label":"軸生存・三連複漏れ","value":failure_counts.get("axis_survived_but_trio_missed",0)},
        {"label":"軸＋三連複的中","value":failure_counts.get("axis_and_trio_hit",0)},
        {"label":"候補内組合せ漏れ","value":combo_miss},
    ]
    state_counts=dict(Counter(r["race_state"] for r in rows))
    today=max((r["date"] for r in rows if r.get("date")), default="")
    today_rows=[r for r in rows if r.get("date")==today] if today else rows

    summary={
        "model_version":sealed.get("model_version") or sealed.get("schema_version") or "JRA-LIVE",
        "snapshot_time":datetime.now(JST).isoformat(timespec="seconds"),
        "total_races":len(today_rows),
        "buy_races":sum(1 for r in today_rows if r.get("decision") in ("BUY","CAUTION")),
        "pass_races":sum(1 for r in today_rows if r.get("decision")=="PASS"),
        "scored_races":len(scored),
        "roi":percent(ret,stake) or 0,
        "stake_amount":stake,
        "return_amount":ret,
        "profit_amount":ret-stake,
        "hit_rate":percent(hits,len(bought)) or 0,
        "hits":hits,
        "daily_budget":10000,
        "remaining_budget":10000,
        "roi_ex_top":percent(ret_ex_top,stake) or 0,
        "axis_survival":percent(axis_top3,len(scored)) or 0,
        "third_column_miss_rate":percent(combo_miss,len(bought)) or 0,
        "elimination_miss_rate":0,
        "max_drawdown":0,
        "purchase_rate":percent(len(bought),len(scored)) or 0,
        "manbaken_opportunities":len(manbaken_opportunities),
        "manbaken_hits":len(manbaken_hits),
        "manbaken_capture_rate":percent(len(manbaken_hits),len(manbaken_opportunities)) or 0,
        "sub10k_opportunities":len(sub10k_opportunities),
        "sub10k_stake_amount":sub10k_stake,
        "sub10k_return_amount":sub10k_return,
        "sub10k_roi":sub10k_roi or 0,
        "sub10k_roi_target_low":sub10k_target_low,
        "sub10k_roi_target_high":sub10k_target_high,
        "sub10k_roi_target_status":sub10k_target_status,
    }

    live_health_metrics={
        "sample_scored_races":len(scored),
        "sample_bought_races":len(bought),
        "roi":summary["roi"],
        "hit_rate":summary["hit_rate"],
        "axis_survival":summary["axis_survival"],
        "combo_miss_rate":summary["third_column_miss_rate"],
        "roi_ex_top":summary["roi_ex_top"],
        "profit_amount":summary["profit_amount"],
    }
    upgrade_rows=[]
    for raw in upgrade_log.get("upgrades") or []:
        x=json.loads(json.dumps(raw,ensure_ascii=False))
        if str(x.get("to_model") or "")==str(summary["model_version"]):
            cmp=x.get("comparison_at_promotion") or {}
            prev=cmp.get("previous_model") or cmp.get("baseline") or {}
            def prev_num(*names):
                for name in names:
                    v=fv(prev.get(name))
                    if v is not None:return v
                return None
            comparisons=[]
            for key,aliases,higher_better in (
                ("roi",("roi","roi_pct"),True),
                ("hit_rate",("hit_rate","hit_rate_pct"),True),
                ("axis_survival",("axis_survival","axis_top3_rate","axis_top3_rate_pct"),True),
                ("combo_miss_rate",("combo_miss_rate","third_column_miss_rate"),False),
            ):
                old=prev_num(*aliases);cur=fv(live_health_metrics.get(key))
                if old is None or cur is None:continue
                better=(cur>old) if higher_better else (cur<old)
                worse=(cur<old) if higher_better else (cur>old)
                comparisons.append({"metric":key,"previous":old,"current":cur,"direction":"BETTER" if better else ("WORSE" if worse else "SAME")})
            better=sum(1 for z in comparisons if z["direction"]=="BETTER")
            worse=sum(1 for z in comparisons if z["direction"]=="WORSE")
            if len(scored)<36:
                status="SAMPLE_SMALL";label="サンプル不足・継続観察"
            elif comparisons and better>worse:
                status="BETTER";label="旧モデル比較で現在は良好"
            elif comparisons and worse>better:
                status="WORSE";label="旧モデル比較で現在は悪化傾向"
            elif comparisons:
                status="MIXED";label="旧モデル比較で一長一短"
            else:
                status="COMPARISON_DATA_MISSING";label="旧モデル比較データ不足"
            x["post_upgrade_health"]={
                "status":status,
                "label":label,
                "last_checked_at":summary["snapshot_time"],
                "current_model_metrics":live_health_metrics,
                "vs_previous_model":comparisons,
            }
        upgrade_rows.append(x)

    public_races=[]
    for r in today_rows:
        public_races.append({
            "date":r["date"],"track":r["track"],"race_no":r["race_no"],
            "start_time":r.get("scheduled_start") or "",
            "classification":r.get("decision") or "PASS",
            "axis":(" ".join(x for x in [r.get("axis_horse_no"),r.get("axis_horse_name")] if x)) or "-",
            "race_state":r.get("race_state"),"ev":None,"stake":r.get("stake_yen") or 0,
            "surface":r.get("surface"),"distance":r.get("distance_m"),
            "axis_durability":r.get("axis_durability") or "-",
            "axis_failure_risk":"要監査" if r.get("axis_finish") not in (None,1,2,3) else "-",
            "ticket_summary":f"三連複 {r.get('ticket_count') or 0}点",
            "role_tags":r.get("role_tags") or [],
            "third_place_intrusion_candidates":r.get("third_place_intrusion_candidates") or [],
            "predicted_scenario":r.get("predicted_scenario") or "",
        })

    dashboard={
        "summary":summary,
        "state_counts":state_counts,
        "races":public_races,
        "risks":[
            {"name":"公開側→管理側データ連携","level":"ok","detail":"公開画面と同じ正規データ源から管理分析JSONを自動生成。手動取り込み不要。"},
            {"name":"市場情報ファイアウォール","level":"ok","detail":"能力予想と結果/払戻の後段分析を分離。"},
            {"name":"自動最適化","level":"ok","detail":"条件別分解からChallenger候補を自動生成。productionは自動上書きしない。"},
        ],
        "models":[
            {"name":"A3/B5/C7 FROZEN v1.0","status":"CHAMPION / READ ONLY","roi":0,"hit_rate":0,"note":"上書き禁止の比較基準"},
            {"name":"Current Integrated","status":"CURRENT","roi":summary["roi"],"hit_rate":summary["hit_rate"],"note":"現行ライブ実績を自動集計"},
        ],
        "mechanisms":[
            {"name":"基礎能力","status":"ACTIVE","note":"人気・オッズ不使用"},
            {"name":"条件適性","status":"ACTIVE","note":"距離・コース・馬場・斤量等"},
            {"name":"展開 / レース構造","status":"ACTIVE","note":"複数シナリオ"},
            {"name":"軸耐久性","status":"ACTIVE","note":"結果後に条件別監査"},
            {"name":"相手役割分散","status":"ACTIVE","note":"役割別に保存・抽出"},
            {"name":"3着侵入","status":"ACTIVE","note":"候補を保存・検証"},
            {"name":"買い目変換PDCA","status":"ACTIVE","note":"組合せ漏れ率を自動監査"},
            {"name":"条件別Challenger生成","status":"ACTIVE","note":"SHADOW_ONLYで自動候補化"},
            {"name":"券価値レジーム","status":"SHADOW","note":"固い=圧縮/厚張り、荒れ=万馬券捕捉、軸飛び保険の点数水増し禁止"},
        ],
        "error_types":error_types,
        "role_distribution":[],
        "audit":[
            {"time":summary["snapshot_time"],"level":"INFO","title":"管理分析データ更新","detail":f"{len(rows)}Rを正規化。{len(scored)}R結果接続、{len(bought)}R購入評価。"}
        ],
        "sources":[
            {"name":"live_predictions_sealed.json","status":"ok" if SEALED.exists() else "bad","detail":"発走前封印予想"},
            {"name":"live_prediction_scores.json","status":"ok" if SCORES.exists() else "warn","detail":"結果照合"},
            {"name":"race_context_2026.csv","status":"ok" if CONTEXT.exists() else "warn","detail":"レース条件"},
            {"name":"race_payouts_2026.csv","status":"ok" if PAYOUTS.exists() else "warn","detail":"公式払戻"},
            {"name":"management_analytics.json","status":"ok","detail":"管理専用の細分化・抽出用データ"},
        ],
        "upgrade_log":{"tracking_started_at":upgrade_log.get("tracking_started_at"),"baseline":upgrade_log.get("baseline"),"policy":upgrade_log.get("policy"),"upgrades":upgrade_rows},
        "analytics":{
            "filters":filters,
            "breakdowns":breakdowns,
            "optimization_candidates":candidates,
            "latest_races":today_rows,
            "all_race_count":len(rows),
            "ticket_value_regime_shadow_counts":dict(Counter((x.get("ticket_value_regime_shadow") or {}).get("regime") or "NO_SHADOW" for x in rows)),
            "manbaken":{"opportunities":len(manbaken_opportunities),"hits":len(manbaken_hits),"capture_rate":percent(len(manbaken_hits),len(manbaken_opportunities)),"threshold_yen":10000},
            "sub10k_baseline":{"eligible_races":len(sub10k_opportunities),"stake_yen":sub10k_stake,"return_yen":sub10k_return,"roi":sub10k_roi,"target_low":sub10k_target_low,"target_high":sub10k_target_high,"status":sub10k_target_status,"purchase_consideration_rule":"80〜90%の範囲で一定期間安定し、万馬券捕捉が上乗せされる状態を実購入検討ラインとする"},
        }
    }
    detail={
        "schema_version":1,
        "updated_at":summary["snapshot_time"],
        "purpose":"管理専用。公開画面には出さない詳細KPI・回収率・条件別分析・Challenger候補。",
        "governance":{
            "production_auto_mutation":False,
            "optimization_mode":"AUTO_DIAGNOSE_AND_SHADOW_CHALLENGER",
            "leakage_rule":"結果・払戻は封印後の分析だけに使用",
            "purchase_stability_target":{"metric":"万馬券除外ROI","definition":"実際の三連複払戻が10,000円以上だったレースを投資・払戻ともに除外","target_range_pct":[80,90],"role":"実購入検討の主要安定性KPI"},
        },
        "summary":summary,
        "filters":filters,
        "breakdowns":breakdowns,
        "optimization_candidates":candidates,
        "races":rows,
        "pdca":pdca,
        "upgrade_log":{"tracking_started_at":upgrade_log.get("tracking_started_at"),"baseline":upgrade_log.get("baseline"),"policy":upgrade_log.get("policy"),"upgrades":upgrade_rows},
    }

    OUT.parent.mkdir(parents=True,exist_ok=True)
    STATUS.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(dashboard,ensure_ascii=False,indent=2),encoding="utf-8")
    DETAIL.write_text(json.dumps(detail,ensure_ascii=False,indent=2),encoding="utf-8")
    STATUS.write_text(json.dumps({
        "status":"PASS",
        "updated_at":summary["snapshot_time"],
        "race_rows":len(rows),
        "scored_rows":len(scored),
        "bought_rows":len(bought),
        "optimization_candidates":len(candidates),
        "production_auto_mutation":False,
    },ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":"PASS","rows":len(rows),"scored":len(scored),"roi":summary["roi"],"candidates":len(candidates)},ensure_ascii=False))

if __name__=="__main__":
    main()
