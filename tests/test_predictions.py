from collections import Counter
from datetime import datetime

import pytest

from world_cup_intel.analysis import predictions as predictions_module
from world_cup_intel.analysis.predictions import build_toto_recommendation
from world_cup_intel.analysis.predictions import diagnose_prediction
from world_cup_intel.analysis.predictions import generate_match_prediction
from world_cup_intel.schema import (
    Match,
    MatchContextSnapshot,
    MatchFeatureSnapshot,
    MatchPrediction,
    MatchTeamStat,
    NationalTeam,
    OddsMarket,
    OddsQuote,
    PredictionFactor,
    TeamLearningSnapshot,
    TeamEnvironmentProfile,
    TeamPowerSnapshot,
    Venue,
    MatchWeatherSnapshot,
)


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


def test_generate_match_prediction_uses_learning_snapshot_for_next_match(session):
    home = NationalTeam(
        fifa_code="JPN",
        name="Japan",
        confederation="AFC",
        tactical_labels=[],
        common_formations=["4-2-3-1"],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code="MEX",
        name="Mexico",
        confederation="CONCACAF",
        tactical_labels=[],
        common_formations=["4-3-3"],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    match_row = Match(
        external_id="wc-10",
        competition="FIFA World Cup",
        stage="Knockout",
        kickoff_at=datetime(2026, 6, 23, 18, 0, 0),
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

    home_previous = Match(
        external_id="wc-10-prev-home",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 6, 22, 18, 0, 0),
        home_team_id=home.id,
        away_team_id=away.id,
        is_neutral_site=True,
        status="finished",
        home_score=2,
        away_score=0,
        half_time_score="1-0",
    )
    away_previous = Match(
        external_id="wc-10-prev-away",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 6, 22, 21, 0, 0),
        home_team_id=away.id,
        away_team_id=home.id,
        is_neutral_site=True,
        status="finished",
        home_score=0,
        away_score=1,
        half_time_score="0-0",
    )
    session.add_all([home_previous, away_previous])
    session.flush()

    session.add_all(
        [
            TeamPowerSnapshot(
                national_team_id=home.id,
                captured_at=datetime(2026, 6, 23, 12, 0, 0),
                overall_score=75.0,
                attack_score=74.0,
                defense_score=74.0,
                midfield_control_score=74.0,
                set_piece_score=70.0,
                squad_completeness_score=78.0,
                recent_form_score=76.0,
            ),
            TeamPowerSnapshot(
                national_team_id=away.id,
                captured_at=datetime(2026, 6, 23, 12, 0, 0),
                overall_score=75.0,
                attack_score=74.0,
                defense_score=74.0,
                midfield_control_score=74.0,
                set_piece_score=70.0,
                squad_completeness_score=78.0,
                recent_form_score=76.0,
            ),
            TeamLearningSnapshot(
                national_team_id=home.id,
                match_id=home_previous.id,
                captured_at=datetime(2026, 6, 22, 22, 0, 0),
                readiness_score=82.0,
                momentum_score=68.0,
                availability_alert_count=0,
                tactical_continuity_score=77.0,
                learning_summary="上一场日本的前场压迫质量和回防速度都比前一战更好。",
                next_match_focus="下一场延续压迫即可继续放大中前场优势。",
            ),
            TeamLearningSnapshot(
                national_team_id=away.id,
                match_id=away_previous.id,
                captured_at=datetime(2026, 6, 22, 22, 0, 0),
                readiness_score=61.0,
                momentum_score=43.0,
                availability_alert_count=2,
                tactical_continuity_score=58.0,
                learning_summary="上一场墨西哥边路回追和中场保护都有明显下滑。",
                next_match_focus="下一场必须先处理边路身后和中场覆盖问题。",
            ),
        ]
    )

    prediction = generate_match_prediction(session, match_row.id, datetime(2026, 6, 23, 13, 0, 0))
    session.commit()

    assert prediction.home_win_probability > prediction.away_win_probability
    assert prediction.recommended_handicap_side == "home"
    learning_factor = session.query(PredictionFactor).filter_by(factor_name="learning_delta").one()
    assert learning_factor.factor_value > 0
    assert "learning" in prediction.summary_conclusion.lower()


def test_generate_match_prediction_penalizes_card_discipline_risk(session):
    home = NationalTeam(
        fifa_code="RSA",
        name="South Africa",
        confederation="CAF",
        tactical_labels=[],
        common_formations=["4-2-3-1"],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code="CZE",
        name="Czechia",
        confederation="UEFA",
        tactical_labels=[],
        common_formations=["3-4-2-1"],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    previous_match = Match(
        external_id="wc-card-history",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 6, 12, 18, 0, 0),
        home_team_id=home.id,
        away_team_id=away.id,
        is_neutral_site=True,
        status="finished",
        home_score=0,
        away_score=0,
    )
    next_match = Match(
        external_id="wc-card-next",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 6, 18, 18, 0, 0),
        home_team_id=home.id,
        away_team_id=away.id,
        is_neutral_site=True,
        status="scheduled",
    )
    session.add_all([previous_match, next_match])
    session.flush()
    session.add_all(
        [
            MatchTeamStat(
                match_id=previous_match.id,
                national_team_id=home.id,
                yellow_cards=5,
                red_cards=1,
                expected_goals=0.6,
                shots_on_target=2,
                corners=2,
                possession=43.0,
            ),
            MatchTeamStat(
                match_id=previous_match.id,
                national_team_id=away.id,
                yellow_cards=1,
                red_cards=0,
                expected_goals=1.2,
                shots_on_target=4,
                corners=4,
                possession=57.0,
            ),
        ]
    )
    for team in [home, away]:
        session.add(
            TeamPowerSnapshot(
                national_team_id=team.id,
                captured_at=datetime(2026, 6, 18, 12, 0, 0),
                overall_score=70.0,
                attack_score=70.0,
                defense_score=70.0,
                midfield_control_score=70.0,
                set_piece_score=70.0,
                squad_completeness_score=90.0,
                recent_form_score=70.0,
            )
        )

    prediction = generate_match_prediction(session, next_match.id, datetime(2026, 6, 18, 13, 0, 0))
    session.commit()

    discipline_factor = session.query(PredictionFactor).filter_by(factor_name="discipline_delta").one()
    assert discipline_factor.factor_value < 0
    assert prediction.away_win_probability > prediction.home_win_probability
    assert "0-1" in prediction.likely_scorelines
    assert "discipline" in prediction.summary_conclusion.lower()


