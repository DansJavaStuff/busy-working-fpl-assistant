# Fantasy EPL Assistant

A personal Fantasy Premier League assistant for analysing the current squad, planning transfers, selecting a starting XI and making captaincy decisions.

The project combines official FPL data with fixture, team-strength and playing-time context. The aim is not simply to find the highest-scoring theoretical squad, but to make useful week-to-week FPL decisions while accounting for free transfers, hits, bank, selling prices, injuries and uncertainty.

## Current Status

The assistant is operational as an in-season decision-support tool.

Current capabilities include:

- Live official FPL player, team and fixture data
- Authenticated retrieval of the current FPL squad
- Rolling multi-gameweek player projections
- Fixture difficulty and team-strength adjustments
- Early-season shrinkage to reduce overreaction to small samples
- Fresh 15-player squad optimisation under FPL constraints
- Current-squad optimisation for HOLD, one-transfer and multi-transfer paths
- Actual selling prices and available bank
- Free-transfer and transfer-hit accounting
- Legal starting-XI and bench selection
- Captain and vice-captain selection
- Formation comparison diagnostics
- Goalkeeper playing-time confidence using RotoWire depth information
- RotoWire outfield availability context
- Official FPL availability percentages as the primary availability signal where supplied
- Minimum free-transfer gain threshold so tiny numerical improvements do not automatically consume a transfer
- Season benchmark history in `data/season_history.csv`
- Local Flask dashboard for weekly squad / transfer decisions
- Approve / Reject workflow and FPL write-layer tooling
- Gameweek history view
- Read-only chip planner for Wildcard, Free Hit, Bench Boost and Triple Captain
- Chip-window comparison through the active half-season boundary (GW19 or GW38)
- Cached cross-chip opportunity analysis
- Blank / Double Gameweek-aware projections using all fixtures assigned to each FPL Gameweek
- Rearranged fixtures automatically follow their current FPL Gameweek assignment

The chip-planner hardening and special-Gameweek milestone is complete. Player projections model each club as having 0, 1 or 2+ fixtures in a Gameweek, chip timing respects the GW19/GW20 refresh boundary, and blank/double/rearranged fixtures feed naturally into normal optimisation and chip timing. The next modelling priority is smarter free-transfer valuation.

## Recommendation Philosophy

The assistant is a decision-support tool rather than an instruction to make every numerically positive transfer.

It distinguishes between:

- the **best available transfer**
- a **transfer worth making**

A transfer that improves the projection by only a tiny amount should not automatically consume a valuable free transfer.

The current implementation therefore uses a minimum projected-gain threshold before recommending that a free transfer is spent.

This is intentionally conservative because:

- projections contain uncertainty
- early-season samples are small
- rolling a transfer creates useful future flexibility
- selling prices and bank matter
- transfer hits can outweigh short-term projected gains
- availability and expected playing time are not the same thing

## Data Sources

The assistant combines official FPL data with carefully limited external context.

### Official Fantasy Premier League

Used for:

- player data
- team data
- fixtures
- current squad
- selling prices
- bank
- free transfers
- availability percentages

Official FPL information is treated as the primary source where available.

### RotoWire

Used as secondary playing-time / availability context.

Current uses include:

- goalkeeper depth information
- outfield availability statuses such as `GTD`, `OUT` and `SUS`

RotoWire's flat outfield ordering is retained as diagnostic metadata only and is not treated as a reliable starting-XI ranking.

### Local Model Data

The project also uses locally derived:

- team-strength context
- player projections
- fixture adjustments
- playing-time confidence
- season benchmark history

External information supplements official FPL information rather than automatically overriding it.

## Historical Data Store

The project has a versioned local SQLite store for historical analysis, weekly snapshots and chip backtesting.

The default database is:

```text
data/runtime/fpl_history.db
```

The runtime database is intentionally excluded from Git. The schema and migrations are tracked in `db/migrations/`, so a clean clone can recreate the database automatically. The Flask app applies pending migrations at startup; the same can be done manually with:

```bash
python3 -m tools.init_history_db
```

The initial schema separates:

- seasons and Gameweeks
- teams and fixtures
- raw timestamped snapshots
- modelled chip opportunities
- measured chip outcomes

JSON payload columns preserve source details that may be useful later without forcing every future field into the first schema. Small curated reference datasets may be committed under `data/historical/`; transient snapshots, caches and SQLite runtime files stay local.

