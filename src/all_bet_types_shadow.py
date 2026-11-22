#!/usr/bin/env python3
"""Odds-free joint ticket probabilities from sealed Monte Carlo top-three outcomes.

SHADOW ONLY: no production bet selection, odds retrieval or ROI claim.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Mapping


def ticket_probabilities(ordered_counts: Mapping[str, int], runs: int, place_positions: int = 3) -> dict:
    """Compute exact joint hit rates from ordered top-3 outcome counts.

    Counts keys are 'first-second-third' horse numbers; horses cannot repeat.
    PLACE payout position is 2 for 4-7 starters, 3 for >=8; 3 starters
    are unsupported here until official settlement rules are supplied.
    """
    if runs <= 0 or place_positions not in (2, 3):
        raise ValueError("invalid runs/place_positions")
    totals = {k: defaultdict(int) for k in ("WIN", "PLACE", "WIDE", "QUINELLA", "EXACTA", "TRIO", "TRIFECTA")}
    counted = 0
    for key, raw in ordered_counts.items():
        a = tuple(key.split("-"))
        if len(a) != 3 or len(set(a)) != 3 or not all(a):
            raise ValueError("invalid ordered finish: " + key)
        n = int(raw)
        if n < 0:
            raise ValueError("negative count")
        counted += n
        if not n:
            continue
        x, y, z = a
        totals["WIN"][x] += n
        for h in a[:place_positions]:
            totals["PLACE"][h] += n
        for pair in combinations(a[:place_positions], 2):
            totals["WIDE"]["-".join(sorted(pair, key=lambda v: int(v)))] += n
        totals["QUINELLA"]["-".join(sorted((x, y), key=int))] += n
        totals["EXACTA"][x + "-" + y] += n
        totals["TRIO"]["-".join(sorted(a, key=int))] += n
        totals["TRIFECTA"][key] += n
    if counted != runs:
        raise ValueError("counts do not sum to runs")
    return {kind: {key: count / runs for key, count in sorted(values.items())}
            for kind, values in totals.items()}


def quote_ev(probability: float, decimal_odds: float | None) -> dict:
    """Gross expected return and net ROI per unit stake; no quote means no EV."""
    if not 0 <= probability <= 1:
        raise ValueError("invalid probability")
    if decimal_odds is None:
        return {"status": "EV_UNAVAILABLE", "gross_roi": None, "net_ev": None}
    if decimal_odds < 1:
        raise ValueError("invalid odds")
    gross = probability * decimal_odds
    return {"status": "QUOTED", "gross_roi": gross, "net_ev": gross - 1}


def test_joint_example() -> None:
    counts = {"1-2-3": 6, "3-1-2": 4}
    p = ticket_probabilities(counts, 10, 3)
    assert p["WIN"]["1"] == 0.6
    assert p["WIN"]["3"] == 0.4
    assert p["TRIO"]["1-2-3"] == 1.0
    assert p["TRIFECTA"]["1-2-3"] == 0.6
    assert p["QUINELLA"]["1-2"] == 0.6
    assert p["WIDE"]["1-3"] == 1.0
    assert abs(quote_ev(0.2, 8)["net_ev"] - 0.6) < 1e-12
    assert quote_ev(0.2, None)["status"] == "EV_UNAVAILABLE"


if __name__ == "__main__":
    test_joint_example()
    print("joint-probability smoke test PASS")