def test_generate_match_prediction_prefers_stronger_team_on_clear_rating_gap(session):
    home = NationalTeam(
        fifa_code="FRA",
        name="France",
        confederation="UEFA",
        tactical_labels=[],
        common_formations=["4-3-3"],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code="CRC",
        name="Costa Rica",
        confederation="CONCACAF",
        tactical_labels=[],
        common_formations=["5-4-1"],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    match_row = Match(
        external_id="wc-11",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 6, 24, 18, 0, 0),
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
                captured_at=datetime(2026, 6, 24, 12, 0, 0),
                overall_score=86.0,
                attack_score=84.0,
                defense_score=82.0,
                midfield_control_score=83.0,
                set_piece_score=76.0,
                squad_completeness_score=91.0,
                recent_form_score=87.0,
            ),
            TeamPowerSnapshot(
                national_team_id=away.id,
                captured_at=datetime(2026, 6, 24, 12, 0, 0),
                overall_score=68.0,
                attack_score=64.0,
                defense_score=67.0,
                midfield_control_score=65.0,
                set_piece_score=63.0,
                squad_completeness_score=78.0,
                recent_form_score=69.0,
            ),
        ]
    )

    prediction = generate_match_prediction(session, match_row.id, datetime(2026, 6, 24, 13, 0, 0))
    session.commit()

    assert prediction.home_win_probability > 0.6
    assert prediction.home_win_probability > prediction.away_win_probability
    assert prediction.recommended_handicap_side == "home"
    assert prediction.confidence_level == "high"


def test_generate_match_prediction_recommends_away_when_market_is_deeper_than_model(session):
    home = NationalTeam(
        fifa_code="GER",
        name="Germany",
        confederation="UEFA",
        tactical_labels=[],
        common_formations=["4-2-3-1"],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code="DEN",
        name="Denmark",
        confederation="UEFA",
        tactical_labels=[],
        common_formations=["4-3-3"],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    match_row = Match(
        external_id="wc-12",
        competition="FIFA World Cup",
        stage="Knockout",
        kickoff_at=datetime(2026, 6, 25, 18, 0, 0),
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
                captured_at=datetime(2026, 6, 25, 12, 0, 0),
                overall_score=80.0,
                attack_score=78.0,
                defense_score=77.0,
                midfield_control_score=78.0,
                set_piece_score=72.0,
                squad_completeness_score=88.0,
                recent_form_score=79.0,
            ),
            TeamPowerSnapshot(
                national_team_id=away.id,
                captured_at=datetime(2026, 6, 25, 12, 0, 0),
                overall_score=76.0,
                attack_score=75.0,
                defense_score=76.0,
                midfield_control_score=75.0,
                set_piece_score=70.0,
                squad_completeness_score=86.0,
                recent_form_score=76.0,
            ),
        ]
    )
    market = OddsMarket(
        match_id=match_row.id,
        source_name="odds-data",
        bookmaker_name="SharpBook",
        market_type="handicap",
    )
    session.add(market)
    session.flush()
    session.add(
        OddsQuote(
            odds_market_id=market.id,
            captured_at=datetime(2026, 6, 25, 12, 30, 0),
            line_value=-0.75,
            home_price=1.90,
            draw_price=None,
            away_price=1.92,
            over_price=None,
            under_price=None,
        )
    )

    prediction = generate_match_prediction(session, match_row.id, datetime(2026, 6, 25, 13, 0, 0))
    session.commit()

    assert prediction.fair_handicap_line > -0.75
    assert prediction.recommended_handicap_side == "away"


def test_generate_match_prediction_sets_totals_and_scorelines_from_goal_profile(session):
    home = NationalTeam(
        fifa_code="ESP",
        name="Spain",
        confederation="UEFA",
        tactical_labels=[],
        common_formations=["4-3-3"],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code="NGA",
        name="Nigeria",
        confederation="CAF",
        tactical_labels=[],
        common_formations=["4-4-2"],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    match_row = Match(
        external_id="wc-13",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 6, 26, 18, 0, 0),
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
                captured_at=datetime(2026, 6, 26, 12, 0, 0),
                overall_score=79.0,
                attack_score=88.0,
                defense_score=66.0,
                midfield_control_score=81.0,
                set_piece_score=72.0,
                squad_completeness_score=90.0,
                recent_form_score=82.0,
            ),
            TeamPowerSnapshot(
                national_team_id=away.id,
                captured_at=datetime(2026, 6, 26, 12, 0, 0),
                overall_score=74.0,
                attack_score=82.0,
                defense_score=61.0,
                midfield_control_score=72.0,
                set_piece_score=69.0,
                squad_completeness_score=85.0,
                recent_form_score=78.0,
            ),
        ]
    )

    prediction = generate_match_prediction(session, match_row.id, datetime(2026, 6, 26, 13, 0, 0))
    session.commit()

    assert prediction.totals_tendency == "over 2.5"
    assert "2-1" in prediction.likely_scorelines