This gives future chip-pattern work a reproducible storage layer while keeping the database itself disposable and rebuildable.

The same SQLite database also provides a persistent cache for expensive derived model results. Chip Planner results are cached by a fingerprint of the current squad, bank, transfer state, chip state and planning Gameweek, together with an explicit model-version key. Cached results expire automatically, and changing those inputs produces a different cache key rather than reusing stale analysis.

The Chip Planner currently uses a 15-minute cache for the main page and a 30-minute cache for the slower future-opportunity analysis. Supplying `?refresh=1` to the corresponding data endpoint bypasses the cache and recalculates immediately.

### Historical fixture import

Historical team and fixture context can be imported into the local SQLite database from the community-maintained `vaastav/Fantasy-Premier-League` dataset.

The importer resolves the requested Git ref to a concrete Git commit before downloading files, and stores that commit alongside the imported season. This makes later backtests reproducible even if the upstream dataset changes.

The default import covers the five completed seasons from 2021-22 through 2025-26:

```bash
python3 -m tools.import_historical_fpl
```

Specific seasons can be selected:

```bash
python3 -m tools.import_historical_fpl 2024-25 2025-26
```

The importer currently loads `teams.csv` and `fixtures.csv`, including historical FPL fixture difficulty, team-strength fields, results and the Gameweek to which each fixture was assigned. From those assignments the assistant can reconstruct normal, blank, double and mixed blank/double Gameweeks.

After import, inspect detected special Gameweeks with:

```bash
python3 -m tools.show_historical_special_gameweeks 2025-26
```

Historical expected-points fields are deliberately not imported as pre-deadline model evidence at this stage. The source dataset documents that its scraped `xP` can contain post-Gameweek information, which would create look-ahead bias in a backtest.

### Pre-deadline snapshots

A small systemd timer can collect append-only snapshots of what FPL data was actually available before each deadline. This is designed for later backtesting so historical models do not accidentally use information that only became known afterwards.

Install the timer once on the Raspberry Pi from the repository root:

```bash
sh tools/install_snapshot_timer.sh
```

The installer starts the collector immediately and then checks every two minutes. It does not write a new row every two minutes; it only saves when a checkpoint is due.

For each Gameweek the current checkpoints are:

- one **baseline** snapshot when the collector first runs more than an hour before the deadline
- approximately **T-60 minutes**
- approximately **T-15 minutes**
- approximately **T-10 minutes**
- approximately **T-5 minutes**

Snapshots are append-only. The baseline is not overwritten by the later pre-deadline records. Each checkpoint is saved at most once per entry/Gameweek.

Checkpoint windows are resilient to short outages. For example, if the Pi is unavailable at exactly T−15m but returns at T−12m, the T−15m checkpoint is still captured and marked with its actual lateness. If a whole checkpoint window is missed, the collector moves on to the next useful checkpoint rather than pretending stale data was captured on time.

Gameweek HQ shows the current collector health, last check and saved/waiting state for baseline, T−60m, T−15m, T−10m and T−5m.

The dashboard also compares consecutive snapshots and reports changes in availability, prices, fixture assignments, the authenticated team state and FPL projection inputs. This is deliberately being collected as an experiment: after roughly 4–5 complete Gameweeks, review whether T−15m, T−10m and T−5m provide meaningfully different decision information. If they are consistently redundant, reduce the checkpoint schedule rather than keeping extra collection indefinitely.

When a snapshot is actually due, the collector bypasses the normal public-data cache and requires fresh official FPL bootstrap and fixture responses, then captures the authenticated current squad and public entry data. If a live public FPL request fails, that checkpoint is not silently filled with stale cached data.

The timer can be inspected with:

```bash
sudo systemctl status fpl-snapshot-collector.timer
sudo journalctl -u fpl-snapshot-collector.service
```

## Main Scripts

### `transfer_optimizer.py`

The main in-season decision tool.

It loads the authenticated FPL squad and compares holding against possible transfer paths, including transfer hits.

Typical output includes:

- current HOLD score
- transfer alternatives
- starting XI
- bench
- captain
- vice-captain
- bank
- hit cost
- projected / net scores
- final recommendation
- comparison with an ideal fresh squad

Run with:

```bash
python3 transfer_optimizer.py
```

### `optimizer.py`

Contains the core player-projection and squad-optimisation model.

It can also construct an unconstrained fresh squad and provides model diagnostics.

### `fpl_api.py`

Handles official FPL public data and authenticated account access, including refresh-token rotation.

