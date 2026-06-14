from datetime import datetime

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from world_cup_intel.db import build_engine, create_schema
from world_cup_intel.schema import MatchPrediction, NationalTeam, Player, TeamRanking


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
        "team_learning_snapshots",
        "team_change_logs",
        "post_match_refresh_runs",
        "sent_reports",
        "venues",
            "match_weather_snapshots",
            "match_referee_snapshots",
            "match_context_snapshots",
            "team_environment_profiles",
        }.issubset(tables)


def test_matches_table_includes_slot_label_columns(tmp_path):
    db_url = f"sqlite:///{(tmp_path / 'schema.db').as_posix()}"
    engine = build_engine(db_url)

    create_schema(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("matches")}
    assert {"home_slot_label", "away_slot_label"}.issubset(columns)


def test_match_prediction_schema_includes_math_engine_fields():
    columns = MatchPrediction.__table__.columns.keys()

    assert "expected_home_goals" in columns
    assert "expected_away_goals" in columns
    assert "over_2_5_probability" in columns
    assert "under_2_5_probability" in columns
    assert "fair_total_line" in columns


def test_create_schema_upgrades_legacy_matches_table_for_placeholder_fixtures(tmp_path):
    db_url = f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    engine = build_engine(db_url)

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE national_teams (
                    id INTEGER PRIMARY KEY,
                    fifa_code VARCHAR(3) UNIQUE NOT NULL,
                    name VARCHAR(120) UNIQUE NOT NULL,
                    confederation VARCHAR(10) NOT NULL,
                    coach_id INTEGER,
                    tactical_labels JSON NOT NULL,
                    common_formations JSON NOT NULL,
                    is_supported BOOLEAN NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE matches (
                    id INTEGER PRIMARY KEY,
                    external_id VARCHAR(80) UNIQUE NOT NULL,
                    competition VARCHAR(120) NOT NULL,
                    stage VARCHAR(60) NOT NULL,
                    kickoff_at DATETIME NOT NULL,
                    home_team_id INTEGER NOT NULL,
                    away_team_id INTEGER NOT NULL,
                    is_neutral_site BOOLEAN NOT NULL,
                    home_score INTEGER,
                    away_score INTEGER,
                    half_time_score VARCHAR(20),
                    status VARCHAR(30) NOT NULL,
                    FOREIGN KEY(home_team_id) REFERENCES national_teams (id),
                    FOREIGN KEY(away_team_id) REFERENCES national_teams (id)
                )
                """
            )
        )

    create_schema(engine)

    columns = {column["name"]: column for column in inspect(engine).get_columns("matches")}
    assert {"home_slot_label", "away_slot_label"}.issubset(columns)
    assert columns["home_team_id"]["nullable"] is True
    assert columns["away_team_id"]["nullable"] is True

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO matches (
                    external_id,
                    competition,
                    stage,
                    kickoff_at,
                    home_team_id,
                    away_team_id,
                    home_slot_label,
                    away_slot_label,
                    is_neutral_site,
                    status
                ) VALUES (
                    'legacy-slot-match',
                    'FIFA World Cup',
                    'Round of 16',
                    '2026-07-04 17:00:00',
                    NULL,
                    NULL,
                    'Match 74 Winner',
                    'Match 77 Winner',
                    1,
                    'scheduled'
                )
                """
            )
        )


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
