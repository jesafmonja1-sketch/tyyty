from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from world_cup_intel.analysis.predictions import generate_match_prediction
from world_cup_intel.ingest.match_data import ingest_match_bundle
from world_cup_intel.ingest.odds import ingest_odds_bundle
from world_cup_intel.schema import Match, NationalTeam, PredictionRun, TeamPowerSnapshot


CURATED_MATCHES = [
    {
        "match": {
            "id": "wc-2026-real-can-bih",
            "competition": "FIFA World Cup",
            "stage": "Group Stage",
            "kickoff_at": "2026-06-12T23:00:00Z",
            "home_team": {"name": "Canada", "fifa_code": "CAN", "confederation": "CONCACAF"},
            "away_team": {"name": "Bosnia and Herzegovina", "fifa_code": "BIH", "confederation": "UEFA"},
            "status": "scheduled",
            "neutral_site": False,
        },
        "power": {
            "CAN": {"overall": 71.0, "attack": 69.0, "defense": 70.0, "midfield": 68.0, "set_piece": 66.0, "squad": 74.0, "form": 71.0},
            "BIH": {"overall": 63.0, "attack": 61.0, "defense": 62.0, "midfield": 60.0, "set_piece": 63.0, "squad": 67.0, "form": 62.0},
        },
        "odds": {
            "bookmaker": "MarketBlend",
            "quotes": [
                {"market_type": "1x2", "home_price": 1.77, "draw_price": 3.60, "away_price": 4.70},
                {"market_type": "handicap", "line_value": -0.5, "home_price": 1.74, "away_price": 2.05},
                {"market_type": "totals", "line_value": 2.5, "over_price": 2.20, "under_price": 1.67},
            ],
        },
    },
    {
        "match": {
            "id": "wc-2026-real-kor-cze",
            "competition": "FIFA World Cup",
            "stage": "Group Stage",
            "kickoff_at": "2026-06-13T02:00:00Z",
            "home_team": {"name": "Korea Republic", "fifa_code": "KOR", "confederation": "AFC"},
            "away_team": {"name": "Czechia", "fifa_code": "CZE", "confederation": "UEFA"},
            "status": "scheduled",
            "neutral_site": True,
        },
        "power": {
            "KOR": {"overall": 66.0, "attack": 65.0, "defense": 64.0, "midfield": 65.0, "set_piece": 62.0, "squad": 68.0, "form": 66.0},
            "CZE": {"overall": 67.0, "attack": 66.0, "defense": 67.0, "midfield": 66.0, "set_piece": 64.0, "squad": 69.0, "form": 67.0},
        },
        "odds": {
            "bookmaker": "MarketBlend",
            "quotes": [
                {"market_type": "1x2", "home_price": 3.15, "draw_price": 3.15, "away_price": 2.35},
                {"market_type": "handicap", "line_value": 0.25, "home_price": 1.95, "away_price": 1.85},
                {"market_type": "totals", "line_value": 2.25, "over_price": 1.98, "under_price": 1.82},
            ],
        },
    },
    {
        "match": {
            "id": "wc-2026-real-swe-tun",
            "competition": "FIFA World Cup",
            "stage": "Group Stage",
            "kickoff_at": "2026-06-15T02:00:00Z",
            "home_team": {"name": "Sweden", "fifa_code": "SWE", "confederation": "UEFA"},
            "away_team": {"name": "Tunisia", "fifa_code": "TUN", "confederation": "CAF"},
            "status": "scheduled",
            "neutral_site": True,
        },
        "power": {
            "SWE": {"overall": 69.0, "attack": 68.0, "defense": 69.0, "midfield": 67.0, "set_piece": 65.0, "squad": 71.0, "form": 69.0},
            "TUN": {"overall": 61.0, "attack": 59.0, "defense": 62.0, "midfield": 60.0, "set_piece": 61.0, "squad": 64.0, "form": 60.0},
        },
        "odds": {
            "bookmaker": "MarketBlend",
            "quotes": [
                {"market_type": "1x2", "home_price": 1.85, "draw_price": 3.35, "away_price": 4.60},
                {"market_type": "handicap", "line_value": -0.5, "home_price": 1.86, "away_price": 1.96},
                {"market_type": "totals", "line_value": 2.25, "over_price": 2.02, "under_price": 1.78},
            ],
        },
    },
    {
        "match": {
            "id": "wc-2026-real-qat-sui",
            "competition": "FIFA World Cup",
            "stage": "Group Stage",
            "kickoff_at": "2026-06-19T19:00:00Z",
            "home_team": {"name": "Qatar", "fifa_code": "QAT", "confederation": "AFC"},
            "away_team": {"name": "Switzerland", "fifa_code": "SUI", "confederation": "UEFA"},
            "status": "scheduled",
            "neutral_site": True,
        },
        "power": {
            "QAT": {"overall": 59.0, "attack": 58.0, "defense": 58.0, "midfield": 57.0, "set_piece": 59.0, "squad": 61.0, "form": 58.0},
            "SUI": {"overall": 73.0, "attack": 71.0, "defense": 73.0, "midfield": 72.0, "set_piece": 68.0, "squad": 75.0, "form": 72.0},
        },
        "odds": {
            "bookmaker": "MarketBlend",
            "quotes": [
                {"market_type": "1x2", "home_price": 5.30, "draw_price": 3.75, "away_price": 1.66},
                {"market_type": "handicap", "line_value": 0.75, "home_price": 1.92, "away_price": 1.88},
                {"market_type": "totals", "line_value": 2.25, "over_price": 2.08, "under_price": 1.74},
            ],
        },
    },
    {
        "match": {
            "id": "wc-2026-real-bra-mar",
            "competition": "FIFA World Cup",
            "stage": "Group Stage",
            "kickoff_at": "2026-06-19T22:00:00Z",
            "home_team": {"name": "Brazil", "fifa_code": "BRA", "confederation": "CONMEBOL"},
            "away_team": {"name": "Morocco", "fifa_code": "MAR", "confederation": "CAF"},
            "status": "scheduled",
            "neutral_site": True,
        },
        "power": {
            "BRA": {"overall": 82.0, "attack": 83.0, "defense": 79.0, "midfield": 81.0, "set_piece": 74.0, "squad": 84.0, "form": 81.0},
            "MAR": {"overall": 74.0, "attack": 72.0, "defense": 75.0, "midfield": 73.0, "set_piece": 70.0, "squad": 76.0, "form": 73.0},
        },
        "odds": {
            "bookmaker": "MarketBlend",
            "quotes": [
                {"market_type": "1x2", "home_price": 1.68, "draw_price": 3.70, "away_price": 5.40},
                {"market_type": "handicap", "line_value": -0.75, "home_price": 1.96, "away_price": 1.84},
                {"market_type": "totals", "line_value": 2.5, "over_price": 1.90, "under_price": 1.90},
            ],
        },
    },
]


