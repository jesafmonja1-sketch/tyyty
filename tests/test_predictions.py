from datetime import datetime

from world_cup_intel.analysis.predictions import generate_match_prediction
from world_cup_intel.schema import Match, MatchPrediction, NationalTeam, OddsMarket, OddsQuote, TeamPowerSnapshot


def test_generate_match_prediction_builds_probabilities_and_handicap(session):
    home = NationalTeam(
        fifa_code="BRA",
        name="Brazil",
        confederation="CONMEBOL",
        tactical_labels=[],
        common_formations=["4-3-3"],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code="POR",
        name="Portugal",
        confederation="UEFA",
        tactical_labels=[],
        common_formations=["4-2-3-1"],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    match_row = Match(
        external_id="wc-2",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 6, 18, 18, 0, 0),
        home_team_id=home.id,
        away_team_id=away.id,
        is_neutral_site=True,
        status="scheduled",
        home_score=None,
        away_score=None,
        half_time_score=None,
    )
    session.add(match_row)
    session.flush()

    session.add(
        TeamPowerSnapshot(
            national_team_id=home.id,
            captured_at=datetime(2026, 6, 18, 12, 0, 0),
            overall_score=85.0,
            attack_score=83.0,
            defense_score=79.0,
            midfield_control_score=82.0,
            set_piece_score=74.0,
            squad_completeness_score=92.0,
            recent_form_score=88.0,
        )
    )
    session.add(
        TeamPowerSnapshot(
            national_team_id=away.id,
            captured_at=datetime(2026, 6, 18, 12, 0, 0),
            overall_score=80.0,
            attack_score=79.0,
            defense_score=78.0,
            midfield_control_score=77.0,
            set_piece_score=73.0,
            squad_completeness_score=89.0,
            recent_form_score=81.0,
        )
    )

    market = OddsMarket(
        match_id=match_row.id,
        source_name="odds-data",
        bookmaker_name="SampleBook",
        market_type="handicap",
    )
    session.add(market)
    session.flush()
    session.add(
        OddsQuote(
            odds_market_id=market.id,
            captured_at=datetime(2026, 6, 18, 12, 30, 0),
            line_value=-0.25,
            home_price=1.92,
            draw_price=None,
            away_price=1.94,
            over_price=None,
            under_price=None,
        )
    )

    prediction = generate_match_prediction(session, match_row.id, datetime(2026, 6, 18, 13, 0, 0))
    session.commit()

    assert round(
        prediction.home_win_probability
        + prediction.draw_probability
        + prediction.away_win_probability,
        6,
    ) == 1.0
    assert prediction.fair_handicap_line <= 0.0
    assert "1-0" in prediction.likely_scorelines
    assert session.query(MatchPrediction).count() == 1
