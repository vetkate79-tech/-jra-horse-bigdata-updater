#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import math
import os
from typing import Any

import numpy as np

MODEL_VERSION = "MONTE_CARLO_FINALIZER_V1"
DEFAULT_RUNS = 100_000
MIN_RUNS = 10_000
MAX_RUNS = 500_000
CHUNK_SIZE = 20_000

SCENARIOS = (
    "SLOW_FRONT",
    "AVERAGE",
    "FAST_BALANCED",
    "FAST_CLOSER",
    "EXTREME_COLLAPSE",
)

STYLE_BONUS = {
    "SLOW_FRONT": {"FRONT": 0.42, "PRESS": 0.24, "MID": -0.05, "CLOSER": -0.18, "UNKNOWN": 0.0},
    "AVERAGE": {"FRONT": 0.12, "PRESS": 0.15, "MID": 0.08, "CLOSER": 0.02, "UNKNOWN": 0.0},
    "FAST_BALANCED": {"FRONT": -0.10, "PRESS": 0.04, "MID": 0.18, "CLOSER": 0.20, "UNKNOWN": 0.0},
    "FAST_CLOSER": {"FRONT": -0.32, "PRESS": -0.08, "MID": 0.22, "CLOSER": 0.40, "UNKNOWN": 0.0},
    "EXTREME_COLLAPSE": {"FRONT": -0.58, "PRESS": -0.26, "MID": 0.24, "CLOSER": 0.56, "UNKNOWN": 0.0},
}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _style(value: Any) -> str:
    s = str(value or "").upper()
    if any(x in s for x in ("逃", "FRONT", "LEAD")):
        return "FRONT"
    if any(x in s for x in ("先", "PRESS", "STALK")):
        return "PRESS"
    if any(x in s for x in ("差", "MID")):
        return "MID"
    if any(x in s for x in ("追", "CLOS", "DEEP")):
        return "CLOSER"
    return "UNKNOWN"


def _scenario_weights(horses: list[dict[str, Any]]) -> np.ndarray:
    styles = [_style(h.get("running_style")) for h in horses]
    front = sum(s in ("FRONT", "PRESS") for s in styles)
    n = max(1, len(styles))
    pressure = front / n
    if pressure >= 0.50:
        w = np.array([0.08, 0.18, 0.28, 0.30, 0.16], dtype=float)
    elif pressure >= 0.34:
        w = np.array([0.14, 0.27, 0.30, 0.21, 0.08], dtype=float)
    else:
        w = np.array([0.28, 0.34, 0.23, 0.11, 0.04], dtype=float)
    return w / w.sum()


def _runs() -> int:
    try:
        value = int(os.getenv("JRA_SIMULATION_RUNS") or DEFAULT_RUNS)
    except Exception:
        value = DEFAULT_RUNS
    return max(MIN_RUNS, min(MAX_RUNS, value))


def _seed(race: dict[str, Any]) -> int:
    material = "|".join(
        [
            MODEL_VERSION,
            str(race.get("race_id") or ""),
            str(race.get("date") or ""),
            str(race.get("track") or ""),
            str(race.get("race_no") or ""),
        ]
    )
    return int(hashlib.sha256(material.encode("utf-8")).hexdigest()[:16], 16) % (2**32)


def _base_strength(horses: list[dict[str, Any]]) -> np.ndarray:
    score = np.array([_num(h.get("score")) for h in horses], dtype=float)
    if np.ptp(score) > 1e-9:
        score_z = (score - score.mean()) / max(score.std(), 1e-6)
    else:
        score_z = np.zeros_like(score)

    show = np.array([_num(h.get("show_rate_prior"), 0.30) for h in horses], dtype=float)
    recent = np.array([_num(h.get("recent_form"), 0.35) for h in horses], dtype=float)
    condition = np.array([_num(h.get("condition_fit"), 0.30) for h in horses], dtype=float)
    draw = np.array([_num(h.get("draw_show_prior"), 0.30) for h in horses], dtype=float)

    strength = (
        1.00 * score_z
        + 0.34 * np.clip((show - 0.30) / 0.20, -1.5, 1.5)
        + 0.20 * np.clip((recent - 0.35) / 0.20, -1.5, 1.5)
        + 0.16 * np.clip((condition - 0.30) / 0.20, -1.5, 1.5)
        + 0.10 * np.clip((draw - 0.30) / 0.15, -1.5, 1.5)
    )

    weights = np.array([_num(h.get("carried_weight"), math.nan) for h in horses], dtype=float)
    finite = np.isfinite(weights)
    if finite.any():
        median = float(np.median(weights[finite]))
        strength += np.where(finite, np.clip((median - weights) * 0.055, -0.25, 0.25), 0.0)

    return strength