def _upsert_power_snapshot(session, team: NationalTeam, captured_at: datetime, values: dict) -> None:
    snapshot = session.scalar(
        select(TeamPowerSnapshot).where(
            TeamPowerSnapshot.national_team_id == team.id,
            TeamPowerSnapshot.captured_at == captured_at,
        )
    )
    if snapshot is None:
        snapshot = TeamPowerSnapshot(
            national_team_id=team.id,
            captured_at=captured_at,
        )
        session.add(snapshot)

    snapshot.overall_score = values["overall"]
    snapshot.attack_score = values["attack"]
    snapshot.defense_score = values["defense"]
    snapshot.midfield_control_score = values["midfield"]
    snapshot.set_piece_score = values["set_piece"]
    snapshot.squad_completeness_score = values["squad"]
    snapshot.recent_form_score = values["form"]


def _match_odds_payload(curated_match: dict, captured_at: datetime) -> dict:
    quotes = []
    for quote in curated_match["odds"]["quotes"]:
        quotes.append(
            {
                "captured_at": captured_at.isoformat() + "Z",
                **quote,
            }
        )
    return {
        "match_external_id": curated_match["match"]["id"],
        "bookmaker": curated_match["odds"]["bookmaker"],
        "quotes": quotes,
    }


def seed_upcoming_world_cup_matches(session, captured_at: datetime) -> list[Match]:
    seeded_matches = []
    for curated_match in CURATED_MATCHES:
        match_row = ingest_match_bundle(session, {"match": curated_match["match"]}, captured_at)
        session.flush()

        home_team = session.get(NationalTeam, match_row.home_team_id)
        away_team = session.get(NationalTeam, match_row.away_team_id)
        _upsert_power_snapshot(session, home_team, captured_at, curated_match["power"][home_team.fifa_code])
        _upsert_power_snapshot(session, away_team, captured_at, curated_match["power"][away_team.fifa_code])

        ingest_odds_bundle(session, _match_odds_payload(curated_match, captured_at), captured_at)

        existing_prediction = session.scalar(
            select(PredictionRun).where(
                PredictionRun.match_id == match_row.id,
                PredictionRun.captured_at == captured_at,
            )
        )
        if existing_prediction is None:
            generate_match_prediction(session, match_row.id, captured_at)

        seeded_matches.append(match_row)

    return seeded_matches
