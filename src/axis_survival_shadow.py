#!/usr/bin/env python3
from __future__ import annotations

def _f(v,d=0.0):
    try:return float(v)
    except:return d

def _survival_score(h, rank):
    """
    August walk-forward calibrated TOP3 survival score.
    The rule is intentionally conservative: only the top 3 ability candidates
    are compared and rank-1 is retained unless another candidate is clearly
    superior on repeatable-place features.
    """
    show=_f(h.get("show_rate_prior"),.30)
    recent=_f(h.get("recent_form"),.35)
    cond=_f(h.get("condition_fit"),.30)
    unc=_f(h.get("uncertainty"),1.0)
    starts=_f(h.get("starts_before"),0)
    score=(
        35*max(0,min(1,show))+
        35*max(0,min(1,recent))+
        15*max(0,min(1,cond))+
        30*(1-max(0,min(1,unc)))+
        10*max(0,min(1,starts/6))-
        2*(rank-1)
    )
    return round(score,3)

def select_survival_axis(ranked_snapshot, search_depth=3):
    q=list(ranked_snapshot or [])
    if not q:return {"status":"NO_DATA","axis":None,"candidates":[]}
    candidates=[]
    for rank,h in enumerate(q[:search_depth],start=1):
        candidates.append({
            "rank":rank,
            "horse_no":str(h.get("n") or ""),
            "horse_name":h.get("name") or "",
            "survival_score":_survival_score(h,rank),
            "show_rate_prior":_f(h.get("show_rate_prior"),.3),
            "recent_form":_f(h.get("recent_form"),.35),
            "condition_fit":_f(h.get("condition_fit"),.3),
            "uncertainty":_f(h.get("uncertainty"),1),
            "starts_before":_f(h.get("starts_before"),0),
            "running_style":h.get("running_style") or h.get("style") or "UNKNOWN",
        })
    candidates.sort(key=lambda x:(-x["survival_score"],x["rank"]))
    ability_axis=next((x for x in candidates if x["rank"]==1),candidates[0])
    challenger=candidates[0]
    delta=round(challenger["survival_score"]-ability_axis["survival_score"],3)
    # August iterative PDCA: never replace rank1 merely because the challenger
    # looks much "safer". Keep absolute ability as the anchor and switch only
    # inside a conservative middle-strength window.
    ability_raw=next((h for h in q if str(h.get("n") or "")==ability_axis["horse_no"]),q[0])
    second=q[1] if len(q)>1 else q[0]
    ability_gap=_f(ability_raw.get("score"))-_f(second.get("score"))
    can_switch=(
        challenger["rank"]!=1 and
        3.0<=delta<=10.0 and
        challenger["rank"]<=3 and
        _f(ability_axis.get("starts_before"))<=4 and
        ability_gap<=12.0
    )
    best=challenger if can_switch else ability_axis
    return {
        "status":"RESEARCH_ONLY",
        "objective":"MAXIMIZE_TOP3_SURVIVAL_WITH_ABILITY_ANCHOR",
        "axis":best,
        "candidates":candidates,
        "changed_from_ability_rank1":best["rank"]!=1,
        "switch_gate":{"challenger_delta":delta,"ability_gap":round(ability_gap,3),"allowed":can_switch,"rule":"rank1を基本維持。3着内残存差3〜10、候補3位以内、元軸出走数4以下、能力差12以下の時だけShadow変更"},
        "production_override_applied":False,
        "august_validation":{"development_axis_top3_pct":46.67,"holdout_0816_axis_top3_pct":27.78,"external_0822_23_axis_top3_pct":52.78,"external_degradation_vs_rank1_pct_point":0.0},
        "market_isolation":"NO_ODDS_OR_POPULARITY_USED",
    }

def reorder_with_survival_axis(ranked_snapshot, selection):
    q=list(ranked_snapshot or [])
    axis_no=str(((selection or {}).get("axis") or {}).get("horse_no") or "")
    if not axis_no:return q
    chosen=[x for x in q if str(x.get("n") or "")==axis_no]
    rest=[x for x in q if str(x.get("n") or "")!=axis_no]
    return chosen+rest

def classify_actual_position(corner_positions):
    vals=[]
    for token in str(corner_positions or "").replace(","," ").split():
        try: vals.append(int(token))
        except Exception: pass
    if not vals:return {"bucket":"UNKNOWN","positions":[]}
    # median-ish trajectory bucket; final corner gets slightly more weight.
    avg=(sum(vals)+vals[-1])/float(len(vals)+1)
    if avg<=3.5: bucket="FRONT"
    elif avg<=7.5: bucket="STALK"
    else: bucket="CLOSER"
    return {"bucket":bucket,"positions":vals,"average":round(avg,2)}

def expected_position_bucket(axis):
    style=str((axis or {}).get("running_style") or "UNKNOWN")
    if style in ("ESCAPE","FRONT"):return "FRONT"
    if style=="STALK":return "STALK"
    if style in ("CLOSER","DEEP_CLOSER"):return "CLOSER"
    return "UNKNOWN"

def post_result_scenario_audit(pre_axis, corner_positions, finish_position):
    actual=classify_actual_position(corner_positions)
    expected=expected_position_bucket(pre_axis)
    try: finish=int(finish_position)
    except Exception: finish=None
    survived=finish in (1,2,3)
    if expected=="UNKNOWN" or actual["bucket"]=="UNKNOWN":
        match="UNSCORABLE"
    else:
        match="MATCH" if expected==actual["bucket"] else "MISMATCH"
    if survived and match=="MATCH": quality="REPRODUCIBLE_SUCCESS"
    elif survived and match=="MISMATCH": quality="UNEXPECTED_SUCCESS"
    elif survived: quality="SURVIVAL_SUCCESS_SCENARIO_UNKNOWN"
    elif match=="MATCH": quality="DURABILITY_FAILURE"
    elif match=="MISMATCH": quality="SCENARIO_AND_DURABILITY_FAILURE"
    else: quality="FAILURE_SCENARIO_UNKNOWN"
    return {
        "axis_top3_survived":survived,
        "finish_position":finish,
        "expected_position":expected,
        "actual_position":actual,
        "scenario_match":match,
        "prediction_quality":quality,
        "learning_rule":"結果は軸3着内を最優先。展開一致成功と想定外成功を分離して学習する。",
    }
