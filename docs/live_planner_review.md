# Live planner review — 4 October 2026

## Findings fixed

- The transfer optimiser already subtracts each hit from `net_score`. The HQ table was displaying `scenario.gain` as gross gain, then subtracting the hit again for net gain. A raw improvement of 10 with a 4-point hit must show gross +10 and net +6, not gross +6 and net +2. This was a display bug; optimiser choice scores did not change.
- The saved weekly report had no generation time or expiry reminder. Add generation time and a 30-minute review reminder; older reports without a timestamp remain readable but request refresh. Recompute the deadline lock at page-serving time rather than retaining an old unlocked flag.
- Explicit refresh previously reused normal public caches and could silently use stale official fallback data. Weekly, chip planner and chip opportunity explicit refresh now require live bootstrap and fixture fetches first. Failed weekly refresh leaves the saved report/approval unchanged and returns a safe error message.
- Explain the objective: current XI projection plus position-weighted captain score plus 15% of all 15 players' five-Gameweek projections, minus hits. HOLD optimises the existing squad's lineup. These are comparison scores, not a forecast of the manager's weekly points.

## Review performed

Traced the HQ report builder, transfer optimiser objectives/constraints/scoring, captain score, chip cache/refresh entry points, chip HOLD/confidence gates and application validation entry point. Existing transfer constraints preserve squad size/positions/club limits and use selling prices for outgoing players. Non-selectable players may be retained but cannot be bought. Only optimal solver results are returned. Paid-transfer choice gates compare net scores; the twice-deducted hit was confined to the table.

Captain choice uses fixed position multipliers (FWD 1.15, MID 1.12, DEF 1.03, GKP 0.95) on projected points. Availability affects player projections. These weights and the chip confidence categories are heuristics, not calibrated probabilities. No weights, thresholds or chip production rules were changed.

## Pending Pi verification

1. Pull and restart `fpl-assistant` to load the web changes.
2. Refresh HQ analysis and run `python3 -m tools.review_weekly_report`.
3. Inspect explicitly refreshed Chips advice and Why explanations.
4. Check squad-specific transfer gains/hits, captain/vice availability and chip HOLD/later-window reasoning against that output.

The new command reads only the saved report, makes no API calls, does not import the Flask app or migrate SQLite, and omits credentials/entry IDs/raw player data. It reports generation freshness, bank/free transfers, transfer comparisons, captain/vice and squad availability flags. An old report is still reviewable, but refresh is required for meaningful current advice. The offline review cannot establish that the live squad matches it.

## Limits and next work

- The normal weekly comparison tests 0–3 transfers. It does not establish an optimum across every possible transfer count; revisit this if the supplied squad needs larger changes or has more banked free transfers.
- INCLUDE constraints can make a zero-transfer baseline infeasible; that future/generalised feature needs a defined baseline policy before exposure as incoming-player locks. Current KEEP controls are for owned players.
- The refresh fetches sequential responses and the calculations still use existing projection/depth-chart mechanisms. Generation time is not per-player provenance, and no new freshness guarantee is made for third-party depth charts.
- A saved report can become outdated when the squad, news, fixtures or prices change. The reminder does not automatically recompute on every page load or change application rules. Existing apply code checks the live planning GW/deadline and squad before submissions; no submissions were made during this review.
- Pi snapshot timer readiness is verified by supplied output. Four later GW6 checkpoints are correctly pending. Actual post-fix checkpoint captures remain to be observed.
- Historical hindsight contamination remains unresolved. Full reconstruction is deferred; it does not justify tuning live thresholds. After 4–5 complete live Gameweeks, review checkpoint changes and realised outcomes.