def test_build_toto_recommendation_prefers_away_when_market_is_deeper_than_model():
    recommendation = build_toto_recommendation(
        home_team="Brazil",
        away_team="Portugal",
        home_win_probability=0.44,
        draw_probability=0.29,
        away_win_probability=0.27,
        fair_handicap_line=-0.25,
        market_handicap_line=-0.5,
        recommended_handicap_side="away",
        totals_tendency="under 2.5",
        likely_scorelines="1-0,1-1,2-1",
        over_2_5_probability=0.41,
        under_2_5_probability=0.59,
        fair_total_line=2.25,
    )

    assert recommendation.handicap_pick == "让负"
    assert recommendation.risk_level == "中"
    assert "盘口比模型更深" in recommendation.reason
    assert recommendation.primary_pick != "不建议下"
    assert recommendation.handicap_suitability_label == "适合碰"
    assert "盘口和模型偏差明显" in recommendation.handicap_suitability_reason


def test_build_toto_recommendation_marks_pass_when_edge_is_small():
    recommendation = build_toto_recommendation(
        home_team="Mexico",
        away_team="Japan",
        home_win_probability=0.37,
        draw_probability=0.31,
        away_win_probability=0.32,
        fair_handicap_line=-0.25,
        market_handicap_line=-0.25,
        recommended_handicap_side="away",
        totals_tendency="under 2.5",
        likely_scorelines="1-0,1-1,2-1",
        over_2_5_probability=0.52,
        under_2_5_probability=0.48,
        fair_total_line=2.5,
    )

    assert recommendation.primary_pick == "不建议下"
    assert recommendation.risk_level == "高"
    assert recommendation.suitability_label == "不建议下"
    assert "优势不足" in recommendation.suitability_reason
    assert "优势不足" in recommendation.reason
    assert recommendation.totals_suitability_label == "不建议碰"
    assert "总进球方向不够清楚" in recommendation.totals_suitability_reason


def test_build_toto_recommendation_marks_suitable_when_edge_is_clear():
    recommendation = build_toto_recommendation(
        home_team="France",
        away_team="Costa Rica",
        home_win_probability=0.71,
        draw_probability=0.18,
        away_win_probability=0.11,
        fair_handicap_line=-1.25,
        market_handicap_line=-0.75,
        recommended_handicap_side="home",
        totals_tendency="over 2.5",
        likely_scorelines="2-0,3-0,2-1",
        over_2_5_probability=0.62,
        under_2_5_probability=0.38,
        fair_total_line=2.75,
    )

    assert recommendation.suitability_label == "适合下"
    assert "优势明确" in recommendation.suitability_reason


def test_build_toto_recommendation_marks_cautious_when_market_is_tricky():
    recommendation = build_toto_recommendation(
        home_team="Belgium",
        away_team="Egypt",
        home_win_probability=0.62,
        draw_probability=0.23,
        away_win_probability=0.15,
        fair_handicap_line=-0.5,
        market_handicap_line=-1.0,
        recommended_handicap_side="away",
        totals_tendency="under 2.5",
        likely_scorelines="1-0,2-0,2-1",
        over_2_5_probability=0.43,
        under_2_5_probability=0.57,
        fair_total_line=2.25,
    )

    assert recommendation.suitability_label == "谨慎下"
    assert "深盘" in recommendation.suitability_reason


def test_build_toto_recommendation_marks_totals_suitable_when_goal_edge_is_clear():
    recommendation = build_toto_recommendation(
        home_team="Spain",
        away_team="Nigeria",
        home_win_probability=0.57,
        draw_probability=0.18,
        away_win_probability=0.25,
        fair_handicap_line=-0.5,
        market_handicap_line=-0.5,
        recommended_handicap_side="home",
        totals_tendency="over 2.5",
        likely_scorelines="2-1,3-1,2-2",
        over_2_5_probability=0.68,
        under_2_5_probability=0.32,
        fair_total_line=3.0,
    )

    assert recommendation.totals_suitability_label == "适合碰"
    assert "总进球方向清楚" in recommendation.totals_suitability_reason


