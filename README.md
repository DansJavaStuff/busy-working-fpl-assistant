# Busy Working FPL Assistant

A personal Fantasy Premier League assistant for analysing the current squad, planning transfers, selecting a starting XI and making captaincy decisions.

The project combines official FPL data with fixture, team-strength and playing-time context. The aim is not simply to find the highest-scoring theoretical squad, but to make useful week-to-week FPL decisions while accounting for free transfers, hits, bank, selling prices, injuries and uncertainty.

## Current Features

- Downloads live official FPL player, team and fixture data.
- Authenticates against an FPL account and retrieves the current squad.
- Models expected player points across upcoming gameweeks.
- Applies fixture difficulty and team-strength adjustments.
- Reduces the influence of very small current-season samples early in the season.
- Optimises a fresh 15-player squad under FPL budget, position and club constraints.
- Optimises the existing squad for HOLD, one-transfer and multi-transfer scenarios.
- Uses actual selling prices, available bank, free transfers and transfer-hit costs.
- Selects the best legal starting XI and bench for each candidate squad.
- Recommends captain and vice-captain.
- Compares legal formations as a model diagnostic.
- Uses RotoWire goalkeeper depth information to estimate goalkeeper playing-time confidence.
- Uses RotoWire outfield information as a secondary availability/team-news source.
- Gives explicit official FPL availability percentages priority over external status information, avoiding duplicate availability penalties.
- Uses a minimum projected-gain threshold before recommending that an unused free transfer is spent.
- Records gameweek benchmark data in `data/season_history.csv` for future model validation.

## Main Scripts

### `transfer_optimizer.py`

The main in-season decision tool. It loads the authenticated FPL squad and compares holding against possible transfer paths, including transfer hits.

Typical output includes the current HOLD score, transfer alternatives, starting XI and bench, captain and vice-captain, bank, hit cost, projected/net scores, final recommendation and comparison with an ideal fresh squad.

Run with:

```bash
python3 transfer_optimizer.py
```

### `optimizer.py`

Contains the core player projection and squad-optimisation model. It can also construct an unconstrained fresh squad and provides model diagnostics.

### `fpl_api.py`

Handles official FPL public data and authenticated account access, including refresh-token rotation.

### `goalkeeper_depth.py`

Matches FPL goalkeepers to RotoWire depth-chart information and supplies goalkeeper playing-time confidence.

### `outfield_depth.py`

Matches FPL outfield players to RotoWire team/depth information and captures external availability statuses such as `GTD`, `OUT` and `SUS`.

RotoWire's flat outfield ordering is retained as diagnostic metadata only; it is not treated as a reliable starting-XI ranking.

### `team_strength.py`

Provides team-strength context used by the projection model.

### `player_context.py`

Contains additional player-level context used by the model.

### `my_team.py`

Utility for retrieving and inspecting the authenticated FPL squad.

## Recommendation Philosophy

The assistant distinguishes between the **best available transfer** and a **transfer worth making**.

A transfer that improves the model by only a tiny amount should not automatically consume a valuable free transfer. The current implementation therefore uses a minimum projected-gain threshold before recommending a free transfer.

This is intentionally conservative: FPL projections contain uncertainty, particularly early in the season, and rolling a transfer creates useful flexibility for future gameweeks.

## Data Sources

The project currently uses official Fantasy Premier League data, RotoWire Premier League depth charts as secondary playing-time/availability context, and locally derived team-strength and projection calculations.

External information supplements official FPL information rather than automatically overriding it.

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

The optimisation model also requires the CBC solver used by PuLP. On Debian/Raspberry Pi OS:

```bash
sudo apt install coinor-cbc
```

## Weekly Workflow

1. Pull the latest code.
2. Activate the Python virtual environment.
3. Run `transfer_optimizer.py` close enough to the deadline to capture current FPL availability information.
4. Review HOLD and the transfer alternatives.
5. Sanity-check important injury, suspension and team-news information.
6. Make the FPL transfer, starting-XI and captaincy decisions.
7. Retain the generated season benchmark for later model validation.

The optimiser is a decision-support tool rather than an instruction to make every numerically positive transfer.

## Development

Development priorities and known modelling limitations are tracked in [ROADMAP.md](ROADMAP.md).

The current main development priority is **budget efficiency**: identifying when a cheaper squad or transfer path gives almost the same projection while preserving useful money in the bank.

## Disclaimer

This is a personal hobby project and is not affiliated with or endorsed by the Premier League, Fantasy Premier League or RotoWire.
