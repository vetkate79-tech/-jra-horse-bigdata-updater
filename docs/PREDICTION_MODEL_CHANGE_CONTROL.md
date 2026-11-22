# JRA prediction operations: immutable model boundary

## Non-negotiable rule (2026-11-22, user-approved)

Maintenance, operational recovery, data collection, reliability, deployment, publication, UI, performance, migration and monitoring MUST NOT change the substance of horse-racing predictions. This includes the model's scoring features, weights, algorithms, new-horse routing, scenario simulation, axis selection, partner and third-place roles, BUY/CAUTION/PASS logic, ticket construction, odds isolation and bankroll rules.

Prediction-method changes are allowed ONLY as a separately scoped **prediction-improvement** change, with explicit change purpose, reproducible before/after tests, out-of-sample checks, leakage checks and rollback path. Do not silently mix prediction improvements into operational repairs.

## Operations and reliability requirements

1. Read existing sealed predictions as the source of truth; never reconstruct scores from assistant intuition or market odds.
2. Keep original prediction artifacts and hashes. New read models are projections of the sealed output, not alternative scoring engines.
3. Validate all scheduled race dates, tracks, races, runners, score ordering, model routing, simulation provenance, and public availability before marking the workflow healthy.
4. Distinguish incomplete future race cards (e.g. unassigned horse numbers) from finalized race cards. Do not fabricate or fill blank numbers.
5. Fail closed and report missing/stale/inconsistent outputs. Never substitute another race or invented numbers.
6. Maintain a stable, machine-readable, all-race prediction feed and clear diagnostics for consumers. Publishing and retrieval must work without manually copying GitHub Actions logs.
7. Prefer root-cause repairs and regression tests over one-off date- or race-specific patches. Preserve existing interfaces and user-visible design unless explicitly authorized.
8. On every operational code change, verify that prediction outputs remain identical for identical frozen inputs; compare canonical sealed prediction hashes and representative race-level scores, ranks, axis, and tickets.
9. Do not modify existing prediction model source modules in operational-only PRs/commits. If a change must touch one, stop and isolate it as a separate, explicitly authorized prediction-improvement change.
10. Retain rollback-ready revisions, source provenance and deployment audit logs.

This policy applies to all subsequent maintenance work, including autonomous tasks and assistant-led changes.

## Mandatory JRA-project prediction answer contract (2026-11-22)

For EVERY JRA race requested through this project, the answer must start with the full-field ability ranking and show, for each horse, the sealed score (three decimals), win probability, top-two probability, top-three probability, and scenario stability. Include the five scenario-specific top-three probabilities when available; provide the sealed simulation run count, model version, axis and durability, pre-market BUY/CAUTION/PASS, formation, exact valid tickets and budget, and source/seal timestamp. All numeric rates must be copied from the sealed Monte Carlo output and labeled as model estimates, never implied to be empirical frequencies. Never fabricate a missing probability. If a compact publication projection omits any required field, retrieve the original sealed prediction or report the field unavailable and repair the projection. Do not alter scoring, ranking or simulation in a presentation/maintenance fix.
