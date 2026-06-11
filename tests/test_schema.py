from sqlalchemy import inspect

from world_cup_intel.db import build_engine, create_schema


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
