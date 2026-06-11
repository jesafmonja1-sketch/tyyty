from datetime import datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from world_cup_intel.db import build_engine, create_schema
from world_cup_intel.schema import NationalTeam, Player, TeamRanking


def test_create_schema_builds_core_tables(tmp_path):
    db_url = f"sqlite:///{(tmp_path / 'schema.db').as_posix()}"
    engine = build_engine(db_url)

    create_schema(engine)

    tables = set(inspect(engine).get_table_names())
    assert {
        "raw_source_runs",
        "raw_payloads",
        "national_teams",
        "coaches",
        "players",
        "team_squads",
        "player_availability",
        "team_rankings",
        "matches",
        "match_team_stats",
        "match_key_events",
        "odds_markets",
        "odds_quotes",
        "team_power_snapshots",
        "team_tactical_profiles",
        "team_form_snapshots",
        "player_impact_ratings",
        "prediction_runs",
        "match_predictions",
        "prediction_factors",
        "match_reviews",
        "team_change_logs",
        "sent_reports",
    }.issubset(tables)


def test_sqlite_foreign_keys_are_enforced(tmp_path):
    db_url = f"sqlite:///{(tmp_path / 'fk.db').as_posix()}"
    engine = build_engine(db_url)
    create_schema(engine)

    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(
                TeamRanking.__table__.insert().values(
                    national_team_id=999,
                    ranking_date=datetime(2026, 6, 12),
                    fifa_rank=1,
                    ranking_points=1850.0,
                )
            )


def test_team_rankings_are_unique_by_team_and_date(session):
    team = NationalTeam(fifa_code="BRA", name="Brazil", confederation="CONMEBOL")
    session.add(team)
    session.flush()
    ranking_date = datetime(2026, 6, 12)
    session.add_all(
        [
            TeamRanking(
                national_team_id=team.id,
                ranking_date=ranking_date,
                fifa_rank=1,
                ranking_points=1850.0,
            ),
            TeamRanking(
                national_team_id=team.id,
                ranking_date=ranking_date,
                fifa_rank=2,
                ranking_points=1845.0,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_structured_collection_fields_round_trip_as_json(session):
    team = NationalTeam(
        fifa_code="ARG",
        name="Argentina",
        confederation="CONMEBOL",
        tactical_labels=["high-press", "counter"],
        common_formations=["4-3-3", "4-2-3-1"],
    )
    session.add(team)
    session.flush()
    player = Player(
        full_name="Lionel Messi",
        national_team_id=team.id,
        position="FW",
        role_tags=["creator", "set-pieces"],
    )
    session.add(player)
    session.commit()

    session.refresh(team)
    session.refresh(player)
    assert team.tactical_labels == ["high-press", "counter"]
    assert team.common_formations == ["4-3-3", "4-2-3-1"]
    assert player.role_tags == ["creator", "set-pieces"]
