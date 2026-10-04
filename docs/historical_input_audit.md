# Historical deadline-input audit

Audited 2026-10-04. Application baseline: PR #49 / `12d8775`. Source head inspected: `9779cdbc0c07f6c900c2d0c181ddf6bb9c800f88`.

## Verdict

**The current historical experiment is retrospective, not deadline-safe.** Source comparisons confirm both a fixture change unknowable at the target deadline and revisions to historical difficulty/team-strength values. Keeping `lookahead_safe = False` and the research HOLD is necessary. Existing correlations remain diagnostic; no replacement correlations or live thresholds were computed in this audit.

Scope: code-path inspection; latest file-change metadata for three input files across all five seasons; pinned fixture comparisons for 2023-24 GW17 and 2024-25 GW15; 2023-24 team-strength and FDR comparison; source update cadence. This is not an exhaustive audit of all 30 FH cases or a verification of the exact Pi database contents.

## Evidence table

| Input | Current handling | Audit status | Required change before deadline-safe evaluation |
|---|---|---|---|
| Fixture membership, blanks/doubles | One pinned source revision per import, applied to all historical weeks | **Confirmed retrospective source contamination**: Bournemouth–Luton reassigned after GW17 deadline | Use dated decision snapshots plus evidenced last-minute amendments; keep final fixtures separately for outcomes |
| Fixture difficulty | Stored from that same season file; reused across historical weeks | **Confirmed revisions**: 168 fixture rows differ between December and final 2023-24 versions | Freeze FDR as of each deadline, or use a prior-results-only alternative |
| Team strength / premium clubs | One season-wide team row; top six ranked by strength, ties by short name (or full name if missing) | **Confirmed revisions**: all 20 teams have a strength-related change; top-six membership changes | Use dated strength values; do not apply later ratings retrospectively |
| Form / past points and minutes | Query selects rows with Gameweek number less than target | **Partial safeguard only** | Verify observation times: earlier GW number does not prove all its fixtures finished before the target deadline; retain correction provenance |
| Ownership / price | Latest available row from an earlier GW, not a target-deadline snapshot | **Unknown capture timing / known lagged proxy** | Check original per-GW files, collection timing and revisions; label lagged values |
| Actual points | Used to score already selected squads; BB/TC remain ceilings | **Outcome data, intentionally retrospective** | Keep inaccessible to decision selection; apply historical scoring/auto-sub rules when testing real decisions |
| Source commit / import time | Import log stores resolved SHA; fixture `source_updated_at` receives current import time | **Reproducible import, not historical availability proof** | Separate import time, archive commit time and verified observation time; persist row/snapshot lineage |

## Confirmed case: Bournemouth–Luton, 2023-24 GW17