def simulate_race(race: dict[str, Any], horses: list[dict[str, Any]]) -> dict[str, Any]:
    if len(horses) < 3:
        raise ValueError("simulation requires at least three horses")

    runs = _runs()
    seed = _seed(race)
    rng = np.random.default_rng(seed)
    n = len(horses)
    styles = [_style(h.get("running_style")) for h in horses]
    scenario_weights = _scenario_weights(horses)
    base_strength = _base_strength(horses)

    uncertainty = np.array([_num(h.get("uncertainty"), 0.5) for h in horses], dtype=float)
    starts = np.array([_num(h.get("starts_before"), 0.0) for h in horses], dtype=float)
    noise_sigma = 0.62 + 0.72 * np.clip(uncertainty, 0.0, 1.25) + np.where(starts < 3, 0.18, 0.0)

    win = np.zeros(n, dtype=np.int64)
    second = np.zeros(n, dtype=np.int64)
    top3 = np.zeros(n, dtype=np.int64)
    scenario_top3 = np.zeros((len(SCENARIOS), n), dtype=np.int64)
    scenario_counts = np.zeros(len(SCENARIOS), dtype=np.int64)

    remaining = runs
    while remaining:
        m = min(CHUNK_SIZE, remaining)
        scenario_idx = rng.choice(len(SCENARIOS), size=m, p=scenario_weights)
        perf = np.broadcast_to(base_strength, (m, n)).copy()
        for si, scenario in enumerate(SCENARIOS):
            mask = scenario_idx == si
            count = int(mask.sum())
            if count == 0:
                continue
            scenario_counts[si] += count
            bonus = np.array([STYLE_BONUS[scenario][s] for s in styles], dtype=float)
            perf[mask] += bonus

        perf += rng.normal(0.0, noise_sigma, size=(m, n))
        top = np.argpartition(-perf, kth=2, axis=1)[:, :3]
        top_scores = np.take_along_axis(perf, top, axis=1)
        top_order = np.argsort(-top_scores, axis=1)
        ordered = np.take_along_axis(top, top_order, axis=1)

        np.add.at(win, ordered[:, 0], 1)
        np.add.at(second, ordered[:, 1], 1)
        for pos in range(3):
            np.add.at(top3, ordered[:, pos], 1)

        for si in range(len(SCENARIOS)):
            mask = scenario_idx == si
            if not mask.any():
                continue
            subset = ordered[mask]
            for pos in range(3):
                np.add.at(scenario_top3[si], subset[:, pos], 1)

        remaining -= m

    win_p = win / runs
    place_p = (win + second) / runs
    top3_p = top3 / runs
    final_index = 0.55 * top3_p + 0.25 * win_p + 0.20 * place_p

    scenario_probs = np.zeros_like(scenario_top3, dtype=float)
    for si, count in enumerate(scenario_counts):
        if count:
            scenario_probs[si] = scenario_top3[si] / count

    horse_rows = []
    for i, horse in enumerate(horses):
        vals = scenario_probs[:, i]
        mean = float(vals.mean())
        dispersion = float(vals.std())
        stability = max(0.0, min(1.0, 1.0 - dispersion / max(mean, 0.08)))
        horse_rows.append(
            {
                "horse_no": str(horse.get("n") or ""),
                "horse_name": horse.get("name") or "",
                "win_rate": round(float(win_p[i]), 6),
                "place_rate": round(float(place_p[i]), 6),
                "top3_rate": round(float(top3_p[i]), 6),
                "final_index": round(float(final_index[i]), 6),
                "scenario_stability": round(stability, 6),
                "scenario_top3": {
                    SCENARIOS[si]: round(float(scenario_probs[si, i]), 6)
                    for si in range(len(SCENARIOS))
                },
            }
        )

    order = sorted(
        range(n),
        key=lambda i: (-final_index[i], -top3_p[i], -win_p[i], int(horses[i]["n"]) if str(horses[i].get("n") or "").isdigit() else 999),
    )
    rank_map = {str(horses[i].get("n") or ""): rank for rank, i in enumerate(order, start=1)}
    rows_by_no = {r["horse_no"]: r for r in horse_rows}

    finalized = []
    for horse in horses:
        h = dict(horse)
        no = str(h.get("n") or "")
        h["simulation"] = {**rows_by_no[no], "final_rank": rank_map[no]}
        finalized.append(h)
    finalized.sort(key=lambda h: h["simulation"]["final_rank"])

    top5 = finalized[: min(5, len(finalized))]
    overall_stability = float(np.mean([h["simulation"]["scenario_stability"] for h in top5])) if top5 else 0.0

    return {
        "model_version": MODEL_VERSION,
        "runs": runs,
        "seed": seed,
        "market_isolation": "NO_ODDS_OR_POPULARITY_OR_RESULTS_USED",
        "scenario_weights": {SCENARIOS[i]: round(float(scenario_weights[i]), 6) for i in range(len(SCENARIOS))},
        "scenario_counts": {SCENARIOS[i]: int(scenario_counts[i]) for i in range(len(SCENARIOS))},
        "rank_stability_top5": round(overall_stability, 6),
        "finalized_ranked_snapshot": finalized,
        "horse_probabilities": [h["simulation"] for h in finalized],
        "input_coverage": {
            "running_style_known": sum(_style(h.get("running_style")) != "UNKNOWN" for h in horses),
            "carried_weight_known": sum(math.isfinite(_num(h.get("carried_weight"), math.nan)) for h in horses),
            "draw_prior_known": sum(h.get("draw_show_prior") is not None for h in horses),
            "starts_known": sum(h.get("starts_before") is not None for h in horses),
        },
        "finalization_rule": "0.55*top3_rate + 0.25*win_rate + 0.20*place_rate; simulation is the final ranking gate before sealing",
    }


def finalize_ranking(race: dict[str, Any], horses: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    summary = simulate_race(race, horses)
    return list(summary["finalized_ranked_snapshot"]), {k: v for k, v in summary.items() if k != "finalized_ranked_snapshot"}
