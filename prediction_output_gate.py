"""Fail-closed gate for publishing official race predictions.

This module is deliberately independent of the model: it only verifies a
signed-off execution envelope. Call validate_official_prediction immediately
before rendering/publishing. Do not fall back to LLM-generated rankings.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping

class PredictionBlocked(ValueError):
    pass

@dataclass(frozen=True)
class VerifiedPrediction:
    race_id: str
    run_id: str
    model_version: str
    payload: Mapping[str, Any]

def _require(value: Any, label: str) -> None:
    if value is None or value == "" or value == [] or value == {}:
        raise PredictionBlocked(f"missing {label}")

def validate_official_prediction(
    envelope: Mapping[str, Any], *, expected_race_id: str,
    expected_runners: set[str], verified_run_ids: set[str]
) -> VerifiedPrediction:
    """Reject missing, stale, incomplete, or internally inconsistent results.

    verified_run_ids must be populated from the trusted GitHub Actions /
    execution-log verifier, never from user text or an LLM response.
    """
    for field in ("race_id", "run_id", "model_version", "input_hash",
                  "model_hash", "status", "runners", "scenarios", "tickets"):
        _require(envelope.get(field), field)
    if envelope["race_id"] != expected_race_id:
        raise PredictionBlocked("race mismatch")
    if str(envelope["run_id"]) not in verified_run_ids:
        raise PredictionBlocked("unverified execution")
    if envelope["status"] != "success":
        raise PredictionBlocked("execution failed")
    runners = envelope["runners"]
    if not isinstance(runners, list) or len(runners) != len(expected_runners):
        raise PredictionBlocked("runner count mismatch")
    ids = [str(r.get("horse_id", "")) for r in runners if isinstance(r, dict)]
    if len(ids) != len(runners) or len(set(ids)) != len(ids) or set(ids) != expected_runners:
        raise PredictionBlocked("runner identities mismatch")
    for runner in runners:
        _require(runner.get("ability_score"), "ability score")
        if not isinstance(runner["ability_score"], (int, float)) or isinstance(runner["ability_score"], bool):
            raise PredictionBlocked("non-numeric ability score")
    scenarios = envelope["scenarios"]
    if not isinstance(scenarios, list) or len(scenarios) < 2:
        raise PredictionBlocked("missing multi-scenario analysis")
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise PredictionBlocked("invalid scenario")
        _require(scenario.get("name"), "scenario name")
        _require(scenario.get("results"), "scenario results")
    tickets = envelope["tickets"]
    if not isinstance(tickets, list):
        raise PredictionBlocked("invalid tickets")
    for ticket in tickets:
        horses = ticket.get("horses") if isinstance(ticket, dict) else None
        if not isinstance(horses, list) or len(horses) != 3 or len(set(horses)) != 3:
            raise PredictionBlocked("invalid trifecta combination")
        if not set(map(str, horses)).issubset(expected_runners):
            raise PredictionBlocked("ticket includes non-runner")
    if envelope.get("scratch_status") != "verified":
        raise PredictionBlocked("scratches not verified")
    if envelope.get("input_time_verified") is not True:
        raise PredictionBlocked("pre-race feature time not verified")
    return VerifiedPrediction(expected_race_id, str(envelope["run_id"]),
                              str(envelope["model_version"]), envelope)