def test_diagnose_prediction_flags_market_gap_and_data_thinness(session):
    home = NationalTeam(
        fifa_code="USA",
        name="United States",
        confederation="CONCACAF",
        tactical_labels=[],
        common_formations=["4-3-3"],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code="PAR",
        name="Paraguay",
        confederation="CONMEBOL",
        tactical_labels=[],
        common_formations=["4-4-2"],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    match_row = Match(
        external_id="wc-30",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 6, 26, 18, 0, 0),
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
                captured_at=datetime(2026, 6, 10, 12, 0, 0),
                overall_score=70.0,
                attack_score=69.0,
                defense_score=69.0,
                midfield_control_score=70.0,
                set_piece_score=66.0,
                squad_completeness_score=72.0,
                recent_form_score=70.0,
            ),
            TeamPowerSnapshot(
                national_team_id=away.id,
                captured_at=datetime(2026, 6, 10, 12, 0, 0),
                overall_score=68.0,
                attack_score=66.0,
                defense_score=69.0,
                midfield_control_score=66.0,
                set_piece_score=66.0,
                squad_completeness_score=69.0,
                recent_form_score=67.0,
            ),
        ]
    )
    market = OddsMarket(
        match_id=match_row.id,
        source_name="odds-data",
        bookmaker_name="SharpBook",
        market_type="handicap",
    )
    session.add(market)
    session.flush()
    session.add(
        OddsQuote(
            odds_market_id=market.id,
            captured_at=datetime(2026, 6, 26, 12, 30, 0),
            line_value=-0.75,
            home_price=1.90,
            draw_price=None,
            away_price=1.92,
            over_price=None,
            under_price=None,
        )
    )

    generate_match_prediction(session, match_row.id, datetime(2026, 6, 26, 13, 0, 0))
    session.commit()

    diagnostic = diagnose_prediction(session, match_row.id)

    assert any("盘口和模型差距较大" in line for line in diagnostic.issue_hints)
    assert any("数据薄弱" in line for line in diagnostic.issue_hints)


def test_generate_match_prediction_adjusts_for_venue_weather_and_environment_fit(session):
    home = NationalTeam(
        fifa_code="MEX",
        name="Mexico",
        confederation="CONCACAF",
        tactical_labels=[],
        common_formations=["4-3-3"],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code="SCO",
        name="Scotland",
        confederation="UEFA",
        tactical_labels=[],
        common_formations=["4-2-3-1"],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    venue = Venue(
        name="Estadio Altura",
        city="Mexico City",
        country="Mexico",
        altitude_meters=2240.0,
        pitch_surface="grass",
        pitch_length_meters=105.0,
        pitch_width_meters=68.0,
        climate_tag="high-altitude",
    )
    session.add(venue)
    session.flush()

    match_row = Match(
        external_id="wc-50",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 6, 30, 18, 0, 0),
        home_team_id=home.id,
        away_team_id=away.id,
        venue_id=venue.id,
        is_neutral_site=False,
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
                captured_at=datetime(2026, 6, 30, 12, 0, 0),
                overall_score=73.0,
                attack_score=72.0,
                defense_score=71.0,
                midfield_control_score=72.0,
                set_piece_score=68.0,
                squad_completeness_score=75.0,
                recent_form_score=72.0,
            ),
            TeamPowerSnapshot(
                national_team_id=away.id,
                captured_at=datetime(2026, 6, 30, 12, 0, 0),
                overall_score=74.0,
                attack_score=73.0,
                defense_score=73.0,
                midfield_control_score=73.0,
                set_piece_score=69.0,
                squad_completeness_score=76.0,
                recent_form_score=73.0,
            ),
            TeamEnvironmentProfile(
                national_team_id=home.id,
                captured_at=datetime(2026, 6, 30, 10, 0, 0),
                heat_adaptation_score=78.0,
                altitude_adaptation_score=82.0,
                humidity_adaptation_score=74.0,
                travel_recovery_score=76.0,
                fast_start_score=71.0,
                training_intensity_preference="high",
                notes="Used to altitude camps and warm conditions.",
            ),
            TeamEnvironmentProfile(
                national_team_id=away.id,
                captured_at=datetime(2026, 6, 30, 10, 0, 0),
                heat_adaptation_score=58.0,
                altitude_adaptation_score=49.0,
                humidity_adaptation_score=60.0,
                travel_recovery_score=63.0,
                fast_start_score=62.0,
                training_intensity_preference="medium",
                notes="Less adapted to altitude and thinner air.",
            ),
            MatchWeatherSnapshot(
                match_id=match_row.id,
                captured_at=datetime(2026, 6, 30, 16, 0, 0),
                source_name="manual-weather",
                temperature_c=29.0,
                humidity_pct=62.0,
                wind_speed_kph=24.0,
                precipitation_mm=0.0,
                apparent_temperature_c=31.0,
                weather_summary="warm, thin air, noticeable wind",
            ),
        ]
    )

    prediction = generate_match_prediction(session, match_row.id, datetime(2026, 6, 30, 16, 10, 0))
    session.commit()

    assert prediction.home_win_probability > prediction.away_win_probability
    venue_factor = session.query(PredictionFactor).filter_by(factor_name="environment_delta").one()
    assert venue_factor.factor_value > 0
    assert "environment" in venue_factor.explanation.lower()


