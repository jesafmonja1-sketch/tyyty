from datetime import datetime

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from world_cup_intel.db import build_engine, create_schema
from world_cup_intel.schema import (
    MatchPrediction,
    MarketCalibrationProfile,
    NationalTeam,
    Player,
    TeamRanking,
    _upgrade_existing_sqlite_matches_table,
)


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


def test_match_prediction_schema_includes_math_engine_fields(tmp_path):
    orm_columns = MatchPrediction.__table__.columns.keys()

    assert "expected_home_goals" in orm_columns
    assert "expected_away_goals" in orm_columns
    assert "over_2_5_probability" in orm_columns
    assert "under_2_5_probability" in orm_columns
    assert "fair_total_line" in orm_columns

    db_url = f"sqlite:///{(tmp_path / 'schema.db').as_posix()}"
    engine = build_engine(db_url)

    create_schema(engine)

    db_columns = {column["name"] for column in inspect(engine).get_columns("match_predictions")}
    assert {
        "expected_home_goals",
        "expected_away_goals",
        "over_2_5_probability",
        "under_2_5_probability",
        "fair_total_line",
    }.issubset(db_columns)


def test_create_schema_builds_market_calibration_profiles_table(tmp_path):
    db_url = f"sqlite:///{(tmp_path / 'schema.db').as_posix()}"
    engine = build_engine(db_url)

    create_schema(engine)

    tables = set(inspect(engine).get_table_names())
    assert "market_calibration_profiles" in tables

    columns = {column["name"] for column in inspect(engine).get_columns("market_calibration_profiles")}
    assert {
        "market_family",
        "bucket_key",
        "profile_version",
        "sample_count",
        "fallback_bucket_key",
        "profile_json",
        "updated_at",
    }.issubset(columns)


def test_market_calibration_profiles_are_unique_by_family_bucket_and_version(session):
    profile = dict(
        market_family="1x2",
        bucket_key="uefa-balanced",
        profile_version="v1",
        sample_count=128,
        fallback_bucket_key="default",
        profile_json={"bins": [0.1, 0.2, 0.3]},
        updated_at=datetime(2026, 6, 21, 12, 0, 0),
    )
    session.add(MarketCalibrationProfile(**profile))
    session.add(MarketCalibrationProfile(**profile))

    with pytest.raises(IntegrityError):
        session.commit()


def test_match_prediction_schema_includes_calibrated_output_fields(tmp_path):
    orm_columns = MatchPrediction.__table__.columns.keys()

    assert {
        "calibrated_home_win_probability",
        "calibrated_draw_probability",
        "calibrated_away_win_probability",
        "handicap_cover_probability",
        "handicap_push_probability",
        "handicap_fail_probability",
        "totals_over_probability",
        "totals_push_probability",
        "totals_under_probability",
        "recommended_totals_side",
        "calibration_summary_json",
    }.issubset(orm_columns)

    db_url = f"sqlite:///{(tmp_path / 'schema.db').as_posix()}"
    engine = build_engine(db_url)

    create_schema(engine)

    db_columns = {column["name"] for column in inspect(engine).get_columns("match_predictions")}
    assert {
        "calibrated_home_win_probability",
        "calibrated_draw_probability",
        "calibrated_away_win_probability",
        "handicap_cover_probability",
        "handicap_push_probability",
        "handicap_fail_probability",
        "totals_over_probability",
        "totals_push_probability",
        "totals_under_probability",
        "recommended_totals_side",
        "calibration_summary_json",
    }.issubset(db_columns)


