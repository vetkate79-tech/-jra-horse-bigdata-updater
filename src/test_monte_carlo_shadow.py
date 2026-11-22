#!/usr/bin/env python3
"""Deterministic shadow comparison; no market or result features."""
import os
from monte_carlo_finalizer import simulate_race

race={"race_id":"MONTE_CARLO_SHADOW_SMOKE","date":"2026-11-22","track":"TEST","race_no":1}
horses=[]
for i in range(1,13):
    horses.append({"n":str(i),"name":f"test{i}","score":70-i*3,
        "starts_before":0 if i<=3 else 6,
        "uncertainty":0.9 if i<=3 else 0.15,
        "running_style":"STALK" if i%2 else "CLOSER",
        "show_rate_prior":None if i<=3 else 0.3,
        "recent_form":None if i<=3 else 0.35,
        "condition_fit":None if i<=3 else 0.3,
        "draw_show_prior":None if i<=3 else 0.3})
os.environ["JRA_SIMULATION_RUNS"]="10000"
os.environ["JRA_MONTE_CARLO_EXPERIMENT"]="0"
baseline=simulate_race(race,horses)
os.environ["JRA_MONTE_CARLO_EXPERIMENT"]="1"
challenger=simulate_race(race,horses)
def rate(result,no):
    return next(x["top3_rate"] for x in result["horse_probabilities"] if x["horse_no"]==no)
assert baseline["experiment_enabled"] is False
assert challenger["experiment_enabled"] is True
assert baseline["model_version"]!=challenger["model_version"]
assert challenger["evidence_reliability"]["1"]<challenger["evidence_reliability"]["12"]
assert rate(challenger,"1")<rate(baseline,"1"),(rate(baseline,"1"),rate(challenger,"1"))
# Race-wide shrinkage must preserve base-strength order.
from monte_carlo_finalizer import _base_strength, _coverage_strength
import numpy as np
strength=_base_strength(horses)
shrunk,reliability=_coverage_strength(horses,strength)
assert np.array_equal(np.argsort(strength),np.argsort(shrunk))
assert 0 < reliability.min() <= reliability.max() <= 1

for result in (baseline,challenger):
    assert abs(sum(h["top3_rate"] for h in result["horse_probabilities"])-3)<0.0001
print({"baseline_top3_1":rate(baseline,"1"),"challenger_top3_1":rate(challenger,"1"),"shadow":"PASS"})

for label in ("full","sparse","equal"):
    case=[dict(h) for h in horses]
    for h in case:
        h["starts_before"]=6 if label=="full" else 0
        h["uncertainty"]=0.1 if label=="full" else 0.9
        if label=="equal": h["score"]=50
        if label=="sparse":
            for k in ("show_rate_prior","recent_form","condition_fit","draw_show_prior"):
                h[k]=None
    os.environ["JRA_MONTE_CARLO_EXPERIMENT"]="1"
    one=simulate_race({**race,"race_id":label},case)
    two=simulate_race({**race,"race_id":label},case)
    assert one["horse_probabilities"]==two["horse_probabilities"],label
    assert abs(sum(h["top3_rate"] for h in one["horse_probabilities"])-3)<0.0001,label
    assert all(0<=h["win_rate"]<=h["place_rate"]<=h["top3_rate"]<=1 for h in one["horse_probabilities"]),label
print("MULTI_CASE_SHADOW_TESTS_PASS")