- Official FPL deadline: **2023-12-15 18:30 UTC** ([Premier League deadline article](https://www.premierleague.com/en/news/3790754)).
- Latest fixture-file commit before that deadline: `392588ec1664432358f9481b81c3a8c1d53a60a3`, **2023-12-11 13:35:55 UTC**. This is a four-day-old archive, not an exact deadline snapshot.
- At that revision, fixture **162** (Bournemouth home, Luton away) has `event=17.0`, kickoff **2023-12-16 15:00 UTC**. GW17 has **10 fixtures**.
- Final revision `204c134d8e90e2b6e69ec252aa3ef6f10f21e73c`: fixture **162** has `event=28`, kickoff **2024-03-13 19:30 UTC**. GW17 has **9 fixtures**.
- The match was abandoned after the deadline. On 20 December the Premier League announced the full replay and voiding of its GW17 FPL points ([official FPL outcome explanation](https://www.premierleague.com/en/news/3830180)).
- Therefore final-file GW17 Bournemouth/Luton blanks cannot be used as decision inputs. The current feature builder derives blanks and candidate weeks from final `event` assignments, so it can introduce an FH candidate that was absent from the scheduled slate at the deadline. Retaining zero realised points as outcome data is correct; removing the scheduled fixture from decision data is not.

## Archive freshness case: Everton–Liverpool, 2024-25 GW15

- Archive commit `651e9adea9e420416fdde96faf920de232383036`, **2024-12-07 01:35:27 UTC**, still schedules fixture **144** in GW15 at **12:30 UTC**. Its GW15 has **10 fixtures**.
- The official postponement announcement was on the morning of 7 December, **before the unchanged 11:00 UTC FPL deadline** ([Premier League statement](https://www.premierleague.com/es/news/4188928)). This is not a post-deadline leak example.
- Final revision `59c767596750f554ba464de94cf4fce8664a6cbe` assigns the match to GW24 and leaves **9 fixtures** in GW15.
- This demonstrates that the latest Git snapshot before a deadline can miss a real last-minute announcement. A blanket rule to use the last pre-deadline commit is insufficient. At T-60/T-15/T-10/T-5, availability must be checked against each cutoff, not simply the deadline date.

## Revised FDR and premium-team signal

Comparing the 2023-24 December fixture revision with the final fixture revision gives **168/380 rows** with changed home or away FDR. **72** of those rows are assigned to final GW1–16 (already completed by the December archive). For fixture **2**, the away difficulty changes **4 → 5**; fixture **8**, away difficulty changes **3 → 2**. A final historical CSV is not a record of the ratings at the time those matches occurred.

Team-file comparison: December commit `392588ec1664432358f9481b81c3a8c1d53a60a3` versus latest team-file change `446af195d2ee324a1217f34a5a2b591189efc983` (**2024-03-07**). All **20 teams** change at least one strength field. Using the application's top-six strength/short-name ordering:

- December: Man City, Arsenal, Liverpool, Man Utd, Newcastle, Aston Villa.
- Later file: Arsenal, Man City, Aston Villa, Liverpool, Spurs, Brighton.

The FH fixture signal includes premium-club blank share, so even its apparently simple fixture-only score depends on these later team ratings. BB/TC also consume premium-double share and FDR. This audit does not quantify the effect on their reported correlations.

## Five-season archive inventory

Latest commits touching each file at the inspected source head (not necessarily collection dates):

| Season | Fixtures | Teams | Merged player GWs |
|---|---|---|---|
| 2021-22 | 2022-05-23 | 2022-04-07 | 2022-08-02 |
| 2022-23 | 2023-05-29 | 2023-02-17 | 2023-06-15 |
| 2023-24 | 2024-05-27 | 2024-03-07 | 2024-05-27 |
| 2024-25 | 2025-06-04 | 2025-06-04 | 2026-01-02 |
| 2025-26 | 2026-06-17 | 2026-06-17 | 2026-06-17 |

Late file timestamps alone do not prove every field leaks future information. The row-level comparisons above establish the concrete changes; untouched fields remain unverified until checked.

The source [README](https://github.com/vaastav/Fantasy-Premier-League/blob/9779cdbc0c07f6c900c2d0c181ddf6bb9c800f88/README.md) announces reduced updates after 2024-25. The inspected 2025-26 fixture history has **12 changes**, including gaps from 1 November to 5 February and from 13 March to 17 June. Historical pre-deadline coverage cannot be assumed. It also flags potential `xP` look-ahead: our FH history query does not select `xP`, so that specific column is not the current projection input.

## Application paths inspected

- `historical_importer.py`: resolves `master` (or supplied ref) once; reads `teams.csv`/`fixtures.csv` at that SHA; overwrites season fixture/team rows without historical versions; passes import time as `source_updated_at`.
- `historical_outcome_importer.py`: reads `gws/merged_gw.csv`, preferably reusing a unique existing import SHA; aggregates per-player/GW rows.
- `historical_chip_features.py`: obtains all season fixtures/current stored team strength, then derives blank/double membership and top-six premium shares; no deadline timestamp constraint.
- `historical_realised_backtest.py`: `_load_predeadline_player_history` uses `gameweeks.gameweek < target`; `_load_team_fixture_projections` uses the stored fixture event and FDR; candidate cases are selected from retrospective feature rows. LOSO percentile training includes other seasons, including later ones, so it is not chronological validation.
- `history_store.py`: import logs retain SHAs/files but rows do not link to a distinct import revision. Multiple overlapping imports make the active row revision ambiguous from the log alone. `imported_at` is not the original data capture time.

## Read-only Pi verification

Run in the usual virtual environment after pulling this change:

```bash
cd ~/busy-working-fpl-assistant
git pull
python3 -m tools.audit_historical_input_provenance
```

The command prints only historical import metadata, deadline coverage and the two fixture cases. It opens SQLite with `mode=ro`, does not create a database, apply migrations, contact the network, or read credentials. Paste the output to match the source evidence against the exact imported SHAs and rows. No service restart or expensive optimiser backtest is needed.

## Pi verification result (2026-10-04)

The user ran the read-only command against the Pi on PR #50 (`13db55e`). It completed in 0.519s.

- All five historical import records name `9779cdbc0c07f6c900c2d0c181ddf6bb9c800f88`, the exact source head inspected here, covering fixtures, teams and merged player GW files.
- All five seasons have 38 Gameweeks and 380 fixtures. **None of the 190 historical Gameweeks has a deadline timestamp.** A sourced UTC deadline catalogue is therefore the first reconstruction step, before per-deadline source comparisons. Do not derive deadlines from final rearranged kickoff times.
- Fixture 162 is stored in GW28, kickoff 2024-03-13 19:30 UTC, FDR 2–2. Fixture 144 is stored in GW24, kickoff 2025-02-12 19:30 UTC, FDR 5–3. Both match the audited final-source examples.
- Fixture source_updated_at values are 2026-09-25, whereas import logs show 2026-09-26. They reflect local import activity rather than original data capture; the difference must not be used as evidence for historical availability.
- The current-season 2026-27 row has one deadline and no history-table fixtures; this diagnostic does not inspect the live API or establish whether collection timers work.

This confirms the targeted local provenance findings, not byte-for-byte identity of every imported row. No repaired-input model results were produced. The verification command need not be repeated for this unchanged dataset.

## Next implementation after provenance is checked

1. First source the 190 historical UTC deadlines with evidence references and explicit missing coverage. Then build immutable decision snapshots with UTC cutoffs and source/evidence lineage. Keep final scoring data in separate outcome records; do not overwrite the current runtime history to approximate snapshots.
2. For each deadline, distinguish verified information, stale archive observations and unknowns. Add evidenced fixture amendments; do not infer their announcement times from final kickoffs/events. Mark missing coverage explicitly.
3. Recreate candidate Gameweeks from deadline-known schedules, not final blank lists. Evaluate all eligible weeks for a true chip-timing experiment, including later unexpected blanks as outcomes.
4. Only then run expanding chronological validation (earlier seasons only), keeping weights/gates fixed. This alone cannot cure retrospective fixture/FDR inputs.

Until then: retain fixture-only as the provisional research baseline; blend HOLD; mixed FH uncalibrated; no live threshold changes. Existing numerical results have not been recomputed with repaired inputs.

## Reproducibility

[`historical_input_audit_evidence.json`](historical_input_audit_evidence.json) records full SHAs, file timestamps, fixture before/after fields, FDR counts/examples, team changes and 2025-26 fixture history. Fetch CSVs at the pinned SHAs under `data/<season>/`; parse with `csv.DictReader`, match fixtures by `id` and teams by `id`, normalise nonempty `event` with `int(float(value))`. Count changes in `team_h_difficulty`/`team_a_difficulty`; compare strength-prefixed fields separately. Git timestamps are archive evidence, not independent proof of historical API capture times.
