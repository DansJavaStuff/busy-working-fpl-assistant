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
python3 tools/init_history_db.py
```

The initial schema separates:

- seasons and Gameweeks
- teams and fixtures
- raw timestamped snapshots
- modelled chip opportunities
- measured chip outcomes

JSON payload columns preserve source details that may be useful later without forcing every future field into the first schema. Small curated reference datasets may be committed under `data/historical/`; transient snapshots, caches and SQLite runtime files stay local.

This gives future chip-pattern work a reproducible storage layer while keeping the database itself disposable and rebuildable.

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