def test_generate_match_prediction_boosts_must_win_side_from_group_context(session):
    home = NationalTeam(
        fifa_code="URU",
        name="Uruguay",
        confederation="CONMEBOL",
        tactical_labels=[],
        common_formations=["4-3-3"],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code="AUT",
        name="Austria",
        confederation="UEFA",
        tactical_labels=[],
        common_formations=["4-2-3-1"],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    baseline_match = Match(
        external_id="wc-motivation-base",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 7, 1, 18, 0, 0),
        home_team_id=home.id,
        away_team_id=away.id,
        is_neutral_site=True,
        status="scheduled",
    )
    motivated_match = Match(
        external_id="wc-motivation-live",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 7, 1, 21, 0, 0),
        home_team_id=home.id,
        away_team_id=away.id,
        is_neutral_site=True,
        status="scheduled",
    )
    session.add_all([baseline_match, motivated_match])
    session.flush()

    for team in [home, away]:
        session.add(
            TeamPowerSnapshot(
                national_team_id=team.id,
                captured_at=datetime(2026, 7, 1, 12, 0, 0),
                overall_score=76.0,
                attack_score=74.0,
                defense_score=74.0,
                midfield_control_score=75.0,
                set_piece_score=71.0,
                squad_completeness_score=84.0,
                recent_form_score=76.0,
            )
        )

    session.add(
        MatchContextSnapshot(
            match_id=motivated_match.id,
            captured_at=datetime(2026, 7, 1, 16, 0, 0),
            source_name="manual-context",
            motivation={
                "group_matchday": 2,
                "home_points": 1,
                "away_points": 4,
                "home_need": "must win",
                "away_need": "draw acceptable",
                "draw_value": "away only",
            },
            scenario_projection={},
        )
    )

    baseline_prediction = generate_match_prediction(
        session,
        baseline_match.id,
        datetime(2026, 7, 1, 13, 0, 0),
    )
    motivated_prediction = generate_match_prediction(
        session,
        motivated_match.id,
        datetime(2026, 7, 1, 16, 30, 0),
    )
    session.commit()

    motivation_factor = (
        session.query(PredictionFactor)
        .join(MatchPrediction, MatchPrediction.prediction_run_id == PredictionFactor.prediction_run_id)
        .filter(
            MatchPrediction.id == motivated_prediction.id,
            PredictionFactor.factor_name == "motivation_delta",
        )
        .one()
    )

    assert motivated_prediction.home_win_probability > baseline_prediction.home_win_probability
    assert motivated_prediction.away_win_probability < baseline_prediction.away_win_probability
    assert motivation_factor.factor_value > 0
    assert "motivation" in motivated_prediction.summary_conclusion.lower()


def test_generate_match_prediction_raises_draw_probability_when_group_draw_value_is_high(session):
    home = NationalTeam(
        fifa_code="SUI",
        name="Switzerland",
        confederation="UEFA",
        tactical_labels=[],
        common_formations=["4-2-3-1"],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code="QAT",
        name="Qatar",
        confederation="AFC",
        tactical_labels=[],
        common_formations=["5-3-2"],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    baseline_match = Match(
        external_id="wc-draw-base",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 7, 2, 18, 0, 0),
        home_team_id=home.id,
        away_team_id=away.id,
        is_neutral_site=True,
        status="scheduled",
    )
    draw_match = Match(
        external_id="wc-draw-live",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 7, 2, 21, 0, 0),
        home_team_id=home.id,
        away_team_id=away.id,
        is_neutral_site=True,
        status="scheduled",
    )
    session.add_all([baseline_match, draw_match])
    session.flush()

    session.add_all(
        [
            TeamPowerSnapshot(
                national_team_id=home.id,
                captured_at=datetime(2026, 7, 2, 12, 0, 0),
                overall_score=72.0,
                attack_score=71.0,
                defense_score=70.0,
                midfield_control_score=71.0,
                set_piece_score=68.0,
                squad_completeness_score=80.0,
                recent_form_score=72.0,
            ),
            TeamPowerSnapshot(
                national_team_id=away.id,
                captured_at=datetime(2026, 7, 2, 12, 0, 0),
                overall_score=72.0,
                attack_score=71.0,
                defense_score=70.0,
                midfield_control_score=71.0,
                set_piece_score=68.0,
                squad_completeness_score=80.0,
                recent_form_score=72.0,
            ),
            MatchContextSnapshot(
                match_id=draw_match.id,
                captured_at=datetime(2026, 7, 2, 16, 0, 0),
                source_name="manual-context",
                motivation={
                    "group_matchday": 3,
                    "home_points": 4,
                    "away_points": 4,
                    "home_need": "draw acceptable",
                    "away_need": "draw acceptable",
                    "draw_value": "high for both teams",
                },
                scenario_projection={},
            ),
        ]
    )

    baseline_prediction = generate_match_prediction(
        session,
        baseline_match.id,
        datetime(2026, 7, 2, 13, 0, 0),
    )
    draw_prediction = generate_match_prediction(
        session,
        draw_match.id,
        datetime(2026, 7, 2, 16, 30, 0),
    )
    session.commit()

    assert draw_prediction.draw_probability > baseline_prediction.draw_probability
    assert "motivation" in draw_prediction.summary_conclusion.lower()


def test_generate_match_prediction_goal_difference_pressure_can_push_totals_over(session):
    home = NationalTeam(
        fifa_code="MAR",
        name="Morocco",
        confederation="CAF",
        tactical_labels=[],
        common_formations=["4-1-4-1"],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code="SEN",
        name="Senegal",
        confederation="CAF",
        tactical_labels=[],
        common_formations=["4-3-3"],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    match_row = Match(
        external_id="wc-gd-live",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 7, 3, 18, 0, 0),
        home_team_id=home.id,
        away_team_id=away.id,
        is_neutral_site=True,
        status="scheduled",
    )
    session.add(match_row)
    session.flush()

    session.add_all(
        [
            TeamPowerSnapshot(
                national_team_id=home.id,
                captured_at=datetime(2026, 7, 3, 12, 0, 0),
                overall_score=73.0,
                attack_score=66.0,
                defense_score=66.0,
                midfield_control_score=71.0,
                set_piece_score=68.0,
                squad_completeness_score=82.0,
                recent_form_score=73.0,
            ),
            TeamPowerSnapshot(
                national_team_id=away.id,
                captured_at=datetime(2026, 7, 3, 12, 0, 0),
                overall_score=73.0,
                attack_score=66.0,
                defense_score=66.0,
                midfield_control_score=71.0,
                set_piece_score=68.0,
                squad_completeness_score=82.0,
                recent_form_score=73.0,
            ),
            MatchContextSnapshot(
                match_id=match_row.id,
                captured_at=datetime(2026, 7, 3, 16, 0, 0),
                source_name="manual-context",
                motivation={
                    "group_matchday": 3,
                    "home_need": "must win",
                    "away_need": "avoid defeat",
                    "home_goal_difference_pressure": "must win by multiple goals",
                },
                scenario_projection={},
            ),
        ]
    )

    prediction = generate_match_prediction(session, match_row.id, datetime(2026, 7, 3, 16, 30, 0))
    session.commit()

    assert prediction.totals_tendency == "over 2.5"
    assert prediction.home_win_probability > prediction.away_win_probability


