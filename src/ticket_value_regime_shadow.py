#!/usr/bin/env python3
from __future__ import annotations

def _f(v,d=0.0):
    try:return float(v)
    except:return d

def classify_ticket_policy(race,q,analysis):
    """
    Research-only ticket allocation policy.
    It never changes pure ability ranking and never reads odds/popularity/results.
    Its job is to decide how concentrated or expansive the ticket structure should be.
    """
    q=list(q or [])
    dur=(analysis or {}).get("axis_durability") or {}
    intrusion=(analysis or {}).get("third_place_intrusion") or []
    situation=(analysis or {}).get("situational_shadow") or {}
    pattern=str(situation.get("pattern") or "STANDARD")
    if not q:
        return {"status":"RESEARCH_ONLY","regime":"PASS","reason":["候補データなし"],"production_override_applied":False}

    top=q[:8]
    scores=[_f(x.get("score")) for x in top]
    unc=[_f(x.get("uncertainty"),1.0) for x in top]
    avg_unc=sum(unc)/len(unc) if unc else 1.0
    gap=_f(dur.get("gap_to_second"))
    dstatus=str(dur.get("status") or "LOW")
    top5_spread=(max(scores[:5])-min(scores[:5])) if len(scores)>=5 else ((max(scores)-min(scores)) if len(scores)>1 else 0.0)
    evidence=sum(1 for x in top if _f(x.get("starts_before"))>=3)
    intrusion_n=len(intrusion)

    hard_score=0
    volatile_score=0
    reasons=[]

    if dstatus=="HIGH": hard_score+=3
    elif dstatus=="MID": hard_score+=1; volatile_score+=1
    else: volatile_score+=3

    # 8月PDCAでは能力1-2位差が大きいほど軸生存が高いという単調関係は再現しなかった。
    # 大差は固さの根拠にせず、僅差だけを不確実性補助信号として扱う。
    if gap<1.5: volatile_score+=2; reasons.append("上位評価差が小さい")

    if avg_unc<=.40: hard_score+=2; reasons.append("上位の不確実性が低い")
    elif avg_unc>=.60: volatile_score+=2; reasons.append("上位の不確実性が高い")

    if top5_spread>=6: hard_score+=2
    elif top5_spread<2: volatile_score+=2

    if evidence>=6: hard_score+=1
    elif evidence<=3: volatile_score+=2

    if intrusion_n>=2: volatile_score+=2; reasons.append("3着侵入候補が複数")
    if pattern in ("FLAT_CHAOS","FRONT_PRESSURE","THIRD_PLACE_VOLATILE","LOW_EVIDENCE"): volatile_score+=2
    if pattern in ("DOMINANT_AXIS","STABLE_TOP_CLUSTER"): hard_score+=2

    if dstatus=="LOW" and volatile_score>=hard_score:
        regime="PASS_BIASED"
        target_points="0-6"
        policy="軸なし点数を増やして救済しない。軸耐久不足ならPASSを優先し、買う場合も根拠のある役割分散だけに限定。"
    elif hard_score>=volatile_score+4:
        regime="CONCENTRATED"
        target_points="3-5"
        policy="固い構造。上位の重複組合せへ絞り、点数を減らす。市場レイヤーでトリガミ/低EVなら買わない。正のEVなら少点数を厚くする候補。"
    elif volatile_score>=hard_score+3:
        regime="HIGH_PAYOUT_CAPTURE"
        target_points="7-10"
        policy="荒れ構造。万馬券級の捕捉を優先するが、軸飛び保険を機械的に足さず、展開・条件・3着侵入の異なる役割を持つ組合せへ配分。"
    else:
        regime="BALANCED"
        target_points="5-8"
        policy="標準構造。現行点数を基準に、候補内組合せ漏れを減らす範囲で入替する。"

    return {
      "status":"RESEARCH_ONLY",
      "architecture":"TICKET_VALUE_REGIME_SHADOW_V3_CAUTION_INTRUSION_GATED",
      "regime":regime,
      "hard_score":hard_score,
      "volatile_score":volatile_score,
      "target_points":target_points,
      "reason":reasons,
      "proposed_policy":policy,
      "axis_objective":"軸は1着精度ではなく3着内残存率を最上位KPIとする",
      "scenario_learning":"結果後にコーナー通過順から、想定通り3着内／想定外で3着内／想定通り圏外／想定外圏外を分離",
      "longshot_objective":"3連複払戻10,000円以上の捕捉率を主要KPIとして追跡",
      "anti_trigami_rule":"券種別実オッズ接続後は、想定払戻が総投資以下または期待値不足の買い目を購入しない",
      "axis_fail_rule":"軸飛び対策のためだけの軸なし点数増加は禁止。軸耐久不足はPASS/非固定軸構造で処理",
      "intrusion_replacement_rule":"低順位3着侵入候補による既存券の1点入替はC/CAUTION系Shadowだけで検証。BUY/固い側の既存券は崩さない",
      "pass_rescue_rule":"PASS救済は8月検証で日別ばらつきが大きく、現時点では採用しない。PASSを機械的に購入へ戻さない",
      "non_manbaken_target":"実払戻10,000円以上のレースを投資・払戻とも除外したROI 80〜90%の安定を主要昇格条件にする",
      "data_limit_note":"過去封印ranked_snapshotは上位10頭保存のため、実頭数別・11位以下侵入の学習には使わない",
      "production_override_applied":False,
      "promotion_rule":"独立検証3回以上（推奨5回）で、軸3着内率・万馬券捕捉率・ROI・万馬券除外ROIを改善し、平均点数を悪化させず、固い群の的中率を毀損しない場合のみ昇格候補",
      "market_isolation":"NO_ODDS_OR_POPULARITY_USED"
    }
