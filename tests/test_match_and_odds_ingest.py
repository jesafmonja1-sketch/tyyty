from datetime import datetime

from sqlalchemy import func, select

from world_cup_intel.ingest.match_data import ingest_match_bundle
from world_cup_intel.ingest.odds import ingest_odds_bundle
from world_cup_intel.schema import Match, MatchTeamStat, NationalTeam, OddsMarket, OddsQuote


def test_ingest_match_bundle_and_odds_quotes(session):
    match_payload = {
        "match": {
            "id": "wc-2026-001",
            "competition": "FIFA World Cup",
            "stage": "Group Stage",
            "kickoff_at": "2026-06-14T18:00:00Z",
            "home_team": {"name": "Argentina", "fifa_code": "ARG", "confederation": "CONMEBOL"},
            "away_team": {"name": "France", "fifa_code": "FRA", "confederation": "UEFA"},
            "status": "scheduled",
            "neutral_site": True,
        }
    }
    odds_payload = {
        "match_external_id": "wc-2026-001",
        "bookmaker": "SampleBook",
        "quotes": [
            {"market_type": "1x2", "captured_at": "2026-06-14T15:00:00Z", "home_price": 2.4, "draw_price": 3.1, "away_price": 3.0},
            {"market_type": "handicap", "captured_at": "2026-06-14T15:00:00Z", "line_value": -0.25, "home_price": 1.95, "away_price": 1.91},
        ],
    }

    ingest_match_bundle(session, match_payload, datetime(2026, 6, 14, 10, 0, 0))
    ingest_odds_bundle(session, odds_payload, datetime(2026, 6, 14, 15, 0, 0))
    session.commit()

    assert session.scalar(select(func.count()).select_from(NationalTeam)) == 2
    assert session.scalar(select(func.count()).select_from(Match)) == 1
    assert session.scalar(select(func.count()).select_from(MatchTeamStat)) == 0
    assert session.scalar(select(func.count()).select_from(OddsMarket)) == 2
    assert session.scalar(select(func.count()).select_from(OddsQuote)) == 2