def test_diagnose_prediction_reports_group_motivation_pressure(session):
    home = NationalTeam(
        fifa_code="POL",
        name="Poland",
        confederation="UEFA",
        tactical_labels=[],
        common_formations=["3-5-2"],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code="IRN",
        name="Iran",
        confederation="AFC",
        tactical_labels=[],
        common_formations=["4-4-2"],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    match_row = Match(
        external_id="wc-motivation-diagnostic",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 7, 4, 18, 0, 0),
        home_team_id=home.id,
        away_team_id=away.id,
        is_neutral_site=True,
        status="scheduled",
    )
    session.add(match_row)
    session.flush()

    session.add_all(
        [
            TeamPowerSnapshot(
                national_team_id=home.id,
                captured_at=datetime(2026, 7, 4, 12, 0, 0),
                overall_score=74.0,
                attack_score=72.0,
                defense_score=73.0,
                midfield_control_score=72.0,
                set_piece_score=69.0,
                squad_completeness_score=82.0,
                recent_form_score=73.0,
            ),
            TeamPowerSnapshot(
                national_team_id=away.id,
                captured_at=datetime(2026, 7, 4, 12, 0, 0),
                overall_score=74.0,
                attack_score=72.0,
                defense_score=73.0,
                midfield_control_score=72.0,
                set_piece_score=69.0,
                squad_completeness_score=82.0,
                recent_form_score=73.0,
            ),
            MatchContextSnapshot(
                match_id=match_row.id,
                captured_at=datetime(2026, 7, 4, 16, 0, 0),
                source_name="manual-context",
                motivation={
                    "group_matchday": 3,
                    "home_need": "must win",
                    "away_need": "draw acceptable",
                    "home_knockout_path_preference": "win group and attack early",
                    "away_suspension_risk": "high",
                },
                scenario_projection={},
            ),
        ]
    )

    generate_match_prediction(session, match_row.id, datetime(2026, 7, 4, 16, 30, 0))
    session.commit()

    diagnostic = diagnose_prediction(session, match_row.id)

    assert any("动机" in line or "出线" in line for line in diagnostic.issue_hints)
    assert any("motivation_delta" in line for line in diagnostic.factor_lines)


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
    baseline_match = _build_math_engine_match(
        session,
        external_id="wc-math-goal-pressure-baseline",
        home_code="GPB",
        away_code="GPC",
        kickoff_at=datetime(2026, 7, 7, 18, 0, 0),
        home_attack=72.0,
        home_defense=72.0,
        away_attack=72.0,
        away_defense=72.0,
    )
    pressured_match = _build_math_engine_match(
        session,
        external_id="wc-math-goal-pressure-live",
        home_code="GPH",
        away_code="GPA",
        kickoff_at=datetime(2026, 7, 7, 21, 0, 0),
        home_attack=72.0,
        home_defense=72.0,
        away_attack=72.0,
        away_defense=72.0,
        motivation={
            "group_matchday": 3,
            "home_need": "must win",
            "away_need": "must win",
            "home_goal_difference_pressure": "must win by multiple goals",
            "away_goal_difference_pressure": "must win by multiple goals",
        },
    )

    baseline_prediction = generate_match_prediction(
        session,
        baseline_match.id,
        datetime(2026, 7, 7, 13, 0, 0),
    )
    pressured_prediction = generate_match_prediction(
        session,
        pressured_match.id,
        datetime(2026, 7, 7, 13, 30, 0),
    )

    assert pressured_prediction.over_2_5_probability > baseline_prediction.over_2_5_probability
    assert any(score in pressured_prediction.likely_scorelines for score in ("2-1", "3-1", "2-2"))


def test_generate_match_prediction_sets_fair_total_line_from_simulation(session):
    match_row = _build_math_engine_match(
        session,
        external_id="wc-math-fair-total",
        home_code="FTH",
        away_code="FTA",
        kickoff_at=datetime(2026, 7, 8, 18, 0, 0),
        home_attack=76.0,
        home_defense=73.0,
        away_attack=74.0,
        away_defense=72.0,
    )

    prediction = generate_match_prediction(session, match_row.id, datetime(2026, 7, 8, 13, 0, 0))

    assert 1.5 <= prediction.fair_total_line <= 4.5
    assert round(
        prediction.home_win_probability
        + prediction.draw_probability
        + prediction.away_win_probability,
        6,
    ) == 1.0


