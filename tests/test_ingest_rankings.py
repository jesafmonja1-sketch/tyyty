from datetime import datetime

from sqlalchemy import func, select

from world_cup_intel.ingest.fifa_rankings import ingest_fifa_rankings
from world_cup_intel.schema import NationalTeam, RawPayload, RawSourceRun, TeamRanking


def test_ingest_fifa_rankings_records_raw_payload_and_ranking_rows(session):
    payload = {
        "updated_at": "2026-06-11T00:00:00Z",
        "rankings": [
            {"rank": 1, "team_name": "Argentina", "fifa_code": "ARG", "confederation": "CONMEBOL", "points": 1887.2},
            {"rank": 2, "team_name": "France", "fifa_code": "FRA", "confederation": "UEFA", "points": 1860.5},
        ],
    }

    ingest_fifa_rankings(session, payload, datetime(2026, 6, 11, 9, 0, 0))
    session.commit()

    assert session.scalar(select(func.count()).select_from(RawSourceRun)) == 1
    assert session.scalar(select(func.count()).select_from(RawPayload)) == 1
    assert session.scalar(select(func.count()).select_from(NationalTeam)) == 2
    assert session.scalar(select(func.count()).select_from(TeamRanking)) == 2
