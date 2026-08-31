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

The current development priority is **budget efficiency**: identifying when a cheaper squad or transfer path gives almost the same projection while preserving useful money in the bank.

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

## Authentication

Authenticated features require an FPL refresh token in a local `.env` file:

```text
FPL_REFRESH_TOKEN=...
```

The refresh token may rotate during authenticated requests and is saved locally by the application.

**Never commit `.env`, refresh tokens or other credentials to Git.**

## Environment

The project is developed primarily on macOS and run on a Raspberry Pi using a Python virtual environment.

Typical setup:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

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

## Web / User Interface Direction

The current tools are terminal-first.

A future lightweight Raspberry Pi web dashboard may include views for:

- This Gameweek
- My Squad
- Transfers
- Player Comparison
- Fixture Planner
- Season Performance
- Model Diagnostics

The terminal tools should remain independently usable.

## Development

Development priorities, technical debt and completed milestones are tracked in [ROADMAP.md](ROADMAP.md).

The current main priority is **budget efficiency**.

The roadmap also tracks the future project rename because the existing `busy-working-fpl-assistant` repository name was inherited from the unrelated Busy Working Fantasy NFL project.

## Repository Principles

- Keep secrets and refresh tokens outside Git.
- Keep Mac development and Raspberry Pi runtime environments reproducible.
- Cache external data where appropriate.
- Handle external-source failures gracefully.
- Keep README and roadmap aligned with implemented behaviour.
- Prefer decision quality over feature count.

## Disclaimer

This is a personal hobby project.

It is not affiliated with or endorsed by the Premier League, Fantasy Premier League or RotoWire.