def test_build_score_probability_matrix_only_adjusts_target_low_scores():
    baseline = predictions_module._build_score_probability_matrix(
        1.2,
        0.9,
        max_goals=6,
        dixon_coles_rho=0.0,
    )
    adjusted = predictions_module._build_score_probability_matrix(
        1.2,
        0.9,
        max_goals=6,
        dixon_coles_rho=-0.1,
    )

    for scoreline in ((0, 0), (1, 0), (0, 1), (1, 1)):
        assert adjusted[scoreline] != baseline[scoreline]
    assert adjusted[(2, 0)] == baseline[(2, 0)]
    assert adjusted[(2, 1)] == baseline[(2, 1)]


def test_build_score_probability_matrix_preserves_total_probability_after_adjustment():
    adjusted = predictions_module._build_score_probability_matrix(
        1.35,
        1.05,
        max_goals=6,
        dixon_coles_rho=-0.12,
    )

    assert sum(adjusted.values()) == pytest.approx(1.0)


def test_build_score_probability_matrix_rejects_negative_probability_adjustments():
    with pytest.raises(ValueError, match="negative probability"):
        predictions_module._build_score_probability_matrix(
            1.2,
            0.9,
            max_goals=6,
            dixon_coles_rho=-2.0,
        )


def test_distribution_from_score_matrix_returns_valid_result_probabilities():
    distribution = predictions_module._distribution_from_score_matrix(1.55, 0.85)

    assert (
        distribution["home_win_probability"]
        + distribution["draw_probability"]
        + distribution["away_win_probability"]
    ) == pytest.approx(1.0)


def test_distribution_from_score_matrix_produces_totals_and_likely_scores():
    distribution = predictions_module._distribution_from_score_matrix(1.95, 0.75)

    assert 1.5 <= distribution["fair_total_line"] <= 4.5
    assert distribution["likely_scorelines"]
    assert any(score in distribution["likely_scorelines"] for score in ("1-0", "2-0", "2-1", "1-1"))


def test_distribution_from_score_matrix_exposes_goal_difference_counts():
    distribution = predictions_module._distribution_from_score_matrix(2.1, 0.8)

    assert isinstance(distribution["goal_diff_counter"], Counter)
    assert sum(distribution["goal_diff_counter"].values()) > 0
    assert distribution["fair_handicap_line"] <= 0.0


def test_fair_total_line_respects_quarter_line_settlement():
    total_counter = Counter({2: 0.5, 3: 0.5})

    fair_total_line = predictions_module._fair_total_line_from_distribution(total_counter, 1)

    assert fair_total_line == 2.5


def test_fair_handicap_line_uses_distribution_shape_not_only_mean():
    goal_diff_counter = Counter({0: 0.75, 2: 0.25})

    fair_handicap_line = predictions_module._fair_handicap_line_from_distribution(goal_diff_counter, 1)

    assert fair_handicap_line == -0.25


def test_generate_match_prediction_does_not_double_count_learning_environment_or_discipline(
    session,
    monkeypatch,
):
    match_row = _build_math_engine_match(
        session,
        external_id="wc-no-double-count",
        home_code="NDC",
        away_code="NDA",
        kickoff_at=datetime(2026, 7, 13, 18, 0, 0),
        home_attack=75.0,
        home_defense=74.0,
        away_attack=74.0,
        away_defense=73.0,
    )

    session.add_all(
        [
            TeamLearningSnapshot(
                national_team_id=match_row.home_team_id,
                match_id=match_row.id,
                captured_at=datetime(2026, 7, 13, 12, 0, 0),
                readiness_score=80.0,
                momentum_score=70.0,
                availability_alert_count=0,
                tactical_continuity_score=75.0,
                learning_summary="home up",
                next_match_focus="keep pushing",
            ),
            TeamLearningSnapshot(
                national_team_id=match_row.away_team_id,
                match_id=match_row.id,
                captured_at=datetime(2026, 7, 13, 12, 0, 0),
                readiness_score=60.0,
                momentum_score=40.0,
                availability_alert_count=2,
                tactical_continuity_score=55.0,
                learning_summary="away down",
                next_match_focus="recover shape",
            ),
        ]
    )

    captured_args: dict[str, float] = {}

    def _fake_expected_goals(**kwargs):
        captured_args["adjusted_gap"] = kwargs["adjusted_gap"]
        captured_args["learning_delta"] = kwargs["learning_delta"]
        captured_args["environment_delta"] = kwargs["environment_delta"]
        captured_args["discipline_delta"] = kwargs["discipline_delta"]
        return (1.4, 0.9)

    def _fake_distribution(*args, **kwargs):
        return {
            "home_win_probability": 0.5,
            "draw_probability": 0.3,
            "away_win_probability": 0.2,
            "over_2_5_probability": 0.4,
            "under_2_5_probability": 0.6,
            "likely_scorelines": "1-0,1-1,2-0,2-1",
            "goal_diff_counter": Counter({1: 0.3, 0: 0.3, 2: 0.2, -1: 0.2}),
            "fair_total_line": 2.5,
            "fair_handicap_line": -0.5,
        }

    monkeypatch.setattr(predictions_module, "_expected_goals", _fake_expected_goals)
    monkeypatch.setattr(predictions_module, "_distribution_from_score_matrix", _fake_distribution)

    generate_match_prediction(session, match_row.id, datetime(2026, 7, 13, 13, 0, 0))

    rating_gap = 1.0
    assert captured_args["learning_delta"] != 0.0
    assert captured_args["adjusted_gap"] == pytest.approx(rating_gap)


