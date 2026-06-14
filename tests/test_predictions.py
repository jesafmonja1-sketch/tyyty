from datetime import datetime

from world_cup_intel.analysis.predictions import generate_match_prediction
from world_cup_intel.schema import Match, MatchPrediction, NationalTeam, OddsMarket, OddsQuote, TeamPowerSnapshot
from world_cup_intel.schema import MatchContextSnapshot


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

def _build_math_engine_match(
    session,
    *,
    external_id: str,
    home_code: str,
    away_code: str,
    kickoff_at: datetime,
    home_attack: float,
    home_defense: float,
    away_attack: float,
    away_defense: float,
    motivation: dict | None = None,
) -> Match:
    home = NationalTeam(
        fifa_code=home_code,
        name=f"{home_code} Test",
        confederation="UEFA",
        tactical_labels=[],
        common_formations=["4-3-3"],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code=away_code,
        name=f"{away_code} Test",
        confederation="CONMEBOL",
        tactical_labels=[],
        common_formations=["4-2-3-1"],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    match_row = Match(
        external_id=external_id,
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=kickoff_at,
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

    session.add_all(
        [
            TeamPowerSnapshot(
                national_team_id=home.id,
                captured_at=kickoff_at.replace(hour=12),
                overall_score=(home_attack + home_defense) / 2,
                attack_score=home_attack,
                defense_score=home_defense,
                midfield_control_score=74.0,
                set_piece_score=70.0,
                squad_completeness_score=86.0,
                recent_form_score=74.0,
            ),
            TeamPowerSnapshot(
                national_team_id=away.id,
                captured_at=kickoff_at.replace(hour=12),
                overall_score=(away_attack + away_defense) / 2,
                attack_score=away_attack,
                defense_score=away_defense,
                midfield_control_score=74.0,
                set_piece_score=70.0,
                squad_completeness_score=86.0,
                recent_form_score=74.0,
            ),
        ]
    )

    if motivation is not None:
        session.add(
            MatchContextSnapshot(
                match_id=match_row.id,
                captured_at=kickoff_at.replace(hour=12, minute=30),
                source_name="manual-context",
                motivation=motivation,
                scenario_projection={},
            )
        )

    return match_row


def test_generate_match_prediction_stores_expected_goals_and_totals_probabilities(session):
    match_row = _build_math_engine_match(
        session,
        external_id="wc-math-xg",
        home_code="XGH",
        away_code="XGA",
        kickoff_at=datetime(2026, 7, 5, 18, 0, 0),
        home_attack=78.0,
        home_defense=74.0,
        away_attack=75.0,
        away_defense=73.0,
    )

    prediction = generate_match_prediction(session, match_row.id, datetime(2026, 7, 5, 13, 0, 0))

    assert prediction.expected_home_goals > 0
    assert prediction.expected_away_goals > 0
    assert 0 < prediction.over_2_5_probability < 1
    assert 0 < prediction.under_2_5_probability < 1
    assert round(prediction.over_2_5_probability + prediction.under_2_5_probability, 6) == 1.0


def test_generate_match_prediction_totals_probabilities_prefers_lower_total_in_cautious_match(session):
    match_row = _build_math_engine_match(
        session,
        external_id="wc-math-cautious",
        home_code="CAH",
        away_code="CAA",
        kickoff_at=datetime(2026, 7, 6, 18, 0, 0),
        home_attack=62.0,
        home_defense=84.0,
        away_attack=61.0,
        away_defense=85.0,
    )

    prediction = generate_match_prediction(session, match_row.id, datetime(2026, 7, 6, 13, 0, 0))

    assert prediction.totals_tendency == "under 2.5"
    assert prediction.under_2_5_probability > prediction.over_2_5_probability


def test_generate_match_prediction_math_engine_prefers_open_scores_with_goal_pressure(session):
    match_row = _build_math_engine_match(
        session,
        external_id="wc-math-goal-pressure",
        home_code="GPH",
        away_code="GPA",
        kickoff_at=datetime(2026, 7, 7, 18, 0, 0),
        home_attack=86.0,
        home_defense=62.0,
        away_attack=83.0,
        away_defense=61.0,
        motivation={
            "group_matchday": 3,
            "home_need": "must win",
            "away_need": "must win",
            "home_goal_difference_pressure": "must win by multiple goals",
            "away_goal_difference_pressure": "must win by multiple goals",
        },
    )

    prediction = generate_match_prediction(session, match_row.id, datetime(2026, 7, 7, 13, 0, 0))

    assert prediction.over_2_5_probability > 0.5
    assert any(score in prediction.likely_scorelines for score in ("2-1", "3-1", "2-2"))