### `goalkeeper_depth.py`

Matches FPL goalkeepers to RotoWire depth-chart information and supplies goalkeeper playing-time confidence.

### `outfield_depth.py`

Matches FPL outfield players to RotoWire information and captures external availability statuses.

### `team_strength.py`

Provides team-strength context used by the projection model.

### `player_context.py`

Contains additional player-level context used by the model.

### `my_team.py`

Utility for retrieving and inspecting the authenticated FPL squad.

## First-run setup and authentication

A fresh installation does not contain an FPL account ID or credentials.

Start the Flask app and browse to it normally. If local configuration is missing, Gameweek HQ redirects to `/setup` and asks for:

- your numeric FPL Entry ID
- your FPL refresh token

The setup page writes these values to the installation's local `.env` file:

```text
FPL_ENTRY_ID=...
FPL_REFRESH_TOKEN=...
```

The refresh token is never displayed back to the browser after it has been saved. On supported systems the file is written with owner-only (`0600`) permissions, and `.env` is excluded from Git.

If a refresh token is rotated during authenticated FPL requests, the replacement is saved back to the same local file without losing the Entry ID.

An optional `.env.example` is included for manual setup, but the web setup page is the preferred route.

**Never commit `.env`, refresh tokens or other credentials to Git.**

## Environment

The project is developed primarily on macOS and run on a Raspberry Pi using a Python virtual environment.

Typical setup:

