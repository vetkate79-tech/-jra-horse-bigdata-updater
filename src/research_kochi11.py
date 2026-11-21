#!/usr/bin/env python3
"""Retrospective NAR research: actual historical card data, no market features.

Post-start acquisition is NEVER described as a sealed pre-race prediction.
"""
import json,sys
from pathlib import Path
from collections import defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_race_week_pre_race_features import feature_for,people_rates,draw_priors,merge_history
from run_nar_isolated import run

def main():
    if len(sys.argv)!=3:raise SystemExit("usage: research_kochi11.py parsed_history.json output.json")
    source=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    horses=source["horses"]
    if len(horses)!=11:raise ValueError(f"expected 11 runners, got {len(horses)}")
    cutoff="2026-11-21"
    race={"race_id":"202611213129100511","date":cutoff,"track":"高知","race_no":11,"surface":"ダート","distance_m":1300}
    all_hist=[]
    for h in horses:
        for row in h["recent_starts"]:
            if row["race_date"]>=cutoff:raise ValueError("target date leakage")
            all_hist.append(row)
    rates=people_rates(all_hist,cutoff);draw=draw_priors(all_hist)
    snapshot_horses=[]
    for i,h in enumerate(horses,1):
        hist=merge_history([],h["recent_starts"],cutoff)
        if not hist:raise ValueError("no past race for "+h["horse_name"])
        f=feature_for({"race":race,"jockey":"","trainer":"","frame_no":None},hist,rates,defaultdict(int),draw)
        snapshot_horses.append({"n":str(i),"name":h["horse_name"],"score":f["pre_race_score"],"score_provenance":"JRA_V4_TRANSFER_PRE_RACE_UNCALIBRATED","running_style":f["pre_race_running_style"],"show_rate_prior":f["show_rate_prior"],"recent_form":f["recent_form"],"condition_fit":f["condition_fit"],"uncertainty":f["uncertainty"],"starts_before":f["starts_before"]})
    snapshot={"source_type":"NAR","race_id":race["race_id"],"date":cutoff,"track":"高知","race_no":11,"horses":snapshot_horses,"model_calibration":"UNVALIDATED_NAR_TRANSFER"}
    result=run(snapshot)
    ranked=result["ability_ranked"]
    top=[int(x["horse_no"]) for x in ranked[:6]]
    axis=int(result["axis_shadow"]["axis"]["horse_no"])
    import itertools
    tickets=[list(sorted((axis,a,b))) for a,b in itertools.combinations([x for x in top if x!=axis],2)]
    result["research_row_index_combinations"]=tickets[:7]
    result["research_trifecta_box_selections"]=[]
    result["research_ticket_status"]="BLOCKED_UNVERIFIED_HORSE_NUMBERS_NO_BETTABLE_TICKETS"
    result["source_provenance"]="RAKUTEN_KEIBA_POST_START_FETCH_RETROSPECTIVE_ONLY"
    result["horse_number_mapping"]="PAGE_ROW_ORDER_ONLY_NOT_VERIFIED_HORSE_NUMBERS"
    result["warning"]="Research-only; no verified pre-start snapshot, not a formal live prediction"
    Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":result["status"],"ranked":result["ability_ranked"],"axis":result["axis_shadow"],"simulation":result["simulation"]},ensure_ascii=False)[:16000])
if __name__=="__main__":main()
