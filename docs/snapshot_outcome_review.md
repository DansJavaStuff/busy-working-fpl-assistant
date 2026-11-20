# Reviewing snapshots against outcomes

Added 20 November 2026. This is a read-only report over the Pi's existing history database.
It never creates/migrates that database, reads credentials, reruns the optimiser, writes
app caches, submits FPL changes or changes projections/thresholds.

## Run on the Pi

```bash
cd ~/busy-working-fpl-assistant
git pull
sudo systemctl restart fpl-assistant
python3 -m tools.review_snapshot_outcomes --summary
python3 -m tools.review_snapshot_outcomes --fetch-outcomes --summary
```

The first command audits stored data offline. The second fetches the public FPL bootstrap
and event/live results for finished, data-checked events. Older seasons are not matched to
current-season player IDs. It caches responses in memory only, once per event per run.
No database backup/migration is required for these read-only commands.

Omit `--summary` for individual checkpoint records and all-player/previously-played error
metrics. Optional `--season 2026-27`, `--checkpoint t60m` and `--db PATH` filters are available.
`latest` is the default: select exactly one latest eligible capture for each entry/Gameweek.
A fixed checkpoint is useful when comparing weeks at the same lead time; missing checkpoints
are not replaced by a different label in that mode. Entry groups are local anonymous group
numbers, not official entry IDs. Empty weeks between the first and last stored captures for
an entry appear as gaps; weeks before collection began are not invented.

## Eligibility and timing

The report recalculates seconds before deadline from the snapshot timestamp and its captured
deadline. It checks the deadline against the captured bootstrap event, the season, future
capture times, the 15 unique owned IDs/positions, captain/vice, player IDs, teams and fixture
presence. The captured `is_next` event must explicitly match the recorded Gameweek before
`ep_next` can be evaluated. Stored `on_time`/`seconds_remaining` claims are not trusted.

A capture after the deadline, with invalid/missing required evaluation data, or with an
unverified prediction event is excluded. A valid pre-deadline capture outside its labelled
checkpoint window remains eligible but is labelled `outside_window`. Both stored counts and
eligible counts matter: five rows do not necessarily mean five usable checkpoints. Future
unstored checkpoints are pending; expired ones are missing. This checks evaluation inputs,
not the completeness of all external historical/depth-chart inputs needed for model replay.

## What the first evaluations measure

Older collector snapshots contain FPL bootstrap/fixtures, the current squad and entry data,
not the app's full historical projection pool or advice. Their evaluation measures:

- Captured FPL `ep_next` against actual event points.
- Captured PPG as a simple baseline, using exactly the same matched player IDs.
- MAE (average absolute error), bias (prediction minus actual), RMSE and matched/unmatched counts.
- Individual player returns for the recorded snapshot captain, the highest `ep_next` and PPG
  players in that snapshot's starting XI, and Haaland if in that XI. Forecast ties use lowest ID.

The full report provides all-player, previously-played-at-capture and owned-player cohorts.
Nonfinite/missing forecasts or missing result IDs are excluded, never filled with zero. Real
zero forecasts/results remain zero. A missing result is not evidence that the player scored
zero. Ranking a highest-forecast captain requires forecasts for the entire captured XI.
Captain comparisons never select using actual points or promote bench players in hindsight.

These captain figures are raw individual player points. They are not doubled team returns,
vice-captain fallback, auto-substitution, chip scoring or net transfer gains. Final submitted
picks may differ from the last snapshot. Transfer-plan multiweek outcomes and full model
variant replay are not implemented in this report. Do not interpret this as the app's
historical accuracy or a controlled old-model/new-model test.

Results are fetched only where current official `finished` AND `data_checked` are true.
They can still contain later scoring corrections, so source URL/retrieval time are reported.
Multiple checkpoints, overlapping players and multiple entries are not independent weeks.
Small samples are diagnostic; no statistical significance or accuracy-improvement claim.

## Saving app predictions from now on

The collector now also reads the existing `data/weekly_report.json` at capture time and
freezes a small, whitelisted advice record in the new snapshot's `app_advice` field. This
adds no API calls or optimiser work and does not alter earlier snapshots. The file must
have the same Gameweek and owned squad, a valid generation timestamp no later than capture,
and finite, consistent player projections. Otherwise a reason is recorded and collection
of raw inputs continues. Missing or malformed saved advice does not block collection.

The copied data include owned/recommended player GW projections, recommended/owned-only
captain IDs, generation age, schema, hit cost and transfer count. Approval data and other
unneeded report content are not copied. A model version is copied only if the report actually
records one; otherwise it stays null, rather than inventing provenance from current code.

Eligible new snapshots can report error for the saved owned-player app projections and
returns of the saved recommended/owned-only captains. Advice may predate the raw snapshot:
inspect `age_at_capture_seconds`. Comparing app errors to newer captured FPL estimates is
not a same-input controlled model comparison. This report does not reconstruct missing app
predictions or use today's historical priors, team strengths or depth charts retrospectively.

The service restart loads the updated collector for any in-process use; the timer's separate
Python invocation also picks it up on its next run. Refresh HQ advice before the checkpoint
if you want fresh app predictions captured. Existing raw-only weeks still have value for the
FPL-estimate baseline and capture-quality checks.
