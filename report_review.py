"""Offline review of a saved weekly report; no FPL calls or runtime writes."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

REPORT_REVIEW_AGE_SECONDS = 30 * 60
MODEL_SCORE_NOTE = (
    "Model scores combine the starting XI projection, a position-weighted captain "
    "score and 15% of the squad's five-Gameweek projection. Net scores deduct "
    "transfer hits once. HOLD optimises the existing squad's lineup. These are "
    "ranking scores, not a forecast of this week's points."
)


def parse_timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp needs a timezone")
    return parsed.astimezone(timezone.utc)


def report_freshness(report, now=None):
    now = now or datetime.now(timezone.utc)
    age = None
    generated_display = None
    generated_at = report.get("generated_at")
    try:
        generated = parse_timestamp(generated_at)
        generated_display = generated.astimezone(ZoneInfo("Europe/London")).strftime("%a %d %b, %H:%M %Z")
        age = (now - generated).total_seconds()
        status = "clock_ahead" if age < 0 else (
            "recent" if age <= REPORT_REVIEW_AGE_SECONDS else "refresh_needed"
        )
    except (ValueError, TypeError, AttributeError):
        status = "unknown"
    try:
        locked = now >= parse_timestamp(report.get("deadline_iso"))
    except (ValueError, TypeError, AttributeError):
        locked = True
    messages = {
        "recent": "Recently generated analysis. Refresh again before applying decisions.",
        "refresh_needed": "Saved analysis is over 30 minutes old. Refresh before making decisions.",
        "unknown": "This saved analysis has no valid generation time. Refresh before making decisions.",
        "clock_ahead": "Analysis timestamp is in the future. Check the Pi clock and refresh.",
    }
    return {
        "status": status, "generated_at": generated_at,
        "generated_display": generated_display,
        "age_seconds": age, "deadline_locked": locked, "message": messages[status],
    }


def transfer_scenario_summary(result, hold):
    return {
        "transfers": result["transfers"],
        "score": result["net_score"],
        "raw_score": result["raw_score"],
        "hit_cost": result["hit_cost"],
        "gross_gain": result["raw_score"] - hold["raw_score"],
        "gain": result["net_score"] - hold["net_score"],
        "bank_after": result["bank_after"] / 10,
    }


def weekly_report_review(report, now=None):
    recommended = report["recommended"]
    captain = report["captain"]
    gw = report["gameweek"]
    return {
        "gameweek": gw,
        "freshness": report_freshness(report, now),
        "model_score_note": MODEL_SCORE_NOTE,
        "free_transfers": report["free_transfers"],
        "bank": report["bank"],
        "current_captain": (report.get("current_captain") or {}).get("name"),
        "availability_flags": [
            {"name": p["name"], "starter": p.get("starter", False),
             "status": p.get("status"),
             "availability_percent": p.get("chance_of_playing_next_round")}
            for p in recommended["squad"]
            if p.get("status", "a") != "a" or (
                p.get("chance_of_playing_next_round") is not None
                and p["chance_of_playing_next_round"] < 100
            )
        ],
        "recommendation": {
            "action": "HOLD" if recommended["transfers"] == 0 else "TRANSFER",
            "transfers": recommended["transfers"],
            "hit_cost": recommended["hit_cost"],
            "net_model_gain": report["transfer_gain"],
            "pairs": [{"out": pair["out"]["name"], "in": pair["in"]["name"]}
                      for pair in report["recommended_pairs"]],
        },
        "captain": {
            "name": captain["name"], "position": captain["position"],
            "gw_projection": captain.get(f"proj_gw{gw}", 0),
            "availability_percent": captain.get("chance_of_playing_next_round"),
        },
        "vice_captain": report["vice"]["name"],
        "scenarios": [{key: scenario[key] for key in (
            "transfers", "score", "raw_score", "hit_cost", "gain"
        )} | {"gross_gain": scenario.get("gross_gain", scenario["gain"] + scenario["hit_cost"])}
            for scenario in report["scenarios"]],
        "note": "Reviews saved advice only; it does not verify your current live squad. "
                "Chip recommendations need the separate Chips page.",
    }
