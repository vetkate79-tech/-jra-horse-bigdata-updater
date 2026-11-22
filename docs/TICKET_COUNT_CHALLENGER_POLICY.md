# Ticket-count challenger policy (2026-11-22)

## Goal
Improve stable realized ROI and reduce drawdowns without discarding high-payout capture. Ticket expansion alone is not evidence of improvement.

## Champion and challengers
- Champion: existing published trio ticket generator, unchanged.
- B: 10-12 tickets; C: adaptive 5-15 tickets (preferred hypothesis); D: adaptive 7-20 tickets.
- Include PASS for races where coverage or expected payout is insufficient.
- Preserve axis-free tickets where justified by measured axis-failure risk, and third-place intrusion coverage.

## Strict replay design
1. Reconstruct each race from immutable pre-start sealed snapshot. Record seal timestamp, race ID, runner set, model version and commit hash.
2. Do not use odds, popularity, payout or results to rank horses or generate pre-race candidate tickets. Post-seal odds may only be used for a separately audited value/purchase decision.
3. Generate each challenger from identical pre-start inputs, with identical available budget and denomination constraints. Also report fixed 100-yen-per-ticket comparison separately.
4. Never manufacture missing predictions or pretend an ungenerated extra ticket was a historical selection. For historical snapshots without the necessary per-horse simulation outputs, mark INELIGIBLE.
5. Compare race-by-race realized stake, return, hit rate, ROI, largest-payout-excluded ROI, drawdown, losing streak, axis top-3 hit rate, partner capture, third-place intrusion and high-payout capture.
6. Use chronological walk-forward splits; avoid selecting a winner on the evaluation period. Require repeated nonoverlapping 36R windows and at least one independent 100R evaluation before production promotion.
7. Preserve all losing races and no-bet decisions; never select only favorable race subsets.
8. Promote a challenger only if independently verified net ROI and drawdown improve without a material high-payout capture regression. Otherwise keep Champion.

## Rollout and governance
- This document authorizes evaluation only; it does not silently change production ticket counts, public UI or sealed past predictions.
- Report separate states for code written, tests passed, workflow completed, results validated and published.
- Archive experiment configurations and rejected alternatives. One mechanism change per experiment.
- V2 Monte Carlo remains the active probability model; ticket-count comparison is a separate challenger mechanism.