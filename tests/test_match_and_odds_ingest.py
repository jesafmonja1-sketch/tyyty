from datetime import datetime

import pytest
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


def test_reingesting_match_bundle_does_not_duplicate_teams_or_match(session):
    match_payload = {
        "match": {
            "id": "wc-2026-002",
            "competition": "FIFA World Cup",
            "stage": "Group Stage",
            "kickoff_at": "2026-06-15T18:00:00Z",
            "home_team": {"name": "Brazil", "fifa_code": "BRA", "confederation": "CONMEBOL"},
            "away_team": {"name": "Germany", "fifa_code": "GER", "confederation": "UEFA"},
            "status": "scheduled",
            "neutral_site": True,
        }
    }

    ingest_match_bundle(session, match_payload, datetime(2026, 6, 15, 10, 0, 0))
    session.commit()
    ingest_match_bundle(session, match_payload, datetime(2026, 6, 15, 11, 0, 0))
    session.commit()

    assert session.scalar(select(func.count()).select_from(NationalTeam)) == 2
    assert session.scalar(select(func.count()).select_from(Match)) == 1


def test_reingesting_odds_bundle_does_not_duplicate_markets_or_quotes(session):
    match_payload = {
        "match": {
            "id": "wc-2026-003",
            "competition": "FIFA World Cup",
            "stage": "Group Stage",
            "kickoff_at": "2026-06-16T18:00:00Z",
            "home_team": {"name": "Spain", "fifa_code": "ESP", "confederation": "UEFA"},
            "away_team": {"name": "Portugal", "fifa_code": "POR", "confederation": "UEFA"},
            "status": "scheduled",
            "neutral_site": True,
        }
    }
    odds_payload = {
        "match_external_id": "wc-2026-003",
        "bookmaker": "SampleBook",
        "quotes": [
            {"market_type": "1x2", "captured_at": "2026-06-16T15:00:00Z", "home_price": 2.2, "draw_price": 3.0, "away_price": 3.4},
            {"market_type": "totals", "captured_at": "2026-06-16T15:00:00Z", "line_value": 2.5, "over_price": 1.88, "under_price": 1.98},
        ],
    }

    ingest_match_bundle(session, match_payload, datetime(2026, 6, 16, 10, 0, 0))
    ingest_odds_bundle(session, odds_payload, datetime(2026, 6, 16, 15, 0, 0))
    session.commit()
    ingest_odds_bundle(session, odds_payload, datetime(2026, 6, 16, 15, 5, 0))
    session.commit()

    assert session.scalar(select(func.count()).select_from(OddsMarket)) == 2
    assert session.scalar(select(func.count()).select_from(OddsQuote)) == 2


def test_ingest_odds_bundle_raises_value_error_for_missing_match(session):
    odds_payload = {
        "match_external_id": "missing-match",
        "bookmaker": "SampleBook",
        "quotes": [
            {"market_type": "1x2", "captured_at": "2026-06-17T15:00:00Z", "home_price": 2.2, "draw_price": 3.0, "away_price": 3.4},
        ],
    }

    with pytest.raises(ValueError, match="missing-match"):
        ingest_odds_bundle(session, odds_payload, datetime(2026, 6, 17, 15, 0, 0))
