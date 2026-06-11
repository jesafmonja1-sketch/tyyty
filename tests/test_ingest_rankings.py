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


def test_ingest_fifa_rankings_updates_existing_team_fields(session):
    team = NationalTeam(
        fifa_code="GER",
        name="Old Germany",
        confederation="OLD",
        tactical_labels=[],
        common_formations=[],
    )
    session.add(team)
    session.commit()
    payload = {
        "updated_at": "2026-06-11T00:00:00Z",
        "rankings": [
            {"rank": 8, "team_name": "Germany", "fifa_code": "GER", "confederation": "UEFA", "points": 1700.1},
        ],
    }

    ingest_fifa_rankings(session, payload, datetime(2026, 6, 11, 9, 0, 0))
    session.commit()

    updated_team = session.scalar(select(NationalTeam).where(NationalTeam.fifa_code == "GER"))
    assert updated_team.name == "Germany"
    assert updated_team.confederation == "UEFA"
    assert session.scalar(select(func.count()).select_from(NationalTeam)) == 1


def test_ingest_fifa_rankings_reuses_existing_ranking_snapshot(session):
    first_payload = {
        "updated_at": "2026-06-11T00:00:00Z",
        "rankings": [
            {"rank": 3, "team_name": "Spain", "fifa_code": "ESP", "confederation": "UEFA", "points": 1810.0},
        ],
    }
    second_payload = {
        "updated_at": "2026-06-11T00:00:00Z",
        "rankings": [
            {"rank": 2, "team_name": "Spain", "fifa_code": "ESP", "confederation": "UEFA", "points": 1820.5},
        ],
    }

    ingest_fifa_rankings(session, first_payload, datetime(2026, 6, 11, 9, 0, 0))
    session.commit()
    ingest_fifa_rankings(session, second_payload, datetime(2026, 6, 11, 10, 0, 0))
    session.commit()

    ranking = session.scalar(select(TeamRanking))
    assert session.scalar(select(func.count()).select_from(TeamRanking)) == 1
    assert ranking.fifa_rank == 2
    assert ranking.ranking_points == 1820.5
