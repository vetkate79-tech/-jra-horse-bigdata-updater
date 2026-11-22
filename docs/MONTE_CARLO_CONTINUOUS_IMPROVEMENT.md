# Monte Carlo continuous improvement policy

## Production baseline
- V2 race-wide evidence shrinkage is default (JRA_MONTE_CARLO_EXPERIMENT=1).
- Emergency rollback to V1: set JRA_MONTE_CARLO_EXPERIMENT=0. Preserve original sealed predictions.
- Record actual model version, run count, seed, pre-race input cutoff and prediction hash.

## Mandatory change cycle
1. Freeze pre-race inputs and record cutoff, race ID, model version, commit and input hash.
2. Run deterministic regression tests: sparse/full/equal data, probability invariants, ranking, repeatability and market/result isolation.
3. Replay baseline and candidate on identical strictly pre-race snapshots.
4. Evaluate walk-forward holdout: top-3 Brier score, calibration, axis hit rate, race selection coverage and actual net ROI. Segment by race type and data coverage.
5. Promote future challengers only after measured out-of-sample improvement and no material regression.
6. Archive counterexamples and revert instructions. Never overwrite frozen predictions.

## Safety gates
- Never feed odds, popularity, post-race results or future starts into pure simulation.
- Reject incomplete runner sets and duplicate horse IDs.
- Verify 0<=win<=place<=top3<=1 and sums win=1, place=2, top3=3 within rounding.
- Separate code commit, CI success, published data and live website verification.
- Lower probability concentration alone does not establish better accuracy.