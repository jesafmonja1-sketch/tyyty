from datetime import UTC, datetime

from sqlalchemy import func, select

from world_cup_intel.seed.upcoming_world_cup import seed_upcoming_world_cup_matches
from world_cup_intel.schema import Match, MatchPrediction, NationalTeam, OddsMarket, OddsQuote, PredictionRun, TeamPowerSnapshot


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def test_seed_upcoming_world_cup_matches_creates_curated_matches_predictions_and_odds(session):
    captured_at = _utcnow()

    seeded_matches = seed_upcoming_world_cup_matches(session, captured_at)
    session.commit()

    assert len(seeded_matches) >= 4
    assert session.scalar(select(func.count()).select_from(Match)) >= 4
    assert session.scalar(select(func.count()).select_from(NationalTeam)) >= 8
    assert session.scalar(select(func.count()).select_from(TeamPowerSnapshot)) >= 8
    assert session.scalar(select(func.count()).select_from(OddsMarket)) >= 8
    assert session.scalar(select(func.count()).select_from(OddsQuote)) >= 8
    assert session.scalar(select(func.count()).select_from(PredictionRun)) >= 4
    assert session.scalar(select(func.count()).select_from(MatchPrediction)) >= 4


def test_seed_upcoming_world_cup_matches_is_rerun_safe_for_same_capture_time(session):
    captured_at = _utcnow()

    seed_upcoming_world_cup_matches(session, captured_at)
    session.commit()
    seed_upcoming_world_cup_matches(session, captured_at)
    session.commit()

    assert session.scalar(select(func.count()).select_from(Match)) >= 4
    assert session.scalar(select(func.count()).select_from(TeamPowerSnapshot)) == 10
    assert session.scalar(select(func.count()).select_from(PredictionRun)) == 5