```bash
git clone https://github.com/DansJavaStuff/busy-working-fpl-assistant.git
cd busy-working-fpl-assistant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

After starting the Flask app, complete the local setup page. This makes a replacement Raspberry Pi or a future clean install reproducible without editing Python source files.

The optimisation model also requires the CBC solver used by PuLP.

On Debian / Raspberry Pi OS:

```bash
sudo apt install coinor-cbc
```

## Weekly Workflow

The current high-level workflow is:

1. Pull the latest code.
2. Activate the Python virtual environment.
3. Run `transfer_optimizer.py` close enough to the deadline to capture current availability information.
4. Review HOLD and transfer alternatives.
5. Sanity-check important injury, suspension and team-news information.
6. Make the FPL transfer, starting-XI and captaincy decisions.
7. Retain the generated season benchmark for later model validation.

The optimiser is intended to make the weekly decision process quicker and more consistent, not to remove judgement entirely.

## Model Direction

Current and planned modelling work includes:

- budget efficiency
- smarter free-transfer valuation
- outfield playing-time confidence
- projection validation
- multi-gameweek transfer planning
- captaincy improvements
- price-change awareness
- chip and special-gameweek planning

See [ROADMAP.md](ROADMAP.md) for the full development plan.

## Web / User Interface

The project now includes a local Flask dashboard used as the main interactive weekly manager while retaining the terminal tools for diagnostics and independent use.

Current web functionality includes:

- This Gameweek / current squad
- Transfer scenarios and recommendations
- Proposed XI, bench, captain and vice-captain
- Approve / Reject workflow
- Gameweek history
- Read-only chip planning and opportunity comparison
- First-run local setup for FPL account configuration

Future web work includes authentication, scheduled optimiser runs, hosted deployment and additional diagnostic / comparison views.

## Development

Development priorities, technical debt and completed milestones are tracked in [ROADMAP.md](ROADMAP.md).

The current main priority is **smarter free-transfer valuation**, now that chip-planner hardening and special-Gameweek awareness are in place.

The roadmap also tracks the future project rename because the existing `busy-working-fpl-assistant` repository name was inherited from the unrelated Busy Working Fantasy NFL project.

## CI and Security

The repository uses GitHub-native security features together with a lightweight CI pipeline.

Repository-side checks include:

- Python source compilation
- Unit tests on Python 3.11 and 3.13
- Ruff checks for undefined-name errors
- `pip-audit` vulnerability checks against runtime dependencies
- Weekly grouped Dependabot updates for Python packages and GitHub Actions

GitHub CodeQL, Dependabot alerts, secret protection and push protection provide the platform-side scanning. Runtime dependencies are declared in `requirements.txt`; development / CI tools are in `requirements-dev.txt`.

The Raspberry Pi still requires the system CBC solver used by PuLP:

```bash
sudo apt install coinor-cbc
```

## Repository Principles

- Keep secrets and refresh tokens outside Git.
- Keep Mac development and Raspberry Pi runtime environments reproducible.
- Require automated checks before treating changes as ready for the Raspberry Pi.
- Cache external data where appropriate.
- Handle external-source failures gracefully.
- Keep README and roadmap aligned with implemented behaviour.
- Prefer decision quality over feature count.

## Disclaimer

This is a personal hobby project.

It is not affiliated with or endorsed by the Premier League, Fantasy Premier League or RotoWire.


### Historical chip-pattern features

Imported historical fixtures can now be reduced to chip-relevant fixture-pattern features.

The current feature layer measures:

- blank severity
- double-gameweek concentration
- whether stronger historical teams were involved
- average fixture quality for teams with doubles
- separate fixture-pattern signals for Free Hit, Bench Boost and Triple Captain

These signals are deliberately **not** treated as realised chip points or as a recommendation by themselves. They are structural historical features that can later be compared with current/future Gameweeks and combined with player projections, fixture certainty and HOLD thresholds.

Inspect the strongest fixture-pattern windows for an imported season with:

```bash
python3 -m tools.show_historical_chip_windows 2025-26 FH
python3 -m tools.show_historical_chip_windows 2025-26 BB
python3 -m tools.show_historical_chip_windows 2025-26 TC
```

Wildcard is not included in this first historical fixture-pattern score because its value is inherently multi-Gameweek and squad-state dependent; treating a single historical Gameweek as a WC score would be misleading.


### Current vs historical chip analogues

Historical chip-pattern rows are indexed across every imported season and zero-signal filler rows are excluded.

A current or future Gameweek can be reduced to the same fixture-pattern feature vector and compared with the historical index. Similarity currently uses blank count, double count, stronger-team blank/double involvement and double-fixture quality.

Examples:

```bash
python3 -m tools.show_current_chip_analogues 10 FH
python3 -m tools.show_current_chip_analogues 10 BB
python3 -m tools.show_current_chip_analogues 10 TC
```

The output reports the current fixture shape plus the closest non-zero historical analogues across all imported seasons.

Similarity is descriptive evidence, not yet a PLAY recommendation. The next modelling layer combines this with current projected chip value, fixture certainty and explicit HOLD logic.


### Chip HOLD and confidence layer

Chip opportunity rows now combine the modelled chip uplift with simple fixture-timing certainty and the historical analogue layer.

For FH, BB and TC, the planner only treats a window as a live **CANDIDATE** when the relevant special fixture shape is present, there is strong historical support, the projected chip value is positive, and the fixture window is not too far away. Otherwise it explicitly returns **HOLD**.

Wildcard is currently held by design in this confidence layer because the future WC timing model is still a simplified single-window comparison. A multi-Gameweek persistent-squad model is required before historical/confidence evidence should be allowed to promote a WC timing recommendation.

Fixture certainty is presently a transparent horizon heuristic: current GW = high, next two GWs = medium, longer-range = low. It does not claim that future rearrangements are impossible.


### Chip Planner decision-first UI

The Chip Planner deliberately separates **model output** from **strategic recommendation**.

The default view now leads with HOLD/CANDIDATE and a short reason. Detailed fixture certainty, historical analogues, cost-of-waiting diagnostics and the larger per-chip model tables are collapsed behind `Why?` / model-detail controls. The asynchronously calculated opportunity decision is also copied back onto each individual chip card so a large theoretical uplift is not visually mistaken for a recommendation to spend the chip.


### Full chip timing curves

The Chip Opportunity view now includes a full Gameweek-by-Gameweek model-value curve for BB, TC, WC and FH across the active chip half.

Each curve shows every remaining Gameweek, highlights the current Gameweek and the strongest model-value window, and reports where the current Gameweek ranks within the remaining horizon. This is descriptive context rather than an automatic PLAY recommendation.

The Wildcard curve remains explicitly provisional until the future WC model is upgraded from a simplified one-window squad comparison to a persistent multi-Gameweek model.


### Timing-curve cache shape

The chip-planner cache model version must be bumped whenever the cached opportunity payload changes shape. The timing-curve release uses `chip-planner-v3` so older cached v2 opportunity rows cannot hide the newly-added `curves` data.


### Chip timing performance

Full chip timing curves are solver-heavy, so the timing path has three performance safeguards:

- zero-transfer/hold timing windows choose the best XI and captain directly from the fixed 15-player squad instead of invoking CBC over the full player pool
- each Gameweek timing window is cached independently in SQLite for up to 12 hours, with the cache key including the squad state and the player projection inputs used by that Gameweek
- an optional low-priority systemd timer can keep the overall opportunity cache warm in the background

Install the background cache warmer once on the Raspberry Pi:

```bash
sh tools/install_chip_cache_timer.sh
```

It checks every 20 minutes. When the normal 30-minute opportunity cache is still fresh it is effectively a cheap cache hit; when that cache needs rebuilding, the longer-lived per-Gameweek timing-window cache avoids repeating unchanged CBC work.

A manual warm-up can also be run with:

```bash
python3 -m tools.warm_chip_opportunity_cache
```

The cache model version is bumped when timing logic changes so stale derived results are not reused.


### Curve-aware chip decisions

Timing-curve rank and percentile are now used as supporting decision evidence.

The planner remains conservative early in a chip half: a normal single-fixture TC week can rank first simply because future Double Gameweeks have not yet been assigned. In that situation the model keeps **HOLD** but explains that the current week is the strongest presently-modelled TC window.

A normal-GW Triple Captain can become a **CANDIDATE** late in the chip half when it is the strongest remaining modelled window, sits at the top of the remaining distribution and only a small number of windows remain. Blank/Double Gameweek structure and historical analogue evidence continue to support special-GW candidates.

Bench Boost and Free Hit still require their relevant special-fixture structure in this first curve-aware pass; Wildcard remains HOLD until the multi-Gameweek WC model is implemented.


### Persistent multi-Gameweek Wildcard timing

Wildcard timing is now evaluated over a persistent horizon of up to five Gameweeks instead of only the immediate Gameweek.

For each candidate Wildcard week the model:

- builds an unrestricted 15-player squad using the existing multi-Gameweek optimiser
- keeps that rebuilt squad fixed across the next five Gameweeks (or to the chip-half boundary)
- re-selects the best legal XI and captain from that fixed squad each Gameweek
- compares it with a no-chip baseline using the stronger of today's squad held constant or one free transfer made at the start of the same window
- reports the cumulative projected-points uplift over that horizon

This deliberately avoids pretending that the model knows a perfect sequence of future weekly transfers. It gives Wildcard a persistent squad value while keeping the comparison understandable and reproducible.

Wildcard HOLD/CANDIDATE logic now uses this five-Gameweek uplift plus the timing-curve rank/percentile and fixture certainty. A CANDIDATE remains a review signal rather than an instruction to activate the chip.


### Wildcard activation vs value horizon

Wildcard availability and Wildcard value use different boundaries.

The first Wildcard must still be activated by GW19, but a squad created by a GW18/GW19 Wildcard continues into GW20+ and therefore its five-Gameweek value horizon is allowed to cross the chip refresh boundary. The projection loader now carries enough future Gameweeks to value that persistent squad fairly.

For example, a GW19 first-half Wildcard is activated legally in GW19 but can be valued across GW19–GW23. Only the end of the FPL season truncates the five-Gameweek Wildcard value horizon.


### Coordinated provisional chip schedule

The Chip Opportunity view now combines the individual chip windows into one conservative provisional schedule.

The scheduler:

- only considers windows that already pass the chip-specific `CANDIDATE` evidence threshold
- respects chip availability and first-/second-half event boundaries
- enforces the FPL rule that only one chip can be used in a Gameweek
- resolves clashes using model confidence, within-chip percentile and historical-pattern support rather than comparing raw BB/TC/FH/WC point values directly
- allows any or all chips to remain **UNSCHEDULED** when the evidence is not strong enough

This is intentionally not a mechanism for filling every chip into the calendar. A useful schedule can contain no assigned chips at all when future fixture information is still weak.


### Historical chip-pattern calibration

The first chip backtest is a leave-one-season-out calibration of the historical fixture-pattern layer for FH, BB and TC.

For every historical special-Gameweek case, the target season is removed from the analogue pool before the closest match is calculated. This avoids the trivial result where a Gameweek matches itself or another week from the same season too closely.

Run:

```bash
python3 -m tools.backtest_historical_chip_patterns
```

The report shows the distribution of best-match similarity and the proportion of historical cases clearing 70%, 75%, 80%, 85% and 90% similarity thresholds.

This is deliberately a **fixture-pattern calibration**, not a realised-points backtest. The imported historical database currently contains fixture/team context but not the player-by-player Gameweek points needed to validate realised BB/TC/FH point outcomes without inventing hindsight. Player/outcome import is the next historical-data step before changing decision thresholds from outcome evidence.