def test_generate_match_prediction_uses_corrected_distribution_for_probabilities(session, monkeypatch):
    match_row = _build_math_engine_match(
        session,
        external_id="wc-dc-integration",
        home_code="DCH",
        away_code="DCA",
        kickoff_at=datetime(2026, 7, 12, 18, 0, 0),
        home_attack=77.0,
        home_defense=75.0,
        away_attack=74.0,
        away_defense=73.0,
    )

    def _fail_old_simulation(*args, **kwargs):
        raise AssertionError("old simulation path should not be used")

    def _fake_distribution(*args, **kwargs):
        return {
            "home_win_probability": 0.51,
            "draw_probability": 0.27,
            "away_win_probability": 0.22,
            "over_2_5_probability": 0.44,
            "under_2_5_probability": 0.56,
            "likely_scorelines": "1-0,1-1,2-0,2-1",
            "goal_diff_counter": Counter({1: 0.31, 0: 0.27, 2: 0.20, -1: 0.22}),
            "fair_total_line": 2.5,
            "fair_handicap_line": -0.5,
        }

    monkeypatch.setattr(predictions_module, "_simulate_match_distribution", _fail_old_simulation)
    monkeypatch.setattr(predictions_module, "_distribution_from_score_matrix", _fake_distribution)

    prediction = generate_match_prediction(session, match_row.id, datetime(2026, 7, 12, 13, 0, 0))

    assert prediction.home_win_probability == pytest.approx(0.51)
    assert prediction.draw_probability == pytest.approx(0.27)
    assert prediction.away_win_probability == pytest.approx(0.22)
    assert prediction.likely_scorelines == "1-0,1-1,2-0,2-1"


def test_generate_match_prediction_computes_market_implied_probabilities_and_value_edges(session):
    match_row = _build_math_engine_match(
        session,
        external_id="wc-math-market-value",
        home_code="MVH",
        away_code="MVA",
        kickoff_at=datetime(2026, 7, 9, 18, 0, 0),
        home_attack=80.0,
        home_defense=76.0,
        away_attack=72.0,
        away_defense=70.0,
    )
    market = OddsMarket(
        match_id=match_row.id,
        source_name="odds-data",
        bookmaker_name="ValueBook",
        market_type="1x2",
    )
    session.add(market)
    session.flush()
    session.add(
        OddsQuote(
            odds_market_id=market.id,
            captured_at=datetime(2026, 7, 9, 12, 30, 0),
            line_value=None,
            home_price=2.0,
            draw_price=4.0,
            away_price=4.0,
            over_price=None,
            under_price=None,
        )
    )

    prediction = generate_match_prediction(session, match_row.id, datetime(2026, 7, 9, 13, 0, 0))
    session.commit()

    factors = {
        factor.factor_name: factor.factor_value
        for factor in session.query(PredictionFactor).all()
    }
    diagnostic = diagnose_prediction(session, match_row.id)

    assert round(factors["market_home_probability"], 6) == 0.5
    assert round(factors["market_draw_probability"], 6) == 0.25
    assert round(factors["market_away_probability"], 6) == 0.25
    assert round(factors["value_edge_home"], 6) == round(prediction.home_win_probability - 0.5, 6)
    assert any("market_home_probability" in line for line in diagnostic.factor_lines)
    assert any("value_edge_home" in line for line in diagnostic.factor_lines)


def test_generate_match_prediction_persists_feature_snapshot(session):
    match_row = _build_math_engine_match(
        session,
        external_id="wc-math-feature-snapshot",
        home_code="FSH",
        away_code="FSA",
        kickoff_at=datetime(2026, 7, 10, 18, 0, 0),
        home_attack=80.0,
        home_defense=77.0,
        away_attack=72.0,
        away_defense=76.0,
    )

    prediction = generate_match_prediction(session, match_row.id, datetime(2026, 7, 10, 13, 0, 0))
    session.commit()

    snapshot = session.query(MatchFeatureSnapshot).one()

    assert snapshot.prediction_run_id == prediction.prediction_run_id
    assert snapshot.match_id == match_row.id
    assert snapshot.power_delta == 4.5
    assert snapshot.lambda_home == prediction.expected_home_goals
    assert snapshot.lambda_away == prediction.expected_away_goals


def test_generate_match_prediction_persists_market_probabilities_in_feature_snapshot(session):
    match_row = _build_math_engine_match(
        session,
        external_id="wc-math-feature-snapshot-market",
        home_code="FMH",
        away_code="FMA",
        kickoff_at=datetime(2026, 7, 11, 18, 0, 0),
        home_attack=80.0,
        home_defense=76.0,
        away_attack=72.0,
        away_defense=70.0,
    )
    market = OddsMarket(
        match_id=match_row.id,
        source_name="odds-data",
        bookmaker_name="ValueBook",
        market_type="1x2",
    )
    session.add(market)
    session.flush()
    session.add(
        OddsQuote(
            odds_market_id=market.id,
            captured_at=datetime(2026, 7, 11, 12, 30, 0),
            line_value=None,
            home_price=2.0,
            draw_price=4.0,
            away_price=4.0,
            over_price=None,
            under_price=None,
        )
    )

    generate_match_prediction(session, match_row.id, datetime(2026, 7, 11, 13, 0, 0))
    session.commit()

    snapshot = session.query(MatchFeatureSnapshot).one()

    assert snapshot.market_home_probability is not None
    assert snapshot.market_draw_probability is not None
    assert snapshot.market_away_probability is not None
    assert round(
        snapshot.market_home_probability
        + snapshot.market_draw_probability
        + snapshot.market_away_probability,
        6,
    ) == 1.0
