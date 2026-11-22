# All-bet-types probability-first EV selection (approved 2026-11-22)

## Mandatory ordering
1. Freeze pre-start runner set and features; calculate V2 abilities and scenario Monte Carlo without odds or popularity.
2. Persist complete ordered finishing top-three outcomes per simulation, or sufficient joint counts. Current monte_carlo_finalizer.py only returns horse-level win/place/top3 marginals; these are NOT sufficient to calculate wide, quinella, exacta, trio or trifecta probabilities correctly.
3. Compute joint ticket hit probabilities for WIN, PLACE, WIDE, QUINELLA, EXACTA, TRIO and TRIFECTA; add bracket quinella if supported by verified race data. For PLACE handle runner-count-dependent payout places and scratches.
4. Freeze a pre-market shortlist and risk profile based on joint hit probability, coverage, calibration uncertainty, and ticket count. No market inputs in this stage.
5. Fetch timestamped official/current ticket-specific odds or payout ranges immediately before purchase. Mark unavailable or stale markets NO_QUOTE; never invent prices. For ranges, use conservative minimum odds.
6. Compute gross expected return as joint hit probability times decimal payout odds; net EV per unit stake equals gross expected return minus 1. Account for pari-mutuel price movement and uncertainty margin. If odds not verifiable, do not claim highest-EV ticket.
7. Compare candidate tickets AND portfolios under fixed total budgets, overlap correlation, drawdown, downside exposure and payout concentration. Select one or multiple bet types, or PASS when net EV does not exceed uncertainty and execution thresholds.
8. Log model version, pre-market snapshot hash, candidate ticket probabilities, market quote timestamps, selection, stakes, estimated EV, realized payouts, and no-bet reasons separately.

## Tests and release gates
- Joint probabilities from actual simulations, not multiplication of independent horse top3 marginals.
- Probability sum checks for ordered and unordered finishes; no duplicated horses in a ticket; proper payouts by field size.
- Odds fetched only after immutable pre-market probability calculation; never leak post-race outcomes into candidate generation.
- Chronological walk-forward testing with fixed stakes and all races, including PASS, using actual recorded odds available at decision time.
- Compare against current trio-only Champion on hit rate, realized ROI, ROI excluding largest payout, max drawdown, losing streak and high-payout capture.
- Keep public trio-only selection unchanged until code, tests, actual odds ingestion and independent holdout checks pass.
- A more accurate probability model is not by itself a profitable betting strategy; model error and fluctuating pari-mutuel payouts require safety margins.

## Implementation status
This is a design specification and authorization to build. It is not an assertion that all-bet-types probability simulation, live market odds ingestion, or production switching has been implemented.