def test_create_schema_upgrades_legacy_match_predictions_table(tmp_path):
    db_url = f"sqlite:///{(tmp_path / 'legacy-match-predictions.db').as_posix()}"
    engine = build_engine(db_url)

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE prediction_runs (
                    id INTEGER PRIMARY KEY,
                    match_id INTEGER NOT NULL,
                    captured_at DATETIME NOT NULL,
                    model_version VARCHAR(40) NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE match_predictions (
                    id INTEGER PRIMARY KEY,
                    prediction_run_id INTEGER NOT NULL,
                    home_win_probability FLOAT NOT NULL,
                    draw_probability FLOAT NOT NULL,
                    away_win_probability FLOAT NOT NULL,
                    fair_handicap_line FLOAT NOT NULL,
                    market_handicap_line FLOAT,
                    recommended_handicap_side VARCHAR(40) NOT NULL,
                    totals_tendency VARCHAR(40) NOT NULL,
                    likely_scorelines TEXT NOT NULL,
                    confidence_level VARCHAR(20) NOT NULL,
                    summary_conclusion TEXT NOT NULL,
                    expected_home_goals FLOAT NOT NULL DEFAULT 0.0,
                    expected_away_goals FLOAT NOT NULL DEFAULT 0.0,
                    over_2_5_probability FLOAT NOT NULL DEFAULT 0.0,
                    under_2_5_probability FLOAT NOT NULL DEFAULT 0.0,
                    fair_total_line FLOAT NOT NULL DEFAULT 2.5,
                    FOREIGN KEY(prediction_run_id) REFERENCES prediction_runs (id)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO prediction_runs (id, match_id, captured_at, model_version)
                VALUES (1, 49, '2026-06-21 20:00:00', 'v1-rules')
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO match_predictions (
                    id,
                    prediction_run_id,
                    home_win_probability,
                    draw_probability,
                    away_win_probability,
                    fair_handicap_line,
                    market_handicap_line,
                    recommended_handicap_side,
                    totals_tendency,
                    likely_scorelines,
                    confidence_level,
                    summary_conclusion,
                    expected_home_goals,
                    expected_away_goals,
                    over_2_5_probability,
                    under_2_5_probability,
                    fair_total_line
                ) VALUES (
                    1,
                    1,
                    0.50,
                    0.25,
                    0.25,
                    -0.5,
                    -0.5,
                    'home',
                    'under 2.5',
                    '1-0,2-0,1-1',
                    'medium',
                    'legacy row',
                    1.40,
                    0.80,
                    0.45,
                    0.55,
                    2.25
                )
                """
            )
        )

    create_schema(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("match_predictions")}
    assert {
        "calibrated_home_win_probability",
        "calibrated_draw_probability",
        "calibrated_away_win_probability",
        "handicap_cover_probability",
        "handicap_push_probability",
        "handicap_fail_probability",
        "totals_over_probability",
        "totals_push_probability",
        "totals_under_probability",
        "recommended_totals_side",
        "calibration_summary_json",
    }.issubset(columns)

    with engine.begin() as connection:
        persisted_row = connection.execute(
            text(
                """
                SELECT
                    id,
                    prediction_run_id,
                    home_win_probability,
                    draw_probability,
                    away_win_probability,
                    fair_handicap_line,
                    market_handicap_line,
                    recommended_handicap_side,
                    totals_tendency,
                    likely_scorelines,
                    confidence_level,
                    summary_conclusion,
                    expected_home_goals,
                    expected_away_goals,
                    over_2_5_probability,
                    under_2_5_probability,
                    fair_total_line
                FROM match_predictions
                WHERE id = 1
                """
            )
        ).one()

    assert persisted_row == (
        1,
        1,
        0.50,
        0.25,
        0.25,
        -0.5,
        -0.5,
        "home",
        "under 2.5",
        "1-0,2-0,1-1",
        "medium",
        "legacy row",
        1.40,
        0.80,
        0.45,
        0.55,
        2.25,
    )


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
        connection.execute(
            text(
                """
                INSERT INTO national_teams (
                    id,
                    fifa_code,
                    name,
                    confederation,
                    coach_id,
                    tactical_labels,
                    common_formations,
                    is_supported
                ) VALUES (
                    1,
                    'BRA',
                    'Brazil',
                    'CONMEBOL',
                    NULL,
                    '[]',
                    '[]',
                    1
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO matches (
                    id,
                    external_id,
                    competition,
                    stage,
                    kickoff_at,
                    home_team_id,
                    away_team_id,
                    is_neutral_site,
                    home_score,
                    away_score,
                    half_time_score,
                    status
                ) VALUES (
                    10,
                    'legacy-existing-match',
                    'FIFA World Cup',
                    'Group Stage',
                    '2026-06-18 18:00:00',
                    1,
                    1,
                    1,
                    0,
                    0,
                    '0-0',
                    'finished'
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
        persisted_match = connection.execute(
            text(
                """
                SELECT external_id, home_team_id, away_team_id, home_score, away_score, half_time_score, status
                FROM matches
                WHERE id = 10
                """
            )
        ).one()
    assert persisted_match == (
        "legacy-existing-match",
        1,
        1,
        0,
        0,
        "0-0",
        "finished",
    )

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


def test_match_upgrade_hook_skips_non_sqlite_connections():
    class _FakeDialect:
        name = "postgresql"

    class _FakeConnection:
        dialect = _FakeDialect()

        def execute(self, statement):
            raise AssertionError(f"should not execute on non-sqlite: {statement}")

    _upgrade_existing_sqlite_matches_table(None, _FakeConnection())


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
